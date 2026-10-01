import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const previousPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v3.xlsx";
const currentPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-full-dimensions-v2.xlsx";

async function answerMap(path) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(path));
  const rows = workbook.worksheets.getItemAt(0).getUsedRange(true).values;
  return new Map(rows.slice(1).map((row) => [String(row[0]), String(row[1] ?? "")]));
}

const previous = await answerMap(previousPath);
const current = await answerMap(currentPath);
const changes = [];

for (const [id, answer] of current) {
  if (!answer.startsWith("{")) continue;
  try {
    const now = JSON.parse(answer);
    const old = JSON.parse(previous.get(id) ?? "{}");
    if (!("row_count" in now) || !("col_count" in now)) continue;
    if (now.row_count !== old.row_count || now.col_count !== old.col_count) {
      changes.push({
        id,
        old: `${old.row_count}x${old.col_count}`,
        current: `${now.row_count}x${now.col_count}`,
        cells: now.cells?.length ?? 0,
      });
    }
  } catch {}
}

console.log(JSON.stringify({ changedStructures: changes.length, examples: changes.slice(0, 20) }, null, 2));
