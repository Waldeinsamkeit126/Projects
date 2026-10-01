import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sourcePath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission.xlsx";
const basePath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/submission-compatible-base.xlsx";
const previewPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/submission-compatible-preview.png";

function replaceNulls(value) {
  if (value === null) return "";
  if (Array.isArray(value)) return value.map(replaceNulls);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, replaceNulls(child)]));
  }
  return value;
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(sourcePath));
const sheet = workbook.worksheets.getItemAt(0);
const target = sheet.getRange("B60");
const original = String(target.values[0][0]);
const normalized = JSON.stringify(replaceNulls(JSON.parse(original)));
target.values = [[normalized]];

const used = sheet.getUsedRange(true);
const values = used.values;
const blankRows = values.slice(1).filter((row) => row[0] == null || String(row[0]).trim() === "" || row[1] == null || String(row[1]).trim() === "");
if (values.length !== 909 || values[0][0] !== "id" || values[0][1] !== "answer" || blankRows.length !== 0) {
  throw new Error(`Validation failed: rows=${values.length}, headers=${JSON.stringify(values[0])}, blankRows=${blankRows.length}`);
}

const keyRange = await workbook.inspect({
  kind: "table",
  range: "Sheet1!A1:B12",
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 2,
  maxChars: 5000,
});
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "submission formula error scan",
});
const preview = await workbook.render({ sheetName: "Sheet1", range: "A1:B12", scale: 1.5, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(basePath);

console.log(JSON.stringify({
  basePath,
  previewPath,
  rows: values.length,
  blankRows: blankRows.length,
  changedCell: "B60",
  before: original,
  after: normalized,
  keyRange: keyRange.ndjson,
  errorScan: errors.ndjson,
}));
