import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v4.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v5.xlsx";

const fixes = new Map([
  ["358", JSON.stringify([{
    "是否横向拍摄": "true",
    "是否含金额列": "true",
    "是否含订单号字段": "false",
    "是否含明细行": "true",
  }])],
  ["438", JSON.stringify([{
    "PubTabNet VAST TEDS": "96.31",
    "PubTabNet TSRFormer S-TEDS": "97.50",
    "训练数据集类型之一": "PTN",
    "表中分组数量": "2",
  }])],
]);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const used = sheet.getUsedRange(true);
const rows = used.values;
const changed = [];

for (let index = 1; index < rows.length; index++) {
  const id = String(rows[index][0]);
  if (!fixes.has(id)) continue;
  sheet.getCell(index, 1).values = [[fixes.get(id)]];
  changed.push(id);
}

if (changed.length !== fixes.size) {
  throw new Error(`Expected ${fixes.size} fixes but applied ${changed.length}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
