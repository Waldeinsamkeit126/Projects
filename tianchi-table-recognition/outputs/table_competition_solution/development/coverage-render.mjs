import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { coverageSources, coverageCases, coverageDatasetVersion } from "./coverage-cases.mjs";
import { sha256 } from "../reliability.mjs";

const outputDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "generated-coverage-v1");
await fs.mkdir(outputDir, { recursive: true });
const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const media = [];
for (const source of coverageSources) {
  const cw = 170, rh = 56, top = 78, gap = 36, margin = 24;
  const width = source.tables.reduce((sum, table) => sum + table.col_count * cw, margin * 2) + (source.tables.length - 1) * gap;
  const height = top + Math.max(...source.tables.map((table) => table.row_count)) * rh + margin;
  let left = margin;
  let body = "";
  for (const table of source.tables) {
    body += `<text x="${left}" y="42" font-size="23">${escape(table.title)}</text>`;
    for (const cell of table.cells) {
      const x = left + cell.col * cw, y = top + cell.row * rh;
      body += `<rect x="${x}" y="${y}" width="${cell.colspan * cw}" height="${cell.rowspan * rh}" fill="white" stroke="#222" stroke-width="2"/><text x="${x + 10}" y="${y + cell.rowspan * rh / 2 + 7}" font-size="21">${escape(cell.text)}</text>`;
    }
    left += table.col_count * cw + gap;
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="white"/><g fill="#111" font-family="Microsoft YaHei,Arial,sans-serif">${body}</g></svg>`;
  const bytes = await sharp(Buffer.from(svg)).png().toBuffer();
  const fileName = `${source.id}.png`;
  await fs.writeFile(path.join(outputDir, fileName), bytes);
  media.push({ sourceId: source.id, fileName, sha256: sha256(bytes), width, height });
}
const questions = coverageCases().map(({ expected, category, split, sourceId, ...question }) => question);
await fs.writeFile(path.join(outputDir, "questions-validation.json"), JSON.stringify({ datasetVersion: coverageDatasetVersion,
  provenance: "synthetic-independent", split: "validation", questions }, null, 2));
await fs.writeFile(path.join(outputDir, "manifest.json"), JSON.stringify({ datasetVersion: coverageDatasetVersion,
  source: "newly-authored-generic-coverage-validation", questionCount: questions.length, media,
  fixtureSha256: sha256(await fs.readFile(new URL("coverage-cases.mjs", import.meta.url))),
  rendererSha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))),
  note: "新源表，非正式测试数据；用于候选策略对比，还未运行真实模型，不能宣称验证了泛化。" }, null, 2));
console.log(JSON.stringify({ outputDir, sourceCount: media.length, questionCount: questions.length, apiCalls: 0 }));
