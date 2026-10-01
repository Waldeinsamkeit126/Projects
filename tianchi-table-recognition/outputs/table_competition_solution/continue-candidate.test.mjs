import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import {createContinuationPlan,executeContinuation,repairTasks,groupRepairTasks,repairPrompt,verifySeed,LIMITS} from "./continue-candidate.mjs";
import {validateContinuation} from "./continuation-export.mjs";
const plan=await createContinuationPlan();
const tmp=()=>fs.mkdtemp(path.join(os.tmpdir(),"tianchi-continuation-test-"));
const opts=async extra=>({allowPaid:true,maxNewRequests:84,apiKey:"test-secret",outputRoot:await tmp(),...extra});
const mockAnswer=q=>q.answer_format==="json_array"?["mock"]:q.answer_format==="number"?"1":q.answer_format==="json"?{row_count:1,col_count:1,cells:[{text:"mock",row:0,col:0,rowspan:1,colspan:1}]}:"mock";
function envelope(body,alter){const text=body.messages[1].content.at(-1).text;const questions=JSON.parse(text.split("\n问题清单：\n")[1].split("\n")[0]);const answers=questions.map(q=>({id:q.id,answer:mockAnswer(q)}));alter?.(answers,questions);return{ok:true,status:200,json:async()=>({model:body.model,choices:[{finish_reason:"stop",message:{content:JSON.stringify({answers})}}],usage:{prompt_tokens:1,completion_tokens:1,total_tokens:2}})}
}
test("seed is immutable, 118 rows preserved, pending base/repair quotas fixed",async()=>{
 const seed=await verifySeed();assert.equal(seed.rows.length,118);assert.equal(plan.pendingUnitIndices.length,79);assert.equal(plan.pendingUnitIndices[0],11);
 assert.equal(LIMITS.newRequests,84);assert.equal(LIMITS.totalRequests,94);assert.equal(LIMITS.repairRequests,5);
 const tasks=repairTasks(seed.plan,seed.rows).filter(t=>t.unit.requestIndex<=10);assert.equal(tasks.length,1);assert.deepEqual(tasks[0].questions.map(q=>q.id),["118"]);
 assert.ok(repairPrompt(tasks).includes("不含对象、null或嵌套数组"));
});
test("dry run does not fetch or create a paid authorization lock",async()=>{
 let calls=0;const o=await opts({allowPaid:false,fetchImpl:()=>{calls++;}});const r=await executeContinuation(plan,o);assert.equal(r.apiRequests,0);assert.equal(calls,0);assert.deepEqual(await fs.readdir(o.outputRoot),[]);
});
test("modified plan, excess quota, absent key or disallowed host fail before API",async()=>{
 let calls=0;const o=await opts({fetchImpl:()=>{calls++;}});const altered=structuredClone(plan);altered.limits.totalRequests=95;
 await assert.rejects(executeContinuation(altered,o));
 for(const extra of [{maxNewRequests:85},{maxNewRequests:undefined},{apiKey:""},{baseUrl:"https://example.com"}])await assert.rejects(executeContinuation(plan,{...o,...extra}));assert.equal(calls,0);
});
test("79 new base calls continue a format failure, then bounded grouped repair; no old base repeats",async()=>{
 let calls=0,repairCalls=0,badId;
 const result=await executeContinuation(plan,await opts({fetchImpl:async(url,init)=>{
   const body=JSON.parse(init.body);assert.equal(init.redirect,"error");assert.equal(body.max_completion_tokens,16384);assert.equal(body.enable_thinking,false);
   const repairing=body.messages[1].content.at(-1).text.includes("这是有限的格式/结构复核");if(repairing)repairCalls++;
   calls++;return envelope(body,(answers,questions)=>{if(calls===1){const i=questions.findIndex(q=>q.answer_format==="number");assert.ok(i>=0);badId=questions[i].id;answers[i].answer="bad-number";}});
 }}));
 assert.equal(result.baseCompleted,79);assert.equal(result.audit.complete,true);assert.equal(result.audit.returnedQuestions,908);assert.equal(result.totalRequests,10+calls);
 assert.ok(calls<=84);assert.ok(repairCalls<=5);assert.equal(result.status,"complete-awaiting-export-review");assert.equal(result.submitted,false);
 const candidates=(await fs.readFile(path.join(result.runDir,"candidates.jsonl"),"utf8")).trim().split(/\r?\n/).map(JSON.parse);
 assert.equal(candidates.filter(r=>r.id===badId&&r.stage==="base")[0].valid,false);
 assert.ok(candidates.some(r=>r.id===badId&&r.stage==="repair"&&r.valid));
 assert.equal((await validateContinuation(result.runDir)).rows.length,908);
 const resultsPath=path.join(result.runDir,"results.jsonl"), original=await fs.readFile(resultsPath,"utf8");
 await fs.writeFile(resultsPath,original.replace('"answer":','"unexpected":'));
 await assert.rejects(validateContinuation(result.runDir));
});
test("smaller cap stops without resetting authorization or losing seed results",async()=>{
 let calls=0;const o=await opts({maxNewRequests:1,fetchImpl:async(_,init)=>{calls++;return envelope(JSON.parse(init.body));}});
 const r=await executeContinuation(plan,o);assert.equal(calls,1);assert.equal(r.stopReason,"approved-request-cap");assert.ok(r.audit.returnedQuestions>=118);
 await assert.rejects(validateContinuation(r.runDir));
 await assert.rejects(executeContinuation(plan,o));assert.equal(calls,1);
});
test("HTTP, network, truncation and malformed JSON stop immediately without retries",async()=>{
 const cases=[async()=>({ok:false,status:403}),async()=>{throw Error("network");},async()=>({ok:true,status:200,json:async()=>({model:plan.basePlan.units[10].model,choices:[{finish_reason:"length",message:{content:"{}"}}]})}),async()=>({ok:true,status:200,json:async()=>({model:plan.basePlan.units[10].model,choices:[{finish_reason:"stop",message:{content:"bad"}}]})})];
 for(const fn of cases){let calls=0;const r=await executeContinuation(plan,await opts({fetchImpl:async()=>{calls++;return fn();}}));assert.equal(calls,1);assert.equal(r.status,"stopped");assert.equal(r.audit.returnedQuestions,118);assert.equal(r.submitted,false);}
});
test("repair groups bound image count, separate PDFs and preserve every target",()=>{
 const rows=[];const tasks=Array.from({length:13},(_,i)=>({unit:{mediaKind:i===12?"pdf":"image",requestIndex:i+1},questions:[{id:String(i)}],diagnostics:[]}));
 const groups=groupRepairTasks(tasks,rows);assert.equal(groups.flat().length,13);assert.equal(groups.length,4);
 for(const g of groups)assert.ok(g.length<=(g[0].unit.mediaKind==="pdf"?1:4));
});
