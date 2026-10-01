import { isNumberText } from "../reliability.mjs";

// Diagnostic comparison only: no rounding, floating-point conversion or answer mutation.
export function decimalIdentity(text) {
  if (!isNumberText(text)) return null;
  const match = text.match(/^([+-]?)(\d*(?:\.\d+)?)(?:[eE]([+-]?\d+))?$/);
  const [integer, fraction = ""] = match[2].split(".");
  let digits = (integer + fraction).replace(/^0+/, "");
  if (!digits) return "0";
  let exponent = BigInt(match[3] ?? "0") - BigInt(fraction.length);
  const trailing = digits.match(/0+$/)?.[0].length ?? 0;
  digits = digits.slice(0, digits.length - trailing);
  exponent += BigInt(trailing);
  return `${match[1] === "-" ? "-" : ""}${digits}e${exponent}`;
}

export function numericEquivalent(left, right) {
  const identity = decimalIdentity(left);
  return identity !== null && identity === decimalIdentity(right);
}

export function structureDifferences(expected, actual) {
  const key = (cell) => `${cell.row}:${cell.col}`;
  const expectedCells = new Map(expected.cells.map((cell) => [key(cell), cell]));
  const actualCells = new Map(actual.cells.map((cell) => [key(cell), cell]));
  const differences = [];
  for (const coordinate of new Set([...expectedCells.keys(), ...actualCells.keys()])) {
    const reference = expectedCells.get(coordinate);
    const prediction = actualCells.get(coordinate);
    if (!reference || !prediction) {
      differences.push({ coordinate, kind: reference ? "missing-cell" : "extra-cell" });
      continue;
    }
    for (const field of ["text", "rowspan", "colspan"]) {
      if (reference[field] !== prediction[field]) differences.push({ coordinate, field, expected: reference[field], actual: prediction[field] });
    }
  }
  return { dimensions: { expected: [expected.row_count, expected.col_count], actual: [actual.row_count, actual.col_count] }, cells: differences };
}
