import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspace = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const baselinePath = `${workspace}/outputs/table_competition_solution/submission-candidate-v36-adjudicated-image-refresh.xlsx`;
const v34Path = `${workspace}/outputs/table_competition_solution/submission-candidate-v34-add-day3-bp.xlsx`;
const outputPath = `${workspace}/outputs/table_competition_solution/submission-candidate-v37-score-feedback-corrections.xlsx`;

async function readRows(filePath) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  return workbook.worksheets.getItemAt(0).getUsedRange(true).values;
}

const [baselineRows, v34Rows] = await Promise.all([readRows(baselinePath), readRows(v34Path)]);
const v34ById = new Map(v34Rows.slice(1).map((row) => [String(row[0]), String(row[1] ?? "")]));
const directFixes = new Map([
  ["108", JSON.stringify([{
    "授课语言/Language of Instruction": "双语/全英文Chinese or English",
    "开课院系/School": "生命科学技术学院School of Life Sciences and Biotechnology",
    "先修课程/Prerequisite": "概率统计Probability and Statistics",
    "授课教师/Teacher": "韦朝春",
  }])],
  ["528", JSON.stringify([{
    "最低活动价": "399",
    "最高活动价": "59999",
    "备注中含退换规则": "3年内非人为原因质量问题硬件免费换新",
    "表格下方说明条数": "3",
  }])],
]);
const revertIds = new Set(["139", "212", "459", "468", "498", "508", "529", "876"]);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(baselinePath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
const changes = [];
for (let rowIndex = 1; rowIndex < rows.length; rowIndex++) {
  const id = String(rows[rowIndex][0]);
  let nextAnswer;
  let reason;
  if (directFixes.has(id)) {
    nextAnswer = directFixes.get(id);
    reason = "visual_correction";
  } else if (revertIds.has(id)) {
    nextAnswer = v34ById.get(id);
    reason = "revert_confirmed_regression";
  } else {
    continue;
  }
  const previous = String(rows[rowIndex][1] ?? "");
  if (previous === nextAnswer) throw new Error(`Fix ${id} does not change the baseline`);
  sheet.getCell(rowIndex, 1).values = [[nextAnswer]];
  changes.push({ id, reason, previous, next: nextAnswer });
}

if (changes.length !== directFixes.size + revertIds.size) {
  throw new Error(`Expected ${directFixes.size + revertIds.size} changes, applied ${changes.length}`);
}

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "v37 formula error scan",
});
if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
  throw new Error(`Formula errors found: ${formulaErrors.ndjson}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const exportedRows = await readRows(outputPath);
const exportedChanged = [];
for (let rowIndex = 1; rowIndex < baselineRows.length; rowIndex++) {
  if (String(exportedRows[rowIndex][1] ?? "") !== String(baselineRows[rowIndex][1] ?? "")) {
    exportedChanged.push(String(baselineRows[rowIndex][0]));
  }
}
const expectedIds = changes.map((item) => item.id);
if (JSON.stringify(exportedChanged) !== JSON.stringify(expectedIds)) {
  throw new Error(`Unexpected exported differences: ${JSON.stringify(exportedChanged)}`);
}

console.log(JSON.stringify({ outputPath: path.normalize(outputPath), changed: exportedChanged, changes }, null, 2));
