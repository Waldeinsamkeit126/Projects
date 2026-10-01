import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v16.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v17.xlsx";

const directFixes = new Map([
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
  ["799", JSON.stringify({
    row_count: 11,
    col_count: 7,
    cells: [
      { text: "The Error Rate on Different Forms", row: 0, col: 0, rowspan: 1, colspan: 7 },
      { text: "Form name", row: 1, col: 0, rowspan: 2, colspan: 1 },
      { text: "A", row: 1, col: 1, rowspan: 2, colspan: 1 },
      { text: "B", row: 1, col: 2, rowspan: 2, colspan: 1 },
      { text: "Total fields\n(X = A × B)", row: 1, col: 3, rowspan: 2, colspan: 1 },
      { text: "Fields with errors (Y)", row: 1, col: 4, rowspan: 2, colspan: 1 },
      { text: "Error rate* (Y/X) × 100 (%)", row: 1, col: 5, rowspan: 1, colspan: 2 },
      { text: "X/Y", row: 2, col: 5, rowspan: 1, colspan: 1 },
      { text: "%age", row: 2, col: 6, rowspan: 1, colspan: 1 },
    ],
  })],
  ["849", JSON.stringify({
    row_count: 10,
    col_count: 9,
    cells: [
      { text: "Games by Continent", row: 0, col: 0, rowspan: 1, colspan: 9 },
      { text: "", row: 1, col: 0, rowspan: 1, colspan: 2 },
      { text: "Place", row: 1, col: 2, rowspan: 1, colspan: 3 },
      { text: "Dates", row: 1, col: 5, rowspan: 1, colspan: 3 },
      { text: "", row: 1, col: 8, rowspan: 1, colspan: 1 },
    ],
  })],
  ["879", JSON.stringify({
    row_count: 5,
    col_count: 9,
    cells: [
      { text: "", row: 0, col: 0, rowspan: 2, colspan: 1 },
      { text: "Predicted", row: 0, col: 1, rowspan: 1, colspan: 8 },
      { text: "Count", row: 1, col: 1, rowspan: 1, colspan: 2 },
      { text: "Overall Percent", row: 1, col: 3, rowspan: 1, colspan: 2 },
      { text: "Row Percent", row: 1, col: 5, rowspan: 1, colspan: 2 },
      { text: "Column Percent", row: 1, col: 7, rowspan: 1, colspan: 2 },
      { text: "Actual", row: 2, col: 0, rowspan: 1, colspan: 1 },
      { text: "Fail", row: 2, col: 1, rowspan: 1, colspan: 1 },
      { text: "Pass", row: 2, col: 2, rowspan: 1, colspan: 1 },
      { text: "Fail", row: 2, col: 3, rowspan: 1, colspan: 1 },
      { text: "Pass", row: 2, col: 4, rowspan: 1, colspan: 1 },
      { text: "Fail", row: 2, col: 5, rowspan: 1, colspan: 1 },
      { text: "Pass", row: 2, col: 6, rowspan: 1, colspan: 1 },
      { text: "Fail", row: 2, col: 7, rowspan: 1, colspan: 1 },
      { text: "Pass", row: 2, col: 8, rowspan: 1, colspan: 1 },
    ],
  })],
  ["899", JSON.stringify({
    row_count: 5,
    col_count: 3,
    cells: [
      { text: "XXX", row: 0, col: 0, rowspan: 2, colspan: 1 },
      { text: "Summary", row: 0, col: 1, rowspan: 1, colspan: 2 },
      { text: "Description", row: 1, col: 1, rowspan: 1, colspan: 1 },
      { text: "Variable Names(units)", row: 1, col: 2, rowspan: 1, colspan: 1 },
      { text: "Note: The following records relate to first pass", row: 2, col: 0, rowspan: 1, colspan: 3 },
    ],
  })],
  ["896", "8999997.75"],
]);

const dimensionFixes = new Map([
  ["779", { row_count: 3 }],
  ["789", { row_count: 10, col_count: 12 }],
  ["819", { row_count: 18 }],
]);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
const changed = [];

for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
  const id = String(rows[rowIndex][0]);
  let nextAnswer;
  if (directFixes.has(id)) {
    nextAnswer = directFixes.get(id);
  } else if (dimensionFixes.has(id)) {
    const structure = JSON.parse(String(rows[rowIndex][1]));
    Object.assign(structure, dimensionFixes.get(id));
    nextAnswer = JSON.stringify(structure);
  } else {
    continue;
  }
  sheet.getCell(rowIndex, 1).values = [[nextAnswer]];
  changed.push(id);
}

const expected = directFixes.size + dimensionFixes.size;
if (changed.length !== expected) {
  throw new Error(`Expected ${expected} fixes, applied ${changed.length}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
