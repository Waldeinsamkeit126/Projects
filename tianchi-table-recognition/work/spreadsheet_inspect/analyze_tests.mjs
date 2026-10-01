import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import fs from "node:fs/promises";

const source = "D:/tests.xlsx";
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(source));
const sheet = workbook.worksheets.getItemAt(0);
const values = sheet.getUsedRange(true).values;
const headers = values[0].map(String);
const rows = values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));

const countBy = (key) => Object.fromEntries(
  [...rows.reduce((map, row) => map.set(String(row[key] ?? ""), (map.get(String(row[key] ?? "")) ?? 0) + 1), new Map())]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
);

const ids = rows.map((row) => String(row.id ?? ""));
const files = [...new Set(rows.map((row) => String(row.file_name ?? "")))].sort();
const duplicateIds = ids.filter((id, index) => ids.indexOf(id) !== index);
const invalidTypes = rows.map((row, index) => ({ excelRow: index + 2, row }))
  .filter(({ row }) => !["structure", "extract", "thinking"].includes(String(row.question_type ?? "")));
const nonBlankAnswers = rows.map((row, index) => ({ excelRow: index + 2, id: row.id, answer: row.answer }))
  .filter(({ answer }) => answer != null && String(answer).trim() !== "");
const mediaNumbers = files.map((file) => Number.parseInt(file.split(".")[0], 10)).filter(Number.isFinite);
const missingMediaNumbers = Array.from({ length: Math.max(...mediaNumbers) }, (_, index) => index + 1)
  .filter((number) => !mediaNumbers.includes(number));
const mediaRoot = "../competition_data/multimodal_table_recognition/files";
const actualFiles = (await fs.readdir(mediaRoot)).sort();
const unreferencedFiles = actualFiles.filter((file) => !files.includes(file));
const missingReferencedFiles = files.filter((file) => !actualFiles.includes(file));
const missingReferenceRows = rows
  .filter((row) => missingReferencedFiles.includes(String(row.file_name)))
  .map((row) => ({ id: row.id, file_name: row.file_name, question_type: row.question_type, answer_format: row.answer_format }));
const missingRequired = {};
for (const key of ["id", "file_name", "question_type", "question"]) {
  missingRequired[key] = rows.filter((row) => row[key] == null || String(row[key]).trim() === "").length;
}

console.log(JSON.stringify({
  rowCount: rows.length,
  headers,
  uniqueFiles: files.length,
  questionTypes: countBy("question_type"),
  answerFormats: countBy("answer_format"),
  fileExtensions: Object.fromEntries(
    [...files.reduce((map, file) => {
      const ext = file.includes(".") ? `.${file.split(".").pop().toLowerCase()}` : "";
      return map.set(ext, (map.get(ext) ?? 0) + 1);
    }, new Map())]
  ),
  tableHintTopValues: Object.entries(countBy("table_hint")).slice(0, 12),
  existingAnswerTopValues: Object.entries(countBy("answer")).slice(0, 12),
  missingRequired,
  duplicateIds: [...new Set(duplicateIds)],
  invalidTypes,
  nonBlankAnswerRows: {
    count: nonBlankAnswers.length,
    first: nonBlankAnswers.slice(0, 5),
    last: nonBlankAnswers.slice(-5),
  },
  missingMediaNumbers,
  unreferencedFiles,
  missingReferencedFiles,
  missingReferenceRows,
  firstId: ids[0],
  lastId: ids.at(-1),
}, null, 2));
