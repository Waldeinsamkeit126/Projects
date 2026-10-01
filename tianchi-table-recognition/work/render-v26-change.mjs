import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workbookPath = process.argv[2];
const previewPath = process.argv[3];
const targetRange = process.argv[4];
if (!workbookPath || !previewPath || !targetRange) {
  throw new Error("Usage: render-v26-change.mjs <workbook> <preview> <range>");
}
const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(workbookPath));
const sheet = workbook.worksheets.getItemAt(0);
const preview = await workbook.render({
  sheetName: sheet.name,
  range: targetRange,
  scale: 1.5,
  format: "png",
});
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
console.log(previewPath);
