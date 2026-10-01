import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const sources = [
  "D:/tests.xlsx",
  "D:/submit-template.xlsx",
];

for (const source of sources) {
  const blob = await FileBlob.load(source);
  const workbook = await SpreadsheetFile.importXlsx(blob);
  const name = path.basename(source, path.extname(source));
  const summary = await workbook.inspect({
    kind: "workbook,sheet,region",
    maxChars: 7000,
    tableMaxRows: 8,
    tableMaxCols: 12,
    tableMaxCellChars: 180,
  });
  console.log(`=== ${source} ===`);
  console.log(summary.ndjson);

  const sheets = await workbook.inspect({ kind: "sheet", include: "id,name", maxChars: 3000 });
  console.log(`--- sheets ---`);
  console.log(sheets.ndjson);

  const sheetNames = [...sheets.ndjson.matchAll(/"name":"([^"]+)"/g)].map((match) => match[1]);
  for (const sheetName of [...new Set(sheetNames)]) {
    const preview = await workbook.render({
      sheetName,
      range: "A1:G20",
      scale: 1.5,
      format: "png",
    });
    const safeSheetName = sheetName.replace(/[\\/:*?"<>|]/g, "_");
    await fs.writeFile(`${name}-${safeSheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
  }
}
