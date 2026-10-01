import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const testsPath = "D:/tests.xlsx";
const submissionPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v8.xlsx";

async function rows(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return { workbook, values, rows: values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]]))) };
}

const tests = await rows(testsPath);
const submission = await rows(submissionPath);
const answers = new Map(submission.rows.map((row) => [String(row.id), String(row.answer ?? "")]));
const failures = tests.rows.map((test) => {
  const id = String(test.id);
  const validationTest = id === "32" ? { ...test, answer_format: "json" } : test;
  return { id, result: validateAnswer(validationTest, answers.get(id) ?? "") };
}).filter((item) => !item.result.valid);
const ids = ["749", "759", "769", "779", "799", "809", "819", "829", "849", "869", "879", "889"];
const structures = ids.map((id) => {
  const value = JSON.parse(answers.get(id));
  return { id, row_count: value.row_count, col_count: value.col_count, cells: value.cells.length };
});
const preview = await submission.workbook.render({ sheetName: submission.workbook.worksheets.getItemAt(0).name, range: "A740:B900", scale: 1.2, format: "png" });
await fs.writeFile("work/finalV8-preview.png", new Uint8Array(await preview.arrayBuffer()));
console.log(JSON.stringify({
  rows: submission.rows.length,
  idSequenceOk: submission.rows.every((row, index) => String(row.id) === String(index + 1)),
  uniqueIds: new Set(submission.rows.map((row) => String(row.id))).size,
  blankAnswers: submission.rows.filter((row) => !String(row.answer ?? "").trim()).length,
  failures,
  structures,
}, null, 2));
