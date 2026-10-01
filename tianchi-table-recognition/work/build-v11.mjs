import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v10.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v11.xlsx";

const fixes = new Map([
  ["117", "Art/Music/Literature at National level and State Level"],
  ["121", "3"],
  ["122", "Component & Specification"],
  ["123", "Notes"],
  ["146", "Not specified"],
  ["147", "Not specified"],
  ["148", JSON.stringify([{
    "电风扇颜色": "Not specified",
    "表格所在页码": "37",
    "圆形线圈表包含规格区": "true",
    "电风扇表包含 Specifications 区": "true",
  }])],
  ["158", JSON.stringify([{
    "Lunch Set 数量单位": "Set of (9) pieces",
    "第一页脚注格式": "11EU/2016 R1",
    "Photocell 是否带红字标题": "true",
    "Lunch Set 是否含图片/示意表": "false",
  }])],
  ["196", "0"],
  ["197", "2169"],
  ["228", JSON.stringify([{
    "Total Malaria visit non-user": "2175",
    "Total Non-malaria visit non-user": "3418",
    "Total Malaria prevalence": "34.7",
    "Area 数量": "21",
  }])],
  ["237", "51"],
  ["238", JSON.stringify([{
    "Never serviced residential inland": "20",
    "Don’t know/refused residential total": "2",
    "Frequency once every two years residential inland": "9",
    "表格主分区数量": "2",
  }])],
  ["404", "142.877±6.584"],
  ["405", "131.852±10.934"],
  ["406", "592.178±95.362"],
  ["407", "279.869±70.830"],
  ["408", JSON.stringify([{
    "Elderly total peak pressure C": "213.564±45.475",
    "分组数量": "2",
    "面罩类别数量": "3",
    "指标区块数量": "4",
  }])],
  ["453", "出生日期"],
  ["479", "中华人民共和国海关出口货物报关单"],
  ["488", JSON.stringify([{
    "表格主色": "黑白",
    "是否含税率列": "false",
    "是否含日期字段": "true",
    "是否含签字栏": "true",
  }])],
  ["521", "13"],
  ["528", JSON.stringify([{
    "最低活动价": "199",
    "最高活动价": "79999",
    "备注中含退换规则": "true",
    "表格下方说明条数": "3",
  }])],
  ["531", "7"],
  ["471", "6"],
  ["476", "中国 829510-678"],
  ["477", "印尼 829509-678"],
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
if (changed.length !== fixes.size) throw new Error(`Expected ${fixes.size} fixes, applied ${changed.length}`);
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
