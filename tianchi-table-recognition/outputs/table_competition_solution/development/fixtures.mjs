// Authored from scratch. No official test files, question IDs, answers or leaderboard feedback.
export const datasetVersion = "synthetic-tables-v1";
const cell = (text, row, col, rowspan = 1, colspan = 1) => ({ text, row, col, rowspan, colspan });
const grid = (rows) => rows.flatMap((row, r) => row.map((text, c) => cell(text, r, c)));
const question = (question_type, answer_format, question, expected, category) => ({ question_type, answer_format, question, expected, category });
export const sources = [
  {
    id: "dev-sales", split: "development", title: "练习订单（单价单位：元）", row_count: 3, col_count: 3,
    cells: grid([["商品编号", "数量", "单价"], ["001", "3", "12.50"], ["002", "4", "7.25"]]),
    questions: [
      question("extract", "string", "第一条商品的编号是什么？保留前导零。", "001", "leading-zero"),
      question("extract", "number", "商品002的数量是多少？", "4", "numeric-extract"),
      question("thinking", "number", "两种商品的总金额是多少元？", "66.5", "arithmetic"),
      question("thinking", "number", "商品001与商品002的单价差是多少元？", "5.25", "arithmetic"),
      question("extract", "json_array", "按原表顺序列出商品编号和单价，键为商品编号、单价，保留原始单价格式。", [{ 商品编号: "001", 单价: "12.50" }, { 商品编号: "002", 单价: "7.25" }], "array-extract"),
    ],
  },
  {
    id: "dev-missing", split: "development", title: "练习库存", row_count: 4, col_count: 3,
    cells: grid([["仓库", "数量", "备注"], ["东仓", "0", ""], ["西仓", "", "未盘点"], ["南仓", "18", "正常"]]),
    questions: [
      question("extract", "number", "东仓数量是多少？", "0", "zero-vs-missing"),
      question("extract", "string", "西仓的备注是什么？", "未盘点", "text-extract"),
      question("extract", "json_array", "依次提取东仓和西仓的仓库、数量、备注，空格内容以空字符串表示。", [{ 仓库: "东仓", 数量: "0", 备注: "" }, { 仓库: "西仓", 数量: "", 备注: "未盘点" }], "zero-vs-missing"),
      question("thinking", "number", "只对已填写数量的仓库求和，总数量是多少？", "18", "arithmetic"),
      question("thinking", "number", "数量单元格为空的仓库共有几个？", "1", "zero-vs-missing"),
    ],
  },
  {
    id: "dev-english", split: "development", title: "Synthetic shipment register", row_count: 4, col_count: 3,
    cells: grid([["Code", "Destination", "Weight (kg)"], ["A-007", "Lima", "1,250"], ["B-012", "Oslo", "750"], ["C-004", "Kyoto", "0"]]),
    questions: [
      question("extract", "string", "What is the code for the shipment to Oslo?", "B-012", "identifier"),
      question("extract", "number", "What is the weight in kg for Lima? Remove thousands separators.", "1250", "numeric-extract"),
      question("thinking", "number", "What is the total weight in kg?", "2000", "arithmetic"),
      question("thinking", "string", "Which destination has the greatest weight?", "Lima", "comparison"),
      question("extract", "json_array", "List Code and Destination for all rows in their original order.", [{ Code: "A-007", Destination: "Lima" }, { Code: "B-012", Destination: "Oslo" }, { Code: "C-004", Destination: "Kyoto" }], "array-extract"),
    ],
  },
  {
    id: "holdout-merged", split: "holdout", title: "练习季度业绩（金额：万元）", row_count: 4, col_count: 5,
    cells: [cell("地区", 0, 0, 2), cell("第一季度", 0, 1, 1, 2), cell("第二季度", 0, 3, 1, 2),
      cell("收入", 1, 1), cell("成本", 1, 2), cell("收入", 1, 3), cell("成本", 1, 4),
      ...["北区", "80", "50", "100", "60"].map((text, c) => cell(text, 2, c)),
      ...["南区", "120", "90", "150", "110"].map((text, c) => cell(text, 3, c))],
    questions: [
      question("extract", "number", "北区第二季度收入是多少万元？", "100", "merged-header"),
      question("extract", "number", "南区第一季度成本是多少万元？", "90", "merged-header"),
      question("thinking", "number", "北区第二季度收入比第一季度增长百分之几？只输出百分数的数值，不带百分号。", "25", "percentage"),
      question("thinking", "number", "南区第二季度利润（收入减成本）是多少万元？", "40", "arithmetic"),
      question("extract", "json_array", "按北区、南区的顺序列出地区及第二季度收入，键为地区、第二季度收入。", [{ 地区: "北区", 第二季度收入: "100" }, { 地区: "南区", 第二季度收入: "150" }], "merged-header"),
    ],
  },
  {
    id: "holdout-units", split: "holdout", title: "练习预算执行", row_count: 4, col_count: 4,
    cells: grid([["项目", "预算（万元）", "实际（万元）", "人数"], ["甲项目", "12.5", "11.75", "4"], ["乙项目", "8", "9.25", "5"], ["丙项目", "0", "0", "0"]]),
    questions: [
      question("thinking", "number", "乙项目实际支出比预算多多少万元？", "1.25", "arithmetic"),
      question("thinking", "number", "甲项目实际支出换算成元是多少？", "117500", "units"),
      question("thinking", "string", "哪个项目超预算？", "乙项目", "comparison"),
      question("thinking", "number", "合计实际支出是多少万元？", "21", "arithmetic"),
      question("extract", "number", "丙项目人数是多少？", "0", "zero-vs-missing"),
    ],
  },
];

export function developmentCases() {
  return sources.flatMap((source) => {
    const fullStructure = { row_count: source.row_count, col_count: source.col_count, cells: source.cells };
    const questions = [...source.questions, question("structure", "json", "恢复完整表格结构；标题不计入表内。row_count、col_count 为完整表格逻辑尺寸，cells 包含所有单元格（含空格），坐标从0开始，合并单元格仅记一次。", fullStructure, "structure")];
    return questions.map((q, index) => ({ ...q, id: `${source.id}-q${index + 1}`, sourceId: source.id,
      split: source.split, file_name: `${source.id}.png`, table_hint: source.title }));
  });
}
