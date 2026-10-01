import path from "node:path";
import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspace = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const baselinePath = `${workspace}/outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx`;
const outputPath = `${workspace}/outputs/table_competition_solution/submission-candidate-v38-landscape-036.xlsx`;
const beforePreviewPath = `${workspace}/work/v38-row358-before.png`;
const afterPreviewPath = `${workspace}/work/v38-row358-after.png`;
const targetId = "358";
const previousAnswer = JSON.stringify([{
  "是否横向拍摄": "否",
  "是否含金额列": "是",
  "是否含订单号字段": "否",
  "是否含明细行": "是",
}]);
const correctedAnswer = JSON.stringify([{
  "是否横向拍摄": "是",
  "是否含金额列": "是",
  "是否含订单号字段": "否",
  "是否含明细行": "是",
}]);

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

const currentAnswer = String(rows[rowIndex][1] ?? "");
if (currentAnswer !== previousAnswer) {
  throw new Error(`Unexpected baseline answer for ID ${targetId}: ${currentAnswer}`);
}

const previewRange = `A${Math.max(1, rowIndex - 2)}:B${Math.min(rows.length, rowIndex + 4)}`;
const beforePreview = await workbook.render({
  sheetName: sheet.name,
  range: previewRange,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(beforePreviewPath, new Uint8Array(await beforePreview.arrayBuffer()));

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
  summary: "v38 final formula error scan",
});
if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
  throw new Error(`Formula errors found: ${formulaErrors.ndjson}`);
}

const afterPreview = await workbook.render({
  sheetName: sheet.name,
  range: previewRange,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(afterPreviewPath, new Uint8Array(await afterPreview.arrayBuffer()));

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
  sheet: sheet.name,
  previewRange,
  changedIds,
  changedRowInspection: changedRow.ndjson,
  formulaErrorInspection: formulaErrors.ndjson,
  beforePreviewPath: path.normalize(beforePreviewPath),
  afterPreviewPath: path.normalize(afterPreviewPath),
}, null, 2));
