import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createFullPlan, executeFullPlan, fullPrompt, publicQuestions, normalizeFull, validateFull, auditFullResults, SETTINGS } from "./full-candidate.mjs";
import { buildPrompt } from "./run.mjs";

const plan = await createFullPlan();
const secret = "unit-test-secret";
const tmp = () => fs.mkdtemp(path.join(os.tmpdir(), "tianchi-full-test-"));
const fakeAnswer = q => q.answer_format === "json_array" ? ["001", 1, true, ""] : q.answer_format === "json"
  ? { row_count: 1, col_count: 1, cells: [{ text: "mock", row: 0, col: 0, rowspan: 1, colspan: 1 }] }
  : q.answer_format === "number" ? "1" : "mock";
const responseFor = (unit, overrides = {}) => ({ ok: true, status: 200, json: async () => ({ model: unit.model,
  choices: [{ finish_reason: "stop", message: { content: JSON.stringify({ answers: unit.questions.map(q => ({ id: q.id, answer: fakeAnswer(q) })) }) } }],
  usage: { prompt_tokens: 10, completion_tokens: 10, total_tokens: 20 }, ...overrides }) });
const opts = async extra => ({ allowPaid: true, maxRequests: 89, apiKey: secret, outputRoot: await tmp(), ...extra });

test("frozen scope has 908 unique IDs, 89 physical sources and no labels", () => {
  assert.equal(plan.questionCount, 908); assert.equal(plan.units.length, 89);
  assert.equal(new Set(plan.units.map(u => u.mediaPath)).size, 89);
  assert.equal(new Set(plan.questionOrder).size, 908);
  assert.equal(plan.units.filter(u => u.mediaKind === "pdf").length, 24);
  assert.deepEqual(plan.settings, SETTINGS);
  for (const unit of plan.units) for (const q of unit.questions) assert.deepEqual(Object.keys(q), ["id", "file_name", "question_type", "question", "table_hint", "answer_format"]);
});
test("mixed prompt changes only array rule and drops hidden keys", () => {
  const rows = plan.units.flatMap(u => u.questions).slice(0, 20).map(q => ({ ...q, answer: "FORBIDDEN_LABEL", expected: "FORBIDDEN_LABEL" }));
  const before = buildPrompt(publicQuestions(rows)).split("\n"), after = fullPrompt(rows).split("\n");
  assert.equal(before.length, after.length); assert.equal(before.filter((x,i)=>x!==after[i]).length, 1);
  assert.ok(!fullPrompt(rows).includes("FORBIDDEN_LABEL"));
});
test("format dispatch preserves arrays and enforces numbers, structure bounds and coverage", () => {
  const arrayQ={answer_format:"json_array"};
  const a=normalizeFull(arrayQ,["001",1,true,""]); assert.equal(a,'["001",1,true,""]'); assert.equal(validateFull(arrayQ,a).valid,true);
  for(const v of ["[null]", '[{"x":"1"}]', "[[1]]", ""]) assert.equal(validateFull(arrayQ,v).valid,false);
  assert.equal(validateFull({answer_format:"number"},"1 yuan").valid,false);
  const q={answer_format:"json",question_type:"structure",question:"请恢复完整表格结构"};
  const s={row_count:2,col_count:1,cells:[{text:"mock",row:0,col:0,rowspan:1,colspan:1}]};
  assert.equal(validateFull(q,JSON.stringify(s)).valid,false);
  s.cells[0].rowspan=3; assert.equal(validateFull(q,JSON.stringify(s)).valid,false);
});
test("default dry run creates no paid artifacts or requests", async () => {
  let calls=0; const o=await opts({allowPaid:false,fetchImpl:async()=>{calls++;throw Error("unexpected");}});
  assert.equal((await executeFullPlan(plan,o)).apiRequests,0); assert.equal(calls,0); assert.deepEqual(await fs.readdir(o.outputRoot),[]);
});
test("modified plan, absent budget/key, out-of-range budget and non-Aliyun endpoint fail before fetch", async () => {
  let calls=0; const base=await opts({fetchImpl:async()=>{calls++;}});
  const altered=structuredClone(plan); altered.settings.maxCompletionTokens++;
  await assert.rejects(executeFullPlan(altered,base));
  for(const extra of [{maxRequests:undefined},{maxRequests:90},{maxRequests:0},{apiKey:""},{baseUrl:"https://example.com"}]) await assert.rejects(executeFullPlan(plan,{...base,...extra}));
  assert.equal(calls,0);
});
test("all 89 mock requests obey limits and produce a complete independently audited set", async () => {
  let calls=0;
  const result=await executeFullPlan(plan,await opts({fetchImpl:async (url,init)=>{
    assert.equal(init.method,"POST"); assert.equal(init.redirect,"error"); assert.ok(url.startsWith("https://dashscope.aliyuncs.com/"));
    const body=JSON.parse(init.body),unit=plan.units[calls++];
    assert.equal(body.max_completion_tokens,16384); assert.equal(body.enable_thinking,false); assert.equal(body.model,unit.model);
    assert.equal(body.messages[1].content[1].text,fullPrompt(unit.questions));
    if(unit.mediaKind==="pdf") assert.equal(body.messages[1].content[0].file.filename,"source.pdf");
    return responseFor(unit);
  }}));
  assert.equal(calls,89); assert.equal(result.audit.complete,true); assert.equal(result.audit.returnedQuestions,908);
  assert.equal(result.status,"complete-awaiting-export-review"); assert.equal(result.exported,false); assert.equal(result.submitted,false);
});
test("smaller cap stops and paid-plan lock prevents replay", async () => {
  let calls=0; const o=await opts({maxRequests:1,fetchImpl:async()=>responseFor(plan.units[calls++])});
  const r=await executeFullPlan(plan,o); assert.equal(calls,1); assert.equal(r.stopReason,"request-cap"); assert.equal(r.audit.complete,false);
  await assert.rejects(executeFullPlan(plan,o)); assert.equal(calls,1);
});
test("HTTP, network, truncation, missing IDs, duplicate IDs, wrong model and invalid formats each stop without retry", async () => {
  const unit=plan.units[0], valid=await responseFor(unit).json();
  const bads=[async()=>({ok:false,status:429}),async()=>{throw Error("network");},
    async()=>responseFor(unit,{choices:[{finish_reason:"length",message:{content:"{}"}}]}),
    async()=>responseFor(unit,{choices:[{finish_reason:"stop",message:{content:'{"answers":[]}'}}]}),
    async()=>responseFor(unit,{choices:[{finish_reason:"stop",message:{content:JSON.stringify({answers:[{id:unit.questions[0].id,answer:"mock"},{id:unit.questions[0].id,answer:"mock"}]})}}]}),
    async()=>responseFor(unit,{model:"not-the-model"}),
    async()=>responseFor(unit,{choices:[{finish_reason:"stop",message:{content:"not JSON"}}]})];
  for(const fn of bads){let calls=0;const r=await executeFullPlan(plan,await opts({fetchImpl:async()=>{calls++;return fn();}}));assert.equal(calls,1);assert.equal(r.status,"stopped");assert.equal(r.exported,false);}
});
test("credential-bearing answer is redacted and blocks completion",async()=>{
  const unit=plan.units[0]; let calls=0;
  const r=await executeFullPlan(plan,await opts({fetchImpl:async()=>{calls++;const envelope=await responseFor(unit).json();
    const content=JSON.parse(envelope.choices[0].message.content);content.answers[0].answer=secret;envelope.choices[0].message.content=JSON.stringify(content);
    return {ok:true,status:200,json:async()=>envelope};}}));
  assert.equal(calls,1);assert.equal(r.status,"stopped");
  for(const name of ["results.jsonl","inference-trace.jsonl","report.json"]) assert.ok(!(await fs.readFile(path.join(r.runDir,name),"utf8")).includes(secret));
});
test("submission gate rejects missing, duplicate, unknown or invalid answers",()=>{
  const unit=plan.units[0],mini={units:[unit]};
  const rows=unit.questions.map(q=>({id:q.id,answer:normalizeFull(q,fakeAnswer(q)),valid:true}));
  assert.equal(auditFullResults(mini,rows).complete,true);
  assert.equal(auditFullResults(mini,rows.slice(1)).complete,false);
  assert.throws(()=>auditFullResults(mini,[...rows,rows[0]]));
  assert.throws(()=>auditFullResults(mini,[...rows,{id:"unknown",answer:"x",valid:true}]));
  assert.equal(auditFullResults(mini,rows.map((r,i)=>i?r:{...r,answerRedacted:true})).complete,false);
});
