import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const workspace = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2";
const inputPath = `${workspace}/outputs/table_competition_solution/submission-final-v16.xlsx`;
const outputDir = `${workspace}/outputs/table_competition_solution`;

const candidates = [
  {
    name: "customs",
    outputPath: `${outputDir}/submission-candidate-v21-customs.xlsx`,
    directFixes: new Map([
      ["481", "9"],
      ["483", "征免"],
      ["491", "9"],
      ["493", "征免"],
    ]),
    dimensionFixes: new Map(),
  },
  {
    name: "price",
    outputPath: `${outputDir}/submission-candidate-v22-price.xlsx`,
    directFixes: new Map([
      ["528", JSON.stringify([{
        "最低活动价": "399",
        "最高活动价": "79999",
        "备注中含退换规则": "true",
        "表格下方说明条数": "3",
      }])],
    ]),
    dimensionFixes: new Map(),
  },
  {
    name: "multiply",
    outputPath: `${outputDir}/submission-candidate-v23-multiply.xlsx`,
    directFixes: new Map([["896", "8999997.75"]]),
    dimensionFixes: new Map(),
  },
  {
    name: "dimensions",
    outputPath: `${outputDir}/submission-candidate-v24-dimensions.xlsx`,
    directFixes: new Map(),
    dimensionFixes: new Map([
      ["779", { row_count: 3 }],
      ["789", { row_count: 10, col_count: 12 }],
      ["819", { row_count: 18 }],
    ]),
  },
  {
    name: "revert-238",
    outputPath: `${outputDir}/submission-candidate-v25-revert-238.xlsx`,
    directFixes: new Map([
      ["238", JSON.stringify([{
        "Never serviced residential inland": "20",
        "Don’t know/refused residential total": "2",
        "Frequency once every two years residential inland": "9",
        "表格主分区数量": "2",
      }])],
    ]),
    dimensionFixes: new Map(),
  },
];

await fs.mkdir(outputDir, { recursive: true });
const baselineWorkbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const baselineRows = baselineWorkbook.worksheets.getItemAt(0).getUsedRange(true).values;
const requestedCandidate = process.argv[2];
const selectedCandidates = requestedCandidate
  ? candidates.filter((candidate) => candidate.name === requestedCandidate)
  : candidates;
if (selectedCandidates.length === 0) {
  throw new Error(`Unknown candidate: ${requestedCandidate}`);
}

for (const candidate of selectedCandidates) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
  const sheet = workbook.worksheets.getItemAt(0);
  const rows = sheet.getUsedRange(true).values;
  const changed = [];

  for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
    const id = String(rows[rowIndex][0]);
    let nextAnswer;

    if (candidate.directFixes.has(id)) {
      nextAnswer = candidate.directFixes.get(id);
    } else if (candidate.dimensionFixes.has(id)) {
      const structure = JSON.parse(String(rows[rowIndex][1]));
      Object.assign(structure, candidate.dimensionFixes.get(id));
      nextAnswer = JSON.stringify(structure);
    } else {
      continue;
    }

    sheet.getCell(rowIndex, 1).values = [[nextAnswer]];
    changed.push(id);
  }

  const expected = candidate.directFixes.size + candidate.dimensionFixes.size;
  if (changed.length !== expected) {
    throw new Error(`${candidate.name}: expected ${expected} fixes, applied ${changed.length}`);
  }

  const formulaErrors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: `${candidate.name} formula error scan`,
  });
  if (!formulaErrors.ndjson.includes("Cell search matched 0 entries.")) {
    throw new Error(`${candidate.name}: formula errors found: ${formulaErrors.ndjson}`);
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(candidate.outputPath);

  const exportedWorkbook = await SpreadsheetFile.importXlsx(await FileBlob.load(candidate.outputPath));
  const exportedRows = exportedWorkbook.worksheets.getItemAt(0).getUsedRange(true).values;
  const exportedChanged = [];
  for (let rowIndex = 1; rowIndex < baselineRows.length; rowIndex += 1) {
    if (String(exportedRows[rowIndex][1]) !== String(baselineRows[rowIndex][1])) {
      exportedChanged.push(String(baselineRows[rowIndex][0]));
    }
  }
  if (JSON.stringify(exportedChanged) !== JSON.stringify(changed)) {
    throw new Error(`${candidate.name}: unexpected exported differences ${JSON.stringify(exportedChanged)}`);
  }

  console.log(JSON.stringify({
    candidate: candidate.name,
    outputPath: path.normalize(candidate.outputPath),
    changed: exportedChanged,
  }));
}
