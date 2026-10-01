import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
import {verifyContinuationPlan,readJson,readJsonl,repairTasks,groupRepairTasks,repairPrompt,VERSION,scopeRule} from './restart-candidate.mjs';
import {verifySeed} from './restart-seed.mjs';
import {fullPrompt,normalizeFull,validateFull,auditFullResults} from './full-candidate.mjs';
import {parseModelAnswers} from './run.mjs';
import {sha256} from './reliability.mjs';

export async function validateContinuation(runDir, {allowInvalidAsBlank=false}={}) {
  const plan=await readJson(path.join(runDir,'plan.json')), report=await readJson(path.join(runDir,'report.json'));
  await verifyContinuationPlan(plan);
  assert.equal(report.version,VERSION);assert.equal(report.planDigest,plan.digest);assert.equal(report.sourceHash,plan.sourceHash);
  assert.equal(report.status,allowInvalidAsBlank?'needs-more-repair-no-export':'complete-awaiting-export-review');assert.equal(report.stopReason,null);
  assert.equal(report.baseCompleted,23);assert.equal(report.priorRequests,68);
  const requests=await readJsonl(path.join(runDir,'requests.jsonl')), traces=await readJsonl(path.join(runDir,'inference-trace.jsonl'));
  const candidates=await readJsonl(path.join(runDir,'candidates.jsonl')), rows=await readJsonl(path.join(runDir,'results.jsonl'));
  assert.deepEqual(report.requests,requests);assert.equal(report.newRequests,requests.length);
  assert.equal(report.totalRequests,requests.length+68);assert.ok(requests.length>=23&&requests.length<=26);
  assert.ok(requests.length<=report.maxNewRequests&&report.maxNewRequests<=26);
  assert.equal(report.repairsMade,requests.length-23);assert.equal(traces.length,requests.length*2);
  assert.equal(report.resultsSha256,sha256(await fs.readFile(path.join(runDir,'results.jsonl'))));
  const seed=await verifySeed(), current=new Map(seed.rows.map(r=>[r.id,r]));let groups;let candidateOffset=0;
  for(const [i,req] of requests.entries()) {
    assert.equal(req.requestIndex,i+69);assert.equal(req.apiRequestMade,true);assert.equal(req.httpStatus,200);
    assert.equal(req.finishReason,'stop');assert.equal(req.resolvedModel,req.model);
    const stage=i<23?'base':'repair';assert.equal(req.stage,stage);
    if(i===23)groups=groupRepairTasks(repairTasks(plan.basePlan,[...current.values()]),[...current.values()]);
    const tasks=stage==='base'?[{unit:plan.basePlan.units[plan.baseTasks[i].unitIndex-1],questions:plan.basePlan.units[plan.baseTasks[i].unitIndex-1].questions.filter(q=>plan.baseTasks[i].questionIds.includes(q.id))}]:groups[i-23];
    assert.ok(tasks?.length);assert.equal(req.model,tasks[0].unit.model);
    assert.deepEqual(req.sourceUnitIndices,tasks.map(t=>t.unit.requestIndex));
    const questions=tasks.flatMap(t=>t.questions);assert.deepEqual(req.questionIds,questions.map(q=>q.id));
    const promptHash=sha256((stage==='base'?fullPrompt(questions):repairPrompt(tasks))+scopeRule);assert.equal(req.promptSha256,promptHash);
    const prepared=traces.filter(t=>t.kind==='request-prepared'&&t.requestIndex===req.requestIndex);
    const responses=traces.filter(t=>t.kind==='response'&&t.requestIndex===req.requestIndex);
    assert.equal(prepared.length,1);assert.equal(responses.length,1);
    assert.deepEqual(prepared[0].tasks,tasks.map(t=>({unitIndex:t.unit.requestIndex,questionIds:t.questions.map(q=>q.id),diagnostics:t.diagnostics??[],mediaSha256:t.unit.mediaSha256})));
    for(const trace of [prepared[0],responses[0]]) {
      assert.equal(trace.promptSha256,promptHash);assert.equal(trace.model,req.model);assert.equal(trace.stage,stage);
      assert.deepEqual(trace.questionIds,req.questionIds);assert.deepEqual(trace.sourceUnitIndices,req.sourceUnitIndices);
    }
    assert.equal(responses[0].resolvedModel,req.model);assert.equal(responses[0].finishReason,'stop');assert.equal(responses[0].httpStatus,200);
    const parsed=parseModelAnswers(responses[0].content,questions);
    const batch=tasks.flatMap(t=>t.questions.map(q=>{const answer=normalizeFull(q,parsed.get(q.id));return {
      id:q.id,answer,...validateFull(q,answer),runId:report.runId,requestIndex:req.requestIndex,stage,model:req.model,
      sourceFile:q.file_name,sourceUnitIndex:t.unit.requestIndex,provenance:VERSION,mediaSha256:t.unit.mediaSha256,promptSha256:promptHash};}));
    const adopted=[];
    for(const task of tasks) {
      const ids=new Set(task.questions.map(q=>q.id)), selected=batch.filter(r=>ids.has(r.id));
      const peers=task.unit.questions.map(q=>selected.find(r=>r.id===q.id)??current.get(q.id)).filter(Boolean);
      if(stage==='base'||auditFullResults({units:[task.unit]},peers).complete)for(const row of selected){current.set(row.id,row);adopted.push(row.id);}
    }
    assert.deepEqual(req.adoptedIds,adopted);assert.equal(req.invalidCount,batch.filter(r=>!r.valid).length);
    assert.equal(req.status,req.invalidCount?'validation-issues-recorded':'format-checked-not-proven-correct');
    for(const row of batch)assert.deepEqual(candidates[candidateOffset++],{...row,adopted:adopted.includes(row.id)});
  }
  assert.equal(candidateOffset,candidates.length);
  assert.deepEqual(rows,plan.basePlan.questionOrder.map(id=>current.get(id)));
  const audit=auditFullResults(plan.basePlan,rows);if(!allowInvalidAsBlank)assert.equal(audit.complete,true);assert.deepEqual(audit,report.audit);
  assert.equal(audit.missing.length,0);assert.equal(audit.consistency.conflictCount,0);
  assert.equal(rows.length,908);for(const row of rows)assert.ok(row.answer.length<=32767,'答案不能截断');
  return {plan,report,rows,audit};
}

export async function exportContinuation(runDir, {allowInvalidAsBlank=false}={}) {
  const {plan,report,rows,audit}=await validateContinuation(runDir,{allowInvalidAsBlank}), base=plan.basePlan;
  const blankIds=new Set(allowInvalidAsBlank?audit.invalid.map(r=>r.id):[]);
  if(allowInvalidAsBlank){assert.equal(blankIds.size,18);assert.equal(rows.filter(r=>!blankIds.has(r.id)).length,890);}
  const output=path.join(runDir,allowInvalidAsBlank?'submission-conservative-890-20260925.xlsx':'submission-automated-restart-20260925.xlsx');
  try{await fs.access(output);throw Error('禁止覆盖已有提交文件');}catch(e){if(e.code!=='ENOENT')throw e;}
  assert.equal(sha256(await fs.readFile(base.templatePath)),base.templateSha256);
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(base.templatePath));
  const sheets=(await wb.inspect({kind:'sheet',include:'id,name'})).ndjson.trim().split('\n').map(JSON.parse).filter(r=>r.kind==='sheet');
  assert.equal(sheets.length,1);assert.equal(sheets[0].range,'A1:B1');
  const sheet=wb.worksheets.getItemAt(0);assert.deepEqual(sheet.getRange('A1:B1').values,[['id','answer']]);
  const byId=new Map(rows.map(r=>[r.id,blankIds.has(r.id)?'':r.answer])),values=base.questionOrder.map(id=>[id,byId.get(id)]);
  sheet.getRange('A2:B909').values=values.map(row=>row.map(v=>v.startsWith('=')?"'"+v:v));
  wb.recalculate();assert.deepEqual(sheet.getRange('A2:B909').values,values);
  assert.ok(sheet.getRange('A1:B909').formulas.flat().every(v=>!v));
  const preview=await wb.render({sheetName:sheets[0].name,range:'A1:B7',scale:1.5});
  const previewPath=path.join(runDir,'submission-preview.png'),previewBytes=new Uint8Array(await preview.arrayBuffer());
  try{await fs.writeFile(previewPath,previewBytes,{flag:'wx'});}catch(e){if(e.code!=='EEXIST')throw e;assert.equal(sha256(await fs.readFile(previewPath)),sha256(previewBytes));}
  const blob=await SpreadsheetFile.exportXlsx(wb);await blob.save(output);
  const bytes=await fs.readFile(output);assert.ok(bytes.length<100*1024*1024);
  const reread=await SpreadsheetFile.importXlsx(await FileBlob.load(output)),saved=reread.worksheets.getItemAt(0);
  assert.deepEqual(saved.getUsedRange(true).values.map(row=>row.map(v=>v===null?'':v)),[['id','answer'],...values]);assert.ok(saved.getRange('A1:B909').formulas.flat().every(v=>!v));
  const result={runId:report.runId,planDigest:plan.digest,output,bytes:bytes.length,sha256:sha256(bytes),questionCount:908,nonemptyAnswers:values.filter(r=>r[1]!=='').length,blankIds:[...blankIds],policy:allowInvalidAsBlank?'user-approved-invalid-as-blank-20260925':'strict',rereadVerified:true,submitted:false,groundTruthAccuracy:null,resultsSha256:report.resultsSha256};
  await fs.writeFile(path.join(runDir,'export-report.json'),JSON.stringify(result,null,2),{flag:'wx'});return result;
}
export async function verifyExistingConservative(runDir) {
 const {plan,report,rows,audit}=await validateContinuation(runDir,{allowInvalidAsBlank:true});
 const blankIds=new Set(audit.invalid.map(r=>r.id));assert.equal(blankIds.size,18);
 const output=path.join(runDir,'submission-conservative-890-20260925.xlsx'),bytes=await fs.readFile(output);
 const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(output));
 const sheets=(await wb.inspect({kind:'sheet',include:'id,name'})).ndjson.trim().split('\n').map(JSON.parse).filter(r=>r.kind==='sheet');assert.equal(sheets.length,1);
 const sheet=wb.worksheets.getItemAt(0),byId=new Map(rows.map(r=>[r.id,blankIds.has(r.id)?'':r.answer]));
 const expected=[['id','answer'],...plan.basePlan.questionOrder.map(id=>[id,byId.get(id)])];
 assert.deepEqual(sheet.getUsedRange(true).values.map(row=>row.map(v=>v===null?'':v)),expected);
 assert.ok(sheet.getRange('A1:B909').formulas.flat().every(v=>!v));assert.ok(bytes.length<100*1024*1024);
 const result={runId:report.runId,planDigest:plan.digest,output,bytes:bytes.length,sha256:sha256(bytes),questionCount:908,nonemptyAnswers:890,blankIds:[...blankIds],policy:'user-approved-invalid-as-blank-20260925',rereadVerified:true,submitted:false,groundTruthAccuracy:null,resultsSha256:report.resultsSha256};
 await fs.writeFile(path.join(runDir,'export-report.json'),JSON.stringify(result,null,2),{flag:'wx'});return result;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  assert.ok(process.argv.length===3||(process.argv.length===4&&process.argv[3]==='--approved-invalid-as-blank'));console.log(JSON.stringify(await exportContinuation(path.resolve(process.argv[2]),{allowInvalidAsBlank:process.argv[3]==='--approved-invalid-as-blank'}),null,2));
}
