import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v2.xlsx";
const testsPath = "D:/tests.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-values-fixed.xlsx";
const previewPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/values-fixed-preview.png";

const inputBook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const testsBook = await SpreadsheetFile.importXlsx(await FileBlob.load(testsPath));
const sheet = inputBook.worksheets.getItemAt(0);
const testsSheet = testsBook.worksheets.getItemAt(0);
const submissionRows = sheet.getUsedRange(true).values;
const testRows = testsSheet.getUsedRange(true).values;
const testHeaders = testRows[0].map(String);
const testObjects = testRows.slice(1).map((row) => Object.fromEntries(testHeaders.map((key, index) => [key, row[index]])));
const formatById = new Map(testObjects.map((row) => [String(row.id), String(row.answer_format)]));

let changedAnswers = 0;
let changedValues = 0;
const outputAnswers = [];
for (const row of submissionRows.slice(1)) {
  const id = String(row[0]);
  let answer = String(row[1] ?? "");
  if (formatById.get(id) === "json_array") {
    const parsed = JSON.parse(answer);
    const normalized = parsed.map((item) => Object.fromEntries(Object.entries(item).map(([key, value]) => {
      if (typeof value !== "string") changedValues += 1;
      return [key, value === null ? "" : String(value)];
    })));
    const normalizedAnswer = JSON.stringify(normalized);
    if (normalizedAnswer !== answer) changedAnswers += 1;
    answer = normalizedAnswer;
  }
  outputAnswers.push([answer]);
}

sheet.getRange(`B2:B${submissionRows.length}`).values = outputAnswers;

const check = await inputBook.inspect({
  kind: "table",
  range: `Sheet1!A1:B${submissionRows.length}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 2,
  maxChars: 5000,
});
console.log(check.ndjson);
const errors = await inputBook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await inputBook.render({ sheetName: sheet.name, range: "A1:B12", scale: 1.5, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(inputBook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewPath, rows: submissionRows.length, changedAnswers, changedValues }));
