import fs from "node:fs/promises";
import path from "node:path";
import { scanCases } from "./scan-cases.mjs";
import { normalizeAnswer, validateAnswer, validateForInference } from "../run.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";
import { numericEquivalent, structureDifferences } from "./diagnostics.mjs";
import { sha256 } from "../reliability.mjs";

const [runDir, variant, output] = process.argv.slice(2);
if (!runDir || !["clean", "scan"].includes(variant) || !output) throw new Error("Usage: node scan-diagnose.mjs DEVELOPMENT_RUN_DIR clean|scan NEW_JSON");
const bytes = await fs.readFile(path.join(runDir, "results.jsonl"));
const report = JSON.parse(await fs.readFile(path.join(runDir, "run-report.json")));
const cases = scanCases({ split: "development", variant });
const predictions = bytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((s) => JSON.parse(s));
const scores = scoreObservedDevelopment(cases, predictions, normalizeAnswer, validateAnswer);
const predicted = new Map(predictions.map((r) => [r.id, r]));
const mismatches = scores.details.filter((d) => d.outcome === "mismatch").map((d) => {
  const q = cases.find((q) => q.id === d.id), p = predicted.get(d.id);
  const answer = normalizeAnswer(q, p.answer), expected = normalizeAnswer(q, q.expected);
  const base = { id: q.id, category: q.category, model: p.model, question: q.question, strictCorrect: false };
  if (q.question_type === "structure") {
    const differences = structureDifferences(q.expected, JSON.parse(answer));
    return { ...base, ...differences, cellDifferenceCount: differences.cells.length,
      coverageDiagnostic: validateForInference(q, answer, { checkFullCoverage: true }) };
  }
  return { ...base, expected, actual: answer, numericEquivalent: q.answer_format === "number" ? numericEquivalent(expected, answer) : null };
});
const result = { mode: "read-only-diagnostics-not-rescoring", generatedAt: new Date().toISOString(),
  runId: report.runId, predictionsSha256: sha256(bytes), apiRequests: 0, predictionsModified: false,
  strictCorrect: scores.correct, total: scores.total, answered: scores.answered, missing: scores.missing,
  formatValid: scores.formatValid, mismatches,
  missingItems: scores.details.filter((d) => ["missing-record", "empty-answer"].includes(d.outcome)),
  limitation: "仅比较本次已返回答案与自建开发标签，不更改原答案或严格分数；未保留的初答/重试内容不能从最终答案倒推。" };
await fs.writeFile(path.resolve(output), JSON.stringify(result, null, 2), { flag: "wx" });
console.log(JSON.stringify(result, null, 2));
