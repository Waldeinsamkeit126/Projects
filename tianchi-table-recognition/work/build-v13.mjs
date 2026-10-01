import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const inputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v12.xlsx";
const outputPath = "C:/Users/zhhzh/Documents/Codex/2026-08-26/x20-x20-2/outputs/table_competition_solution/submission-final-v13.xlsx";

const fixes = new Map([
  ["81", "4"],
  ["82", "[{\"day\":\"Day 2\",\"session\":\"导师评审项目方向\",\"record_type\":\"评审记录\"},{\"day\":\"Day 4\",\"session\":\"产品评审\",\"record_type\":\"评审记录\"},{\"day\":\"Day 5\",\"session\":\"路演演练\",\"record_type\":\"评审记录\"}]"],
  ["83", "[{\"day\":\"Day 3\",\"session\":\"产品结构设计\",\"label\":\"成果：产品框架\"},{\"day\":\"Day 4\",\"session\":\"产品开发推进\",\"label\":\"成果：产品原型v2.0\"},{\"day\":\"Day 6\",\"session\":\"项目路演\",\"label\":\"成果：Pitch路演全记录\"},{\"day\":\"Day 1\",\"session\":\"营地集结与入场\",\"label\":\"成果启动：项目立项\"},{\"day\":\"Day 3\",\"session\":\"功能与流程设计\",\"label\":\"成果：产品逻辑图\"},{\"day\":\"Day 4\",\"session\":\"用户验证实验\",\"label\":\"成果：测试数据\"},{\"day\":\"Day 4\",\"session\":\"基于数据分析\",\"label\":\"成果：原型v3.0\"},{\"day\":\"Day 5\",\"session\":\"基于价值分析\",\"label\":\"成果：原型v4.0\"},{\"day\":\"Day 6\",\"session\":\"发布成果与成长\",\"label\":\"结营证书+项目档案\"},{\"day\":\"Day 1\",\"session\":\"AI趋势与案例解析\",\"label\":\"AI商业认知建立\"},{\"day\":\"Day 3\",\"session\":\"MVP开发推进\",\"label\":\"产品原型v1.0\"}]"],
  ["92", "90"],
  ["93", "[{\"day\":\"Day 2\",\"activity\":\"导师评审项目方向\",\"output\":\"评审记录\"},{\"day\":\"Day 4\",\"activity\":\"产品评审\",\"output\":\"评审记录\"},{\"day\":\"Day 5\",\"activity\":\"路演演练\",\"output\":\"评审记录\"}]"],
  ["94", "[{\"day\":\"Day 1\",\"card_title\":\"营地集结与入场\",\"result_label\":\"成果启动：项目立项\"},{\"day\":\"Day 3\",\"card_title\":\"功能与流程设计\",\"result_label\":\"成果：产品逻辑图\"},{\"day\":\"Day 4\",\"card_title\":\"用户验证实验\",\"result_label\":\"成果：测试数据\"},{\"day\":\"Day 4\",\"card_title\":\"基于数据分析\",\"result_label\":\"成果：原型v3.0\"},{\"day\":\"Day 5\",\"card_title\":\"基于价值分析\",\"result_label\":\"成果：原型v4.0\"},{\"day\":\"Day 6\",\"card_title\":\"发布成果与成长\",\"result_label\":\"结营证书+项目档案\"}]"],
  ["97", "4"],
  ["168", "[{\"District 2 第二名学校\":\"Idaho State University\",\"District 1 第一名分数\":\"313\",\"District 2 第一名分数\":\"250\",\"页脚\":\"Fall 2012 NDT Ranking Report\"}]"],
  ["288", "[{\"Fransk nivå 3 endelig valg\":\"0\",\"Spansk 1+2 endelig valg\":\"11\",\"Tysk 1+2* endelig valg\":\"21\",\"最高 endelig valg 科目\":\"Sosiologi og sosialentr.\"}]"],
  ["768", "23765"],
  ["817", "Stearalkonium Chloride"],
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
