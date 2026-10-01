import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v5-excel.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v6.xlsx";

const answer32 = JSON.stringify({
  row_count: 14,
  col_count: 6,
  cells: [
    { text: "类别", row: 0, col: 0, rowspan: 3, colspan: 1 },
    { text: "期末余额", row: 0, col: 1, rowspan: 1, colspan: 5 },
    { text: "账面余额", row: 1, col: 1, rowspan: 1, colspan: 2 },
    { text: "坏账准备", row: 1, col: 3, rowspan: 1, colspan: 2 },
    { text: "账面价值", row: 1, col: 5, rowspan: 2, colspan: 1 },
    { text: "单项计提坏账准备的应收账款", row: 3, col: 0, rowspan: 1, colspan: 1 },
    { text: "按组合计提坏账准备的应收账款", row: 4, col: 0, rowspan: 1, colspan: 1 },
    { text: "其中：信用风险特征组合", row: 5, col: 0, rowspan: 1, colspan: 1 },
    { text: "合计", row: 6, col: 0, rowspan: 1, colspan: 1 },
    { text: "类别", row: 7, col: 0, rowspan: 3, colspan: 1 },
    { text: "单项计提坏账准备的应收账款", row: 10, col: 0, rowspan: 1, colspan: 1 },
    { text: "按组合计提坏账准备的应收账款", row: 11, col: 0, rowspan: 1, colspan: 1 },
    { text: "其中：信用风险特征组合", row: 12, col: 0, rowspan: 1, colspan: 1 },
    { text: "合计", row: 13, col: 0, rowspan: 1, colspan: 1 },
  ],
});

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
const index = rows.findIndex((row) => String(row[0]) === "32");
if (index < 1) throw new Error("id 32 not found");
sheet.getCell(index, 1).values = [[answer32]];

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed: ["32"] }));
