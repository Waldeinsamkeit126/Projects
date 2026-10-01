import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { sha256 } from "../reliability.mjs";
import { verifyArrayPlan } from "./array-value-trial.mjs";
import { scoreValueArrayContract } from "./array-value-contract.mjs";

// Offline only. Kept separate from inference to prevent reference-label transmission.
const [reportArg, outputArg] = process.argv.slice(2);
if (!reportArg || !outputArg) throw new Error("Usage: node array-value-evaluate.mjs REPORT_JSON NEW_SCORE_JSON");
const reportPath = path.resolve(reportArg), runDir = path.dirname(reportPath);
const reportBytes = await fs.readFile(reportPath), report = JSON.parse(reportBytes);
const plan = JSON.parse(await fs.readFile(path.join(runDir, "plan.json")));
await verifyArrayPlan(plan);
if (report.planDigest !== plan.digest || report.sourceHash !== plan.sourceHash) throw new Error("Report/plan mismatch");
const referencesBytes = await fs.readFile(new URL("array-value-references.json", import.meta.url));
if (sha256(referencesBytes) !== plan.referenceSha256) throw new Error("Frozen references changed");
const references = JSON.parse(referencesBytes).references;
const questionIds = plan.units.flatMap((u) => u.questions.map((q) => q.id));
if (JSON.stringify(questionIds) !== JSON.stringify(references.map((r) => r.id))) throw new Error("Question/reference mismatch");
const resultPath = path.join(runDir, "results.jsonl");
if (path.resolve(report.resultPath) !== resultPath) throw new Error("Results outside run directory");
let resultBytes;
try { resultBytes = await fs.readFile(resultPath); }
catch (error) { if (error.code !== "ENOENT") throw error; resultBytes = Buffer.alloc(0); }
const predictions = resultBytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
for (const row of predictions) {
  if (row.runId !== report.runId || row.provenance !== "automated-qwen-value-array-candidate"
      || !report.requests.some((r) => r.requestIndex === row.requestIndex && r.questionIds.includes(row.id))) {
    throw new Error("Prediction provenance mismatch");
  }
}
const score = scoreValueArrayContract(references, predictions);
const positive = scoreValueArrayContract(references, references.map((r) => ({ id: r.id, answer: r.expected })));
const negative = scoreValueArrayContract(references, references.map((r) => ({ id: r.id, answer: ["INVALID_REFERENCE_CONTROL"] })));
if (positive.correct !== 10 || negative.correct !== 0) throw new Error("Evaluator control failed");
const result = { mode: "offline-synthetic-array-smoke-evaluation", evaluatedAt: new Date().toISOString(),
  planDigest: plan.digest, reportSha256: sha256(reportBytes), predictionSha256: sha256(resultBytes),
  referenceSha256: sha256(referencesBytes), evaluatorSha256: sha256(await fs.readFile(fileURLToPath(import.meta.url))),
  score, controls: { positive: positive.correct, negative: negative.correct, note: "Evaluator self-check, not model accuracy" },
  apiRequestsInInference: report.apiRequests, evaluationApiRequests: 0, submitted: false, leaderboardScore: null,
  limitation: "Ten new questions about two previously seen authored synthetic tables. Not blind validation, not paired A/B, not official accuracy. This does not prove a leaderboard gain." };
await fs.writeFile(path.resolve(outputArg), JSON.stringify(result, null, 2), { flag: "wx" });
console.log(JSON.stringify({ output: path.resolve(outputArg), ...score, evaluationApiRequests: 0 }, null, 2));
