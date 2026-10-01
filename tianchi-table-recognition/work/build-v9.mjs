import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v6-excel.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v9.xlsx";

const fixes = new Map([
  ["19", JSON.stringify([{ "组成项": "营业收入" }])],
  ["103", "学分 (Credits)"],
  ["208", JSON.stringify([{
    "BTM Si%": "0.220",
    "2HM C%": "0.450",
    "红色限制单元数量": "8",
    "绿色数值单元数量": "16",
  }])],
  ["378", JSON.stringify([{
    "HCMRM total pore volume": "8.635",
    "HCMRM average particle size": "84.172",
    "编码列名": "Coded name",
    "设计因素数量": "4",
  }])],
  ["877", "是"],
]);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
const changed = [];
for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
  const id = String(rows[rowIndex][0]);
  if (!fixes.has(id)) continue;
  sheet.getCell(rowIndex, 1).values = [[fixes.get(id)]];
  changed.push(id);
}
if (changed.length !== fixes.size) throw new Error(`Expected ${fixes.size} fixes, applied ${changed.length}`);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
