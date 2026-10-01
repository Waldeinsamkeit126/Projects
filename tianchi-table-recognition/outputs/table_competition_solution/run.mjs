import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { PIPELINE_VERSION, CACHE_SCHEMA, SYSTEM_PROMPT, FALLBACK_MODEL, sha256, normalizeNumberText,
  isNumberText, assertProvider, makeCacheIdentity, checkCache, assertUniqueQuestions, summarizeRequests, inferenceSourceHash } from "./reliability.mjs";
import { COVERAGE_VERSION, inferStructureScope, validateCoverage } from "./structure-coverage.mjs";
import { CONSISTENCY_VERSION, inspectStructureConsistency } from "./structure-consistency.mjs";
import { TRACE_VERSION, createRedactor, emitTrace, protectResult } from "./inference-trace.mjs";

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
  if (value === undefined || value === null) return fallback;
  const text = String(value);
  if (!/^[1-9]\d*$/.test(text) || !Number.isSafeInteger(Number(text))) throw new Error("次数、并发和 token 上限必须是正整数，不能省略参数值");
  return Number(text);
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
    ...(["full", "partial"].includes(row.structure_scope) ? { structure_scope: row.structure_scope } : {}),
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
            itemValue === null ? "" : (typeof itemValue === "object" ? itemValue : String(itemValue)),
          ]));
        });
      }
      // Never change dimensions to make an inconsistent prediction pass validation.
      answer = JSON.stringify(parsed);
    } catch {
      return answer;
    }
  }

  if (question.answer_format === "number") {
    answer = normalizeNumberText(answer);
  }
  return answer.trim();
}

function validateAnswer(question, answer) {
  if (typeof answer !== "string" || !answer.trim()) return { valid: false, error: "答案为空或不是字符串" };
  if (question.answer_format === "number") {
    return isNumberText(answer) ? { valid: true } : { valid: false, error: "number 答案必须是纯数值，不得含单位、说明文字或非法分隔符；请依题意处理百分比" };
  }
  if (!["string", "json", "json_array"].includes(question.answer_format)) return { valid: false, error: "未知答案格式" };
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
    if (!Number.isSafeInteger(parsed.row_count) || parsed.row_count < 1) {
      return { valid: false, error: "row_count 必须是正整数" };
    }
    if (!Number.isSafeInteger(parsed.col_count) || parsed.col_count < 1) {
      return { valid: false, error: "col_count 必须是正整数" };
    }
    if (!Array.isArray(parsed.cells) || !parsed.cells.length) return { valid: false, error: "cells 必须是非空数组" };
    const rectangles = [];
    for (const [index, cell] of parsed.cells.entries()) {
      const ints = ["row", "col", "rowspan", "colspan"];
      if (!cell || typeof cell !== "object" || typeof cell.text !== "string") {
        return { valid: false, error: `cells[${index}] 缺少字符串 text` };
      }
      for (const field of ints) {
        if (!Number.isSafeInteger(cell[field])) return { valid: false, error: `cells[${index}].${field} 不是安全整数` };
      }
      if (cell.row < 0 || cell.col < 0 || cell.rowspan < 1 || cell.colspan < 1) {
        return { valid: false, error: `cells[${index}] 的坐标或跨度非法` };
      }
      if (cell.rowspan > parsed.row_count - cell.row || cell.colspan > parsed.col_count - cell.col) {
        return { valid: false, error: `cells[${index}] 超出表格范围` };
      }
      if (rectangles.some((other) => cell.row < other.row + other.rowspan && other.row < cell.row + cell.rowspan
        && cell.col < other.col + other.colspan && other.col < cell.col + cell.colspan)) {
        return { valid: false, error: `cells[${index}] 与其他单元格重叠` };
      }
      rectangles.push(cell);
    }
  }
  return { valid: true };
}

function validateForInference(question, answer, options = {}) {
  const validation = validateAnswer(question, answer);
  if (!validation.valid || !options.checkFullCoverage || inferStructureScope(question) !== "full") return validation;
  return validateCoverage(question, JSON.parse(answer));
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

async function callQwen(options) {
  const { apiKey, baseUrl, model, mediaPath, questions, retryReason, maxAttempts, maxCompletionTokens = 32768,
    enableThinking = false, requestState, onRequest = async () => {} } = options;
  const redact = createRedactor(apiKey), stage = options.requestStage ?? "direct";
  assertProvider(baseUrl, [model]);
  const block = async (reason) => {
    await emitTrace(options, { kind: "request-blocked", stage, model, sourceFile: path.basename(mediaPath), questionIds: questions.map((q) => q.id), reason, apiRequestMade: false });
    throw new Error(reason);
  };
  const assertAllowed = async () => {
    const reason = requestState?.haltReason || (requestState && requestState.attempts >= requestState.maxRequests
      ? "已达到本轮 API 请求次数上限（含重试），停止新增调用" : "");
    if (reason) await block(reason);
  };
  await assertAllowed();
  const url = `${baseUrl.replace(/\/$/, "")}/chat/completions`;
  const media = await mediaContent(mediaPath);
  const body = {
    model,
    messages: [
      {
        role: "system",
        content: SYSTEM_PROMPT,
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
    await assertAllowed();
    // Recheck synchronously after the awaited trace boundary: concurrent workers share this cap.
    if (requestState?.haltReason) await block(requestState.haltReason);
    if (requestState && requestState.attempts >= requestState.maxRequests) await block("已达到本轮 API 请求次数上限（含重试），停止新增调用");
    if (requestState) requestState.attempts++;
    const started = Date.now();
    const event = { model, sourceFile: path.basename(mediaPath), questionIds: questions.map((q) => q.id),
      stage, requestIndex: requestState?.attempts ?? attempt, attempt, maxCompletionTokens: body.max_completion_tokens, status: "error", usage: null };
    try {
      const response = await fetch(url, {
        method: "POST",
        redirect: "error",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(600_000),
      });
      const responseText = await response.text();
      event.httpStatus = response.status;
      if (!response.ok) {
        // Do not log response bodies: an upstream error may echo a credential.
        const responseError = new Error(`阿里云 API HTTP ${response.status}`);
        responseError.status = response.status;
        if (requestState && [401, 402, 403].includes(response.status)) {
          requestState.haltReason = `出现认证、权限或计费相关拒绝（HTTP ${response.status}），本轮停止新增请求`;
        }
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
      let responseJson;
      try { responseJson = JSON.parse(responseText); }
      catch { throw new Error("阿里云响应信封不是合法 JSON；正文未记录"); }
      event.status = "ok";
      event.usage = responseJson.usage ?? null;
      event.requestId = responseJson.id ?? null;
      const choice = responseJson?.choices?.[0];
      event.finishReason = choice?.finish_reason ?? null;
      event.resolvedModel = responseJson.model ?? model;
      const content = choice?.message?.content;
      if (typeof content !== "string" || !content) {
        const finishReason = choice?.finish_reason ?? "unknown";
        const responseError = new Error(`模型响应缺少 choices[0].message.content (finish_reason=${finishReason})`);
        responseError.retryable = true;
        throw responseError;
      }
      // Only the answer content is traced: never request headers, HTTP error bodies or reasoning_content.
      await emitTrace(options, { kind: "response", stage, requestIndex: event.requestIndex, model: event.resolvedModel,
        sourceFile: event.sourceFile, questionIds: event.questionIds, finishReason: event.finishReason, requestId: event.requestId, content });
      return { content, usage: responseJson.usage ?? null, request_id: responseJson.id ?? null, model: responseJson.model ?? model, requestIndex: event.requestIndex };
    } catch (error) {
      event.elapsedMs = Date.now() - started;
      lastError = error;
      event.error = redact(error.message);
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
        `[RETRY] ${path.basename(mediaPath)} 请求失败 (${redact(error.message).split("\n")[0]}); `
        + `第 ${attempt}/${maxAttempts} 次，${Math.ceil(delayMs / 1000)} 秒后重试`
        + (error?.retryNote ? `；${redact(error.retryNote)}` : ""),
      );
      await new Promise((resolve) => setTimeout(resolve, delayMs));
    } finally {
      event.elapsedMs ??= Date.now() - started;
      await onRequest(redact(event));
      await emitTrace(options, { kind: "request", ...event });
    }
  }
  const safeError = new Error(redact(lastError?.message ?? "阿里云调用失败"));
  safeError.name = lastError?.name ?? "Error";
  safeError.status = lastError?.status;
  throw safeError;
}

function parseModelAnswers(content, expectedQuestions) {
  const parsed = JSON.parse(stripCodeFence(content));
  const list = Array.isArray(parsed) ? parsed : parsed?.answers;
  if (!Array.isArray(list)) throw new Error("模型 JSON 中缺少 answers 数组");
  const answers = new Map();
  const allowed = expectedQuestions ? new Set(expectedQuestions.map((q) => q.id)) : null;
  for (const item of list) {
    if (!item || !["string", "number"].includes(typeof item.id) || !String(item.id).trim() || !("answer" in item)) throw new Error("模型答案缺少有效 id 或 answer");
    const id = String(item.id).trim();
    if (allowed && !allowed.has(id)) throw new Error("模型答案包含本次请求以外的题号");
    if (answers.has(id)) throw new Error("模型答案存在重复题号");
    answers.set(id, item.answer);
  }
  return answers;
}

async function processGroup(options, mediaPath, questions) {
  const extension = path.extname(mediaPath).toLowerCase();
  const model = extension === ".pdf" ? options.modelPdf : options.modelImage;
  const redact = createRedactor(options.apiKey);
  const parse = async (response, requested, stage) => {
    try {
      const answers = parseModelAnswers(response.content, requested);
      await emitTrace(options, { kind: "parse", stage, requestIndex: response.requestIndex, model: response.model,
        sourceFile: path.basename(mediaPath), questionIds: requested.map((q) => q.id), valid: true,
        missingIds: requested.filter((q) => !answers.has(q.id)).map((q) => q.id) });
      return answers;
    } catch (error) {
      const message = redact(error.message);
      await emitTrace(options, { kind: "parse", stage, requestIndex: response.requestIndex, model: response.model,
        sourceFile: path.basename(mediaPath), questionIds: requested.map((q) => q.id), valid: false, error: message });
      throw new Error(message);
    }
  };
  const observe = async (question, rawAnswer, response, stage, history) => {
    const originalAnswer = normalizeAnswer(question, rawAnswer), answer = redact(originalAnswer);
    const validation = answer !== originalAnswer
      ? { valid: false, error: "答案含疑似凭证内容，已脱敏并禁止导出", answerRedacted: true }
      : validateForInference(question, answer, options);
    if (validation.error) validation.error = redact(validation.error);
    const record = { stage, model: response?.model ?? model, requestIndex: response?.requestIndex ?? null,
      requestId: response?.request_id ?? null, rawAnswer: redact(rawAnswer ?? null), answer, ...validation };
    history.push(record);
    await emitTrace(options, { kind: "validation", sourceFile: path.basename(mediaPath), id: question.id, ...record });
    return { answer, validation, usedModel: record.model };
  };
  const failedAttempt = async (question, stage, requestedModel, error, history) => {
    const record = { stage, model: requestedModel, outcome: "request-or-parse-error", valid: false, answer: null, error: redact(error.message) };
    history.push(record);
    await emitTrace(options, { kind: "attempt-error", sourceFile: path.basename(mediaPath), id: question.id, ...record });
    return record.error;
  };
  const structureGuidance = options.refreshStructure && questions.some((question) => question.answer_format === "json")
    ? "这是结构答案的强制复核。请重新查看完整表格并逐行计数；局部/表头题的 row_count 必须包含表头和所有数据行，不能等于仅输出的表头行数。"
    : "";
  const first = await callQwen({ ...options, model, mediaPath, questions, retryReason: structureGuidance, requestStage: "initial" });
  let answerMap, batchResponse = first, batchStage = "initial";
  try {
    answerMap = await parse(first, questions, "initial");
  } catch (error) {
    console.warn(`[WARN] ${path.basename(mediaPath)} 批量 JSON 解析失败: ${redact(error.message)}`);
    batchStage = "batch-repair";
    try {
      const repairedBatch = await callQwen({
        ...options,
        model,
        mediaPath,
        questions,
        requestStage: "batch-repair",
        maxCompletionTokens: options.maxCompletionTokens ?? 32768,
        retryReason: `上次批量答案不是完整合法的 JSON（${redact(error.message)}）。请只返回一个完整 JSON 对象，确保所有字符串、数组和对象正确闭合。`,
      });
      batchResponse = repairedBatch;
      answerMap = await parse(repairedBatch, questions, "batch-repair");
    } catch (batchRetryError) {
      answerMap = new Map();
      batchResponse = null;
      await emitTrace(options, { kind: "batch-error", stage: "batch-repair", sourceFile: path.basename(mediaPath), error: redact(batchRetryError.message) });
      console.warn(`[WARN] ${path.basename(mediaPath)} 批量 JSON 修复失败，将逐题补答: ${redact(batchRetryError.message)}`);
    }
  }

  const results = [];
  for (const question of questions) {
    const validationHistory = [];
    let { answer, validation, usedModel } = await observe(question, answerMap.get(question.id), batchResponse, batchStage, validationHistory);
    if (!validation.valid) {
      try {
        const retry = await callQwen({
          ...options,
          model,
          mediaPath,
          questions: [question],
          requestStage: "retry",
          retryReason: validation.error,
        });
        const retryMap = await parse(retry, [question], "retry");
        ({ answer, validation, usedModel } = await observe(question, retryMap.get(question.id), retry, "retry", validationHistory));
      } catch (error) {
        const failure = await failedAttempt(question, "retry", model, error, validationHistory);
        validation = { valid: false, error: `${validation.error}; 重试失败: ${failure}` };
      }
    }
    if (!validation.valid) {
      try {
        const fallbackModel = FALLBACK_MODEL;
        const fallbackGuidance = "重新定位题目指定的表格和单元格，逐字核对后按题意作答。只能依据可见证据，不得编造缺失的标题、数值或单位，不得改动表格维度来掩盖坐标错误。";
        const fallback = await callQwen({
          ...options,
          model: fallbackModel,
          mediaPath,
          questions: [question],
          requestStage: "fallback",
          retryReason: `${validation.error}。${fallbackGuidance}`,
        });
        const fallbackMap = await parse(fallback, [question], "fallback");
        ({ answer, validation, usedModel } = await observe(question, fallbackMap.get(question.id), fallback, "fallback", validationHistory));
      } catch (error) {
        const failure = await failedAttempt(question, "fallback", FALLBACK_MODEL, error, validationHistory);
        validation = { valid: false, error: `${validation.error}; 复核失败: ${failure}` };
      }
    }
    results.push(protectResult({
      id: question.id,
      source_file: question.file_name,
      resolved_file: path.basename(mediaPath),
      model: usedModel,
      provenance: "automated-qwen",
      answer,
      valid: validation.valid,
      error: validation.error ?? "",
      answerRedacted: Boolean(validationHistory.filter((v) => v.answer !== null).at(-1)?.answerRedacted),
      structureScope: inferStructureScope(question), validationHistory,
    }, options.apiKey));
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

async function main({ argv = process.argv.slice(2), experimentRoot = projectDir } = {}) {
  const args = parseArgs(argv);
  if (args.base) throw new Error("新流程禁用 --base：历史工作簿缺少可核验的自动答题来源，不能导入或合并");
  const dryRun = Boolean(args["dry-run"]);
  if (!dryRun && !args["allow-paid"]) throw new Error("默认不调用付费 API。先 --dry-run；确认预算后才使用 --allow-paid --max-requests N");
  const startedAt = new Date().toISOString();
  const runId = `${startedAt.replace(/[:.]/g, "-")}-${crypto.randomUUID().slice(0, 8)}`;
  const runDir = path.join(experimentRoot, "runs", runId);
  const testsPath = path.resolve(String(args.tests ?? "D:/tests.xlsx"));
  const templatePath = path.resolve(String(args.template ?? "D:/submit-template.xlsx"));
  const questionsJsonPath = args["questions-json"] ? path.resolve(String(args["questions-json"])) : null;
  const noExport = Boolean(args["no-export"]);
  const mediaDir = path.resolve(String(args.media ?? path.join(projectDir, "../../work/competition_data/multimodal_table_recognition/files")));
  const outputPath = path.resolve(String(args.output ?? path.join(runDir, "submission.xlsx")));
  const stateDir = path.resolve(String(args.state ?? path.join(projectDir, "state-reliable-v3")));
  const concurrency = intOption(args.concurrency, 2);
  const limit = args.limit ? intOption(args.limit, null) : null;
  const modelPdf = String(args["model-pdf"] ?? "qwen3.8-max");
  const modelImage = String(args["model-image"] ?? "qwen3-vl-plus");
  const maxAttempts = intOption(args["max-attempts"], 3);
  const maxCompletionTokens = intOption(args["max-completion-tokens"], 32768);
  const refreshStructure = Boolean(args["refresh-structure"]);
  const maxRequests = intOption(args["max-requests"], 20);
  const checkFullCoverage = Boolean(args["check-full-coverage"]);
  const checkStructureConsistency = Boolean(args["check-structure-consistency"]);

  const allQuestions = questionsJsonPath
    ? (JSON.parse(await fs.readFile(questionsJsonPath, "utf8")).questions ?? []).map(normalizeQuestion)
    : await readQuestions(testsPath);
  assertUniqueQuestions(allQuestions);
  const includeSources = csvSet(args["include-source"]);
  const includeTypes = csvSet(args["include-type"]);
  const excludeTypes = csvSet(args["exclude-type"]);
  const enableThinking = Boolean(args["enable-thinking"]);
  let questions = allQuestions.filter((question) => {
    if (includeSources && !includeSources.has(sourceKind(question.file_name))) return false;
    if (includeTypes && !includeTypes.has(question.question_type)) return false;
    if (excludeTypes && excludeTypes.has(question.question_type)) return false;
    return true;
  });
  if (limit) questions = questions.slice(0, limit);
  if (!questions.length) throw new Error("筛选后没有题目");
  const { resolved, unresolved } = await resolveMediaFiles(questions, mediaDir);
  const groups = groupByResolvedFile(questions, resolved);
  const anomalyRows = questions.filter((question) => question.original_question_type !== question.question_type);
  const filenameCorrections = [...resolved.entries()]
    .filter(([requested, actual]) => requested.toLowerCase() !== path.basename(actual).toLowerCase())
    .map(([requested, actual]) => ({ requested, actual: path.basename(actual) }));
  const preflight = {
    runId, pipeline: PIPELINE_VERSION, startedAt,
    testsPath,
    questionsJsonPath, noExport,
    templatePath,
    mediaDir,
    questionCount: questions.length,
    allQuestionCount: allQuestions.length,
    uniqueResolvedFiles: groups.size,
    questionTypes: countBy(questions, "question_type"),
    answerFormats: countBy(questions, "answer_format"),
    structureScopes: countBy(questions.map((question) => ({ scope: inferStructureScope(question) })), "scope"),
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
    maxRequests, maxAttempts, checkFullCoverage, coverageVersion: COVERAGE_VERSION,
    checkStructureConsistency, consistencyVersion: CONSISTENCY_VERSION, traceVersion: TRACE_VERSION, historicalAnswersImported: false,
    partialRun: questions.length !== allQuestions.length,
    validationMeaning: "格式与结构约束检查，不代表答案正确率或合规认证",
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
  assertProvider(baseUrl, [modelPdf, modelImage, FALLBACK_MODEL]);
  try {
    await fs.access(outputPath);
    throw new Error("输出文件已存在，请选择新路径以保留历史版本");
  } catch (error) { if (error.code !== "ENOENT") throw error; }

  await fs.mkdir(stateDir, { recursive: true });
  await fs.mkdir(runDir, { recursive: true });
  const sourceHash = await inferenceSourceHash(projectDir);
  const manifest = { ...preflight, sourceHash, inputSha256: sha256(await fs.readFile(questionsJsonPath ?? testsPath)),
    templateSha256: noExport ? null : sha256(await fs.readFile(templatePath)), endpoint: baseUrl,
    purpose: String(args.purpose ?? "unspecified"), status: "running", outputPath };
  await fs.writeFile(path.join(runDir, "manifest.json"), JSON.stringify(manifest, null, 2), { flag: "wx" });
  const events = [];
  const redact = createRedactor(apiKey);
  const tracePath = path.join(runDir, "inference-trace.jsonl");
  await fs.writeFile(tracePath, "", { flag: "wx" });
  let traceWrites = Promise.resolve(), traceCount = 0;
  const onTrace = (event) => {
    const safe = redact({ sequence: ++traceCount, ...event });
    traceWrites = traceWrites.then(() => fs.appendFile(tracePath, JSON.stringify(safe) + "\n"));
    return traceWrites;
  };
  let eventWrites = Promise.resolve();
  const onRequest = (event) => {
    events.push(event);
    eventWrites = eventWrites.then(() => fs.appendFile(path.join(runDir, "requests.jsonl"), JSON.stringify(event) + "\n"));
    return eventWrites;
  };
  const requestState = { attempts: 0, maxRequests };
  let cacheHits = 0;
  const groupEntries = [...groups.entries()];
  const optionBag = { apiKey, baseUrl, modelPdf, modelImage, maxAttempts, maxCompletionTokens, refreshStructure, enableThinking,
    checkFullCoverage, checkStructureConsistency, requestState, onRequest, onTrace };
  const nestedResults = await runPool(groupEntries, concurrency, async ([mediaPath, groupQuestions], index) => {
    try {
    const selectedModel = path.extname(mediaPath).toLowerCase() === ".pdf" ? modelPdf : modelImage;
    const identity = makeCacheIdentity({ mediaBytes: await fs.readFile(mediaPath), questions: groupQuestions,
      prompt: buildPrompt(groupQuestions), options: { ...optionBag, model: selectedModel }, sourceHash });
    const cachePath = path.join(stateDir, `${path.basename(mediaPath)}-${identity.digest}.json`);
    let cache;
    try {
      const cached = JSON.parse(await fs.readFile(cachePath, "utf8"));
      cache = checkCache(cached, identity, groupQuestions, normalizeAnswer, (q, answer) => validateForInference(q, answer, optionBag));
    } catch (error) {
      if (error.code !== "ENOENT" && !(error instanceof SyntaxError)) throw error;
      cache = { reusable: false };
    }
    if (cache.reusable && !cache.repairQuestions.length && !refreshStructure) {
      cacheHits++;
      await emitTrace(optionBag, { kind: "cache-hit", sourceFile: path.basename(mediaPath), sourceRunId: cache.sourceRunId,
        questionIds: groupQuestions.map((q) => q.id), apiRequestMade: false });
      console.log(`[${index + 1}/${groupEntries.length}] CACHE ${path.basename(mediaPath)}`);
      return groupQuestions.map((q) => cache.resultsById.get(q.id));
    }
    const repairQuestions = cache.reusable && !refreshStructure ? cache.repairQuestions : groupQuestions;
    console.log(`[${index + 1}/${groupEntries.length}] CALL ${path.basename(mediaPath)} (${repairQuestions.length} questions)`);
    const repaired = await processGroup(optionBag, mediaPath, repairQuestions);
    const merged = cache.reusable ? cache.resultsById : new Map();
    for (const result of repaired) merged.set(result.id, { ...result, runId });
    const results = groupQuestions.map((q) => protectResult(merged.get(q.id), apiKey));
    await fs.writeFile(cachePath, JSON.stringify({ schema: CACHE_SCHEMA, digest: identity.digest,
      provenance: "automated-qwen", manifest: identity.manifest, runId, mediaPath, results }, null, 2), "utf8");
    return results;
    } catch (error) {
      // Preserve failures in the run report instead of silently starting a second full paid call.
      return groupQuestions.map((q) => ({ id: q.id, source_file: q.file_name, answer: "", valid: false, error: redact(error.message),
        validationHistory: [{ stage: "group-error", answer: null, valid: false, error: redact(error.message) }] }));
    }
  });

  const results = nestedResults.flat().map((row) => protectResult(row, apiKey));
  const resultsById = new Map(results.map((result) => [result.id, result]));
  const answersById = new Map();
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
  await fs.writeFile(path.join(runDir, "results.jsonl"), orderedResults.map((row) => JSON.stringify(row)).join("\n") + "\n", "utf8");
  const invalid = orderedResults.filter((row) => !row.valid);
  const consistencyAudit = checkStructureConsistency
    ? redact(inspectStructureConsistency(questions, orderedResults, normalizeAnswer, validateAnswer)) : null;
  const needsReview = Boolean(consistencyAudit?.conflictCount);
  if (consistencyAudit) await fs.writeFile(path.join(runDir, "structure-consistency.json"), JSON.stringify(consistencyAudit, null, 2), { flag: "wx" });
  const runReport = {
    ...manifest,
    status: invalid.length ? "failed-validation" : needsReview ? "needs-structure-review" : preflight.partialRun ? "partial-no-submission" : noExport ? "answers-only-no-submission" : "ready-to-export",
    completedAt: new Date().toISOString(),
    elapsedMs: Date.now() - Date.parse(startedAt),
    requests: summarizeRequests(events), cacheHits,
    tracePath, traceEvents: traceCount,
    consistency: consistencyAudit ? { conflictCount: consistencyAudit.conflictCount, comparedPairs: consistencyAudit.comparisons.length,
      skippedCount: consistencyAudit.skipped.length, needsReview } : null,
    completed: orderedResults.length,
    valid: orderedResults.length - invalid.length,
    invalid: invalid.length,
    invalidItems: invalid.map(({ id, source_file, error }) => ({ id, source_file, error })),
    outputPath: null,
  };
  const reportPath = path.join(runDir, "run-report.json");
  await fs.writeFile(reportPath, JSON.stringify(runReport, null, 2), "utf8");
  if (!invalid.length && !needsReview && !preflight.partialRun && !noExport) {
    try {
      await writeSubmission(templatePath, outputPath, allQuestions, answersById);
      const reopened = await readSubmissionAnswers(outputPath);
      if (reopened.size !== allQuestions.length || allQuestions.some((q) => reopened.get(q.id) !== answersById.get(q.id))) throw new Error("导出后逐题复读不一致");
      runReport.outputPath = outputPath;
      runReport.outputSha256 = sha256(await fs.readFile(outputPath));
      runReport.status = "exported-format-checked-not-submitted";
    } catch (error) {
      runReport.status = "export-failed";
      runReport.exportError = error.message;
      process.exitCode = 2;
    }
  }
  await fs.writeFile(reportPath, JSON.stringify(runReport, null, 2), "utf8");
  await fs.appendFile(path.join(experimentRoot, "experiments.jsonl"), JSON.stringify({ runId, reportPath, status: runReport.status,
    purpose: manifest.purpose, sourceHash, inputSha256: manifest.inputSha256, outputSha256: runReport.outputSha256 ?? null,
    requestSummary: runReport.requests, formatValid: runReport.valid, questionCount: questions.length, leaderboardScore: null }) + "\n");
  console.log(JSON.stringify(runReport, null, 2));
  if (invalid.length || needsReview) process.exitCode = 2;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

export { normalizeAnswer, normalizeQuestion, resolveMediaFiles, validateAnswer, validateForInference, parseModelAnswers, buildPrompt, callQwen, processGroup, main };
