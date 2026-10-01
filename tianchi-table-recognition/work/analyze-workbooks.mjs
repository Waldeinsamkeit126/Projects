import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import fs from "node:fs/promises";

const inputs = [
  { label: "template", path: "D:/submit-template.xlsx" },
  { label: "tests", path: "D:/tests.xlsx" },
  {
    label: "submission",
    path: "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission.xlsx",
  },
  {
    label: "fixed",
    path: "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-fixed.xlsx",
  },
  {
    label: "arraysFixed",
    path: "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-arrays-fixed.xlsx",
  },
  {
    label: "finalV6",
    path: "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v6.xlsx",
  },
];

for (const input of inputs) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(input.path));
  const sheet = workbook.worksheets.getItemAt(0);
  const used = sheet.getUsedRange(true);
  const values = used?.values ?? [];
  const dataRows = values.slice(1);
  const answers = dataRows.map((row) => row?.[1]);
  const textAnswers = answers.map((value) => (value == null ? "" : String(value)));
  const ids = dataRows.map((row) => row?.[0]);
  const summary = {
    label: input.label,
    sheetName: sheet.name,
    worksheetCount: workbook.worksheets.items?.length,
    tableCount: sheet.tables.items?.length,
    usedAddress: used?.address,
    rowCount: values.length,
    colCount: Math.max(0, ...values.map((row) => row.length)),
    headers: values[0] ?? [],
    firstRows: values.slice(0, 4),
    lastRows: values.slice(-3),
    idTypes: [...new Set(ids.map((value) => typeof value))],
    answerTypes: [...new Set(answers.map((value) => typeof value))],
    blankIds: ids.filter((value) => value == null || String(value).trim() === "").length,
    blankAnswers: textAnswers.filter((value) => value.trim() === "").length,
    maxAnswerLength: Math.max(0, ...textAnswers.map((value) => value.length)),
    answersOver32767: textAnswers.filter((value) => value.length > 32767).length,
    controlCharAnswers: textAnswers.filter((value) => /[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(value)).length,
  };
  console.log(JSON.stringify(summary));
  if (input.label !== "tests") {
    const preview = await workbook.render({ sheetName: sheet.name, range: input.label === "template" ? "A1:B1" : "A1:B12", scale: 1.5, format: "png" });
    await fs.writeFile(`C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/${input.label}-preview.png`, new Uint8Array(await preview.arrayBuffer()));
  }
}

const testsBook = await SpreadsheetFile.importXlsx(await FileBlob.load("D:/tests.xlsx"));
const testRows = testsBook.worksheets.getItemAt(0).getUsedRange(true).values;
const headers = testRows[0].map(String);
const tests = testRows.slice(1).map((row) => Object.fromEntries(headers.map((key, i) => [key, row[i]])));
const resultLines = (await fs.readFile(
  "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/state/results.jsonl",
  "utf8",
)).split(/\r?\n/).filter(Boolean).map(JSON.parse);
const answers = new Map(resultLines.map((row) => [String(row.id), String(row.answer ?? "")]));
const anomalies = [];
const shapeCounts = {};
const numberSpecials = [];
for (const row of tests) {
  const id = String(row.id);
  const format = String(row.answer_format ?? "string");
  const answer = answers.get(id) ?? "";
  if (/^[=+\-@]/.test(answer)) anomalies.push({ id, format, issue: "formula-like prefix", answer: answer.slice(0, 80) });
  if (format === "number" && !/^-?(?:\d+(?:\.\d+)?|\.\d+)%?$/.test(answer)) {
    anomalies.push({ id, format, issue: "non-canonical number", answer: answer.slice(0, 120) });
  }
  if (format === "number" && /%$/.test(answer)) numberSpecials.push({ id, answer, question: String(row.question) });
  if (format === "json_array") {
    try {
      const parsed = JSON.parse(answer);
      const shape = !Array.isArray(parsed) ? "not-array" : parsed.length === 0 ? "empty" : typeof parsed[0] === "object" && parsed[0] !== null && !Array.isArray(parsed[0]) ? "object-array" : `${typeof parsed[0]}-array`;
      shapeCounts[shape] = (shapeCounts[shape] ?? 0) + 1;
      if (JSON.stringify(parsed).includes("null")) anomalies.push({ id, format, issue: "contains null", answer: answer.slice(0, 180) });
    } catch (error) {
      anomalies.push({ id, format, issue: "invalid json array", error: error.message });
    }
  }
  if (format === "json") {
    try {
      const parsed = JSON.parse(answer);
      const seen = new Set();
      let duplicateCoordinates = 0;
      for (const cell of parsed.cells ?? []) {
        const key = `${cell.row}:${cell.col}`;
        if (seen.has(key)) duplicateCoordinates += 1;
        seen.add(key);
      }
      if (duplicateCoordinates) anomalies.push({ id, format, issue: "duplicate structure coordinates", duplicateCoordinates });
    } catch (error) {
      anomalies.push({ id, format, issue: "invalid structure json", error: error.message });
    }
  }
}
console.log(JSON.stringify({ shapeCounts, numberSpecials, anomalyCount: anomalies.length, anomalies: anomalies.slice(0, 100) }));
