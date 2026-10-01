import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v14.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v15.xlsx";

const fixes = new Map([
  ["22", JSON.stringify([
    { "变动项目": "专项储备" },
    { "变动项目": "未分配利润" },
    { "变动项目": "少数股东权益" },
    { "变动项目": "股东权益合计" },
  ])],
  ["59", JSON.stringify([
    { "项目": "房屋及建筑物", "金额": "0" },
    { "项目": "管网设备", "金额": "0" },
    { "项目": "运输工具", "金额": "1,876,349.13" },
  ])],
  ["117", "Art/Music/Literature at \"National level\"; Art/Music/Literature at State Level"],
  ["128", JSON.stringify([{
    "电源": "AC≥(220)V/(50)Hz",
    "过滤网": "Available",
    "室内机颜色": "Not specified",
    "保修": "Compressor (5) Year. Other parts: ≥ (2) Year",
  }])],
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
