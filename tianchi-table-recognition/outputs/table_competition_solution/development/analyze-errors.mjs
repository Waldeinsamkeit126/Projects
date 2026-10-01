import fs from "node:fs/promises";
import path from "node:path";
import { developmentCases } from "./fixtures.mjs";
import { normalizeAnswer, validateAnswer } from "../run.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";
import { numericEquivalent, structureDifferences } from "./diagnostics.mjs";
import { sha256 } from "../reliability.mjs";

const [predictionArgument, outputArgument, split = "holdout"] = process.argv.slice(2);
if (!predictionArgument || !outputArgument || !["development", "holdout"].includes(split)) throw new Error("Usage: node analyze-errors.mjs PREDICTIONS OUTPUT [development|holdout]");
const input = await fs.readFile(path.resolve(predictionArgument));
const predictions = input.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
const cases = developmentCases().filter((item) => item.split === split);
const byId = new Map(predictions.map((item) => [item.id, item]));
const caseById = new Map(cases.map((item) => [item.id, item]));
const score = scoreObservedDevelopment(cases, predictions, normalizeAnswer, validateAnswer);
const errors = score.details.filter((item) => !item.correct).map((item) => {
  const question = caseById.get(item.id);
  const expected = normalizeAnswer(question, question.expected);
  const actual = normalizeAnswer(question, byId.get(item.id)?.answer);
  const representationOnly = item.valid && question.answer_format === "number" && numericEquivalent(expected, actual);
  return { id: item.id, category: item.category, outcome: item.outcome,
    diagnosis: representationOnly ? "numeric-representation-difference" : item.valid ? "content-or-structure-mismatch" : "missing-or-invalid-answer",
    ...(question.answer_format === "number" ? { expected, actual, representationOnly } : {}),
    ...(item.valid && question.question_type === "structure" && question.answer_format === "json"
      ? { structureDiff: structureDifferences(JSON.parse(expected), JSON.parse(actual)) } : {}),
    upstreamError: item.upstreamError };
});
const equivalentCount = errors.filter((item) => item.representationOnly).length;
const report = { split, predictionsSha256: sha256(input), evaluatedAt: new Date().toISOString(),
  strictCorrect: score.correct, total: score.total, numericEquivalentDifferences: equivalentCount,
  strictPlusNumericEquivalent: score.correct + equivalentCount,
  limitation: "这是附加诊断，不替换严格匹配成绩，不修改预测或标签，不声称官方评测接受等价数值格式。当前留出集在误差分析后不再是未查看的验证集。",
  errors };
await fs.mkdir(path.dirname(path.resolve(outputArgument)), { recursive: true });
await fs.writeFile(path.resolve(outputArgument), JSON.stringify(report, null, 2), { flag: "wx" });
console.log(JSON.stringify(report, null, 2));
