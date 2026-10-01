import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspace = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const inputPath = `${workspace}/outputs/table_competition_solution/submission-candidate-v30-financial-arithmetic.xlsx`;
const outputPath = `${workspace}/outputs/table_competition_solution/submission-candidate-v34-add-day3-bp.xlsx`;
const fixes = new Map([
  [
    "98",
    {
      previous: JSON.stringify([
        { "Day": "Day 2", "时段": "9:30-12:00", "卡片标题": "AI应用商业探索", "BP模块": "Problem" },
        { "Day": "Day 5", "时段": "9:30-12:00", "卡片标题": "项目商业闭环构建", "BP模块": "Business" },
      ]),
      next: JSON.stringify([
        { "Day": "Day 2", "时段": "9:30-12:00", "卡片标题": "AI应用商业探索", "BP模块": "Problem" },
        { "Day": "Day 3", "时段": "9:30-12:00", "卡片标题": "产品结构设计", "BP模块": "Product" },
        { "Day": "Day 5", "时段": "9:30-12:00", "卡片标题": "项目商业闭环构建", "BP模块": "Business" },
      ]),
    },
  ],
]);

const baselineWorkbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const baselineRows = baselineWorkbook.worksheets.getItemAt(0).getUsedRange(true).values;
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;

const changed = [];
for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
  const id = String(rows[rowIndex][0]);
  if (!fixes.has(id)) continue;
  const fix = fixes.get(id);
  if (String(rows[rowIndex][1]) !== fix.previous) {
    throw new Error(`Unexpected baseline answer for ${id}: ${String(rows[rowIndex][1])}`);
  }
  sheet.getCell(rowIndex, 1).values = [[fix.next]];
  changed.push(id);
}

if (changed.length !== fixes.size) {
  throw new Error(`Expected ${fixes.size} fixes, applied ${changed.length}`);
}

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "v34 formula error scan",
});
if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
  throw new Error(`Formula errors found: ${formulaErrors.ndjson}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);

const exportedWorkbook = await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
const exportedRows = exportedWorkbook.worksheets.getItemAt(0).getUsedRange(true).values;
const exportedChanged = [];
for (let rowIndex = 1; rowIndex < baselineRows.length; rowIndex += 1) {
  if (String(exportedRows[rowIndex][1]) !== String(baselineRows[rowIndex][1])) {
    exportedChanged.push(String(baselineRows[rowIndex][0]));
  }
}

if (JSON.stringify(exportedChanged) !== JSON.stringify([...fixes.keys()])) {
  throw new Error(`Unexpected exported differences: ${JSON.stringify(exportedChanged)}`);
}

console.log(JSON.stringify({
  outputPath: path.normalize(outputPath),
  changed: exportedChanged,
  fixes: Object.fromEntries(fixes),
}));
