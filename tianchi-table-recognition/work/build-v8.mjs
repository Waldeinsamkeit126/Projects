import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v7.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v8.xlsx";
const structure = (row_count, col_count, cells) => JSON.stringify({ row_count, col_count, cells });
const cell = (text, row, col, rowspan = 1, colspan = 1) => ({ text, row, col, rowspan, colspan });

const yearHeader = (rowCount) => structure(rowCount, 4, [
  cell("", 0, 0, 2, 1),
  cell("Year Ended December 31,", 0, 1, 1, 3),
  cell("2015", 1, 1), cell("2016", 1, 2), cell("2017", 1, 3),
]);

const fixes = new Map([
  ["749", yearHeader(27)],
  ["759", yearHeader(40)],
  ["769", structure(46, 7, [
    cell("FINANCIAL STATEMENTS", 0, 0),
    cell("2012", 0, 1), cell("2013", 0, 2), cell("2014", 0, 3),
    cell("2015", 0, 4), cell("2016", 0, 5), cell("2017", 0, 6),
  ])],
  ["779", structure(3, 3, [
    cell("SCHOOL", 0, 0), cell("BOARD", 0, 1), cell("CLASSES", 0, 2),
  ])],
  ["799", structure(11, 7, [
    cell("The Error Rate on Different Forms", 0, 0, 1, 7),
    cell("Form name", 1, 0, 2, 1), cell("A", 1, 1, 2, 1), cell("B", 1, 2, 2, 1),
    cell("Total fields\n(X = A × B)", 1, 3, 2, 1),
    cell("Fields with errors (Y)", 1, 4, 2, 1),
    cell("Error rate* (Y/X) × 100 (%)", 1, 5, 1, 2),
    cell("X/Y", 2, 5), cell("%age", 2, 6),
  ])],
  ["809", structure(17, 12, [
    cell("Chemical name", 0, 0), cell("International number", 0, 1), cell("Vendor", 0, 2),
    cell("Resistance index", 0, 3), cell("Density", 0, 4), cell("Viscosity", 0, 5),
    cell("Freezing point", 0, 6), cell("Packaging", 0, 7), cell("Pack size", 0, 8),
    cell("Unit", 0, 9), cell("Price", 0, 10), cell("Last update", 0, 11),
  ])],
  ["819", structure(18, 9, [
    cell("Chemicals by producer", 0, 0, 2, 1), cell("Status", 0, 1, 2, 1),
    cell("Planned", 0, 2), cell("Produced", 0, 3), cell("Ordered", 0, 4),
    cell("Sold, Europe", 0, 5), cell("Sold, Asia", 0, 6), cell("Sold, Americas", 0, 7), cell("Sold, Total", 0, 8),
    cell("MT", 1, 2), cell("MT", 1, 3), cell("MT", 1, 4),
    cell("M$", 1, 5), cell("M$", 1, 6), cell("M$", 1, 7), cell("M$", 1, 8),
  ])],
  ["829", structure(17, 4, [
    cell("id", 0, 0), cell("entry_id", 0, 1), cell("field_id", 0, 2), cell("slug", 0, 3),
  ])],
  ["849", structure(10, 9, [
    cell("Games by Continent", 0, 0, 1, 9),
    cell("", 1, 0, 1, 2), cell("Place", 1, 2, 1, 3), cell("Dates", 1, 5, 1, 3), cell("", 1, 8),
  ])],
  ["869", structure(8, 6, [
    cell("Row 1", 0, 0), cell("", 0, 1),
    cell("ColumnSpan=\"2\"", 0, 2, 1, 2), cell("ColumnSpan=\"2\"", 0, 4, 1, 2),
  ])],
  ["879", structure(5, 9, [
    cell("", 0, 0, 2, 1), cell("Predicted", 0, 1, 1, 8),
    cell("Count", 1, 1, 1, 2), cell("Overall Percent", 1, 3, 1, 2),
    cell("Row Percent", 1, 5, 1, 2), cell("Column Percent", 1, 7, 1, 2),
    cell("Actual", 2, 0),
    cell("Fail", 2, 1), cell("Pass", 2, 2), cell("Fail", 2, 3), cell("Pass", 2, 4),
    cell("Fail", 2, 5), cell("Pass", 2, 6), cell("Fail", 2, 7), cell("Pass", 2, 8),
  ])],
  ["889", structure(11, 13, [
    cell("FUNNEL MANAGEMENT PLAN BASED ON INDIVIDUAL CONVERSION RATES", 0, 0, 1, 13),
    cell("Account Manager", 1, 0), cell("Debajit Mukherjee", 1, 1, 1, 12),
    cell("", 2, 0),
    ...Array.from({ length: 12 }, (_, index) => cell(String(index + 1), 2, index + 1)),
    cell("", 3, 0),
    cell("ANNUAL TARGET", 3, 1),
    cell("AVG CONTRACT VALUE (CURRENT AVG VALUE)", 3, 2),
    cell("NO. OF CONTRACTS REQUIRED", 3, 3),
    cell("TOTAL MEETINGS TO BE DONE PER MONTH", 3, 4),
    cell("DISCUSSION TO PROPOSAL CONVERSION RATIO (CURRENT RATIO)", 3, 5),
    cell("# PROPOSALS TO BE GENERATED PER MONTH", 3, 6),
    cell("PIPELINE VALUE PER MONTH", 3, 7),
    cell("PROPOSAL TO ORDERBOOK (CURRENT RATIO)", 3, 8),
    cell("# CONTRACTS GENERATED PER MONTH", 3, 9),
    cell("ORDER BOOK VALUE GENERATED PER MONTH", 3, 10),
    cell("AVG TARGET PER MONTH", 3, 11),
    cell("SHORTFALL / SURPLUS", 3, 12),
  ])],
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
