import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
import {sha256} from './reliability.mjs';
const dir=path.resolve('restart-runs/2026-09-25T03-28-15-719Z-53d112a3');
const source=path.join(dir,'submission-conservative-890-20260925.xlsx'),output=path.join(dir,'submission-conservative-890-emptystring-20260926.xlsx');
assert.equal(sha256(await fs.readFile(source)),'37a75d851149776909ef3248f1257ececcddb092d565322dca56b280a5e1ce38');
try{await fs.access(output);throw Error('Output exists; do not overwrite');}catch(e){if(e.code!=='ENOENT')throw e;}
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(source)),sheet=wb.worksheets.getItemAt(0);
const before=sheet.getRange('A1:B909').values;assert.deepEqual(before[0],['id','answer']);
const expected=before.map(r=>[...r]);const blankIds=[];
for(let i=1;i<expected.length;i++)if(expected[i][1]===null||expected[i][1]===''){blankIds.push(expected[i][0]);expected[i][1]='""';}
assert.equal(blankIds.length,18);assert.equal(new Set(expected.slice(1).map(r=>r[0])).size,908);
sheet.getRange('A1:B909').values=expected;wb.recalculate();assert.deepEqual(sheet.getRange('A1:B909').values,expected);assert.ok(sheet.getRange('A1:B909').formulas.flat().every(v=>!v));
const preview=await wb.render({sheetName:'Sheet1',range:'A124:B129',scale:1.5});await fs.writeFile(path.join(dir,'compat-preview.png'),new Uint8Array(await preview.arrayBuffer()),{flag:'wx'});
await(await SpreadsheetFile.exportXlsx(wb)).save(output);
const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(output));assert.deepEqual(saved.worksheets.getItemAt(0).getUsedRange(true).values,expected);
const report={output,source,sha256:sha256(await fs.readFile(output)),blankIds,substantiveAnswers:890,totalRows:908,policy:'encode-abstentions-as-json-empty-string',reason:'Platform failed prior workbook; blank parsing issue suspected, not confirmed',submitted:false};
await fs.writeFile(path.join(dir,'compat-export-report.json'),JSON.stringify(report,null,2),{flag:'wx'});console.log(JSON.stringify(report));
