import { scoreDevelopment } from "../reliability.mjs";

// Evaluation-only changes must not alter the inference code/cache fingerprint.
export function scoreObservedDevelopment(cases, predictions, normalize, validate) {
  const base = scoreDevelopment(cases, predictions, normalize, validate);
  const byId = new Map(predictions.map((row) => [row.id, row]));
  const caseById = new Map(cases.map((row) => [row.id, row]));
  const details = base.details.map((detail) => {
    const prediction = byId.get(detail.id);
    const answer = normalize(caseById.get(detail.id), prediction?.answer);
    const outcome = !prediction ? "missing-record" : !answer.trim() ? "empty-answer"
      : !detail.valid ? "invalid-format" : detail.correct ? "matched" : "mismatch";
    return { ...detail, outcome, upstreamError: String(prediction?.error ?? "") };
  });
  const count = (outcome) => details.filter((detail) => detail.outcome === outcome).length;
  const missingRecords = count("missing-record");
  const emptyAnswers = count("empty-answer");
  const missing = missingRecords + emptyAnswers;
  const answered = cases.length - missing;
  return { ...base, metric: "local-exact-match-v2 (not the official evaluator)",
    missing, missingRecords, emptyAnswers, answered,
    invalidNonempty: count("invalid-format"), mismatchedValid: count("mismatch"),
    answerCoverage: answered / cases.length,
    overallExactMatch: base.correct / cases.length,
    answeredExactMatch: answered ? base.correct / answered : null,
    complete: missing === 0,
    rateNote: "answeredExactMatch 仅针对非空回答；不代表全量准确率。缺失答案不应归因于识别能力，须结合 upstreamError 和请求记录判断。",
    details };
}
