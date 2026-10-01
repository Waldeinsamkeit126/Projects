import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const projectDir = path.dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[index + 1];
    if (!next || next.startsWith("--")) result[key] = true;
    else {
      result[key] = next;
      index += 1;
    }
  }
  return result;
}

function intOption(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function csvSet(value) {
  if (!value) return null;
  return new Set(String(value).split(",").map((item) => item.trim()).filter(Boolean));
}

function sourceKind(fileName) {
  return path.extname(String(fileName)).toLowerCase() === ".pdf" ? "pdf" : "image";
}

function countBy(items, key) {
  const counts = {};
  for (const item of items) {
    const value = String(item[key] ?? "");
    counts[value] = (counts[value] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(counts).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])));
}

function normalizeQuestion(row) {
  const knownTypes = new Set(["structure", "extract", "thinking"]);
  const originalType = String(row.question_type ?? "").trim();
  return {
    id: String(row.id ?? "").trim(),
    file_name: String(row.file_name ?? "").trim(),
    question_type: knownTypes.has(originalType) ? originalType : "extract",
    original_question_type: originalType,
    question: String(row.question ?? "").trim(),
    table_hint: String(row.table_hint ?? "").trim() === "11" ? "" : String(row.table_hint ?? "").trim(),
    answer_format: String(row.answer_format ?? "string").trim() || "string",
  };
}

function stripCodeFence(text) {
  const trimmed = String(text ?? "").trim();
  const match = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1].trim() : trimmed;
}

function normalizeAnswer(question, value) {
  let answer = value;
  if (answer == null) return "";
  if (typeof answer !== "string") answer = JSON.stringify(answer);
  answer = stripCodeFence(answer);

  if (question.answer_format === "json" || question.answer_format === "json_array") {
    try {
      let parsed = JSON.parse(answer);
      if (question.answer_format === "json_array" && Array.isArray(parsed)) {
        parsed = parsed.map((item) => {
          if (!item || typeof item !== "object" || Array.isArray(item)) return item;
          return Object.fromEntries(Object.entries(item).map(([key, itemValue]) => [
            key,
            itemValue === null ? "" : String(itemValue),
          ]));
        });
      }
      if (question.answer_format === "json" && question.question_type === "structure" &&
          parsed && typeof parsed === "object" && !Array.isArray(parsed) && Array.isArray(parsed.cells)) {
        let requiredRows = 0;
        let requiredCols = 0;
        for (const cell of parsed.cells) {
          if (!cell || typeof cell !== "object") continue;
          if (Number.isInteger(cell.row) && Number.isInteger(cell.rowspan) && cell.row >= 0 && cell.rowspan >= 1) {
            requiredRows = Math.max(requiredRows, cell.row + cell.rowspan);
          }
          if (Number.isInteger(cell.col) && Number.isInteger(cell.colspan) && cell.col >= 0 && cell.colspan >= 1) {
            requiredCols = Math.max(requiredCols, cell.col + cell.colspan);
          }
        }
        if (Number.isInteger(parsed.row_count)) parsed.row_count = Math.max(parsed.row_count, requiredRows);
        if (Number.isInteger(parsed.col_count)) parsed.col_count = Math.max(parsed.col_count, requiredCols);
      }
      answer = JSON.stringify(parsed);
    } catch {
      return answer;
    }
  }

  if (question.answer_format === "number") {
    answer = answer.replace(/(?<=\d),(?=\d{3}(?:\D|$))/g, "");
  }
  return answer.trim();
}

function validateAnswer(question, answer) {
  if (!answer) return { valid: false, error: "答案为空" };
  if (question.answer_format === "json_array") {
    try {
      const parsed = JSON.parse(answer);
      if (!Array.isArray(parsed)) return { valid: false, error: "答案不是 JSON 数组" };
      if (!parsed.length) return { valid: false, error: "JSON 数组为空" };
      for (const [index, item] of parsed.entries()) {
        if (!item || typeof item !== "object" || Array.isArray(item)) {
          return { valid: false, error: `JSON 数组第 ${index + 1} 项不是简单键值对象` };
        }
        const entries = Object.entries(item);
        if (!entries.length) return { valid: false, error: `JSON 数组第 ${index + 1} 项为空对象` };
        for (const [key, value] of entries) {
          if (!key || typeof value !== "string") {
            return { valid: false, error: `JSON 数组第 ${index + 1} 项字段 ${key || "<空键>"} 的值必须是字符串` };
          }
        }
      }
      return { valid: true };
    } catch (error) {
      return { valid: false, error: `JSON 数组解析失败: ${error.message}` };
    }
  }
  if (question.answer_format === "json") {
    let parsed;
    try {
      parsed = JSON.parse(answer);
    } catch (error) {
      return { valid: false, error: `JSON 解析失败: ${error.message}` };
    }
    if (question.question_type !== "structure") return { valid: true };
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { valid: false, error: "结构恢复答案不是 JSON 对象" };
    }
    if (!Number.isInteger(parsed.row_count) || parsed.row_count < 1) {
      return { valid: false, error: "row_count 必须是正整数" };
    }
    if (!Number.isInteger(parsed.col_count) || parsed.col_count < 1) {
      return { valid: false, error: "col_count 必须是正整数" };
    }
    if (!Array.isArray(parsed.cells)) return { valid: false, error: "cells 必须是数组" };
    const occupied = new Set();
    for (const [index, cell] of parsed.cells.entries()) {
      const ints = ["row", "col", "rowspan", "colspan"];
      if (!cell || typeof cell !== "object" || typeof cell.text !== "string") {
        return { valid: false, error: `cells[${index}] 缺少字符串 text` };
      }
      for (const field of ints) {
        if (!Number.isInteger(cell[field])) return { valid: false, error: `cells[${index}].${field} 不是整数` };
      }
      if (cell.row < 0 || cell.col < 0 || cell.rowspan < 1 || cell.colspan < 1) {
        return { valid: false, error: `cells[${index}] 的坐标或跨度非法` };
      }
      if (cell.row + cell.rowspan > parsed.row_count || cell.col + cell.colspan > parsed.col_count) {
        return { valid: false, error: `cells[${index}] 超出表格范围` };
      }
      for (let row = cell.row; row < cell.row + cell.rowspan; row += 1) {
        for (let col = cell.col; col < cell.col + cell.colspan; col += 1) {
          const coordinate = `${row}:${col}`;
          if (occupied.has(coordinate)) {
            return { valid: false, error: `cells[${index}] 与其他单元格重叠于 ${coordinate}` };
          }
          occupied.add(coordinate);
        }
      }
    }
  }
  return { valid: true };
}

async function readQuestions(testsPath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(testsPath));
  const sheet = workbook.worksheets.getItemAt(0);
  const values = sheet.getUsedRange(true).values;
  const headers = values[0].map((value) => String(value));
  return values.slice(1)
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])))
    .map(normalizeQuestion)
    .filter((row) => row.id);
}

async function resolveMediaFiles(questions, mediaDir) {
  const actualNames = await fs.readdir(mediaDir);
  const byLower = new Map(actualNames.map((name) => [name.toLowerCase(), name]));
  const resolved = new Map();
  const unresolved = [];
  for (const question of questions) {
    if (resolved.has(question.file_name)) continue;
    const requested = question.file_name.toLowerCase();
    let actual = byLower.get(requested);
    if (!actual) {
      const extension = path.extname(requested);
      const numericStem = Number.parseInt(path.basename(requested, extension), 10);
      if (Number.isFinite(numericStem)) {
        const candidates = [
          `${String(numericStem).padStart(3, "0")}${extension}`,
          `${numericStem}${extension}`,
        ];
        actual = candidates.map((candidate) => byLower.get(candidate)).find(Boolean);
      }
    }
    if (actual) resolved.set(question.file_name, path.join(mediaDir, actual));
    else unresolved.push(question.file_name);
  }
  return { resolved, unresolved: [...new Set(unresolved)] };
}

function groupByResolvedFile(questions, resolved) {
  const groups = new Map();
  for (const question of questions) {
    const mediaPath = resolved.get(question.file_name);
    if (!mediaPath) continue;
    if (!groups.has(mediaPath)) groups.set(mediaPath, []);
    groups.get(mediaPath).push(question);
  }
  return groups;
}

function buildPrompt(questions, retryReason = "") {
  const payload = questions.map((question) => ({
    id: question.id,
    question_type: question.question_type,
    question: question.question,
    table_hint: question.table_hint,
    answer_format: question.answer_format,
  }));
  return `你正在参加复杂表格识别比赛。请只依据随消息提供的文件内容回答问题，禁止依据文件名猜测。\n\n` +
    `必须返回一个合法 JSON 对象，格式为 {"answers":[{"id":"题号","answer":最终答案}]}。不要输出解释、Markdown 或代码围栏。\n` +
    `answer 规则：\n` +
    `1. answer_format=json：answer 为结构对象，必须包含 row_count、col_count、cells；row_count 和 col_count 必须是完整表格的逻辑行列数，即使题目只要求局部结构。对于“表头行结构”“第一行”“前几行”等局部题，必须数出整张表的全部数据行，row_count=表头逻辑行数+全部数据行数，绝不能只填写表头行数；col_count 同样填写完整表格总列数。cells 只输出题目要求范围内的真实单元格，每项含 text、row、col、rowspan、colspan。行列从 0 开始；每个真实单元格只输出一次，任意两个 cells 的覆盖坐标不得重叠，合并单元格只输出左上角。\n` +
    `2. answer_format=json_array：answer 必须为 JSON 数组，数组中的每一项必须是扁平的简单键值对象，并使用题目或表格里的字段名作为键；对象中的所有值都必须是 JSON 字符串，数字和布尔结果也必须加双引号；不得直接输出字符串数组、数字数组、布尔数组或嵌套数组。表中缺失值写空字符串 ""，禁止写 null。\n` +
    `3. answer_format=number：只给最终数值，删除千分位逗号。\n` +
    `4. answer_format=string：只给最终文本。\n` +
    `5. 保留原表语义；单位、日期、金额和百分比按问题要求。不得写“答案是”等说明文字。\n` +
    (retryReason ? `\n上次结果未通过校验：${retryReason}。请修正。\n` : "") +
    `\n问题清单：\n${JSON.stringify(payload)}`;
}

function mediaContent(mediaPath) {
  const extension = path.extname(mediaPath).toLowerCase();
  if (extension === ".pdf") {
    return fs.readFile(mediaPath).then((bytes) => ({
      type: "file",
      file: {
        file_data: `data:application/pdf;base64,${bytes.toString("base64")}`,
        filename: path.basename(mediaPath),
      },
    }));
  }
  const mime = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
  }[extension];
  if (!mime) throw new Error(`不支持的媒体格式: ${extension}`);
  return fs.readFile(mediaPath).then((bytes) => ({
    type: "image_url",
    image_url: { url: `data:${mime};base64,${bytes.toString("base64")}` },
  }));
}

async function callQwen({ apiKey, baseUrl, model, mediaPath, questions, retryReason, maxAttempts, maxCompletionTokens = 32768, enableThinking = false }) {
  const url = `${baseUrl.replace(/\/$/, "")}/chat/completions`;
  const media = await mediaContent(mediaPath);
  const body = {
    model,
    messages: [
      {
        role: "system",
        content: "你是严谨的复杂表格识别与问答程序。所有输出必须是机器可解析的 JSON。",
      },
      {
        role: "user",
        content: [media, { type: "text", text: buildPrompt(questions, retryReason) }],
      },
    ],
    ...(enableThinking ? {} : { response_format: { type: "json_object" } }),
    enable_thinking: enableThinking,
    max_completion_tokens: maxCompletionTokens,
    temperature: 0,
  };

  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(600_000),
      });
      const responseText = await response.text();
      if (!response.ok) {
        const responseError = new Error(`HTTP ${response.status}: ${responseText.slice(0, 1000)}`);
        responseError.status = response.status;
        const retryAfter = response.headers.get("retry-after");
        if (retryAfter) {
          const retryAfterSeconds = Number(retryAfter);
          const retryAfterDate = Date.parse(retryAfter);
          responseError.retryAfterMs = Number.isFinite(retryAfterSeconds)
            ? retryAfterSeconds * 1000
            : Number.isFinite(retryAfterDate)
              ? Math.max(0, retryAfterDate - Date.now())
              : 0;
        }
        throw responseError;
      }
      const responseJson = JSON.parse(responseText);
      const choice = responseJson?.choices?.[0];
      const content = choice?.message?.content;
      if (!content) {
        const finishReason = choice?.finish_reason ?? "unknown";
        const responseError = new Error(`模型响应缺少 choices[0].message.content (finish_reason=${finishReason})`);
        responseError.retryable = true;
        if (enableThinking && body.max_completion_tokens < 32768) {
          body.max_completion_tokens = Math.min(32768, body.max_completion_tokens * 2);
          responseError.retryDelayMs = 1_000;
          responseError.retryNote = `提升 max_completion_tokens 至 ${body.max_completion_tokens}`;
        }
        throw responseError;
      }
      return { content, usage: responseJson.usage ?? null, request_id: responseJson.id ?? null };
    } catch (error) {
      lastError = error;
      const status = Number(error?.status);
      const transient = status === 429
        || status >= 500
        || error?.retryable === true
        || error?.name === "TimeoutError"
        || error?.name === "AbortError"
        || error instanceof TypeError;
      if (!transient || attempt >= maxAttempts) break;

      const baseDelayMs = Number(error?.retryDelayMs) || (status === 429 ? 15_000 : 3_000);
      const exponentialDelayMs = Math.min(180_000, baseDelayMs * 2 ** (attempt - 1));
      const retryAfterMs = Number(error?.retryAfterMs) || 0;
      const delayMs = Math.max(exponentialDelayMs, retryAfterMs) + Math.floor(Math.random() * 2_000);
      console.warn(
        `[RETRY] ${path.basename(mediaPath)} 请求失败 (${error.message.split("\n")[0]}); `
        + `第 ${attempt}/${maxAttempts} 次，${Math.ceil(delayMs / 1000)} 秒后重试`
        + (error?.retryNote ? `；${error.retryNote}` : ""),
      );
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
  }
  throw lastError;
}

function parseModelAnswers(content) {
  const parsed = JSON.parse(stripCodeFence(content));
  const list = Array.isArray(parsed) ? parsed : parsed.answers;
  if (!Array.isArray(list)) throw new Error("模型 JSON 中缺少 answers 数组");
  return new Map(list.map((item) => [String(item.id), item.answer]));
}

async function processGroup(options, mediaPath, questions) {
  const extension = path.extname(mediaPath).toLowerCase();
  const model = extension === ".pdf" ? options.modelPdf : options.modelImage;
  let usedModel = model;
  const structureGuidance = options.refreshStructure && questions.some((question) => question.answer_format === "json")
    ? "这是结构答案的强制复核。请重新查看完整表格并逐行计数；局部/表头题的 row_count 必须包含表头和所有数据行，不能等于仅输出的表头行数。"
    : "";
  const first = await callQwen({ ...options, model, mediaPath, questions, retryReason: structureGuidance });
  let answerMap;
  try {
    answerMap = parseModelAnswers(first.content);
  } catch (error) {
    console.warn(`[WARN] ${path.basename(mediaPath)} 批量 JSON 解析失败: ${error.message}`);
    try {
      const repairedBatch = await callQwen({
        ...options,
        model,
        mediaPath,
        questions,
        maxCompletionTokens: Math.max(Number(options.maxCompletionTokens) || 0, 16384),
        retryReason: `上次批量答案不是完整合法的 JSON（${error.message}）。请只返回一个完整 JSON 对象，确保所有字符串、数组和对象正确闭合。`,
      });
      answerMap = parseModelAnswers(repairedBatch.content);
    } catch (batchRetryError) {
      answerMap = new Map();
      console.warn(`[WARN] ${path.basename(mediaPath)} 批量 JSON 修复失败，将逐题补答: ${batchRetryError.message}`);
    }
  }

  const results = [];
  for (const question of questions) {
    let answer = normalizeAnswer(question, answerMap.get(question.id));
    let validation = validateAnswer(question, answer);
    if (!validation.valid) {
      try {
        const retry = await callQwen({
          ...options,
          model,
          mediaPath,
          questions: [question],
          retryReason: validation.error,
        });
        const retryMap = parseModelAnswers(retry.content);
        answer = normalizeAnswer(question, retryMap.get(question.id));
        validation = validateAnswer(question, answer);
      } catch (error) {
        validation = { valid: false, error: `${validation.error}; 重试失败: ${error.message}` };
      }
    }
    if (!validation.valid) {
      try {
        const fallbackModel = "qwen3.8-max";
        const fallbackGuidance = validation.error.includes("答案为空")
          ? "请先在内部逐字识别主表顶部、表头上方及页面中央的显著文字，再返回标题原文。严禁返回 null、空字符串或省略该题；如果没有独立标题，则返回最能准确概括该主表用途的简短单据名称。table_hint 仅用于定位，不要机械照抄。"
          : "请严格修正格式，并确保 row_count 和 col_count 覆盖全部 cells。";
        const fallback = await callQwen({
          ...options,
          model: fallbackModel,
          mediaPath,
          questions: [question],
          retryReason: `${validation.error}。${fallbackGuidance}`,
        });
        const fallbackMap = parseModelAnswers(fallback.content);
        answer = normalizeAnswer(question, fallbackMap.get(question.id));
        validation = validateAnswer(question, answer);
        if (validation.valid) usedModel = fallbackModel;
      } catch (error) {
        validation = { valid: false, error: `${validation.error}; 复核失败: ${error.message}` };
      }
    }
    results.push({
      id: question.id,
      source_file: question.file_name,
      resolved_file: path.basename(mediaPath),
      model: usedModel,
      answer,
      valid: validation.valid,
      error: validation.error ?? "",
    });
  }
  return results;
}

async function runPool(entries, concurrency, worker) {
  const results = new Array(entries.length);
  let cursor = 0;
  async function runner() {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= entries.length) return;
      results[index] = await worker(entries[index], index);
    }
  }
  await Promise.all(Array.from({ length: Math.min(concurrency, entries.length) }, runner));
  return results;
}

async function writeSubmission(templatePath, outputPath, questions, answersById) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(templatePath));
  const sheet = workbook.worksheets.getItemAt(0);
  const values = questions.map((question) => [question.id, answersById.get(question.id) ?? ""]);
  if (values.length) sheet.getRangeByIndexes(1, 0, values.length, 2).values = values;
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await output.save(outputPath);
}

async function readSubmissionAnswers(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const rows = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  return new Map(rows.slice(1).map((row) => [String(row[0]), String(row[1] ?? "")]));
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const testsPath = path.resolve(String(args.tests ?? "D:/tests.xlsx"));
  const templatePath = path.resolve(String(args.template ?? "D:/submit-template.xlsx"));
  const mediaDir = path.resolve(String(args.media ?? path.join(projectDir, "../../work/competition_data/multimodal_table_recognition/files")));
  const outputPath = path.resolve(String(args.output ?? path.join(projectDir, "submission.xlsx")));
  const stateDir = path.resolve(String(args.state ?? path.join(projectDir, "state")));
  const dryRun = Boolean(args["dry-run"]);
  const concurrency = intOption(args.concurrency, 2);
  const limit = args.limit ? intOption(args.limit, null) : null;
  const modelPdf = String(args["model-pdf"] ?? "qwen3.8-max");
  const modelImage = String(args["model-image"] ?? "qwen3-vl-plus");
  const maxAttempts = intOption(args["max-attempts"], 3);
  const maxCompletionTokens = intOption(args["max-completion-tokens"], 32768);
  const refreshStructure = Boolean(args["refresh-structure"]);

  const allQuestions = await readQuestions(testsPath);
  const includeSources = csvSet(args["include-source"]);
  const includeTypes = csvSet(args["include-type"]);
  const excludeTypes = csvSet(args["exclude-type"]);
  const baseSubmission = args.base ? path.resolve(String(args.base)) : null;
  const enableThinking = Boolean(args["enable-thinking"]);
  let questions = allQuestions.filter((question) => {
    if (includeSources && !includeSources.has(sourceKind(question.file_name))) return false;
    if (includeTypes && !includeTypes.has(question.question_type)) return false;
    if (excludeTypes && excludeTypes.has(question.question_type)) return false;
    return true;
  });
  if (limit) questions = questions.slice(0, limit);
  if (questions.length !== allQuestions.length && !baseSubmission && !dryRun) {
    throw new Error("筛选部分题目时必须通过 --base 提供完整基准提交文件");
  }
  const { resolved, unresolved } = await resolveMediaFiles(questions, mediaDir);
  const groups = groupByResolvedFile(questions, resolved);
  const anomalyRows = questions.filter((question) => question.original_question_type !== question.question_type);
  const filenameCorrections = [...resolved.entries()]
    .filter(([requested, actual]) => requested.toLowerCase() !== path.basename(actual).toLowerCase())
    .map(([requested, actual]) => ({ requested, actual: path.basename(actual) }));
  const preflight = {
    testsPath,
    templatePath,
    mediaDir,
    questionCount: questions.length,
    allQuestionCount: allQuestions.length,
    uniqueResolvedFiles: groups.size,
    questionTypes: countBy(questions, "question_type"),
    answerFormats: countBy(questions, "answer_format"),
    unresolved,
    filenameCorrections,
    normalizedQuestionTypes: anomalyRows.map((question) => ({
      id: question.id,
      from: question.original_question_type,
      to: question.question_type,
    })),
    ignoredSourceAnswerColumn: true,
    models: { pdf: modelPdf, image: modelImage },
    maxCompletionTokens,
    refreshStructure,
    enableThinking,
    includeSources: includeSources ? [...includeSources] : ["pdf", "image"],
    includeTypes: includeTypes ? [...includeTypes] : ["structure", "extract", "thinking"],
    excludeTypes: excludeTypes ? [...excludeTypes] : [],
    baseSubmission,
  };
  console.log(JSON.stringify(preflight, null, 2));
  if (unresolved.length) throw new Error(`有无法定位的媒体文件: ${unresolved.join(", ")}`);
  if (dryRun) return;

  const apiKey = process.env.DASHSCOPE_API_KEY;
  const baseUrl = process.env.ALIYUN_BASE_URL || (
    process.env.ALIYUN_WORKSPACE_ID
      ? `https://${process.env.ALIYUN_WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
      : "https://dashscope.aliyuncs.com/compatible-mode/v1"
  );
  if (!apiKey) throw new Error("缺少 DASHSCOPE_API_KEY 环境变量。请在本机配置，不要把密钥发到聊天中。");

  await fs.mkdir(stateDir, { recursive: true });
  const groupEntries = [...groups.entries()];
  const optionBag = { apiKey, baseUrl, modelPdf, modelImage, maxAttempts, maxCompletionTokens, refreshStructure, enableThinking };
  const nestedResults = await runPool(groupEntries, concurrency, async ([mediaPath, groupQuestions], index) => {
    const selectedModel = path.extname(mediaPath).toLowerCase() === ".pdf" ? modelPdf : modelImage;
    const digest = crypto.createHash("sha256")
      .update(await fs.readFile(mediaPath))
      .update(JSON.stringify(groupQuestions))
      .update(selectedModel)
      .update(enableThinking ? "thinking" : "instruct")
      .digest("hex")
      .slice(0, 20);
    const cachePath = path.join(stateDir, `${path.basename(mediaPath)}-${digest}.json`);
    try {
      const cached = JSON.parse(await fs.readFile(cachePath, "utf8"));
      const questionsById = new Map(groupQuestions.map((question) => [question.id, question]));
      for (const result of cached.results) {
        const question = questionsById.get(result.id);
        if (!question) continue;
        result.answer = normalizeAnswer(question, result.answer);
        const revalidation = validateAnswer(question, result.answer);
        result.valid = revalidation.valid;
        result.error = revalidation.error ?? "";
      }
      const invalidIds = new Set(cached.results.filter((result) => {
        const question = questionsById.get(result.id);
        return !question || (refreshStructure && question.answer_format === "json") || !result.valid || !validateAnswer(question, result.answer).valid;
      }).map((result) => result.id));
      if (!invalidIds.size) {
        console.log(`[${index + 1}/${groupEntries.length}] CACHE ${path.basename(mediaPath)}`);
        return cached.results;
      }
      console.log(`[${index + 1}/${groupEntries.length}] REPAIR ${path.basename(mediaPath)} (${invalidIds.size} questions)`);
      const repairQuestions = groupQuestions.filter((question) => invalidIds.has(question.id));
      const repaired = await processGroup(optionBag, mediaPath, repairQuestions);
      const repairedById = new Map(repaired.map((result) => [result.id, result]));
      const merged = cached.results.map((result) => repairedById.get(result.id) ?? result);
      await fs.writeFile(cachePath, JSON.stringify({ mediaPath, results: merged }, null, 2), "utf8");
      return merged;
    } catch {
      console.log(`[${index + 1}/${groupEntries.length}] CALL  ${path.basename(mediaPath)} (${groupQuestions.length} questions)`);
    }
    const results = await processGroup(optionBag, mediaPath, groupQuestions);
    await fs.writeFile(cachePath, JSON.stringify({ mediaPath, results }, null, 2), "utf8");
    return results;
  });

  const results = nestedResults.flat();
  const resultsById = new Map(results.map((result) => [result.id, result]));
  const answersById = baseSubmission ? await readSubmissionAnswers(baseSubmission) : new Map();
  for (const result of results) {
    if (result.valid && result.answer) answersById.set(result.id, result.answer);
  }
  const orderedResults = questions.map((question) => resultsById.get(question.id) ?? ({
    id: question.id,
    source_file: question.file_name,
    answer: "",
    valid: false,
    error: "缺少处理结果",
  }));
  await fs.writeFile(path.join(stateDir, "results.jsonl"), orderedResults.map((row) => JSON.stringify(row)).join("\n") + "\n", "utf8");
  const invalid = orderedResults.filter((row) => !row.valid);
  const runReport = {
    ...preflight,
    completed: orderedResults.length,
    valid: orderedResults.length - invalid.length,
    invalid: invalid.length,
    invalidItems: invalid.map(({ id, source_file, error }) => ({ id, source_file, error })),
    outputPath,
  };
  await fs.writeFile(path.join(stateDir, "run-report.json"), JSON.stringify(runReport, null, 2), "utf8");
  await writeSubmission(baseSubmission ?? templatePath, outputPath, allQuestions, answersById);
  console.log(JSON.stringify(runReport, null, 2));
  if (invalid.length) process.exitCode = 2;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

export { normalizeAnswer, normalizeQuestion, resolveMediaFiles, validateAnswer };
