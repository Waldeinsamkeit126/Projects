import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { validateAnswer } from "../outputs/table_competition_solution/run.mjs";

const root = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const testsPath = `${root}/work/competition_data/multimodal_table_recognition/tests.xlsx`;
const baselinePath = `${root}/outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx`;
const candidatePath = process.argv[2] ?? `${root}/outputs/table_competition_solution/submission-candidate-v41-qwen38max-adjudicated.xlsx`;
const judgeReportPath = `${root}/outputs/table_competition_solution/state-v41-qwen38max-judge/judge-report.json`;
const previewDir = `${root}/work/v41-preview`;

async function loadWorkbook(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const sheet = workbook.worksheets.getItemAt(0);
  return { workbook, sheet, values: sheet.getUsedRange(true).values };
}

function rowsToObjects(values) {
  const headers = values[0].map(String);
  return values.slice(1).map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
}

const [testsLoaded, baselineLoaded, candidateLoaded, judgeReport] = await Promise.all([
  loadWorkbook(testsPath),
  loadWorkbook(baselinePath),
  loadWorkbook(candidatePath),
  fs.readFile(judgeReportPath, "utf8").then(JSON.parse),
]);

const tests = rowsToObjects(testsLoaded.values);
const baseline = baselineLoaded.values;
const candidate = candidateLoaded.values;
if (candidate.length !== baseline.length || candidate.length !== tests.length + 1) {
  throw new Error(`行数错误: candidate=${candidate.length}, baseline=${baseline.length}, tests=${tests.length + 1}`);
}
if (String(candidate[0][0]) !== "id" || String(candidate[0][1]) !== "answer") {
  throw new Error(`表头错误: ${JSON.stringify(candidate[0])}`);
}

const changedIds = [];
const invalid = [];
for (let index = 1; index < candidate.length; index += 1) {
  const expectedId = String(tests[index - 1].id ?? "");
  const candidateId = String(candidate[index][0] ?? "");
  const answer = String(candidate[index][1] ?? "");
  if (candidateId !== expectedId) throw new Error(`第 ${index + 1} 行 ID 顺序错误: ${candidateId} != ${expectedId}`);
  if (String(baseline[index][0] ?? "") !== candidateId) throw new Error(`基准 ID 顺序错误: ${candidateId}`);
  if (String(baseline[index][1] ?? "") !== answer) changedIds.push(candidateId);
  const question = {
    ...tests[index - 1],
    id: candidateId,
    question_type: ["structure", "extract", "thinking"].includes(String(tests[index - 1].question_type ?? ""))
      ? String(tests[index - 1].question_type)
      : "extract",
    answer_format: String(tests[index - 1].answer_format ?? "string") || "string",
  };
  const validation = validateAnswer(question, answer);
  if (!validation.valid) invalid.push({ id: candidateId, error: validation.error });
}
if (invalid.length) throw new Error(`存在无效答案: ${JSON.stringify(invalid.slice(0, 20))}`);

const expectedChangedIds = (judgeReport.applied ?? []).map((row) => String(row.id));
if (JSON.stringify(changedIds) !== JSON.stringify(expectedChangedIds)) {
  throw new Error(`改动 ID 与仲裁报告不一致: ${JSON.stringify({ changedIds, expectedChangedIds })}`);
}

candidateLoaded.workbook.recalculate();
const formulaErrors = await candidateLoaded.workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",
  options: { useRegex: true, maxResults: 300 },
  summary: "v41 final formula error scan",
});
if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
  throw new Error(`发现公式错误: ${formulaErrors.ndjson}`);
}

const usedRange = await candidateLoaded.workbook.inspect({
  kind: "table",
  range: `${candidateLoaded.sheet.name}!A1:B${candidate.length}`,
  include: "values,formulas",
  tableMaxRows: 12,
  tableMaxCols: 2,
  summary: "v41 submission shape and sample",
});

await fs.mkdir(previewDir, { recursive: true });
const previewPaths = [];
for (let start = 1, part = 1; start <= candidate.length; start += 230, part += 1) {
  const end = Math.min(candidate.length, start + 229);
  const rendered = await candidateLoaded.workbook.render({
    sheetName: candidateLoaded.sheet.name,
    range: `A${start}:B${end}`,
    scale: 1.2,
    format: "png",
  });
  const previewPath = path.join(previewDir, `part-${part}.png`);
  await fs.writeFile(previewPath, new Uint8Array(await rendered.arrayBuffer()));
  previewPaths.push(previewPath);
}

const reopened = await loadWorkbook(candidatePath);
if (JSON.stringify(reopened.values) !== JSON.stringify(candidate)) {
  throw new Error("导出文件重新打开后的值发生变化");
}

console.log(JSON.stringify({
  candidatePath,
  rows: candidate.length - 1,
  changedCount: changedIds.length,
  changedIds,
  invalidCount: invalid.length,
  usedRangeInspection: usedRange.ndjson,
  formulaErrorInspection: formulaErrors.ndjson,
  previewPaths,
  reopenedMatches: true,
}, null, 2));
