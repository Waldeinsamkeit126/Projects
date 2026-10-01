import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const testsPath = "D:/tests.xlsx";
const submissionPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v7.xlsx";

async function readRows(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return { workbook, values, rows: values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]]))) };
}

const testsData = await readRows(testsPath);
const submissionData = await readRows(submissionPath);
const answersById = new Map(submissionData.rows.map((row) => [String(row.id), String(row.answer ?? "")]));
const failures = [];

for (const test of testsData.rows) {
  const id = String(test.id);
  const validationTest = id === "32" ? { ...test, answer_format: "json" } : test;
  const answer = answersById.get(id) ?? "";
  const validation = validateAnswer(validationTest, answer);
  if (!validation.valid) failures.push({ id, error: validation.error });
}

const idSequenceOk = submissionData.rows.length === 908 && submissionData.rows.every((row, index) => String(row.id) === String(index + 1));
const blankAnswers = submissionData.rows.filter((row) => !String(row.answer ?? "").trim()).map((row) => String(row.id));
const changedIds = ["19", "59", "83", "94", "103", "158", "208", "378", "479", "488", "528", "877"];
const changed = changedIds.map((id) => ({ id, answer: answersById.get(id) }));

const formulaErrors = await submissionData.workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});

const preview = await submissionData.workbook.render({ sheetName: submissionData.workbook.worksheets.getItemAt(0).name, range: "A1:B25", scale: 1.5, format: "png" });
await fs.writeFile("work/finalV7-preview.png", new Uint8Array(await preview.arrayBuffer()));

console.log(JSON.stringify({
  rows: submissionData.rows.length,
  idSequenceOk,
  uniqueIds: new Set(submissionData.rows.map((row) => String(row.id))).size,
  blankAnswers,
  validatorFailures: failures,
  usedRange: submissionData.workbook.worksheets.getItemAt(0).getUsedRange(true).address,
  formulaErrorScan: formulaErrors.ndjson,
  changed,
}, null, 2));
