import test from "node:test";
import assert from "node:assert/strict";
import { scoreObservedDevelopment } from "./scoring.mjs";
import { normalizeAnswer, validateAnswer } from "../run.mjs";

const cases = ["a", "b", "c", "d", "e"].map((id) => ({ id, answer_format: "number", question_type: "extract", expected: "3" }));
const evaluate = (predictions) => scoreObservedDevelopment(cases, predictions, normalizeAnswer, validateAnswer);

test("distinguish matched, mismatched, invalid, empty and absent predictions", () => {
  const report = evaluate([{ id: "a", answer: "3" }, { id: "b", answer: "4" }, { id: "c", answer: "abc" }, { id: "d", answer: "", valid: false, error: "fetch failed" }]);
  assert.equal(report.correct, 1);
  assert.equal(report.formatValid, 2);
  assert.equal(report.missingRecords, 1);
  assert.equal(report.emptyAnswers, 1);
  assert.equal(report.missing, 2);
  assert.equal(report.answered, 3);
  assert.equal(report.invalidNonempty, 1);
  assert.equal(report.mismatchedValid, 1);
  assert.equal(report.overallExactMatch, 0.2);
  assert.equal(report.answeredExactMatch, 1 / 3);
  assert.equal(report.answerCoverage, 0.6);
  assert.equal(report.complete, false);
  assert.equal(report.details.find((d) => d.id === "d").upstreamError, "fetch failed");
});

test("all empty responses do not produce an answered accuracy", () => {
  const report = evaluate(cases.map((c) => ({ id: c.id, answer: " " })));
  assert.equal(report.missing, 5);
  assert.equal(report.missingRecords, 0);
  assert.equal(report.answeredExactMatch, null);
});

test("complete correct responses remain complete", () => {
  const report = evaluate(cases.map((c) => ({ id: c.id, answer: "3" })));
  assert.equal(report.correct, 5);
  assert.equal(report.complete, true);
  assert.equal(report.answerCoverage, 1);
  assert.equal(report.answeredExactMatch, 1);
});

test("extra and duplicate IDs are still rejected", () => {
  assert.throws(() => evaluate([{ id: "unknown", answer: "3" }]));
  assert.throws(() => evaluate([{ id: "a", answer: "3" }, { id: "a", answer: "3" }]));
});
