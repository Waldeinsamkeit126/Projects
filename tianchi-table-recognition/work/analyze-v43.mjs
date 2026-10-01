import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const testsPath = path.join(root, "work/competition_data/multimodal_table_recognition/tests.xlsx");
const versions = {
  v35: path.join(root, "outputs/table_competition_solution/submission-candidate-v35-qwen37-image-refresh.xlsx"),
  v37: path.join(root, "outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx"),
  v41: path.join(root, "outputs/table_competition_solution/submission-candidate-v41-qwen38max-adjudicated.xlsx"),
  v42: path.join(root, "outputs/table_competition_solution/submission-candidate-v42-qwen38max-image-full.xlsx"),
};
const outputPath = path.join(root, "work/v43-diff-analysis.json");

async function rowsFrom(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

function canonical(value) {
  const text = String(value ?? "").trim();
  try {
    const parsed = JSON.parse(text);
    return JSON.stringify(parsed);
  } catch {
    return text.replace(/\s+/g, " ");
  }
}

function summarize(rows, keyFn) {
  const out = {};
  for (const row of rows) {
    const key = keyFn(row);
    out[key] = (out[key] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(out).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])));
}

const [tests, ...versionRows] = await Promise.all([rowsFrom(testsPath), ...Object.values(versions).map(rowsFrom)]);
const testById = new Map(tests.map((row) => [String(row.id), row]));
const maps = Object.fromEntries(Object.keys(versions).map((name, index) => [name, new Map(versionRows[index].map((row) => [String(row.id), String(row.answer ?? "")]))]));

const diffs = [];
for (const [id, v37] of maps.v37) {
  const v42 = maps.v42.get(id) ?? "";
  if (canonical(v37) === canonical(v42)) continue;
  const test = testById.get(id) ?? {};
  const v35 = maps.v35.get(id) ?? "";
  const v41 = maps.v41.get(id) ?? "";
  const question = String(test.question ?? "");
  const questionType = String(test.question_type ?? "");
  const answerFormat = id === "32" ? "json" : String(test.answer_format ?? "string");
  const titleQuestion = /主表或主区域的标题|标题是什么/.test(question);
  const refusal = /无法|未找到|不确定|看不清|unknown|not found|cannot/i.test(v42);
  const scalarExtract = questionType === "extract" && ["string", "number"].includes(answerFormat);
  const conservative = scalarExtract && !titleQuestion && !refusal && v42.trim() !== "" && (answerFormat !== "string" || v42.length <= 80);
  const ultraConservative = conservative && (
    answerFormat === "number" ||
    canonical(v42) === canonical(v35) ||
    canonical(v42) === canonical(v41)
  );
  diffs.push({
    id,
    file_name: String(test.file_name ?? ""),
    question_type: questionType,
    answer_format: answerFormat,
    question,
    table_hint: String(test.table_hint ?? ""),
    v35,
    v37,
    v41,
    v42,
    v42_matches_v35: canonical(v42) === canonical(v35),
    v42_matches_v41: canonical(v42) === canonical(v41),
    title_question: titleQuestion,
    conservative,
    ultra_conservative: ultraConservative,
  });
}

const conservative = diffs.filter((row) => row.conservative);
const ultraConservative = diffs.filter((row) => row.ultra_conservative);
const report = {
  changed: diffs.length,
  by_question_type: summarize(diffs, (row) => row.question_type),
  by_answer_format: summarize(diffs, (row) => row.answer_format),
  v42_matches_v35: diffs.filter((row) => row.v42_matches_v35).length,
  v42_matches_v41: diffs.filter((row) => row.v42_matches_v41).length,
  conservative_count: conservative.length,
  conservative_by_format: summarize(conservative, (row) => row.answer_format),
  ultra_conservative_count: ultraConservative.length,
  ultra_conservative_by_format: summarize(ultraConservative, (row) => row.answer_format),
  conservative,
  ultra_conservative: ultraConservative,
  diffs,
};
await fs.writeFile(outputPath, JSON.stringify(report, null, 2), "utf8");
console.log(JSON.stringify({
  changed: report.changed,
  by_question_type: report.by_question_type,
  by_answer_format: report.by_answer_format,
  v42_matches_v35: report.v42_matches_v35,
  v42_matches_v41: report.v42_matches_v41,
  conservative_count: report.conservative_count,
  conservative_by_format: report.conservative_by_format,
  ultra_conservative_count: report.ultra_conservative_count,
  ultra_conservative_by_format: report.ultra_conservative_by_format,
  ultra_conservative_ids: ultraConservative.map((row) => row.id),
  outputPath,
}, null, 2));
