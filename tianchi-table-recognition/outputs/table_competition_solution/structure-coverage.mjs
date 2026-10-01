export const COVERAGE_VERSION = "explicit-full-grid-v1";

export function inferStructureScope(question) {
  if (question.question_type !== "structure" || question.answer_format !== "json") return "not-applicable";
  const text = String(question.question ?? "");
  // Local/negative wording takes precedence over the phrase "complete table dimensions".
  if (question.structure_scope === "partial"
    || /(?:只|仅|只需|只要|仅需).{0,16}(?:表头|首行|第一行|前.{0,4}行|局部|选定区域)/.test(text)
    || /(?:表头|局部|选定区域)(?:行)?结构/.test(text)
    || /(?:不要|无需|不需要).{0,10}(?:恢复|输出|提取).{0,6}(?:完整|整张|全部)/.test(text)
    || /(?:only\s+(?:the\s+)?(?:header|first\s+\w+\s+rows|selected\s+region)|header[s]?\s+only|partial\s+structure|do\s+not\s+recover\s+(?:the\s+)?(?:full|entire))/i.test(text)) return "partial";
  if (question.structure_scope === "full") return "full";
  if (/(?:恢复|输出|提取|返回)(?:整张|完整)(?:的)?表格(?:的)?结构/.test(text)
    || /cells\s*(?:包含|包括|覆盖)(?:表格)?(?:所有|全部)(?:的)?单元格/i.test(text)
    || /(?:recover|return|extract)\s+(?:the\s+)?(?:full|entire|complete)\s+table\s+structure/i.test(text)) return "full";
  return "unspecified";
}

// Precondition: dimensions, bounds and non-overlap have passed the normal structure validator.
// Area arithmetic avoids allocating a row_count * col_count grid for large merged cells.
export function inspectFullCoverage(table) {
  const total = BigInt(table.row_count) * BigInt(table.col_count);
  const covered = table.cells.reduce((sum, cell) => sum + BigInt(cell.rowspan) * BigInt(cell.colspan), 0n);
  const missing = total - covered;
  const gaps = [];
  if (missing > 0n) {
    const boundaries = [...new Set([0, table.row_count, ...table.cells.flatMap((cell) => [cell.row, cell.row + cell.rowspan])])].sort((a, b) => a - b);
    for (let index = 0; index < boundaries.length - 1 && gaps.length < 4; index++) {
      const row = boundaries[index], height = boundaries[index + 1] - row;
      const active = table.cells.filter((cell) => cell.row <= row && cell.row + cell.rowspan > row).sort((a, b) => a.col - b.col);
      let col = 0;
      for (const cell of active) {
        if (cell.col > col && gaps.length < 4) gaps.push({ row, col, height, width: cell.col - col });
        col = Math.max(col, cell.col + cell.colspan);
      }
      if (col < table.col_count && gaps.length < 4) gaps.push({ row, col, height, width: table.col_count - col });
    }
  }
  return { version: COVERAGE_VERSION, totalSlots: total.toString(), coveredSlots: covered.toString(),
    missingSlots: missing.toString(), complete: missing === 0n, firstGaps: gaps };
}

export function validateCoverage(question, table) {
  if (inferStructureScope(question) !== "full") return { valid: true };
  const coverage = inspectFullCoverage(table);
  if (coverage.complete) return { valid: true, coverage };
  const examples = coverage.firstGaps.map((gap) => `(row=${gap.row},col=${gap.col},高=${gap.height},宽=${gap.width})`).join("、");
  return { valid: false, coverage,
    error: `题目明确要求完整表格，但当前 cells 有 ${coverage.missingSlots} 个逻辑网格未覆盖，例如 ${examples}。请重新查看原图，核对空白单元格与纵向/横向合并边界。不得为了填满网格直接补值或扩大跨度；完整范围仍须以题目和图像为准。` };
}
