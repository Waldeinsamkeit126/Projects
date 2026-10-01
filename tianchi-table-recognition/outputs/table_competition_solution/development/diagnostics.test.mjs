import test from "node:test";
import assert from "node:assert/strict";
import { numericEquivalent, structureDifferences } from "./diagnostics.mjs";

test("exact numeric equivalence handles notation, signs and zero", () => {
  for (const [a, b] of [["21", "21.0"], ["2.100e1", "21"], ["-0", "0.000"], [".5", "0.50"], ["-1.2500", "-1.25"]]) assert.equal(numericEquivalent(a, b), true);
});
test("numeric diagnostic does not round, coerce units or collapse large integers", () => {
  for (const [a, b] of [["21", "21.01"], ["9007199254740992", "9007199254740993"], ["1e-999", "0"], ["12元", "12"], ["", "0"], ["-1", "1"]]) assert.equal(numericEquivalent(a, b), false);
});
test("structure comparison localizes an incorrect vertical span", () => {
  const expected = { row_count: 2, col_count: 1, cells: [{ text: "地区", row: 0, col: 0, rowspan: 2, colspan: 1 }] };
  const actual = { ...expected, cells: [{ ...expected.cells[0], rowspan: 1 }] };
  assert.deepEqual(structureDifferences(expected, actual).cells, [{ coordinate: "0:0", field: "rowspan", expected: 2, actual: 1 }]);
  assert.equal(expected.cells[0].rowspan, 2);
  assert.equal(actual.cells[0].rowspan, 1);
});
