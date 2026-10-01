import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const testsPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/work/competition_data/multimodal_table_recognition/tests.xlsx";
const finalPath = process.argv[2] ?? "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-candidate-v35-qwen37-image-refresh.xlsx";

async function rowsFrom(path) {
  const book = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
  const values = book.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

const tests = await rowsFrom(testsPath);
const submitted = await rowsFrom(finalPath);
const byId = new Map(submitted.map((row) => [String(row.id), String(row.answer ?? "")]));
const problems = [];
const stats = { formats: {}, structure: {}, arrays: {}, numbers: {} };

for (const test of tests) {
  const id = String(test.id);
  const format = id === "32" ? "json" : String(test.answer_format);
  const answer = byId.get(id) ?? "";
  stats.formats[format] = (stats.formats[format] ?? 0) + 1;
  if (!answer.trim()) problems.push({ id, format, issue: "direct blank" });
  if (/^\s|\s$/.test(answer)) problems.push({ id, format, issue: "outer whitespace" });
  if (answer.includes("\uFEFF")) problems.push({ id, format, issue: "BOM" });
  if (format === "number") {
    const canonical = /^-?(?:\d+(?:\.\d+)?|\.\d+)%?$/.test(answer);
    stats.numbers[canonical ? "canonical" : "noncanonical"] = (stats.numbers[canonical ? "canonical" : "noncanonical"] ?? 0) + 1;
    if (!canonical) problems.push({ id, format, issue: "noncanonical number", answer });
  }
  if (format === "json_array") {
    try {
      const parsed = JSON.parse(answer);
      const keyShapes = new Set();
      let emptyValues = 0;
      let boolValues = 0;
      let numberValues = 0;
      let stringValues = 0;
      for (const item of parsed) {
        keyShapes.add(Object.keys(item).sort().join("|"));
        for (const value of Object.values(item)) {
          if (value === "") emptyValues++;
          if (typeof value === "boolean") boolValues++;
          if (typeof value === "number") numberValues++;
          if (typeof value === "string") stringValues++;
        }
      }
      const shapeCount = keyShapes.size;
      stats.arrays.items = (stats.arrays.items ?? 0) + parsed.length;
      stats.arrays.emptyValues = (stats.arrays.emptyValues ?? 0) + emptyValues;
      stats.arrays.booleanValues = (stats.arrays.booleanValues ?? 0) + boolValues;
      stats.arrays.numberValues = (stats.arrays.numberValues ?? 0) + numberValues;
      stats.arrays.stringValues = (stats.arrays.stringValues ?? 0) + stringValues;
      if (shapeCount > 1) problems.push({ id, format, issue: "heterogeneous object keys", shapes: [...keyShapes] });
    } catch (error) {
      problems.push({ id, format, issue: "parse error", error: error.message });
    }
  }
  if (format === "json") {
    try {
      const parsed = JSON.parse(answer);
      const cells = parsed.cells ?? [];
      stats.structure.answers = (stats.structure.answers ?? 0) + 1;
      stats.structure.cells = (stats.structure.cells ?? 0) + cells.length;
      if (!cells.length) problems.push({ id, format, issue: "empty cells" });
      const starts = new Set();
      const occupied = new Set();
      let overlaps = 0;
      let emptyTexts = 0;
      for (const cell of cells) {
        const start = `${cell.row}:${cell.col}`;
        if (starts.has(start)) problems.push({ id, format, issue: "duplicate cell start", start });
        starts.add(start);
        if (cell.text === "") emptyTexts++;
        for (let r = cell.row; r < cell.row + cell.rowspan; r++) {
          for (let c = cell.col; c < cell.col + cell.colspan; c++) {
            const key = `${r}:${c}`;
            if (occupied.has(key)) overlaps++;
            occupied.add(key);
          }
        }
      }
      const total = parsed.row_count * parsed.col_count;
      const holes = total - occupied.size;
      stats.structure.emptyTexts = (stats.structure.emptyTexts ?? 0) + emptyTexts;
      stats.structure.overlaps = (stats.structure.overlaps ?? 0) + overlaps;
      stats.structure.holes = (stats.structure.holes ?? 0) + holes;
      if (overlaps) problems.push({ id, format, issue: "overlapping spans", overlaps });
      // Partial-structure questions intentionally leave most of the full logical
      // table grid uncovered; record those positions as a statistic, not an error.
    } catch (error) {
      problems.push({ id, format, issue: "parse error", error: error.message });
    }
  }
}

const idSequenceOk = submitted.length === tests.length && submitted.every((row, index) => String(row.id) === String(index + 1));
const uniqueIds = new Set(submitted.map((row) => String(row.id))).size;
const validatorFailures = tests.map((row) => {
  const validationRow = String(row.id) === "32" ? { ...row, answer_format: "json" } : row;
  return { id: String(row.id), result: validateAnswer(validationRow, byId.get(String(row.id)) ?? "") };
}).filter((row) => !row.result.valid);
const structureDimensions = tests.filter((row) => String(row.answer_format) === "json").map((row) => {
  const parsed = JSON.parse(byId.get(String(row.id)));
  return { id: String(row.id), file_name: row.file_name, question: row.question, row_count: parsed.row_count, col_count: parsed.col_count, cell_count: parsed.cells.length };
});
const structureDimensionStats = {
  total: structureDimensions.length,
  rowCountAtMost10: structureDimensions.filter((row) => row.row_count <= 10).length,
  explicitlyPartial: structureDimensions.filter((row) => /前|表头|首行|首列|第\s*\d+\s*[行列]/.test(String(row.question))).length,
};
console.log(JSON.stringify({ submittedRows: submitted.length, idSequenceOk, uniqueIds, validatorFailures, stats, structureDimensionStats, problemCount: problems.length, problems }, null, 2));
console.log(JSON.stringify(tests.filter((row) => ["358", "438", "679"].includes(String(row.id))).map((row) => ({...row, submitted_answer: byId.get(String(row.id))})), null, 2));
