import test from "node:test";
import assert from "node:assert/strict";
import { inspectStructureConsistency } from "./structure-consistency.mjs";
import { inspectFullCoverage } from "./structure-coverage.mjs";
import { normalizeAnswer, validateAnswer } from "./run.mjs";

const full = { id: "whole", file_name: "made-up.png", table_hint: "明确目标表", question_type: "structure", answer_format: "json", structure_scope: "full", question: "恢复完整表格结构" };
const header = { ...full, id: "header", structure_scope: "partial", question: "仅恢复表头结构，行列数为整表尺寸" };
const table = { row_count: 2, col_count: 2, cells: [
  { text: "表头", row: 0, col: 0, rowspan: 1, colspan: 2 },
  { text: "甲", row: 1, col: 0, rowspan: 1, colspan: 1 }, { text: "乙", row: 1, col: 1, rowspan: 1, colspan: 1 },
] };
const head = () => ({ ...structuredClone(table), cells: [structuredClone(table.cells[0])] });
const predictions = (a = table, b = head()) => [{ id: full.id, answer: JSON.stringify(a) }, { id: header.id, answer: JSON.stringify(b) }];
const audit = (qs = [full, header], ps = predictions()) => inspectStructureConsistency(qs, ps, normalizeAnswer, validateAnswer);

test("matching explicit full/header structures produce no conflicts without modifying answers", () => {
  const qs = [full, header], ps = predictions(), before = JSON.stringify([qs, ps]);
  const result = audit(qs, ps);
  assert.equal(result.comparisons.length, 1); assert.equal(result.conflictCount, 0);
  assert.equal(result.apiRequests, 0); assert.equal(JSON.stringify([qs, ps]), before);
});
test("self-consistent wrong dimensions can pass coverage but conflict with a header answer", () => {
  const wrong = { row_count: 2, col_count: 1, cells: [
    { text: "表头", row: 0, col: 0, rowspan: 1, colspan: 1 }, { text: "甲", row: 1, col: 0, rowspan: 1, colspan: 1 },
  ] };
  assert.equal(inspectFullCoverage(wrong).complete, true);
  const result = audit([full, header], predictions(wrong));
  assert.equal(result.conflictCount, 1);
  assert.ok(result.comparisons[0].differences.some((d) => d.field === "col_count"));
  assert.ok(result.comparisons[0].differences.some((d) => d.field === "colspan"));
});
test("header text, spans and unmatched cell origins are all audited", () => {
  const b = head(); b.cells = [{ text: "不同表头", row: 0, col: 0, rowspan: 2, colspan: 1 }, { text: "另一格", row: 0, col: 1, rowspan: 1, colspan: 1 }];
  const result = audit([full, header], predictions(table, b));
  assert.equal(result.conflictCount, 1);
  assert.deepEqual(result.comparisons[0].differences.map((d) => d.field ?? d.kind), ["text", "rowspan", "colspan", "missing-header-origin-in-full"]);
});
test("different files or explicit table hints are not grouped", () => {
  for (const changed of [{ file_name: "different.png" }, { table_hint: "另一目标" }]) assert.equal(audit([full, { ...header, ...changed }]).comparisons.length, 0);
});
test("missing hints, PDFs, unspecified scope and non-header regions are skipped", () => {
  for (const changed of [{ table_hint: "" }, { table_hint: "11" }, { file_name: "multi.pdf" }, { structure_scope: "partial", question: "仅输出指定区域" }]) {
    const result = audit([{ ...full, ...changed }, { ...header, ...changed }]);
    assert.equal(result.comparisons.length, 0); assert.ok(result.skipped.length > 0);
  }
});
test("missing, invalid and duplicate records cannot silently pass pair alignment", () => {
  assert.equal(audit([full, header], [predictions()[0]]).comparisons.length, 0);
  assert.equal(audit([full, header], predictions(table, {})).comparisons.length, 0);
  assert.throws(() => audit([full, full], predictions()), /duplicate/);
  assert.throws(() => audit([full, header], [...predictions(), predictions()[0]]), /duplicate/);
  assert.throws(() => audit([full, header], [...predictions(), { id: "unknown", answer: "x" }]), /unknown/);
});
test("multiple complete answers for one target are considered ambiguous", () => {
  const another = { ...full, id: "whole-2" };
  const result = audit([full, another, header], [...predictions(), { id: another.id, answer: JSON.stringify(table) }]);
  assert.equal(result.comparisons.length, 0); assert.ok(result.skipped.every((s) => s.reason === "ambiguous-multiple-full-answers"));
});
test("two mutually consistent wrong structures are not falsely certified correct", () => {
  const wrong = { row_count: 1, col_count: 1, cells: [{ text: "可能漏列", row: 0, col: 0, rowspan: 1, colspan: 1 }] };
  const result = audit([full, header], predictions(wrong, wrong));
  assert.equal(result.conflictCount, 0); assert.equal(result.accuracy, undefined);
  assert.match(result.limitation, /共同漏列/);
});
