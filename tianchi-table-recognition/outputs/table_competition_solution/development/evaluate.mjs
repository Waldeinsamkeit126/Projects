import fs from "node:fs/promises";
import path from "node:path";
import { normalizeAnswer, validateAnswer } from "../run.mjs";
import { sha256 } from "../reliability.mjs";
import { scoreObservedDevelopment as scoreDevelopment } from "./scoring.mjs";
import { datasetVersion as baselineVersion, developmentCases } from "./fixtures.mjs";
import { coverageDatasetVersion, coverageCases } from "./coverage-cases.mjs";

const args = process.argv.slice(2);
const value = (name) => args[args.indexOf(name) + 1];
const predictionsPath = args.includes("--predictions") ? path.resolve(value("--predictions")) : null;
const outputPath = args.includes("--output") ? path.resolve(value("--output")) : null;
const dataset = args.includes("--dataset") ? value("--dataset") : "baseline";
if (!["baseline", "coverage"].includes(dataset)) throw new Error("dataset 必须为 baseline 或 coverage");
const datasetVersion = dataset === "coverage" ? coverageDatasetVersion : baselineVersion;
const split = args.includes("--split") ? value("--split") : dataset === "coverage" ? "validation" : "development";
if (!(dataset === "coverage" ? ["validation", "all"] : ["development", "holdout", "all"]).includes(split)) throw new Error("split 与所选数据集不匹配");
const cases = (dataset === "coverage" ? coverageCases() : developmentCases()).filter((item) => split === "all" || item.split === split);
const fixtureHash = sha256(await fs.readFile(new URL(dataset === "coverage" ? "coverage-cases.mjs" : "fixtures.mjs", import.meta.url)));
const scorerHash = sha256(Buffer.concat(await Promise.all([
  fs.readFile(new URL("scoring.mjs", import.meta.url)), fs.readFile(new URL("../reliability.mjs", import.meta.url)),
  fs.readFile(new URL("../run.mjs", import.meta.url)), fs.readFile(new URL("evaluate.mjs", import.meta.url)),
])));

if (!predictionsPath) {
  // A reference self-check tests the evaluator only. It is NOT a model score.
  const reference = cases.map((item) => ({ id: item.id, answer: item.expected }));
  const report = scoreDevelopment(cases, reference, normalizeAnswer, validateAnswer);
  const negative = scoreDevelopment(cases, reference.map((item) => ({ ...item, answer: "not-an-answer" })), normalizeAnswer, validateAnswer);
  if (report.correct !== cases.length || negative.correct !== 0) throw new Error("评估器正/负对照失败");
  console.log(JSON.stringify({ mode: "evaluator-self-check-only", datasetVersion, fixtureHash, scorerHash,
    cases: cases.length, positiveControl: report.correct, negativeControl: negative.correct,
    modelAccuracy: null, note: "尚未调用模型；正对照满分不代表识别效果" }, null, 2));
} else {
  const bytes = await fs.readFile(predictionsPath);
  const predictions = bytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  const report = { datasetVersion, fixtureHash, scorerHash, split, predictionsSha256: sha256(bytes),
    evaluatedAt: new Date().toISOString(), ...scoreDevelopment(cases, predictions, normalizeAnswer, validateAnswer),
    limitation: dataset === "coverage"
      ? "新增独立合成源表，供候选策略对比；本地精确匹配，不能换算天池成绩。这个小型验证集不是未见真实扫描件上的泛化证明。"
      : "合成表格，本地精确匹配；不能换算天池成绩。按源表划分开发与留出集，不混用同一表的题目。" };
  if (outputPath) {
    await fs.mkdir(path.dirname(outputPath), { recursive: true });
    await fs.writeFile(outputPath, JSON.stringify(report, null, 2), { flag: "wx" });
  }
  console.log(JSON.stringify(report, null, 2));
}
