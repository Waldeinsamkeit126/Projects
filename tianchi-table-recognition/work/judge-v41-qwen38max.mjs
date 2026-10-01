import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { normalizeAnswer, validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const workDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(workDir);
const testsPath = path.join(workDir, "competition_data/multimodal_table_recognition/tests.xlsx");
const filesDir = path.join(workDir, "competition_data/multimodal_table_recognition/files");
const currentBestPath = path.join(root, "outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx");
const refreshedPath = path.join(root, "outputs/table_competition_solution/submission-candidate-v35-qwen37-image-refresh.xlsx");
const outputPath = path.join(root, "outputs/table_competition_solution/submission-candidate-v41-qwen38max-adjudicated.xlsx");
const stateDir = path.join(root, "outputs/table_competition_solution/state-v41-qwen38max-judge");
const reportPath = path.join(stateDir, "judge-report.json");
const model = process.argv[2] ?? "qwen3.8-max-0902";
const apiKey = process.env.DASHSCOPE_API_KEY;
const baseUrl = (process.env.ALIYUN_BASE_URL || "https://dashscope.aliyuncs.com/compatible-mode/v1").replace(/\/$/, "");

if (!apiKey) throw new Error("缺少 DASHSCOPE_API_KEY");

async function rowsFrom(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

function stripFence(value) {
  return String(value ?? "").trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
}

function mimeFor(fileName) {
  const extension = path.extname(fileName).toLowerCase();
  return extension === ".png" ? "image/png" : extension === ".webp" ? "image/webp" : "image/jpeg";
}

function promptFor(items) {
  const payload = items.map((item) => ({
    id: item.id,
    question_type: item.question_type,
    answer_format: item.answer_format,
    question: item.question,
    table_hint: item.table_hint,
    A: item.currentAnswer,
    B: item.refreshedAnswer,
  }));
  return `你是复杂表格识别比赛的最终自动仲裁器。请直接查看随消息提供的图片，只依据图片与题目判断，禁止依据文件名、题号或其他无关模式猜测。\n` +
    `候选 A 是当前线上最优提交，候选 B 是另一千问模型的独立识别结果。逐题选择更准确的候选；只有 A、B 都错且你能从图片中高置信确定时才使用 CUSTOM。\n` +
    `这是逐题完全匹配计分：不要为了“更完整”添加题目未要求的字段或解释。string/number 只给最终值；number 删除千分位逗号；json_array 使用题目要求的字段组织扁平对象数组，所有值必须是字符串，空值写空字符串，保留题目要求的顺序；日期、金额、百分比和单位严格按题目要求。\n` +
    `若 A、B 语义等价，优先选择更贴近原表字面、字段名更贴合题目、无多余内容的答案。看不清或无法可靠判断时必须选择 A 且 confidence=low，不得猜测。\n` +
    `返回严格 JSON：{"decisions":[{"id":"题号","choice":"A|B|CUSTOM","answer":"仅 CUSTOM 时填写最终答案，否则为空字符串","confidence":"high|medium|low","reason":"极短理由"}]}。不要输出 Markdown 或其他文字。\n\n` +
    JSON.stringify(payload);
}

async function callJudge(fileName, items) {
  const filePath = path.join(filesDir, fileName);
  const bytes = await fs.readFile(filePath);
  const body = {
    model,
    messages: [
      { role: "system", content: "你是严谨的多模态表格问答仲裁器，最终只输出可解析 JSON。" },
      {
        role: "user",
        content: [
          { type: "image_url", image_url: { url: `data:${mimeFor(fileName)};base64,${bytes.toString("base64")}` } },
          { type: "text", text: promptFor(items) },
        ],
      },
    ],
    enable_thinking: true,
    max_completion_tokens: 32768,
    temperature: 0,
  };

  let lastError;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(600_000),
      });
      const text = await response.text();
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${text.slice(0, 700)}`);
      const json = JSON.parse(text);
      const parsed = JSON.parse(stripFence(json?.choices?.[0]?.message?.content));
      if (!Array.isArray(parsed.decisions)) throw new Error("响应缺少 decisions 数组");
      return { decisions: parsed.decisions, usage: json.usage ?? null, requestId: json.id ?? null, model };
    } catch (error) {
      lastError = error;
      if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 1500 * (2 ** (attempt - 1))));
    }
  }
  throw lastError;
}

const [tests, currentRows, refreshedRows] = await Promise.all([
  rowsFrom(testsPath),
  rowsFrom(currentBestPath),
  rowsFrom(refreshedPath),
]);
const testById = new Map(tests.map((row) => [String(row.id), row]));
const refreshedById = new Map(refreshedRows.map((row) => [String(row.id), String(row.answer ?? "")]));
const currentById = new Map(currentRows.map((row) => [String(row.id), String(row.answer ?? "")]));
const diffs = currentRows.flatMap((row) => {
  const id = String(row.id);
  const currentAnswer = String(row.answer ?? "");
  const refreshedAnswer = refreshedById.get(id) ?? "";
  if (currentAnswer === refreshedAnswer) return [];
  const test = testById.get(id) ?? {};
  return [{
    id,
    file_name: String(test.file_name ?? ""),
    question_type: String(test.question_type ?? "extract"),
    answer_format: String(test.answer_format ?? "string"),
    question: String(test.question ?? ""),
    table_hint: String(test.table_hint ?? "") === "11" ? "" : String(test.table_hint ?? ""),
    currentAnswer,
    refreshedAnswer,
  }];
});
const grouped = Object.groupBy(diffs, (row) => row.file_name);
const entries = Object.entries(grouped);

await fs.mkdir(stateDir, { recursive: true });
const decisions = [];
const failures = [];
let cursor = 0;

async function worker() {
  while (true) {
    const index = cursor;
    cursor += 1;
    if (index >= entries.length) return;
    const [fileName, items] = entries[index];
    const cachePath = path.join(stateDir, `${path.parse(fileName).name}-${model.replace(/[^a-z0-9.-]/gi, "_")}.json`);
    try {
      let result;
      try {
        result = JSON.parse(await fs.readFile(cachePath, "utf8"));
        console.log(`[${index + 1}/${entries.length}] CACHE ${fileName}`);
      } catch {
        console.log(`[${index + 1}/${entries.length}] CALL  ${fileName} (${items.length}题)`);
        result = await callJudge(fileName, items);
        await fs.writeFile(cachePath, JSON.stringify(result, null, 2), "utf8");
      }
      decisions.push(...result.decisions.map((decision) => ({ ...decision, file_name: fileName })));
    } catch (error) {
      failures.push({ file_name: fileName, error: error.message });
      console.error(`[${index + 1}/${entries.length}] FAIL  ${fileName}: ${error.message}`);
    }
  }
}

await Promise.all(Array.from({ length: Math.min(3, entries.length) }, () => worker()));

const decisionById = new Map(decisions.map((row) => [String(row.id), row]));
const selectedById = new Map(currentById);
const applied = [];
const skipped = [];

for (const diff of diffs) {
  const decision = decisionById.get(diff.id);
  if (!decision) {
    skipped.push({ id: diff.id, reason: "missing_decision" });
    continue;
  }
  const choice = String(decision.choice ?? "").toUpperCase();
  const confidence = String(decision.confidence ?? "low").toLowerCase();
  let answer = diff.currentAnswer;
  if (confidence === "high" && choice === "B") answer = diff.refreshedAnswer;
  if (confidence === "high" && choice === "CUSTOM") answer = normalizeAnswer(testById.get(diff.id), decision.answer);
  const validation = validateAnswer(testById.get(diff.id), answer);
  if (!validation.valid) {
    skipped.push({ id: diff.id, reason: validation.error, choice, confidence });
    answer = diff.currentAnswer;
  }
  selectedById.set(diff.id, answer);
  if (answer !== diff.currentAnswer) {
    applied.push({ ...diff, finalAnswer: answer, decision: { choice, confidence, reason: String(decision.reason ?? "") } });
  }
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(currentBestPath));
const sheet = workbook.worksheets.getItemAt(0);
sheet.getRangeByIndexes(1, 1, currentRows.length, 1).values = currentRows.map((row) => [selectedById.get(String(row.id)) ?? ""]);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const byChoice = Object.fromEntries(Object.entries(Object.groupBy(decisions, (row) => String(row.choice ?? "UNKNOWN").toUpperCase())).map(([key, rows]) => [key, rows.length]));
const byConfidence = Object.fromEntries(Object.entries(Object.groupBy(decisions, (row) => String(row.confidence ?? "UNKNOWN").toLowerCase())).map(([key, rows]) => [key, rows.length]));
const report = {
  model,
  sourceA: currentBestPath,
  sourceB: refreshedPath,
  diffCount: diffs.length,
  fileCount: entries.length,
  decisions: decisions.length,
  byChoice,
  byConfidence,
  appliedCount: applied.length,
  skipped,
  failures,
  applied,
  outputPath,
};
await fs.writeFile(reportPath, JSON.stringify(report, null, 2), "utf8");
console.log(JSON.stringify({
  model,
  diffCount: report.diffCount,
  fileCount: report.fileCount,
  decisions: report.decisions,
  byChoice,
  byConfidence,
  appliedCount: report.appliedCount,
  skipped: skipped.length,
  failures: failures.length,
  outputPath,
  reportPath,
}, null, 2));
