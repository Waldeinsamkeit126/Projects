import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizeQuestion, normalizeAnswer, validateAnswer } from "../run.mjs";
import { sha256, assertUniqueQuestions, inferenceSourceHash } from "../reliability.mjs";
import { inspectStructureConsistency } from "../structure-consistency.mjs";

const [questionsPath, predictionsPath, output] = process.argv.slice(2);
if (!questionsPath || !predictionsPath || !output) throw new Error("Usage: node audit-consistency.mjs QUESTIONS_JSON PREDICTIONS_JSONL NEW_REPORT_JSON");
const questionBytes = await fs.readFile(path.resolve(questionsPath)), predictionBytes = await fs.readFile(path.resolve(predictionsPath));
const questions = JSON.parse(questionBytes).questions.map(normalizeQuestion);
assertUniqueQuestions(questions);
const predictions = predictionBytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((s) => JSON.parse(s));
const result = { mode: "read-only-consistency-audit", generatedAt: new Date().toISOString(),
  questionSha256: sha256(questionBytes), predictionsSha256: sha256(predictionBytes),
  auditSourceHash: await inferenceSourceHash(fileURLToPath(new URL("../", import.meta.url))),
  ...inspectStructureConsistency(questions, predictions, normalizeAnswer, validateAnswer),
  modelAccuracy: null, note: "对已有输出离线交叉检查，不修改预测、不回写缓存、不改变历史分数。不是新推理或修复结果。" };
await fs.writeFile(path.resolve(output), JSON.stringify(result, null, 2), { flag: "wx" });
console.log(JSON.stringify(result, null, 2));
