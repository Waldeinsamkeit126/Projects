import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { normalizeAnswer, validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const root = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const testsPath = `${root}/work/competition_data/multimodal_table_recognition/tests.xlsx`;
const filesDir = `${root}/work/competition_data/multimodal_table_recognition/files`;
const v34Path = `${root}/outputs/table_competition_solution/submission-candidate-v34-add-day3-bp.xlsx`;
const v35Path = `${root}/outputs/table_competition_solution/submission-candidate-v35-qwen37-image-refresh.xlsx`;
const outputPath = `${root}/outputs/table_competition_solution/submission-candidate-v36-adjudicated-image-refresh.xlsx`;
const diffPath = `${root}/work/v35-diff-audit.json`;
const stateDir = `${root}/outputs/table_competition_solution/state-v36-judge`;
const model = process.argv[2] ?? "qwen3.7-plus";
const apiKey = process.env.DASHSCOPE_API_KEY;
if (!apiKey) throw new Error("缺少 DASHSCOPE_API_KEY");

async function rowsFrom(filePath) {
  const book = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = book.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

function stripFence(text) {
  return String(text).trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
}

function mimeFor(fileName) {
  const ext = path.extname(fileName).toLowerCase();
  return ext === ".png" ? "image/png" : ext === ".webp" ? "image/webp" : "image/jpeg";
}

function promptFor(items) {
  return `你是复杂表格识别比赛的答案仲裁器。请直接查看图片，对每道题比较候选 A（旧答案）和候选 B（新答案）。\n` +
    `只能依据图片和题目判断。优先选择准确、简洁、保留原表文本且符合 answer_format 的答案。若两者语义等价，优先选择更贴近原表字面、字段名更符合题目、没有多余字段的答案。只有两者都错时才用 CUSTOM 并给出修正答案。\n` +
    `number 只保留最终数值；string 只保留最终文本；json_array 必须是扁平对象数组，所有值为字符串，缺失值为空字符串。\n` +
    `返回严格 JSON：{"decisions":[{"id":"题号","choice":"A|B|CUSTOM","answer":"仅 CUSTOM 时填写，否则空字符串","confidence":"high|medium|low","reason":"极短理由"}]}，不要输出 Markdown。\n\n` +
    JSON.stringify(items.map((item) => ({
      id: item.id,
      question_type: item.question_type,
      answer_format: item.answer_format,
      question: item.question,
      A: item.oldAnswer,
      B: item.newAnswer,
    })));
}

async function callJudge(fileName, items) {
  const bytes = await fs.readFile(path.join(filesDir, fileName));
  const body = {
    model,
    messages: [
      { role: "system", content: "你是严谨的表格视觉问答仲裁器；最终只输出可解析 JSON。" },
      { role: "user", content: [
        { type: "image_url", image_url: { url: `data:${mimeFor(fileName)};base64,${bytes.toString("base64")}` } },
        { type: "text", text: promptFor(items) },
      ] },
    ],
    enable_thinking: true,
    max_completion_tokens: 32768,
    temperature: 0,
  };
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const response = await fetch("https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions", {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(600000),
      });
      const text = await response.text();
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${text.slice(0, 500)}`);
      const json = JSON.parse(text);
      const content = json?.choices?.[0]?.message?.content;
      const parsed = JSON.parse(stripFence(content));
      if (!Array.isArray(parsed.decisions)) throw new Error("响应缺少 decisions 数组");
      return { decisions: parsed.decisions, usage: json.usage ?? null, requestId: json.id ?? null };
    } catch (error) {
      lastError = error;
      if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 1500 * 2 ** (attempt - 1)));
    }
  }
  throw lastError;
}

const [tests, v34Rows, v35Rows, diffAudit] = await Promise.all([
  rowsFrom(testsPath), rowsFrom(v34Path), rowsFrom(v35Path), JSON.parse(await fs.readFile(diffPath, "utf8")),
]);
await fs.mkdir(stateDir, { recursive: true });
const testById = new Map(tests.map((row) => [String(row.id), row]));
const oldById = new Map(v34Rows.map((row) => [String(row.id), String(row.answer ?? "")]));
const newById = new Map(v35Rows.map((row) => [String(row.id), String(row.answer ?? "")]));
const grouped = Object.groupBy(diffAudit.diffs, (row) => row.file_name);
const entries = Object.entries(grouped);
const results = [];
let cursor = 0;

async function worker() {
  while (true) {
    const index = cursor++;
    if (index >= entries.length) return;
    const [fileName, items] = entries[index];
    const cachePath = path.join(stateDir, `${path.parse(fileName).name}.json`);
    let result;
    try {
      result = JSON.parse(await fs.readFile(cachePath, "utf8"));
    } catch {
      result = await callJudge(fileName, items);
      await fs.writeFile(cachePath, JSON.stringify(result, null, 2), "utf8");
    }
    results.push(...result.decisions.map((decision) => ({ ...decision, file_name: fileName })));
    console.log(`[${index + 1}/${entries.length}] ${fileName}: ${result.decisions.length} decisions`);
  }
}

await Promise.all(Array.from({ length: 6 }, () => worker()));
const decisionById = new Map(results.map((row) => [String(row.id), row]));
const selectedById = new Map(oldById);
const applied = [];
const skipped = [];
for (const diff of diffAudit.diffs) {
  const id = String(diff.id);
  const decision = decisionById.get(id);
  if (!decision) {
    skipped.push({ id, reason: "missing_decision" });
    continue;
  }
  let answer = oldById.get(id);
  const choice = String(decision.choice ?? "").toUpperCase();
  const confidence = String(decision.confidence ?? "low").toLowerCase();
  if (choice === "B" && confidence !== "low") answer = newById.get(id);
  if (choice === "CUSTOM" && confidence !== "low") answer = normalizeAnswer(testById.get(id), decision.answer);
  const validation = validateAnswer(testById.get(id), answer);
  if (!validation.valid) {
    skipped.push({ id, reason: validation.error, choice, confidence });
    answer = oldById.get(id);
  }
  selectedById.set(id, answer);
  if (answer !== oldById.get(id)) applied.push({ id, file_name: diff.file_name, choice, confidence, answer, oldAnswer: oldById.get(id), newAnswer: newById.get(id), reason: decision.reason ?? "" });
}

// Manual safety overrides for visually confirmed regressions in the refreshed batch.
for (const id of ["90", "117", "128", "148", "238", "737"]) selectedById.set(id, oldById.get(id));

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(v34Path));
const sheet = workbook.worksheets.getItemAt(0);
sheet.getRangeByIndexes(1, 0, v34Rows.length, 2).values = v34Rows.map((row) => [String(row.id), selectedById.get(String(row.id)) ?? ""]);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const finalApplied = diffAudit.diffs.filter((row) => selectedById.get(String(row.id)) !== oldById.get(String(row.id))).map((row) => {
  const decision = decisionById.get(String(row.id));
  return { ...row, finalAnswer: selectedById.get(String(row.id)), decision };
});
const report = {
  model,
  diffCount: diffAudit.diffs.length,
  decisions: results.length,
  selectedChanges: finalApplied.length,
  byChoice: Object.groupBy(results, (row) => String(row.choice ?? "UNKNOWN").toUpperCase()),
  skipped,
  manualOverrides: ["90", "117", "128", "148", "238", "737"],
  outputPath,
  applied: finalApplied,
};
report.byChoice = Object.fromEntries(Object.entries(report.byChoice).map(([key, rows]) => [key, rows.length]));
await fs.writeFile(path.join(stateDir, "judge-report.json"), JSON.stringify(report, null, 2), "utf8");
console.log(JSON.stringify({ model, diffCount: report.diffCount, decisions: report.decisions, selectedChanges: report.selectedChanges, byChoice: report.byChoice, skipped: skipped.length, outputPath }, null, 2));
