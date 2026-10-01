import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v18.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v20.xlsx";

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
let changed = false;

for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
  if (String(rows[rowIndex][0]) !== "251") continue;
  sheet.getCell(rowIndex, 1).values = [["8"]];
  changed = true;
  break;
}

if (!changed) throw new Error("ID 251 was not found");

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed: ["251"] }));
