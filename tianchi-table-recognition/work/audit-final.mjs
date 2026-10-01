import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspace = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const outputDir = path.join(workspace, "outputs/table_competition_solution");

const workbooks = [
  ["model", "submission.xlsx"],
  ["v6", "submission-final-v6-excel.xlsx"],
  ["v7", "submission-final-v7.xlsx"],
  ["v8", "submission-final-v8.xlsx"],
  ["v9", "submission-final-v9.xlsx"],
  ["v10", "submission-final-v10.xlsx"],
  ["v11", "submission-final-v11.xlsx"],
  ["v12", "submission-final-v12.xlsx"],
  ["v13", "submission-final-v13.xlsx"],
  ["v14", "submission-final-v14.xlsx"],
  ["v15", "submission-final-v15.xlsx"],
  ["v16", "submission-final-v16.xlsx"],
  ["v17", "submission-final-v17.xlsx"],
  ["v18", "submission-final-v18.xlsx"],
  ["v19", "submission-final-v19.xlsx"],
  ["v20", "submission-final-v20.xlsx"],
  ["v21", "submission-candidate-v21-customs.xlsx"],
  ["v22", "submission-candidate-v22-price.xlsx"],
  ["v23", "submission-candidate-v23-multiply.xlsx"],
  ["v24", "submission-candidate-v24-dimensions.xlsx"],
  ["v25", "submission-candidate-v25-revert-238.xlsx"],
  ["v26", "submission-candidate-v26-title-459.xlsx"],
  ["v27", "submission-candidate-v27-daily-value-503.xlsx"],
  ["v28", "submission-candidate-v28-origin-field-473.xlsx"],
  ["v29", "submission-candidate-v29-lot-title-129.xlsx"],
  ["v30", "submission-candidate-v30-financial-arithmetic.xlsx"],
  ["v31", "submission-candidate-v31-verified-value-fixes.xlsx"],
  ["v32", "submission-candidate-v32-customs-title-349.xlsx"],
  ["v33", "submission-candidate-v33-text-normalization.xlsx"],
];

async function loadRows(filePath) {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  return wb.worksheets.getItemAt(0).getUsedRange(true).values;
}

const testRows = await loadRows(path.join(workspace, "work/competition_data/multimodal_table_recognition/tests.xlsx"));
const headers = testRows[0].map(String);
const tests = new Map(testRows.slice(1).map((row) => {
  const item = Object.fromEntries(headers.map((header, index) => [header, row[index]]));
  return [String(item.id), item];
}));

const loaded = new Map();
for (const [label, fileName] of workbooks) {
  const rows = await loadRows(path.join(outputDir, fileName));
  loaded.set(label, new Map(rows.slice(1).map((row) => [String(row[0]), String(row[1] ?? "")])));
}

function diffMaps(from, to) {
  const diffs = [];
  for (const [id, next] of to) {
    const previous = from.get(id) ?? "";
    if (previous === next) continue;
    const test = tests.get(id) ?? {};
    diffs.push({
      id,
      file: String(test.file_name ?? ""),
      type: String(test.question_type ?? ""),
      format: String(test.answer_format ?? ""),
      question: String(test.question ?? ""),
      previous,
      next,
    });
  }
  return diffs;
}

const pairDiffs = [];
for (let index = 1; index < workbooks.length; index += 1) {
  const [previousLabel] = workbooks[index - 1];
  const [label] = workbooks[index];
  pairDiffs.push({
    pair: `${previousLabel}->${label}`,
    diffs: diffMaps(loaded.get(previousLabel), loaded.get(label)),
  });
}

const current = loaded.get("v33");
const risks = [];
for (const [id, answer] of current) {
  const test = tests.get(id) ?? {};
  const format = String(test.answer_format ?? "");
  const question = String(test.question ?? "");
  const file = String(test.file_name ?? "");
  const issues = [];
  if (format === "json_array") {
    try {
      const value = JSON.parse(answer);
      if (!Array.isArray(value)) issues.push("not_array");
      if (Array.isArray(value) && JSON.stringify(value).includes('\"\"')) issues.push("empty_value");
    } catch {
      issues.push("invalid_json_array");
    }
  }
  if (format === "json") {
    try {
      const value = JSON.parse(answer);
      const cells = Array.isArray(value.cells) ? value.cells : [];
      const neededRows = Math.max(0, ...cells.map((cell) => Number(cell.row ?? 0) + Number(cell.rowspan ?? 1)));
      const neededCols = Math.max(0, ...cells.map((cell) => Number(cell.col ?? 0) + Number(cell.colspan ?? 1)));
      if (Number(value.row_count) < neededRows) issues.push(`row_count_lt_cells:${value.row_count}<${neededRows}`);
      if (Number(value.col_count) < neededCols) issues.push(`col_count_lt_cells:${value.col_count}<${neededCols}`);
      if (cells.some((cell) => String(cell.text ?? "") === "")) issues.push("empty_structure_text");
      if (/表头行结构|表头结构/.test(question) && cells.some((cell) => Number(cell.row ?? 0) >= 3)) issues.push("header_includes_deep_rows");
    } catch {
      issues.push("invalid_structure_json");
    }
  }
  if (format === "number" && /%/.test(question) && !/%$/.test(answer)) issues.push("percent_answer_without_symbol");
  if (/对应的值/.test(question) && /^(?:Not specified|未提及|无|0)$/.test(answer)) issues.push("possibly_missing_extraction");
  if (issues.length) risks.push({ id, file, format, question, answer, issues });
}

const result = {
  pairDiffs,
  allChangesFromModel: diffMaps(loaded.get("model"), current),
  risks,
};
await fs.writeFile(path.join(workspace, "work/final-audit.json"), JSON.stringify(result, null, 2), "utf8");
console.log(JSON.stringify({
  pairSummary: pairDiffs.map(({ pair, diffs }) => ({ pair, ids: diffs.map((item) => item.id) })),
  allChangeCount: result.allChangesFromModel.length,
  riskCount: risks.length,
  riskIds: risks.map((item) => item.id),
}));
