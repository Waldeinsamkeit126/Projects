import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const testsPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/competition_data/multimodal_table_recognition/tests.xlsx";
const oldPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-candidate-v34-add-day3-bp.xlsx";
const newPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-candidate-v35-qwen37-image-refresh.xlsx";
const outPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/v35-diff-audit.json";

async function rowsFrom(path) {
  const book = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
  const values = book.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

const [tests, oldRows, newRows] = await Promise.all([rowsFrom(testsPath), rowsFrom(oldPath), rowsFrom(newPath)]);
const testById = new Map(tests.map((row) => [String(row.id), row]));
const newById = new Map(newRows.map((row) => [String(row.id), String(row.answer ?? "")]));
const diffs = [];
const summary = { changed: 0, unchanged: 0, byType: {}, byFormat: {}, byFile: {}, suspicious: 0 };

for (const oldRow of oldRows) {
  const id = String(oldRow.id);
  const oldAnswer = String(oldRow.answer ?? "");
  const newAnswer = newById.get(id) ?? "";
  if (oldAnswer === newAnswer) {
    summary.unchanged++;
    continue;
  }
  const test = testById.get(id) ?? {};
  const type = String(test.question_type ?? "");
  const format = id === "32" ? "json" : String(test.answer_format ?? "");
  const file = String(test.file_name ?? "");
  const flags = [];
  if (!newAnswer.trim()) flags.push("blank_new");
  if (/无法|未找到|不确定|看不清|无法确定|unknown|not found|cannot/i.test(newAnswer)) flags.push("refusal_or_uncertainty");
  if (format === "string" && /答案|根据|表中|显示|可知/.test(newAnswer)) flags.push("explanatory_string");
  if (format === "string" && newAnswer.length > 80) flags.push("long_string");
  if (format === "number") {
    const oldNum = Number(oldAnswer.replace(/%$/, ""));
    const newNum = Number(newAnswer.replace(/%$/, ""));
    if (Number.isFinite(oldNum) && Number.isFinite(newNum)) {
      const denominator = Math.max(Math.abs(oldNum), 1);
      if (Math.abs(newNum - oldNum) / denominator >= 1) flags.push("large_numeric_change");
    }
    if (oldAnswer.endsWith("%") !== newAnswer.endsWith("%")) flags.push("percent_style_changed");
  }
  if (format === "json_array") {
    try {
      const parsed = JSON.parse(newAnswer);
      if (!Array.isArray(parsed)) flags.push("new_not_array");
      if (parsed.some((item) => Object.values(item ?? {}).some((value) => value === ""))) flags.push("array_empty_value");
    } catch {
      flags.push("bad_array");
    }
  }
  summary.changed++;
  summary.byType[type] = (summary.byType[type] ?? 0) + 1;
  summary.byFormat[format] = (summary.byFormat[format] ?? 0) + 1;
  summary.byFile[file] = (summary.byFile[file] ?? 0) + 1;
  if (flags.length) summary.suspicious++;
  diffs.push({ id, file_name: file, question_type: type, answer_format: format, question: String(test.question ?? ""), oldAnswer, newAnswer, flags });
}

const payload = { summary, suspicious: diffs.filter((row) => row.flags.length), diffs };
await fs.writeFile(outPath, JSON.stringify(payload, null, 2), "utf8");
console.log(JSON.stringify({ ...summary, suspiciousPreview: payload.suspicious.slice(0, 30), outPath }, null, 2));
