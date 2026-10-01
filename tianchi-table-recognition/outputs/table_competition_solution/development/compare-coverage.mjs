import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { normalizeAnswer, validateAnswer } from "../run.mjs";
import { sha256 } from "../reliability.mjs";
import { coverageCases, coverageDatasetVersion } from "./coverage-cases.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";

const [controlArgument, candidateArgument, outputArgument] = process.argv.slice(2);
if (!controlArgument || !candidateArgument || !outputArgument) throw new Error("Usage: node compare-coverage.mjs CONTROL_RUN_DIR CANDIDATE_RUN_DIR NEW_OUTPUT_JSON");
const cases = coverageCases();
async function loadRun(dir) {
  const report = JSON.parse(await fs.readFile(path.join(dir, "run-report.json"), "utf8"));
  const bytes = await fs.readFile(path.join(dir, "results.jsonl"));
  const predictions = bytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
  const score = scoreObservedDevelopment(cases, predictions, normalizeAnswer, validateAnswer);
  assert.equal(report.noExport, true);
  assert.equal(report.outputPath, null);
  assert.equal(report.questionCount, cases.length);
  return { report, predictions, score, predictionsSha256: sha256(bytes) };
}
const control = await loadRun(path.resolve(controlArgument)), candidate = await loadRun(path.resolve(candidateArgument));
assert.equal(control.report.checkFullCoverage, false);
assert.equal(candidate.report.checkFullCoverage, true);
for (const key of ["sourceHash", "inputSha256", "endpoint", "models", "maxCompletionTokens", "maxAttempts", "enableThinking", "refreshStructure", "checkStructureConsistency"]) {
  assert.deepEqual(control.report[key], candidate.report[key], `组间条件不一致: ${key}`);
}
const candidateById = new Map(candidate.score.details.map((row) => [row.id, row]));
const pairs = control.score.details.map((row) => ({ id: row.id, category: row.category,
  controlCorrect: row.correct, candidateCorrect: candidateById.get(row.id).correct,
  controlOutcome: row.outcome, candidateOutcome: candidateById.get(row.id).outcome }));
const retries = candidate.predictions.filter((row) => row.validationHistory?.some((v) => v.coverage && !v.coverage.complete)).map((row) => {
  const q = cases.find((item) => item.id === row.id);
  const initial = row.validationHistory[0];
  const initialScore = scoreObservedDevelopment([q], [{ id: q.id, answer: initial.answer }], normalizeAnswer, validateAnswer);
  const finalCorrect = candidateById.get(q.id).correct;
  return { id: q.id, stages: row.validationHistory.map((v) => v.stage),
    initialCorrect: initialScore.correct === 1, finalCorrect,
    initialMissingSlots: initial.coverage?.missingSlots ?? null, finalValid: row.valid,
    error: row.error ?? "" };
});
const brief = ({ report, score, predictionsSha256 }) => ({ runId: report.runId, status: report.status,
  predictionsSha256, correct: score.correct, total: score.total, missing: score.missing,
  formatValid: score.formatValid, categories: score.categories, requests: report.requests });
const comparison = { generatedAt: new Date().toISOString(), datasetVersion: coverageDatasetVersion,
  fixtureSha256: sha256(await fs.readFile(new URL("coverage-cases.mjs", import.meta.url))),
  sourceHash: control.report.sourceHash, inputSha256: control.report.inputSha256,
  control: brief(control), candidate: brief(candidate),
  totalAttempts: control.report.requests.attempts + candidate.report.requests.attempts,
  reportedTotalTokens: control.report.requests.reportedTotalTokens + candidate.report.requests.reportedTotalTokens,
  improved: pairs.filter((row) => !row.controlCorrect && row.candidateCorrect).length,
  regressed: pairs.filter((row) => row.controlCorrect && !row.candidateCorrect).length,
  coverageTriggeredRechecks: retries, pairs,
  costCny: null, leaderboardScore: null,
  limitation: "独立合成小表上的单次对比；初次生成存在波动。结果不是官方评测，不能归因所有差异、推断真实扫描泛化或换算天池成绩。" };
assert.ok(comparison.totalAttempts <= 12, "实际请求超出预设 12 次总上限");
await fs.writeFile(path.resolve(outputArgument), JSON.stringify(comparison, null, 2), { flag: "wx" });
console.log(JSON.stringify(comparison, null, 2));
