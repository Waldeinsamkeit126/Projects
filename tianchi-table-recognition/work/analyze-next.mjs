import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const files = {
  tests: `${root}/work/competition_data/multimodal_table_recognition/tests.xlsx`,
  v34: `${root}/outputs/table_competition_solution/submission-candidate-v34-add-day3-bp.xlsx`,
  v35: `${root}/outputs/table_competition_solution/submission-candidate-v35-qwen37-image-refresh.xlsx`,
  v36: `${root}/outputs/table_competition_solution/submission-candidate-v36-adjudicated-image-refresh.xlsx`,
  v37: `${root}/outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx`,
};

async function rowsFrom(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const values = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

function counts(rows, selector) {
  const result = {};
  for (const row of rows) {
    const key = String(selector(row));
    result[key] = (result[key] ?? 0) + 1;
  }
  return Object.fromEntries(Object.entries(result).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])));
}

function compare(leftRows, rightRows, testById) {
  const rightById = new Map(rightRows.map((row) => [String(row.id), String(row.answer ?? "")]));
  return leftRows.flatMap((row) => {
    const id = String(row.id);
    const left = String(row.answer ?? "");
    const right = rightById.get(id) ?? "";
    if (left === right) return [];
    const test = testById.get(id) ?? {};
    return [{
      id,
      file_name: String(test.file_name ?? ""),
      question_type: String(test.question_type ?? "extract"),
      answer_format: String(test.answer_format ?? "string"),
      left,
      right,
    }];
  });
}

const [tests, v34, v35, v36, v37] = await Promise.all(Object.values(files).map(rowsFrom));
const testById = new Map(tests.map((row) => [String(row.id), row]));
const v37VsV35 = compare(v37, v35, testById);
const v36VsV37 = compare(v36, v37, testById);
const v34VsV37 = compare(v34, v37, testById);

console.log(JSON.stringify({
  candidatePair: "v37(current best) vs v35(qwen3.7 image refresh)",
  diffCount: v37VsV35.length,
  byType: counts(v37VsV35, (row) => row.question_type),
  byFormat: counts(v37VsV35, (row) => row.answer_format),
  byFileTop20: Object.fromEntries(Object.entries(counts(v37VsV35, (row) => row.file_name)).slice(0, 20)),
  distinctFiles: new Set(v37VsV35.map((row) => row.file_name)).size,
  v36ToV37: {
    diffCount: v36VsV37.length,
    byType: counts(v36VsV37, (row) => row.question_type),
    byFormat: counts(v36VsV37, (row) => row.answer_format),
    ids: v36VsV37.map((row) => row.id),
  },
  v34ToV37: {
    diffCount: v34VsV37.length,
    byType: counts(v34VsV37, (row) => row.question_type),
    byFormat: counts(v34VsV37, (row) => row.answer_format),
  },
}, null, 2));
