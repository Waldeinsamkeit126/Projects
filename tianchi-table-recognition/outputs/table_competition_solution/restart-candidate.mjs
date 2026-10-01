import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { verifyFullPlan, fullSourceHash, fullPrompt, normalizeFull, validateFull, auditFullResults, VERSION as BASE_VERSION } from "./full-candidate.mjs";
import { parseModelAnswers } from "./run.mjs";
import { sha256, assertProvider, SYSTEM_PROMPT } from "./reliability.mjs";
import { createRedactor, protectResult } from "./inference-trace.mjs";
import { makeMediaBlock } from "./development/real-array-trial.mjs";

import {verifySeed,SEED_DIR,SEED_HASHES} from "./restart-seed.mjs";
export const VERSION="bounded-restart-v2";
const root=path.dirname(fileURLToPath(import.meta.url));
export const LIMITS=Object.freeze({totalRequests:94,priorRequests:68,newRequests:26,baseRequests:23,repairRequests:3,outputTokens:16384,concurrency:1,retries:0,repairImagesPerRequest:4,repairPriorAnswerCharBudget:18000,repairPdfPerRequest:1});
export const readJson=async p=>JSON.parse(await fs.readFile(p,"utf8"));
export const readJsonl=async p=>(await fs.readFile(p,"utf8")).trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);
export const scopeRule="\n范围限制：仅要求表头结构时，cells 只列所问表头单元格，不能扩展为整表内容；row_count/col_count 仍按该表全局逻辑尺寸。仅返回本次问题清单中的答案，不附解释或重复题干。";
async function sourceHash(){return sha256(JSON.stringify({base:await fullSourceHash(),files:await Promise.all(["restart-candidate.mjs","restart-candidate.ps1","restart-seed.mjs","continue-candidate.mjs"].map(async n=>[n,sha256(await fs.readFile(path.join(root,n)))]))}));}
export async function createContinuationPlan(){
 const seed=await verifySeed(),unit=seed.plan.units[67];
 const baseTasks=[{unitIndex:68,questionIds:unit.questions.filter(q=>q.answer_format!=="json").map(q=>q.id)},{unitIndex:68,questionIds:unit.questions.filter(q=>q.answer_format==="json").map(q=>q.id)},...seed.plan.units.slice(68).map(u=>({unitIndex:u.requestIndex,questionIds:u.questions.map(q=>q.id)}))];
 assert.equal(baseTasks.length,23);assert.equal(baseTasks[0].questionIds.length,9);assert.equal(baseTasks[1].questionIds.length,1);
 const payload={version:VERSION,sourceHash:await sourceHash(),seedDir:SEED_DIR,seedHashes:SEED_HASHES,basePlan:seed.plan,limits:LIMITS,baseTasks,adoptedQuestions:688,newBaseQuestions:220,historicalManualAnswersImported:false,automaticSubmission:false};
 return{...payload,digest:sha256(JSON.stringify(payload))};
}
export async function verifyContinuationPlan(plan){assert.deepEqual(plan,await createContinuationPlan());}
export function repairTasks(basePlan, rows) {
  const audit = auditFullResults(basePlan, rows), errors = new Map();
  for (const id of audit.missing) errors.set(id, "缺少答案");
  for (const { id, error } of audit.invalid) errors.set(id, error);
  for (const pair of audit.consistency.comparisons.filter(p => !p.consistent)) {
    for (const id of [pair.fullId, pair.headerId]) errors.set(id, "同表完整结构与局部结构不一致：" + JSON.stringify(pair.differences));
  }
  return basePlan.units.map(unit => ({ unit, questions: unit.questions.filter(q => errors.has(q.id)),
    diagnostics: unit.questions.filter(q => errors.has(q.id)).map(q => ({ id: q.id, error: errors.get(q.id) })) }))
    .filter(t => t.questions.length).sort((a,b) => b.questions.length - a.questions.length || a.unit.requestIndex - b.unit.requestIndex);
}
export function groupRepairTasks(tasks, rows) {
  const byId = new Map(rows.map(r => [r.id, r])), groups = [];
  for (const task of tasks) {
    const chars = task.questions.reduce((n,q) => n + (byId.get(q.id)?.answer?.length ?? 1000), 0);
    let group = task.unit.mediaKind === "image" ? groups.find(g => g[0].unit.mediaKind === "image" && g.length < LIMITS.repairImagesPerRequest
      && g.reduce((n,t)=>n+t.priorAnswerChars,0) + chars <= LIMITS.repairPriorAnswerCharBudget) : undefined;
    if (!group) { group = []; groups.push(group); }
    group.push({ ...task, priorAnswerChars: chars });
  }
  return groups;
}
export function repairPrompt(tasks) {
  const questions = tasks.flatMap(t => t.questions);
  const mapping = tasks.map((t,i) => ({ source: `source-${i+1}`, questionIds: t.questions.map(q=>q.id) }));
  return fullPrompt(questions) + "\n这是有限的格式/结构复核。请重新依据对应原始文件回答，不凭错误报告猜测表格内容。各源文件独立，不能跨文件取值。\n" +
    "json_array 必须是一层直接值数组，不含对象、null或嵌套数组。若题目要求的一个字段本身包含多个名称，该字段用一个字符串保留名称及顺序，不额外增加字段。完整结构检查所有逻辑格覆盖，空白真实单元格也计入；局部结构不擅自补全。\n" +
    "源文件与题号映射：" + JSON.stringify(mapping) + "\n自动校验诊断（不是正确答案）：" + JSON.stringify(tasks.flatMap(t=>t.diagnostics));
}

export async function executeContinuation(plan, options = {}) {
  await verifyContinuationPlan(plan);
  if (options.dryRun || !options.allowPaid) return { mode: "dry-run", apiRequests: 0, digest: plan.digest,
    priorRequests: 68, pendingRequests: 23, repairRequestCap: 3, newRequestCap: 26, totalCap: 94 };
  if (!Number.isSafeInteger(options.maxNewRequests) || options.maxNewRequests < 1 || options.maxNewRequests > 26) throw new Error("显式新额度必须为 1 至 26");
  if (!options.apiKey) throw new Error("缺少凭证");
  const baseUrl = options.baseUrl || "https://dashscope.aliyuncs.com/compatible-mode/v1";
  assertProvider(baseUrl, [plan.basePlan.settings.imageModel, plan.basePlan.settings.pdfModel]);
  const redact = createRedactor(options.apiKey), seed = await verifySeed();
  const outputRoot = path.resolve(options.outputRoot ?? path.join(root, "restart-runs"));
  const runId = `${new Date().toISOString().replace(/[:.]/g,"-")}-${crypto.randomBytes(4).toString("hex")}`;
  await fs.mkdir(outputRoot, { recursive: true });
  // Authorization-level lock: changing a plan cannot silently reset the 94-call budget.
  await fs.writeFile(path.join(outputRoot,"authorization-94-total-20260925.started.json"),JSON.stringify({runId,digest:plan.digest,maxNewRequests:options.maxNewRequests}),{flag:"wx"});
  const runDir = path.join(outputRoot,runId); await fs.mkdir(runDir);
  await fs.writeFile(path.join(runDir,"plan.json"),JSON.stringify(plan,null,2),{flag:"wx"});
  const append = (name,value) => fs.appendFile(path.join(runDir,name),JSON.stringify(redact(value))+"\n");
  const current = new Map(seed.rows.map(r=>[r.id,r])), requests = [];
  let stopReason = null, baseCompleted = 0, repairsMade = 0;
  const invoke = async (tasks,stage) => {
    if(requests.length >= options.maxNewRequests) throw new Error("approved-request-cap");
    const questions=tasks.flatMap(t=>t.questions), prompt=(stage==="base"?fullPrompt(questions):repairPrompt(tasks))+scopeRule;
    const content=[];
    for(const [i,t] of tasks.entries()) {
      const bytes=await fs.readFile(t.unit.mediaPath); assert.equal(sha256(bytes),t.unit.mediaSha256);
      if(stage==="repair") content.push({type:"text",text:`source-${i+1}，只用于题号 ${t.questions.map(q=>q.id).join(",")}`});
      content.push(makeMediaBlock(t.unit,bytes));
    }
    content.push({type:"text",text:prompt});
    const event={requestIndex:requests.length+69,stage,model:tasks[0].unit.model,questionIds:questions.map(q=>q.id),
      sourceUnitIndices:tasks.map(t=>t.unit.requestIndex),promptSha256:sha256(prompt),status:"prepared",apiRequestMade:false,usage:null};
    await append("inference-trace.jsonl",{kind:"request-prepared",...event,timestamp:new Date().toISOString(),
      tasks:tasks.map(t=>({unitIndex:t.unit.requestIndex,questionIds:t.questions.map(q=>q.id),diagnostics:t.diagnostics??[],mediaSha256:t.unit.mediaSha256}))});
    requests.push(event); event.apiRequestMade=true; event.status="error";
    options.onProgress?.({stage:"request-started",phase:stage,totalRequestIndex:event.requestIndex,questionCount:questions.length});
    const started=Date.now();
    try {
      const response=await (options.fetchImpl??fetch)(`${baseUrl.replace(/\/$/,"")}/chat/completions`,{
        method:"POST",redirect:"error",signal:AbortSignal.timeout(300_000),headers:{Authorization:`Bearer ${options.apiKey}`,"Content-Type":"application/json"},
        body:JSON.stringify({model:event.model,temperature:0,max_completion_tokens:16384,enable_thinking:false,response_format:{type:"json_object"},
          messages:[{role:"system",content:SYSTEM_PROMPT},{role:"user",content}]})});
      event.httpStatus=response.status; event.elapsedMs=Date.now()-started;
      if(!response.ok) throw new Error(`API HTTP ${response.status}`);
      let envelope;try{envelope=await response.json();}catch{throw new Error("API envelope is not JSON");}
      const choice=envelope?.choices?.[0],body=choice?.message?.content;
      event.usage=envelope.usage??null;event.finishReason=choice?.finish_reason??null;event.resolvedModel=envelope.model??null;
      await append("inference-trace.jsonl",{kind:"response",...event,content:typeof body==="string"?body:null});
      if(event.finishReason!=="stop"||typeof body!=="string")throw new Error("truncated-or-empty-response");
      if(event.resolvedModel!==event.model)throw new Error("unexpected-response-model");
      const parsed=parseModelAnswers(body,questions);
      const batch=tasks.flatMap(t=>t.questions.map(q=>{
        const answer=normalizeFull(q,parsed.get(q.id));
        return protectResult({id:q.id,answer,...validateFull(q,answer),runId,requestIndex:event.requestIndex,stage,model:event.model,
          sourceFile:q.file_name,sourceUnitIndex:t.unit.requestIndex,provenance:VERSION,mediaSha256:t.unit.mediaSha256,promptSha256:event.promptSha256},options.apiKey);
      }));
      // Base responses always retained, including invalid ones. Repairs replace only a whole validated task.
      const adoptedIds=[];
      for(const task of tasks){
        const ids=new Set(task.questions.map(q=>q.id)),candidate=batch.filter(r=>ids.has(r.id));
        const peers=task.unit.questions.map(q=>candidate.find(r=>r.id===q.id)??current.get(q.id)).filter(Boolean);
        const canAdopt=stage==="base"||auditFullResults({units:[task.unit]},peers).complete;
        if(canAdopt)for(const row of candidate){current.set(row.id,row);adoptedIds.push(row.id);}
      }
      for(const row of batch)await append("candidates.jsonl",{...row,adopted:adoptedIds.includes(row.id)});
      event.adoptedIds=adoptedIds;event.invalidCount=batch.filter(r=>!r.valid).length;
      event.status=event.invalidCount?"validation-issues-recorded":"format-checked-not-proven-correct";
      await append("requests.jsonl",event);
      options.onProgress?.({phase:stage,totalRequestIndex:event.requestIndex,returnedQuestions:current.size,invalidInResponse:event.invalidCount,adopted:adoptedIds.length,usage:event.usage});
      return batch;
    }catch(error){event.error=redact(String(error.message));await append("requests.jsonl",event);throw error;}
  };
  try {
    for(const task of plan.baseTasks){const unit=plan.basePlan.units[task.unitIndex-1];const questions=unit.questions.filter(q=>task.questionIds.includes(q.id));await invoke([{unit,questions}],"base");baseCompleted++;}
    const groups=groupRepairTasks(repairTasks(plan.basePlan,[...current.values()]),[...current.values()]);
    await fs.writeFile(path.join(runDir,"repair-schedule.json"),JSON.stringify(groups.map(g=>g.map(t=>({unitIndex:t.unit.requestIndex,questionIds:t.questions.map(q=>q.id),diagnostics:t.diagnostics,priorAnswerChars:t.priorAnswerChars}))),null,2),{flag:"wx"});
    for(const group of groups.slice(0,3)){await invoke(group,"repair");repairsMade++;}
  } catch(error) {stopReason=redact(String(error.message));}
  const rows=plan.basePlan.questionOrder.map(id=>current.get(id)).filter(Boolean),audit=auditFullResults(plan.basePlan,rows);
  await fs.writeFile(path.join(runDir,"results.jsonl"),rows.map(r=>JSON.stringify(redact(r))).join("\n")+"\n",{flag:"wx"});
  const report=redact({version:VERSION,runId,planDigest:plan.digest,sourceHash:plan.sourceHash,priorRequests:68,newRequests:requests.length,
    totalRequests:requests.length+68,maxNewRequests:options.maxNewRequests,baseCompleted,repairsMade,requests,stopReason,audit,
    status:stopReason?"stopped":audit.complete?"complete-awaiting-export-review":"needs-more-repair-no-export",
    resultsSha256:sha256(await fs.readFile(path.join(runDir,"results.jsonl"))),exported:false,submitted:false,groundTruthAccuracy:null});
  await fs.writeFile(path.join(runDir,"report.json"),JSON.stringify(report,null,2),{flag:"wx"});
  return {...report,runDir};
}

async function main(argv){
  const flags=new Set(["--dry-run","--allow-paid"]),keys=new Set(["--plan","--write-plan","--max-new-requests"]),args={};
  for(let i=0;i<argv.length;i++){const key=argv[i];if(Object.hasOwn(args,key)||(!flags.has(key)&&!keys.has(key)))throw Error("未知参数");args[key]=flags.has(key)?true:argv[++i];if(!args[key]||String(args[key]).startsWith("--"))throw Error("缺少参数值");}
  if(args["--write-plan"]){if(Object.keys(args).length!==1)throw Error("不得在冻结计划时付费");const p=await createContinuationPlan();await fs.writeFile(path.resolve(args["--write-plan"]),JSON.stringify(p,null,2),{flag:"wx"});console.log(JSON.stringify({mode:"plan-only",digest:p.digest,limits:p.limits}));return;}
  if(!args["--plan"])throw Error("缺少计划");
  const dryRun=!!args["--dry-run"]||!args["--allow-paid"];
  const result=await executeContinuation(await readJson(path.resolve(args["--plan"])),{dryRun,allowPaid:!!args["--allow-paid"],maxNewRequests:Number(args["--max-new-requests"]),
    apiKey:dryRun?undefined:process.env.DASHSCOPE_API_KEY,baseUrl:dryRun?undefined:process.env.ALIYUN_BASE_URL||(process.env.ALIYUN_WORKSPACE_ID?`https://${process.env.ALIYUN_WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`:undefined),onProgress:v=>console.log(JSON.stringify(v))});
  console.log(JSON.stringify(result.mode?result:{runDir:result.runDir,status:result.status,newRequests:result.newRequests,totalRequests:result.totalRequests,baseCompleted:result.baseCompleted,repairsMade:result.repairsMade,stopReason:result.stopReason,returned:result.audit.returnedQuestions,missing:result.audit.missing.length,invalid:result.audit.invalid,conflicts:result.audit.consistency.conflictCount},null,2));
  if(!result.mode&&result.status!=="complete-awaiting-export-review")process.exitCode=2;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))main(process.argv.slice(2)).catch(()=>{console.error("续跑未执行或中止；检查冻结计划/日志/授权锁，未自动重试。");process.exitCode=1;});
