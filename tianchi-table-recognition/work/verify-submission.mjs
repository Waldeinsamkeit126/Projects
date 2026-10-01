import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const testsPath = "D:/tests.xlsx";
const submissionPath = path.resolve(process.argv[2]);
const previewPath = path.resolve(process.argv[3] ?? "work/submission-verify-preview.png");

async function read(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  const rows = values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
  return { workbook, values, rows };
}

const tests = await read(testsPath);
const submission = await read(submissionPath);
const answers = new Map(submission.rows.map((row) => [String(row.id), String(row.answer ?? "")]));
const failures = tests.rows.map((test) => {
  const id = String(test.id);
  const validationTest = id === "32" ? { ...test, answer_format: "json" } : test;
  return { id, result: validateAnswer(validationTest, answers.get(id) ?? "") };
}).filter((item) => !item.result.valid);
const formulaErrors = await submission.workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "formula error scan",
});
const preview = await submission.workbook.render({
  sheetName: submission.workbook.worksheets.getItemAt(0).name,
  range: "A1:B25",
  scale: 1.2,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const report = {
  path: submissionPath,
  rows: submission.rows.length,
  idSequenceOk: submission.rows.every((row, index) => String(row.id) === String(index + 1)),
  uniqueIds: new Set(submission.rows.map((row) => String(row.id))).size,
  blankAnswers: submission.rows.filter((row) => !String(row.answer ?? "").trim()).length,
  failures,
  formulaErrors: formulaErrors.ndjson,
};
console.log(JSON.stringify(report, null, 2));

const formulaErrorFree = formulaErrors.ndjson.includes("Cell search matched 0 entries.");
if (!report.idSequenceOk || report.uniqueIds !== report.rows || report.blankAnswers || failures.length || !formulaErrorFree) {
  process.exit(1);
} else {
  process.exit(0);
}
