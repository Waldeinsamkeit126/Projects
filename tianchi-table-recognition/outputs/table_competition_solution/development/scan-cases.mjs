// New, authored synthetic fixtures. Never import official media, answers or old predictions here.
export const scanDatasetVersion = "scan-stress-v1";
export const variants = ["clean", "scan"];
const c = (text, row, col, rowspan = 1, colspan = 1) => ({ text, row, col, rowspan, colspan });
const rows = (values, start = 0) => values.flatMap((row, r) => row.map((text, col) => c(text, r + start, col)));
const t = (title, row_count, col_count, cells) => ({ title, row_count, col_count, cells });
const q = (question_type, answer_format, question, expected, category, evidence) => ({ question_type, answer_format, question, expected, category, evidence });
export const scanSources = [
  {
    id: "ss-budget", split: "development", target: 0, headerRows: 3, profile: "tilted", seed: 101,
    tables: [t("季度经费登记（单位：元）", 8, 8, [
      c("项目", 0, 0, 3), c("编号", 0, 1, 3), c("第一季度", 0, 2, 1, 3), c("第二季度", 0, 5, 1, 3),
      c("执行", 1, 2, 1, 2), c("结余", 1, 4, 2), c("执行", 1, 5, 1, 2), c("结余", 1, 7, 2),
      c("预算", 2, 2), c("实支", 2, 3), c("预算", 2, 5), c("实支", 2, 6),
      ...rows([
        ["设备", "0031", "126.50", "118.25", "8.25", "144.00", "140.50", "3.50"],
        ["场地", "0032", "90.00", "90.00", "0", "96.00", "92.50", "3.50"],
        ["测试", "0033", "38.75", "40.25", "-1.50", "42.00", "0", "42.00"],
        ["资料", "0034", "20.00", "", "", "22.00", "19.75", "2.25"],
        ["培训", "0035", "56.00", "53.50", "2.50", "60.00", "58.25", "1.75"],
      ], 3),
    ])],
    questions: [
      q("extract", "number", "场地项目第二季度的实支是多少元？", "92.5", "header-path", [[4, 6]]),
      q("extract", "string", "设备项目的编号是什么？保留前导零。", "0031", "identifier", [[3, 1]]),
      q("thinking", "number", "设备项目第二季度实支减去第一季度实支是多少元？", "22.25", "arithmetic", [[3, 6], [3, 3]]),
    ],
  },
  {
    id: "ss-assembly", split: "development", target: 0, headerRows: 2, profile: "faint", seed: 211,
    tables: [t("装配班次记录", 8, 6, [
      c("班组", 0, 0, 2), c("机器编号", 0, 1, 2), c("数量", 0, 2, 1, 2), c("单价（元）", 0, 4, 2), c("备注", 0, 5, 2),
      c("计划", 1, 2), c("完成", 1, 3), c("甲组", 2, 0, 3), c("乙组", 5, 0, 3),
      ...[
        ["0017", "12", "10", "6.40", ""], ["0018", "0", "0", "12.50", "未启用"], ["0019", "6", "", "8.00", "待补"],
        ["0020", "8", "9", "5.50", ""], ["0021", "1", "1", "3.75", "复核"], ["0022", "4", "2", "4.20", ""],
      ].flatMap((row, index) => row.map((text, col) => c(text, index + 2, col + 1))),
    ])],
    questions: [
      q("extract", "number", "机器0019的计划数量是多少？", "6", "header-path", [[4, 2]]),
      q("extract", "string", "机器0018的备注是什么？", "未启用", "text-extract", [[3, 5]]),
      q("thinking", "number", "机器0017和0020的完成数量合计是多少？", "19", "arithmetic", [[2, 3], [5, 3]]),
    ],
  },
  {
    id: "ss-warehouse", split: "development", target: 1, headerRows: 1, profile: "small", seed: 307,
    tables: [
      t("入库登记", 5, 4, rows([["部件", "批号", "数量", "状态"], ["垫片", "0041", "28", "已验"], ["轴套", "0042", "14", "待验"], ["连杆", "0043", "0", "已验"], ["销钉", "0044", "", "待验"]])),
      t("出库登记", 5, 4, rows([["部件", "批号", "数量", "状态"], ["垫片", "0041", "3", "已发"], ["轴套", "0042", "7", "已发"], ["连杆", "0043", "0", "暂存"], ["销钉", "0044", "5", "已发"]])),
    ],
    questions: [
      q("extract", "number", "轴套的数量是多少？", "7", "neighbor-table", [[2, 2]]),
      q("extract", "string", "销钉的批号是什么？保留前导零。", "0044", "identifier", [[4, 1]]),
      q("thinking", "number", "四种部件的数量合计是多少？", "15", "arithmetic", [[1, 2], [2, 2], [3, 2], [4, 2]]),
    ],
  },
  {
    id: "ss-production", split: "validation", target: 0, headerRows: 2, profile: "tilted", seed: 419,
    tables: [t("月度生产记录", 8, 7, [
      c("区域", 0, 0, 2), c("编号", 0, 1, 2), c("一月份", 0, 2, 1, 2), c("二月份", 0, 4, 1, 2), c("备注", 0, 6, 2),
      c("产量", 1, 2), c("返工", 1, 3), c("产量", 1, 4), c("返工", 1, 5),
      ...rows([
        ["一线", "0101", "82", "3", "91", "2", ""], ["二线", "0102", "74", "0", "78", "1", "复核"],
        ["三线", "0103", "0", "0", "", "", "停机"], ["四线", "0104", "66", "2", "70", "0", ""],
        ["五线", "0105", "59", "1", "64", "2", ""], ["六线", "0106", "88", "4", "92", "3", ""],
      ], 2),
    ])],
    questions: [
      q("extract", "number", "二线二月份的返工数量是多少？", "1", "header-path", [[3, 5]]),
      q("extract", "string", "一线的编号是什么？保留前导零。", "0101", "identifier", [[2, 1]]),
      q("thinking", "number", "一线二月份产量减去返工数量是多少？", "89", "arithmetic", [[2, 4], [2, 5]]),
    ],
  },
  {
    id: "ss-measurement", split: "validation", target: 0, headerRows: 3, profile: "faint", seed: 521,
    tables: [t("分区温度记录（单位：摄氏度）", 9, 5, [
      c("区域", 0, 0, 3), c("编号", 0, 1, 3), c("测量记录", 0, 2, 1, 3), c("温度", 1, 2, 1, 2), c("次数", 1, 4, 2),
      c("读数", 2, 2), c("修正", 2, 3), c("一区", 3, 0, 3), c("二区", 6, 0, 3),
      ...[
        ["070", "18.6", "-0.4", "2"], ["071", "0.0", "0.0", "0"], ["072", "", "0.2", "1"],
        ["073", "21.5", "-0.5", "3"], ["074", "19.8", "0.2", "1"], ["075", "20.2", "0.0", "2"],
      ].flatMap((row, index) => row.map((text, col) => c(text, index + 3, col + 1))),
    ])],
    questions: [
      q("extract", "number", "编号073的测量次数是多少？", "3", "header-path", [[6, 4]]),
      q("extract", "json_array", "依次提取编号071和072的编号、读数；两个字段均用字符串，保留原始读数格式，空白写空字符串。", [{ 编号: "071", 读数: "0.0" }, { 编号: "072", 读数: "" }], "zero-vs-blank", [[4, 1], [4, 2], [5, 1], [5, 2]]),
      q("thinking", "number", "编号073的读数加上修正值是多少摄氏度？", "21", "arithmetic", [[6, 2], [6, 3]]),
    ],
  },
  {
    id: "ss-inspection", split: "validation", target: 0, headerRows: 1, profile: "small", seed: 631,
    tables: [
      t("检验台账", 5, 5, rows([["批号", "项目", "抽样数", "不合格数", "判定"], ["X-091", "陶瓷", "24", "1", "待复核"], ["X-092", "钢片", "18", "0", "合格"], ["X-093", "胶圈", "30", "1", "不合格"], ["X-094", "支架", "12", "0", "合格"]])),
      t("复检台账", 5, 5, rows([["批号", "项目", "抽样数", "不合格数", "判定"], ["X-091", "陶瓷", "12", "0", "合格"], ["X-092", "钢片", "6", "0", "合格"], ["X-093", "胶圈", "10", "0", "合格"], ["X-094", "支架", "4", "0", "合格"]])),
    ],
    questions: [
      q("extract", "number", "批号X-093的抽样数是多少？", "30", "neighbor-table", [[3, 2]]),
      q("extract", "string", "批号X-092的判定是什么？", "合格", "text-extract", [[2, 4]]),
      q("thinking", "number", "四个批号的抽样数合计是多少？", "84", "arithmetic", [[1, 2], [2, 2], [3, 2], [4, 2]]),
    ],
  },
];

export function scanCases({ split = "all", variant = "all" } = {}) {
  if (!["all", "development", "validation"].includes(split) || !["all", ...variants].includes(variant)) throw new Error("Invalid scan split/variant");
  return scanSources.filter((s) => split === "all" || s.split === split).flatMap((source) => {
    const target = source.tables[source.target];
    const structure = { row_count: target.row_count, col_count: target.col_count, cells: target.cells };
    const structureQuestions = [
      { question_type: "structure", answer_format: "json", structure_scope: "full", question: "恢复完整表格结构；标题和表外说明不计入表内，cells须包含所有单元格（含空白），坐标从0开始，合并单元格仅记录一次。", expected: structure, category: "full-structure" },
      { question_type: "structure", answer_format: "json", structure_scope: "partial", question: "仅恢复表头行结构；cells只输出表头，row_count和col_count仍填写整张目标表的逻辑尺寸。", expected: { ...structure, cells: target.cells.filter((cell) => cell.row < source.headerRows) }, category: "partial-structure" },
    ];
    return variants.filter((v) => variant === "all" || v === variant).flatMap((v) => [...structureQuestions, ...source.questions].map((item, i) => ({
      ...item, id: `${source.id}-${v}-q${i + 1}`, sourceId: source.id, split: source.split, variant: v,
      pairId: `${source.id}-q${i + 1}`, file_name: `${source.id}-${v}.png`, table_hint: target.title,
      question: `只依据《${target.title}》。${item.question}${item.answer_format === "number" ? "只输出数值，不保留多余的小数末尾零。" : ""}`,
    })));
  });
}

// Positive allow-list, not a deny-list: future reference metadata cannot leak to the model.
export function publicScanQuestions(cases) {
  return cases.map(({ id, file_name, table_hint, question_type, answer_format, question, structure_scope }) => ({
    id, file_name, table_hint, question_type, answer_format, question, ...(structure_scope ? { structure_scope } : {}),
  }));
}
