import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const root = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const testsPath = `${root}/work/competition_data/multimodal_table_recognition/tests.xlsx`;
const baselinePath = `${root}/outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx`;
const outputPath = `${root}/outputs/table_competition_solution/submission-candidate-v47-verified-column-counts.xlsx`;
const previewDir = `${root}/work/v47-preview`;
const reportPath = `${root}/work/v47-report.json`;

const fixes = new Map([
  ["251", "8"],
  ["291", "4"],
  ["371", "6"],
  ["391", "6"],
  ["401", "8"],
  ["481", "9"],
  ["491", "9"],
  ["890", "Debajit Mukherjee"],
]);

async function loadWorkbook(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const sheet = workbook.worksheets.getItemAt(0);
  return { workbook, sheet, values: sheet.getUsedRange(true).values };
}

function rowsToObjects(values) {
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

const [baselineLoaded, testsLoaded] = await Promise.all([
  loadWorkbook(baselinePath),
  loadWorkbook(testsPath),
]);
const { workbook, sheet } = baselineLoaded;
const baselineRows = baselineLoaded.values;
const tests = rowsToObjects(testsLoaded.values);

if (baselineRows.length !== 909 || tests.length !== 908) {
  throw new Error(`Unexpected input rows: baseline=${baselineRows.length}, tests=${tests.length}`);
}
if (String(baselineRows[0][0]) !== "id" || String(baselineRows[0][1]) !== "answer") {
  throw new Error(`Unexpected baseline headers: ${JSON.stringify(baselineRows[0])}`);
}

const applied = [];
for (let rowIndex = 1; rowIndex < baselineRows.length; rowIndex += 1) {
  const id = String(baselineRows[rowIndex][0] ?? "");
  if (!fixes.has(id)) continue;
  const previous = String(baselineRows[rowIndex][1] ?? "");
  const next = fixes.get(id);
  if (previous === next) throw new Error(`Fix ${id} does not change the baseline`);
  sheet.getCell(rowIndex, 1).values = [[next]];
  applied.push({ id, previous, next, basis: "manual_visual_verification" });
}
if (applied.length !== fixes.size) {
  const appliedIds = new Set(applied.map((item) => item.id));
  const missing = [...fixes.keys()].filter((id) => !appliedIds.has(id));
  throw new Error(`Applied ${applied.length}/${fixes.size}; missing=${JSON.stringify(missing)}`);
}

workbook.recalculate();
const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "v47 formula error scan",
});
if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
  throw new Error(`Formula errors found: ${formulaErrors.ndjson}`);
}

const usedRange = await workbook.inspect({
  kind: "table",
  range: `${sheet.name}!A1:B909`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 2,
  summary: "v47 submission shape and sample",
});

await fs.mkdir(path.dirname(outputPath), { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const reopened = await loadWorkbook(outputPath);
const candidateRows = reopened.values;
if (candidateRows.length !== baselineRows.length) {
  throw new Error(`Exported row count changed: ${candidateRows.length}`);
}
if (String(candidateRows[0][0]) !== "id" || String(candidateRows[0][1]) !== "answer") {
  throw new Error(`Unexpected exported headers: ${JSON.stringify(candidateRows[0])}`);
}

const changedIds = [];
const invalid = [];
for (let rowIndex = 1; rowIndex < candidateRows.length; rowIndex += 1) {
  const test = tests[rowIndex - 1];
  const id = String(candidateRows[rowIndex][0] ?? "");
  const answer = String(candidateRows[rowIndex][1] ?? "");
  if (id !== String(test.id ?? "")) throw new Error(`ID order mismatch at row ${rowIndex + 1}: ${id}`);
  if (id !== String(baselineRows[rowIndex][0] ?? "")) throw new Error(`Baseline ID mismatch at row ${rowIndex + 1}: ${id}`);
  if (answer !== String(baselineRows[rowIndex][1] ?? "")) changedIds.push(id);
  const question = {
    ...test,
    id,
    question_type: ["structure", "extract", "thinking"].includes(String(test.question_type ?? ""))
      ? String(test.question_type)
      : "extract",
    answer_format: String(test.answer_format ?? "string") || "string",
  };
  const validation = validateAnswer(question, answer);
  if (!validation.valid) invalid.push({ id, error: validation.error });
}
const expectedIds = [...fixes.keys()];
if (JSON.stringify(changedIds) !== JSON.stringify(expectedIds)) {
  throw new Error(`Unexpected exported differences: ${JSON.stringify(changedIds)}`);
}
if (invalid.length) throw new Error(`Invalid answers: ${JSON.stringify(invalid.slice(0, 20))}`);

await fs.mkdir(previewDir, { recursive: true });
const previewPaths = [];
for (let start = 1, part = 1; start <= candidateRows.length; start += 230, part += 1) {
  const end = Math.min(candidateRows.length, start + 229);
  const rendered = await reopened.workbook.render({
    sheetName: reopened.sheet.name,
    range: `A${start}:B${end}`,
    scale: 1.2,
    format: "png",
  });
  const previewPath = path.join(previewDir, `part-${part}.png`);
  await fs.writeFile(previewPath, new Uint8Array(await rendered.arrayBuffer()));
  previewPaths.push(previewPath);
}

const report = {
  outputPath: path.normalize(outputPath),
  reportPath: path.normalize(reportPath),
  baselinePath: path.normalize(baselinePath),
  rows: candidateRows.length - 1,
  changedCount: changedIds.length,
  changedIds,
  invalidCount: invalid.length,
  reopenedMatches: true,
  usedRangeInspection: usedRange.ndjson,
  formulaErrorInspection: formulaErrors.ndjson,
  previewPaths,
  applied,
};
await fs.writeFile(reportPath, JSON.stringify(report, null, 2), "utf8");
console.log(JSON.stringify(report, null, 2));
