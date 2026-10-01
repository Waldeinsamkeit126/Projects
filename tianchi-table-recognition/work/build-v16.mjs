import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v14.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v16.xlsx";

const fixes = new Map([
  ["22", JSON.stringify([
    { "变动项目": "专项储备" },
    { "变动项目": "未分配利润" },
    { "变动项目": "少数股东权益" },
    { "变动项目": "股东权益合计" },
  ])],
  ["100", "中文和英文"],
  ["101", "6"],
  ["108", JSON.stringify([{
    "授课语言/Language of Instruction": "双语/全英文(Chinese or English)",
    "开课院系/School": "生命科学与技术学院(School of Life Sciences and Biotechnology)",
    "先修课程/Prerequisite": "概率统计(Probability and Statistics)",
    "授课教师/Teacher": "韦朝春",
  }])],
  ["131", "2"],
  ["138", JSON.stringify([{
    "直缝纫机送料机构": "Drop feed",
    "直缝纫机针距": "≥ 5 mm",
    "直缝纫机保修": "2 year",
    "之字形缝纫机最大速度": "≥ 1800 spm",
  }])],
  ["156", "(25) cm long (red, black, and yellow); (50) cm long (red, black, and green); (100) cm long (red, black, and blue)"],
  ["188", JSON.stringify([{
    "gaminių pogrupis": "Virtuvės čiaupai",
    "vandens srautas (l/min.)": "8,0",
    "main_unit": "l/min.",
    "table_count": "3",
  }])],
  ["198", JSON.stringify([{
    "2011-12 Average staffing level": "129",
    "2012-13 Average staffing level": "129",
    "列单位": "$'000",
    "年度列数": "5",
  }])],
  ["238", JSON.stringify([{
    "Never serviced residential inland": "20",
    "Don’t know/refused residential total": "2",
    "Frequency once every two years residential inland": "10",
    "表格主分区数量": "2",
  }])],
  ["314", "张萌"],
  ["317", "江飞"],
  ["373", "1"],
  ["414", "6"],
  ["444", "合合信息"],
  ["448", JSON.stringify([{
    "Driver contact number": "021-88888888",
    "Car reason": "公务出行",
    "License plate number": "沪M888888",
    "Driver name": "合小安",
  }])],
  ["470", "中文和英文"],
  ["498", JSON.stringify([{
    "是否含单价列": "是",
    "是否含金额列": "是",
    "是否含多行明细": "是",
    "是否横向拍摄": "是",
  }])],
  ["871", "RowSpan=\"3\"\nColumnSpan=\"2\""],
  ["875", "8"],
]);

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(inputPath));
const sheet = workbook.worksheets.getItemAt(0);
const rows = sheet.getUsedRange(true).values;
const changed = [];

for (let rowIndex = 1; rowIndex < rows.length; rowIndex += 1) {
  const id = String(rows[rowIndex][0]);
  if (!fixes.has(id)) continue;
  sheet.getCell(rowIndex, 1).values = [[fixes.get(id)]];
  changed.push(id);
}

if (changed.length !== fixes.size) {
  throw new Error(`Expected ${fixes.size} fixes, applied ${changed.length}`);
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
