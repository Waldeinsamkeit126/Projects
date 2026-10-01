import fs from "node:fs/promises";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v6-excel.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v7.xlsx";

const fixes = new Map([
  ["19", JSON.stringify([{ "组成项": "营业收入" }])],
  ["59", JSON.stringify([
    { "项目": "房屋及建筑物", "金额": "0" },
    { "项目": "管网设备", "金额": "0" },
    { "项目": "运输工具", "金额": "1,876,349.13" },
  ])],
  ["83", JSON.stringify([
    { "day": "Day 1" },
    { "day": "Day 3" },
    { "day": "Day 4" },
    { "day": "Day 5" },
    { "day": "Day 6" },
  ])],
  ["94", JSON.stringify([
    { "day": "Day 1", "card_title": "营地集结与入场", "result_label": "成果启动：项目立项" },
    { "day": "Day 3", "card_title": "功能与流程设计", "result_label": "成果：产品逻辑图" },
    { "day": "Day 4", "card_title": "用户验证实验", "result_label": "成果：测试数据" },
    { "day": "Day 4", "card_title": "基于数据分析", "result_label": "成果：原型v3.0" },
    { "day": "Day 5", "card_title": "基于价值分析", "result_label": "成果：原型v4.0" },
    { "day": "Day 6", "card_title": "发布成果与成长", "result_label": "结营证书+项目档案" },
  ])],
  ["103", "学分 (Credits)"],
  ["158", JSON.stringify([{
    "Lunch Set 数量单位": "Set of (9) pieces",
    "第一页脚注格式": "11EU/2016 R1",
    "Photocell 是否带红字标题": "true",
    "Lunch Set 是否含图片/示意表": "false",
  }])],
  ["208", JSON.stringify([{
    "BTM Si%": "0.220",
    "2HM C%": "0.450",
    "红色限制单元数量": "8",
    "绿色数值单元数量": "16",
  }])],
  ["378", JSON.stringify([{
    "HCMRM total pore volume": "8.635",
    "HCMRM average particle size": "84.172",
    "编码列名": "Coded name",
    "设计因素数量": "4",
  }])],
  ["479", "中华人民共和国海关出口货物报关单"],
  ["488", JSON.stringify([{
    "表格主色": "黑白",
    "是否含税率列": "false",
    "是否含日期字段": "true",
    "是否含签字栏": "true",
  }])],
  ["528", JSON.stringify([{
    "最低活动价": "199",
    "最高活动价": "79999",
    "备注中含退换规则": "true",
    "表格下方说明条数": "3",
  }])],
  ["877", "是"],
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

await fs.mkdir("C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution", { recursive: true });
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, changed }));
