import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v9.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v10.xlsx";

const fixes = new Map([
  ["297", "najneskôr 30 dní pred uvedením zariadenia na výrobu elektriny do prevádzky"],
  ["302", "Agremiação"],
  ["303", "Notas por Extenso"],
  ["315", "91"],
  ["318", JSON.stringify([{
    "最低分": "68",
    "最低分姓名": "曾蓉",
    "计应10班分数": "82",
    "记录人数": "11",
  }])],
  ["361", "7"],
  ["368", JSON.stringify([{
    "周三第三节": "数学",
    "周四第六节": "音乐",
    "上午节数": "5",
    "下午节数": "2",
  }])],
  ["387", "0.0107"],
  ["395", "962"],
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
