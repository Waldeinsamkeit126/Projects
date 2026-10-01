import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const testsPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/competition_data/multimodal_table_recognition/tests.xlsx";
const submissionPath = process.argv[2] ?? "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v10.xlsx";
const resultsPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/state/results.jsonl";

async function readRows(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

const tests = await readRows(testsPath);
const submitted = await readRows(submissionPath);
const submittedById = new Map(submitted.map((row) => [String(row.id), String(row.answer ?? "")]));
const resultRows = (await fs.readFile(resultsPath, "utf8")).split(/\r?\n/).filter(Boolean).map(JSON.parse);
const resultById = new Map(resultRows.map((row) => [String(row.id), row]));
const risky = [];
const joined = [];

for (const test of tests) {
  const id = String(test.id);
  const answer = submittedById.get(id) ?? "";
  const result = resultById.get(id) ?? {};
  const flags = [];
  const question = String(test.question ?? "");
  const format = id === "32" ? "json" : String(test.answer_format ?? "string");
  const hint = String(test.table_hint ?? "");
  if (/无法|未找到|不确定|看不清|无法确定|unknown|not found|cannot/i.test(answer)) flags.push("refusal_or_uncertainty");
  if (/答案|根据|表中|显示|可知/.test(answer) && format === "string") flags.push("explanatory_string");
  if (format === "string" && answer.length > 80) flags.push("long_string");
  if (format === "string" && answer.length <= 1) flags.push("very_short_string");
  if (format === "number" && /百分|比例|率/.test(question) && !answer.includes("%") && Number(answer) > 1 && Number(answer) < 100) flags.push("percent_without_symbol");
  if (format === "number" && /多少个|数量|行数|列数|几项|几个/.test(question) && !/^-?\d+$/.test(answer)) flags.push("non_integer_count");
  if (format === "json_array") {
    try {
      const parsed = JSON.parse(answer);
      const values = parsed.flatMap((item) => Object.values(item ?? {}));
      if (values.some((value) => value === "")) flags.push("array_empty_value");
      if (parsed.length > 6) flags.push("large_array");
      if (parsed.length === 1 && Object.keys(parsed[0] ?? {}).length === 1) flags.push("singleton_array");
    } catch {
      flags.push("bad_array");
    }
  }
  if (format === "json") {
    try {
      const parsed = JSON.parse(answer);
      const cellCount = parsed.cells?.length ?? 0;
      const headerOnly = /表头|第一行|首行|前\s*\d+\s*行|前两行/.test(question);
      if (headerOnly && cellCount > parsed.col_count * 3) flags.push("structure_too_many_cells");
      if (headerOnly && parsed.row_count <= 4) flags.push("structure_row_count_too_small");
      if (cellCount === parsed.row_count * parsed.col_count && headerOnly) flags.push("structure_full_grid_for_header");
      if ((parsed.cells ?? []).some((cell) => cell.text === "")) flags.push("structure_empty_text");
    } catch {
      flags.push("bad_structure");
    }
  }
  if (answer === hint && hint && hint !== "11") flags.push("answer_equals_hint");
  const row = {
    id,
    file_name: String(test.file_name ?? ""),
    question_type: String(test.question_type ?? ""),
    answer_format: format,
    question,
    hint,
    answer,
    model: String(result.model ?? ""),
    flags,
  };
  joined.push(row);
  if (flags.length) risky.push(row);
}

const byFlag = {};
for (const row of risky) for (const flag of row.flags) byFlag[flag] = (byFlag[flag] ?? 0) + 1;
const byFile = Object.values(joined.reduce((acc, row) => {
  acc[row.file_name] ??= { file_name: row.file_name, total: 0, risky: 0, ids: [] };
  acc[row.file_name].total += 1;
  if (row.flags.length) {
    acc[row.file_name].risky += 1;
    acc[row.file_name].ids.push(row.id);
  }
  return acc;
}, {})).sort((a, b) => b.risky - a.risky || b.total - a.total);

const joinedPath = process.argv[3] ?? "work/audit-joined-v10.json";
await fs.writeFile(joinedPath, JSON.stringify(joined, null, 2));
console.log(JSON.stringify({ riskCount: risky.length, byFlag, byFile: byFile.slice(0, 30), risky }, null, 2));
