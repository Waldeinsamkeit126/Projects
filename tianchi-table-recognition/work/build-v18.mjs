import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v16.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v18.xlsx";

const fixes = new Map([
  ["481", "9"],
  ["483", "征免"],
  ["491", "9"],
  ["493", "征免"],
  ["528", JSON.stringify([{
    "最低活动价": "399",
    "最高活动价": "79999",
    "备注中含退换规则": "true",
    "表格下方说明条数": "3",
  }])],
  ["896", "8999997.75"],
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

if (changed.length !== fixes.size) {
  throw new Error(`Expected ${fixes.size} fixes, applied ${changed.length}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
