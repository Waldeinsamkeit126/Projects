import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspace = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const baselinePath = `${workspace}/outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx`;
const outputPath = `${workspace}/outputs/table_competition_solution/submission-candidate-v40-source-recovered-merged-header.xlsx`;
const previewPath = `${workspace}/work/v40-row859-after.png`;
const targetId = "859";

const correctedAnswer = JSON.stringify({
  row_count: 19,
  col_count: 7,
  cells: [
    { text: "1", row: 0, col: 0, rowspan: 3, colspan: 1 },
    { text: "", row: 0, col: 1, rowspan: 2, colspan: 1 },
    { text: "", row: 0, col: 2, rowspan: 1, colspan: 2 },
    { text: "", row: 0, col: 4, rowspan: 3, colspan: 1 },
    { text: "", row: 0, col: 5, rowspan: 1, colspan: 2 },
    { text: "2", row: 1, col: 2, rowspan: 1, colspan: 1 },
    { text: "", row: 1, col: 3, rowspan: 1, colspan: 1 },
    { text: "", row: 1, col: 5, rowspan: 1, colspan: 1 },
    { text: "", row: 1, col: 6, rowspan: 1, colspan: 1 },
    { text: "3", row: 2, col: 1, rowspan: 1, colspan: 2 },
    { text: "", row: 2, col: 3, rowspan: 1, colspan: 1 },
    { text: "", row: 2, col: 5, rowspan: 1, colspan: 1 },
    { text: "", row: 2, col: 6, rowspan: 3, colspan: 1 },
  ],
});

async function loadRows(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  return workbook.worksheets.getItemAt(0).getUsedRange(true).values;
}

const baselineRows = await loadRows(baselinePath);
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(baselinePath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
const rowIndex = rows.findIndex((row, index) => index > 0 && String(row[0]) === targetId);
if (rowIndex < 0) throw new Error(`Could not locate ID ${targetId}`);

const prior = JSON.parse(String(rows[rowIndex][1] ?? ""));
if (prior.row_count !== 13 || prior.col_count !== 8) {
  throw new Error(`Unexpected baseline dimensions for ID ${targetId}: ${prior.row_count}x${prior.col_count}`);
}

sheet.getCell(rowIndex, 1).values = [[correctedAnswer]];
workbook.recalculate();

const changedRow = await workbook.inspect({
  kind: "table",
  range: `${sheet.name}!A${rowIndex + 1}:B${rowIndex + 1}`,
  include: "values,formulas",
  tableMaxRows: 2,
  tableMaxCols: 2,
});
const changedRowData = JSON.parse(changedRow.ndjson);
if (String(changedRowData.values?.[0]?.[0] ?? "") !== targetId ||
    String(changedRowData.values?.[0]?.[1] ?? "") !== correctedAnswer) {
  throw new Error(`Changed-row inspection failed: ${changedRow.ndjson}`);
}

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "v40 final formula error scan",
});
if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
  throw new Error(`Formula errors found: ${formulaErrors.ndjson}`);
}

const preview = await workbook.render({
  sheetName: sheet.name,
  range: `A${Math.max(1, rowIndex - 2)}:B${Math.min(rows.length, rowIndex + 4)}`,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const exportedRows = await loadRows(outputPath);
if (exportedRows.length !== baselineRows.length) {
  throw new Error(`Row count changed from ${baselineRows.length} to ${exportedRows.length}`);
}
const changedIds = [];
for (let i = 0; i < baselineRows.length; i++) {
  const beforeRow = baselineRows[i].map((value) => String(value ?? ""));
  const afterRow = exportedRows[i].map((value) => String(value ?? ""));
  if (JSON.stringify(beforeRow) !== JSON.stringify(afterRow)) {
    changedIds.push(String(baselineRows[i][0] ?? ""));
  }
}
if (JSON.stringify(changedIds) !== JSON.stringify([targetId])) {
  throw new Error(`Unexpected exported differences: ${JSON.stringify(changedIds)}`);
}
if (String(exportedRows[rowIndex][1] ?? "") !== correctedAnswer) {
  throw new Error("Corrected answer was not preserved after export/reopen");
}

console.log(JSON.stringify({
  outputPath: path.normalize(outputPath),
  changedIds,
  dimensions: "19x7",
  headerCells: 13,
  changedRowInspection: changedRow.ndjson,
  formulaErrorInspection: formulaErrors.ndjson,
  previewPath: path.normalize(previewPath),
}, null, 2));
