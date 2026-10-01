import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizeQuestion, normalizeAnswer, validateAnswer } from "../run.mjs";
import { sha256 } from "../reliability.mjs";
import { verifyReviewPlan } from "./structure-review.mjs";
import { scanCases, scanDatasetVersion } from "./scan-cases.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";
import { structureDifferences } from "./diagnostics.mjs";

// Offline evaluator only. Reference labels are never imported by the inference runner.
const [reportArg, outputArg] = process.argv.slice(2);
if (!reportArg || !outputArg) throw new Error("Usage: node evaluate-structure-review.mjs REVIEW_REPORT NEW_SCORE_JSON");
const reportPath = path.resolve(reportArg), reportBytes = await fs.readFile(reportPath), report = JSON.parse(reportBytes);
const plan = JSON.parse(await fs.readFile(path.join(path.dirname(reportPath), "plan.json")));
await verifyReviewPlan(plan);
if (report.planDigest !== plan.digest || report.sourceHash !== plan.sourceHash) throw new Error("Review report/plan identity mismatch");
const manifestBytes = await fs.readFile(new URL("generated-scan-v1/manifest.json", import.meta.url));
const manifest = JSON.parse(manifestBytes), fixtureHash = sha256(await fs.readFile(new URL("scan-cases.mjs", import.meta.url)));
if (manifest.fixtureSha256 !== fixtureHash) throw new Error("Frozen reference changed");
const references = new Map(scanCases({ split: "development", variant: "clean" }).map((q) => [q.id, q]));
const selectedQuestions = plan.units.flatMap((u) => u.questions), ids = new Set(selectedQuestions.map((q) => q.id));
if (ids.size !== selectedQuestions.length) throw new Error("Duplicate selected question IDs");
const cases = selectedQuestions.map((q) => {
  const reference = references.get(q.id);
  if (!reference || JSON.stringify(normalizeQuestion(reference)) !== JSON.stringify(normalizeQuestion(q))) throw new Error("Selected question differs from frozen reference question");
  return reference;
});
const baselineBytes = await fs.readFile(plan.inputs.predictionsPath);
if (sha256(baselineBytes) !== plan.inputHashes.predictions) throw new Error("Baseline changed");
const candidatePath = path.join(path.dirname(reportPath), "review-candidates.jsonl");
if (path.resolve(report.resultPath) !== candidatePath) throw new Error("Candidate path mismatch");
const candidateBytes = await fs.readFile(candidatePath);
const parseLines = (bytes) => bytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((s) => JSON.parse(s));
const baseline = parseLines(baselineBytes).filter((r) => ids.has(r.id)), candidates = parseLines(candidateBytes);
for (const r of candidates) {
  if (r.reviewRunId !== report.runId || r.baselinePredictionsSha256 !== plan.inputHashes.predictions
    || r.provenance !== "automated-qwen-review-candidate") throw new Error("Candidate provenance mismatch");
}
const score = (qs, rows) => scoreObservedDevelopment(qs, rows, normalizeAnswer, validateAnswer);
const positive = score(cases, cases.map((q) => ({ id: q.id, answer: q.expected })));
const negative = score(cases, cases.map((q) => ({ id: q.id, answer: "INVALID-CONTROL" })));
if (positive.correct !== cases.length || negative.correct !== 0) throw new Error("Evaluator control failed");
const before = score(cases, baseline), after = score(cases, candidates);
const byOld = new Map(baseline.map((r) => [r.id, r])), byNew = new Map(candidates.map((r) => [r.id, r]));
const beforeDetails = new Map(before.details.map((r) => [r.id, r]));
const transitions = after.details.map((detail) => {
  const q = references.get(detail.id), old = byOld.get(q.id), current = byNew.get(q.id);
  const oldCorrect = beforeDetails.get(q.id).correct;
  const diagnostic = (record) => {
    const answer = normalizeAnswer(q, record?.answer);
    return validateAnswer(q, answer).valid ? structureDifferences(JSON.parse(normalizeAnswer(q, q.expected)), JSON.parse(answer)) : null;
  };
  return { id: q.id, beforeCorrect: oldCorrect, afterCorrect: detail.correct, outcome: detail.outcome,
    transition: !current ? "not-returned" : detail.outcome === "empty-answer" ? "empty-answer" : oldCorrect ? detail.correct ? "stayed-correct" : "regressed" : detail.correct ? "corrected" : "still-not-matched",
    priorModel: old?.model ?? null, reviewModel: current?.model ?? null, candidatePassedChecks: current?.candidatePassedChecks ?? null,
    beforeDifferences: diagnostic(old), afterDifferences: diagnostic(current) };
});
const attemptedIds = new Set(report.outcomes.flatMap((o) => plan.units.find((u) => u.fileName === o.fileName)?.questions.map((q) => q.id) ?? []));
const result = { mode: "offline-targeted-review-evaluation", evaluatedAt: new Date().toISOString(), datasetVersion: scanDatasetVersion,
  split: "development", variant: "clean", planDigest: plan.digest, sourceHash: plan.sourceHash, reportSha256: sha256(reportBytes),
  baselinePredictionsSha256: sha256(baselineBytes), candidatePredictionsSha256: sha256(candidateBytes), fixtureHash,
  manifestSha256: sha256(manifestBytes), evaluatorSha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))),
  plannedQuestions: cases.length, attemptedQuestions: attemptedIds.size, unattemptedQuestions: cases.filter((q) => !attemptedIds.has(q.id)).map((q) => q.id),
  before, after, transitions,
  corrected: transitions.filter((t) => t.transition === "corrected").length,
  regressed: transitions.filter((t) => t.transition === "regressed").length,
  evaluatorControls: { positive: positive.correct, negative: negative.correct, note: "评分器自检，不是模型成绩" },
  reviewRun: { runId: report.runId, status: report.status, stopReason: report.stopReason, requests: report.requests },
  evaluationApiRequests: 0, baselineModified: false, leaderboardScore: null,
  limitation: "已分析的合成开发集上的定向复核，不是独立盲测或同预算 A/B；旧最终答案的模型可能不同，不能将差异归因于单一提示策略。缺答计入固定计划分母，但未调用题不属于识别错误。" };
await fs.writeFile(path.resolve(outputArg), JSON.stringify(result, null, 2), { flag: "wx" });
console.log(JSON.stringify({ output: path.resolve(outputArg), planned: cases.length, beforeCorrect: before.correct,
  afterCorrect: after.correct, answered: after.answered, missing: after.missing, corrected: result.corrected,
  regressed: result.regressed, unattemptedQuestions: result.unattemptedQuestions,
  transitions: transitions.map(({ beforeDifferences, afterDifferences, ...t }) => t), evaluationApiRequests: 0 }, null, 2));
