import { inferStructureScope } from "./structure-coverage.mjs";

export const CONSISTENCY_VERSION = "same-image-explicit-table-v1";

// No labels, model calls, guessed dimensions or answer mutation. Ambiguous targets are skipped.
export function inspectStructureConsistency(questions, results, normalize, validate) {
  const groups = new Map(), byId = new Map(), skipped = [], comparisons = [];
  for (const result of results) {
    if (byId.has(result.id)) throw new Error("Consistency audit received duplicate result IDs.");
    byId.set(result.id, result);
  }
  const ids = new Set();
  for (const q of questions) {
    if (ids.has(q.id)) throw new Error("Consistency audit received duplicate question IDs.");
    ids.add(q.id);
    if (q.question_type !== "structure" || q.answer_format !== "json") continue;
    const hint = String(q.table_hint ?? "").trim(), file = String(q.file_name ?? "");
    const scope = inferStructureScope(q);
    let reason;
    if (!hint || hint === "11") reason = "missing-explicit-table-hint";
    else if (!/\.(?:png|jpe?g|webp)$/i.test(file)) reason = "not-single-image-target";
    else if (scope !== "full" && !(scope === "partial" && /表头|headers?/i.test(q.question ?? ""))) reason = "not-full-or-explicit-header";
    const result = byId.get(q.id), answer = normalize(q, result?.answer);
    if (!reason && (!result || !validate(q, answer).valid)) reason = "missing-or-invalid-structure";
    if (reason) { skipped.push({ id: q.id, reason }); continue; }
    const key = JSON.stringify([file, hint]);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({ question: q, scope, table: JSON.parse(answer) });
  }
  if ([...byId.keys()].some((id) => !ids.has(id))) throw new Error("Consistency audit received unknown result IDs.");
  for (const group of groups.values()) {
    const fulls = group.filter((g) => g.scope === "full"), headers = group.filter((g) => g.scope === "partial");
    if (fulls.length !== 1 || headers.length === 0) {
      skipped.push(...group.map((g) => ({ id: g.question.id, reason: fulls.length > 1 ? "ambiguous-multiple-full-answers" : "no-full-header-pair" })));
      continue;
    }
    const full = fulls[0], cells = new Map(full.table.cells.map((c) => [`${c.row}:${c.col}`, c]));
    for (const header of headers) {
      let differenceCount = 0;
      const differences = [];
      const add = (difference) => { differenceCount++; if (differences.length < 20) differences.push(difference); };
      for (const field of ["row_count", "col_count"]) {
        if (full.table[field] !== header.table[field]) add({ kind: "dimensions", field, full: full.table[field], header: header.table[field] });
      }
      for (const cell of header.table.cells) {
        const coordinate = `${cell.row}:${cell.col}`, peer = cells.get(coordinate);
        if (!peer) { add({ kind: "missing-header-origin-in-full", coordinate }); continue; }
        for (const field of ["text", "rowspan", "colspan"]) {
          if (peer[field] !== cell[field]) add({ kind: "header-cell", coordinate, field, full: peer[field], header: cell[field] });
        }
      }
      comparisons.push({ fileName: full.question.file_name, tableHint: full.question.table_hint,
        fullId: full.question.id, headerId: header.question.id, consistent: differenceCount === 0,
        differenceCount, differences, omittedDifferences: differenceCount - differences.length });
    }
  }
  return { version: CONSISTENCY_VERSION, comparisons, conflictCount: comparisons.filter((c) => !c.consistent).length,
    skipped, apiRequests: 0, answersModified: false,
    limitation: "同一图片和明确相同 table_hint 的完整表/表头交叉检查；只标记不一致，不判定哪份正确。一致仍可能共同漏列或错跨度；同名多表可能歧义。PDF、缺少目标提示或范围不明确时跳过。" };
}
