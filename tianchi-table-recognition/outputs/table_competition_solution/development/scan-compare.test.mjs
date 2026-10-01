import test from "node:test";
import assert from "node:assert/strict";
import { scanCases } from "./scan-cases.mjs";
import { compareScanPredictions } from "./scan-compare.mjs";
const refs = (variant) => scanCases({ split: "development", variant }).map((q) => ({ id: q.id, answer: q.expected }));

test("paired scorer aligns variants by base question, not record order", () => {
  const result = compareScanPredictions(refs("clean"), refs("scan").reverse());
  assert.equal(result.bothCorrect, 15); assert.equal(result.pairCount, 15); assert.equal(result.sourceCount, 3);
  assert.equal(result.cleanCorrectScanWrong, 0); assert.equal(result.cleanWrongScanCorrect, 0);
});
test("one error in either direction is counted as a separate paired outcome", () => {
  const a = refs("clean"), b = refs("scan");
  a.find((p) => p.id === "ss-budget-clean-q3").answer = "999";
  b.find((p) => p.id === "ss-assembly-scan-q3").answer = "999";
  const result = compareScanPredictions(a, b);
  assert.equal(result.bothCorrect, 13); assert.equal(result.cleanCorrectScanWrong, 1); assert.equal(result.cleanWrongScanCorrect, 1);
  assert.equal(result.clean.correct, 14); assert.equal(result.scan.correct, 14);
});
test("missing records stay missing, not apparently correct empty references", () => {
  const result = compareScanPredictions(refs("clean"), []);
  assert.equal(result.scan.missing, 15); assert.equal(result.cleanCorrectScanWrong, 15);
  assert.ok(result.pairs.every((p) => p.scanOutcome === "missing-record"));
});
test("paired scorer rejects unknown, duplicate and cross-split records", () => {
  assert.throws(() => compareScanPredictions(refs("scan"), refs("clean")));
  const a = refs("clean"); assert.throws(() => compareScanPredictions([...a, a[0]], refs("scan")));
  assert.throws(() => compareScanPredictions(refs("clean"), refs("scan"), "all"));
});
