import fs from "node:fs/promises";
import path from "node:path";
import { normalizeAnswer, validateAnswer } from "../run.mjs";
import { sha256 } from "../reliability.mjs";
import { scanCases, scanDatasetVersion } from "./scan-cases.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const index = args.indexOf(name);
  if (index < 0) return fallback;
  const value = args[index + 1];
  if (!value || value.startsWith("--")) throw new Error(`Missing value for ${name}`);
  return value;
};
const predictionsPath = option("--predictions", null), output = option("--output", null);
const split = option("--split", predictionsPath ? null : "all");
const variant = option("--variant", predictionsPath ? null : "all");
if (predictionsPath && (!split || !variant || split === "all" || variant === "all")) {
  throw new Error("Real predictions require explicit --split development|validation and --variant clean|scan; do not pool paired/split scores.");
}
const cases = scanCases({ split, variant });
const manifestBytes = await fs.readFile(new URL("generated-scan-v1/manifest.json", import.meta.url));
const manifest = JSON.parse(manifestBytes);
const fixtureHash = sha256(await fs.readFile(new URL("scan-cases.mjs", import.meta.url)));
if (manifest.fixtureSha256 !== fixtureHash) throw new Error("Frozen scan reference has changed.");
const scorerHash = sha256(Buffer.concat(await Promise.all(["scan-evaluate.mjs", "scoring.mjs", "../run.mjs", "../reliability.mjs"].map((p) => fs.readFile(new URL(p, import.meta.url))))));
const metadata = { datasetVersion: scanDatasetVersion, manifestSha256: sha256(manifestBytes), fixtureHash, scorerHash, split, variant };
const score = (predictions) => scoreObservedDevelopment(cases, predictions, normalizeAnswer, validateAnswer);
let result;
if (!predictionsPath) {
  const positive = score(cases.map((q) => ({ id: q.id, answer: q.expected })));
  const negative = score(cases.map((q) => ({ id: q.id, answer: "INVALID-REFERENCE-CONTROL" })));
  if (positive.correct !== cases.length || negative.correct !== 0) throw new Error("Evaluator control failed.");
  result = { ...metadata, mode: "evaluator-self-check-only", cases: cases.length, positiveControl: positive.correct,
    negativeControl: negative.correct, apiCalls: 0, modelAccuracy: null, note: "评估器自检，不是模型正确率。" };
} else {
  const bytes = await fs.readFile(path.resolve(predictionsPath));
  const predictions = bytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((s) => JSON.parse(s));
  result = { ...metadata, mode: "observed-model-predictions", predictionsSha256: sha256(bytes), ...score(predictions),
    evaluatedAt: new Date().toISOString(),
    limitation: "合成配对退化图像；不是实际扫描分布或天池评测。清晰/扫描变体不是独立样本，分组按源表固定。数值格式约定在题目中明确，不改变历史题目、标签或严格评分器。" };
}
if (output) await fs.writeFile(path.resolve(output), JSON.stringify(result, null, 2), { flag: "wx" });
console.log(JSON.stringify(result, null, 2));
