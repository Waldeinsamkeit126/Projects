import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v18.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v19.xlsx";

const fixes = new Map([
  ["241", "7"],
  ["251", "8"],
  ["391", "6"],
  ["401", "8"],
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
