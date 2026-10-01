import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { scanSources, scanCases, publicScanQuestions, scanDatasetVersion, variants } from "./scan-cases.mjs";
import { sha256 } from "../reliability.mjs";

export const scanProfiles = {
  tilted: { scale: 0.82, blur: 0.35, contrast: 0.78, brightness: 45, angle: 1.2, jpeg: 65, noise: 3 },
  faint: { scale: 0.78, blur: 0.4, contrast: 0.60, brightness: 88, angle: -0.8, jpeg: 55, noise: 4 },
  small: { scale: 0.70, blur: 0.35, contrast: 0.73, brightness: 62, angle: 0.6, jpeg: 50, noise: 3 },
};
const escape = (text) => String(text).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
export function makeScanSvg(source) {
  const cw = 108, rh = 34, margin = 32, gap = 36, top = 72, font = 16;
  const width = margin * 2 + source.tables.reduce((sum, t) => sum + t.col_count * cw, 0) + gap * (source.tables.length - 1);
  const height = top + Math.max(...source.tables.map((t) => t.row_count)) * rh + 66;
  let left = margin, body = "";
  for (const table of source.tables) {
    body += `<text x="${left}" y="43" font-size="19">${escape(table.title)}</text>`;
    for (const cell of table.cells) {
      const x = left + cell.col * cw, y = top + cell.row * rh, w = cell.colspan * cw, h = cell.rowspan * rh;
      const estimate = [...cell.text].reduce((sum, ch) => sum + (ch.charCodeAt(0) > 255 ? 1 : 0.65), 0) * font;
      if (estimate > w - 12) throw new Error(`Text exceeds cell width: ${source.id} ${cell.row}:${cell.col}`);
      body += `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#fff" stroke="#444" stroke-width="1"/><text x="${x + 7}" y="${y + h / 2 + 5.5}" font-size="${font}">${escape(cell.text)}</text>`;
    }
    left += table.col_count * cw + gap;
  }
  body += `<text x="${margin}" y="${height - 24}" font-size="14">说明：空白表示未登记，0 表示已登记的零；各表独立记录。</text>`;
  return { width, height, svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="white"/><g fill="#292929" font-family="Microsoft YaHei,Arial,sans-serif">${body}</g></svg>` };
}
export function seededNoise(bytes, seed, amplitude) {
  const result = Buffer.from(bytes);
  let state = seed >>> 0;
  for (let i = 0; i < result.length; i++) {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    const offset = Math.floor((state / 2 ** 32) * (2 * amplitude + 1)) - amplitude;
    result[i] = Math.min(255, Math.max(0, result[i] + offset));
  }
  return result;
}
export async function renderScanSource(source) {
  const drawing = makeScanSvg(source), profile = scanProfiles[source.profile];
  const clean = await sharp(Buffer.from(drawing.svg)).png().toBuffer();
  const { data, info } = await sharp(clean).resize({ width: Math.round(drawing.width * profile.scale) }).flatten({ background: "white" })
    .greyscale().blur(profile.blur).linear(profile.contrast, profile.brightness).raw().toBuffer({ resolveWithObject: true });
  const noisy = seededNoise(data, source.seed, profile.noise);
  // Deterministic measurement fixtures, not generated artwork; geometry/labels are unchanged.
  const jpeg = await sharp(noisy, { raw: info }).rotate(profile.angle, { background: "#f2f2f2" }).jpeg({ quality: profile.jpeg }).toBuffer();
  const scan = await sharp(jpeg).png().toBuffer();
  return { clean, scan };
}

export async function renderScanDataset() {
  const outputDir = fileURLToPath(new URL("generated-scan-v1/", import.meta.url));
  // A frozen dataset must never be overwritten, even by accidentally running this script twice.
  await fs.mkdir(outputDir);
  const media = [];
  for (const source of scanSources) {
    const rendered = await renderScanSource(source);
    for (const variant of variants) {
      const bytes = rendered[variant], name = `${source.id}-${variant}.png`, meta = await sharp(bytes).metadata();
      await fs.writeFile(path.join(outputDir, name), bytes, { flag: "wx" });
      media.push({ sourceId: source.id, split: source.split, variant, fileName: name, sha256: sha256(bytes), width: meta.width, height: meta.height,
        profile: variant === "scan" ? scanProfiles[source.profile] : null, seed: variant === "scan" ? source.seed : null });
    }
  }
  const questionFiles = [];
  for (const split of ["development", "validation"]) for (const variant of variants) {
    const name = `questions-${split}-${variant}.json`, questions = publicScanQuestions(scanCases({ split, variant }));
    const bytes = Buffer.from(JSON.stringify({ datasetVersion: scanDatasetVersion, provenance: "newly-authored-synthetic-paired", split, variant, questions }, null, 2));
    await fs.writeFile(path.join(outputDir, name), bytes, { flag: "wx" });
    questionFiles.push({ name, split, variant, count: questions.length, sha256: sha256(bytes) });
  }
  const manifest = { datasetVersion: scanDatasetVersion, createdAt: new Date().toISOString(), sourceCount: scanSources.length,
    tableCount: scanSources.reduce((n, s) => n + s.tables.length, 0), questionCount: scanCases().length,
    media, questionFiles, fixtureSha256: sha256(await fs.readFile(new URL("scan-cases.mjs", import.meta.url))),
    rendererSha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))), sharpVersions: sharp.versions,
    apiCalls: 0, modelAccuracy: null, visualQa: "pending-manual-review-see-separate-record",
    note: "合成扫描退化，不是真实扫描数据；同源清晰/扫描版本同组，禁止跨组调参或将参考文件发送给模型。不同平台字体可能不同，以这些媒体哈希为准。" };
  await fs.writeFile(path.join(outputDir, "manifest.json"), JSON.stringify(manifest, null, 2), { flag: "wx" });
  return { outputDir, sourceCount: manifest.sourceCount, imageCount: media.length, questionCount: manifest.questionCount, apiCalls: 0, modelAccuracy: null };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(JSON.stringify(await renderScanDataset(), null, 2));
}
