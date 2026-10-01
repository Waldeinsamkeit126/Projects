export const coverageDatasetVersion = "coverage-validation-v1";
const cell = (text, row, col, rowspan = 1, colspan = 1) => ({ text, row, col, rowspan, colspan });
const grid = (rows) => rows.flatMap((row, r) => row.map((text, c) => cell(text, r, c)));
const table = (title, row_count, col_count, cells) => ({ title, row_count, col_count, cells });

export const coverageSources = [
  { id: "cv-tiered", tables: [table("半年度练习计划", 5, 6, [
    cell("部门", 0, 0, 3), cell("数量与金额", 0, 1, 1, 4), cell("负责人", 0, 5, 3),
    cell("上半年", 1, 1, 1, 2), cell("下半年", 1, 3, 1, 2),
    cell("数量", 2, 1), cell("金额", 2, 2), cell("数量", 2, 3), cell("金额", 2, 4),
    ...["采购", "6", "150", "8", "200", "林青"].map((x, c) => cell(x, 3, c)),
    ...["研发", "4", "180", "5", "225", ""].map((x, c) => cell(x, 4, c)),
  ])], target: 0, headerRows: 3, question: "采购部门下半年数量是多少？", expected: "8" },
  { id: "cv-blanks", tables: [table("空白与零练习表", 4, 3, grid([
    ["编号", "数量", "备注"], ["007", "0", ""], ["008", "", "待核"], ["009", "4", ""],
  ]))], target: 0, headerRows: 1, question: "编号007的数量是多少？", expected: "0" },
  { id: "cv-groups", tables: [table("分组物料练习表", 5, 4, [
    ...["组别", "品名", "数量", "单价"].map((x, c) => cell(x, 0, c)),
    cell("甲组", 1, 0, 2), cell("纸", 1, 1), cell("3", 1, 2), cell("5.50", 1, 3),
    cell("墨", 2, 1), cell("2", 2, 2), cell("12.00", 2, 3),
    cell("乙组", 3, 0, 2), cell("笔", 3, 1), cell("5", 3, 2), cell("2.00", 3, 3),
    cell("尺", 4, 1), cell("1", 4, 2), cell("4.00", 4, 3),
  ])], target: 0, headerRows: 1, question: "品名为墨的数量是多少？", expected: "2" },
  { id: "cv-multitable", tables: [
    table("库存记录（非目标）", 3, 3, grid([["项目", "数量", "状态"], ["配件A", "70", "在库"], ["配件B", "90", "在库"]])),
    table("订单记录（目标表）", 3, 3, grid([["项目", "数量", "状态"], ["配件A", "2", "已发"], ["配件B", "7", "待发"]])),
  ], target: 1, headerRows: 1, question: "只依据右侧订单记录，配件B的数量是多少？", expected: "7" },
];

export function coverageCases() {
  return coverageSources.flatMap((source) => {
    const target = source.tables[source.target];
    const structure = { row_count: target.row_count, col_count: target.col_count, cells: target.cells };
    const partial = { ...structure, cells: target.cells.filter((c) => c.row < source.headerRows) };
    const location = source.tables.length > 1 ? "只针对右侧的订单记录（目标表）。" : "";
    const common = { sourceId: source.id, split: "validation", file_name: `${source.id}.png`, table_hint: target.title };
    return [
      { ...common, id: `${source.id}-full`, question_type: "structure", answer_format: "json", structure_scope: "full",
        question: `${location}恢复完整表格结构，cells包含所有单元格，包括空白单元格。标题不计入表内。`, expected: structure, category: "full-structure" },
      { ...common, id: `${source.id}-header`, question_type: "structure", answer_format: "json", structure_scope: "partial",
        question: `${location}仅恢复表头行结构；cells只输出表头，row_count与col_count仍填写整张目标表的逻辑尺寸。`, expected: partial, category: "partial-structure" },
      { ...common, id: `${source.id}-value`, question_type: "extract", answer_format: "number",
        question: source.question, expected: source.expected, category: "table-location-and-value" },
    ];
  });
}
