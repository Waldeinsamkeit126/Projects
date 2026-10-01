import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizeQuestion, normalizeAnswer, validateAnswer, validateForInference } from "../run.mjs";
import { inferStructureScope, COVERAGE_VERSION } from "../structure-coverage.mjs";
import { sha256, assertUniqueQuestions, inferenceSourceHash } from "../reliability.mjs";

const args = process.argv.slice(2);
const arg = (name) => {
  const index = args.indexOf(name);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith("--")) throw new Error(`缺少参数 ${name}`);
  return path.resolve(args[index + 1]);
};
const questionBytes = await fs.readFile(arg("--questions"));
const predictionBytes = await fs.readFile(arg("--predictions"));
const questions = JSON.parse(questionBytes).questions.map(normalizeQuestion);
assertUniqueQuestions(questions);
const predictions = predictionBytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
const ids = new Set(questions.map((q) => q.id));
const byId = new Map();
for (const prediction of predictions) {
  if (!ids.has(prediction.id) || byId.has(prediction.id)) throw new Error("结果含未知或重复题号，不能审计");
  byId.set(prediction.id, prediction);
}
const details = questions.map((question) => {
  const prediction = byId.get(question.id);
  const answer = normalizeAnswer(question, prediction?.answer);
  const baseline = validateAnswer(question, answer);
  const candidate = validateForInference(question, answer, { checkFullCoverage: true });
  return { id: question.id, scope: inferStructureScope(question), recordPresent: Boolean(prediction),
    baselineValid: baseline.valid, candidateValid: candidate.valid,
    newlyFlagged: baseline.valid && !candidate.valid,
    error: candidate.error ?? "", coverage: candidate.coverage ?? null };
});
const report = { mode: "read-only-coverage-audit", generatedAt: new Date().toISOString(), coverageVersion: COVERAGE_VERSION,
  questionSha256: sha256(questionBytes), predictionsSha256: sha256(predictionBytes),
  sourceHash: await inferenceSourceHash(fileURLToPath(new URL("../", import.meta.url))),
  apiRequests: 0, predictionsModified: false, modelAccuracy: null,
  total: details.length, fullScope: details.filter((r) => r.scope === "full").length,
  newlyFlagged: details.filter((r) => r.newlyFlagged).length,
  missingRecords: details.filter((r) => !r.recordPresent).length, details,
  limitation: "只离线检查已有答案，不生成或修正答案，不重算模型成绩。已查看样例的错误定位不是独立泛化验证。" };
if (args.includes("--output")) await fs.writeFile(arg("--output"), JSON.stringify(report, null, 2), { flag: "wx" });
console.log(JSON.stringify(report, null, 2));
