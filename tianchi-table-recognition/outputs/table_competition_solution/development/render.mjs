import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { sources, developmentCases, datasetVersion } from "./fixtures.mjs";
import { sha256 } from "../reliability.mjs";

const outputDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "generated");
await fs.mkdir(outputDir, { recursive: true });
const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const media = [];
for (const source of sources) {
  const columnWidth = 230, rowHeight = 64, left = 32, top = 90;
  const width = source.col_count * columnWidth + left * 2;
  const height = source.row_count * rowHeight + top + 32;
  const cells = source.cells.map((cell) => {
    const x = left + cell.col * columnWidth, y = top + cell.row * rowHeight;
    const w = columnWidth * cell.colspan, h = rowHeight * cell.rowspan;
    return `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="white" stroke="#222" stroke-width="2"/><text x="${x + 12}" y="${y + h / 2 + 8}" font-size="22">${escape(cell.text)}</text>`;
  }).join("");
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="white"/><g fill="#111" font-family="Microsoft YaHei,Arial,sans-serif"><text x="32" y="48" font-size="26">${escape(source.title)}</text>${cells}</g></svg>`;
  const bytes = await sharp(Buffer.from(svg)).png().toBuffer();
  const fileName = `${source.id}.png`;
  await fs.writeFile(path.join(outputDir, fileName), bytes);
  media.push({ sourceId: source.id, fileName, split: source.split, sha256: sha256(bytes), width, height });
}
const cases = developmentCases();
for (const split of ["development", "holdout"]) {
  const selected = cases.filter((item) => item.split === split);
  // The inference input deliberately omits labels and category metadata.
  const questions = selected.map(({ id, file_name, question_type, question, table_hint, answer_format }) => ({ id, file_name, question_type, question, table_hint, answer_format }));
  await fs.writeFile(path.join(outputDir, `questions-${split}.json`), JSON.stringify({ datasetVersion, provenance: "synthetic-independent", split, questions }, null, 2));
}
await fs.writeFile(path.join(outputDir, "manifest.json"), JSON.stringify({ datasetVersion, source: "independently-authored-no-competition-data",
  fixtureSha256: sha256(await fs.readFile(new URL("fixtures.mjs", import.meta.url))),
  rendererSha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))),
  questionCount: cases.length, media, limitations: "Clean synthetic images only; not a representative benchmark of real scans. Labels are never included in inference input." }, null, 2));
console.log(JSON.stringify({ outputDir, sourceCount: sources.length, questionCount: cases.length, development: 18, holdout: 12, apiCalls: 0 }));
