import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {verifySeed as verifyOriginal,verifyContinuationPlan,readJson,readJsonl,VERSION} from './continue-candidate.mjs';
import {normalizeFull,validateFull,auditFullResults} from './full-candidate.mjs';
import {parseModelAnswers} from './run.mjs';
import {sha256} from './reliability.mjs';
export const SEED_DIR=path.join(path.dirname(fileURLToPath(import.meta.url)),'continuation-runs/2026-09-24T14-30-08-662Z-456905b9');
export const SEED_HASHES={
 'plan.json':'1e528867fe08d23326a826139ff641e2504baf0ee97119de591565fff9f3c5f6',
 'report.json':'1fe210706a0580066ee16ce489f8c341333c652d3679a64e887c4b816a7cf955',
 'requests.jsonl':'7b4c48d509ae0617b01e1c84e9957b21180fd0949d673af9e5cde44a4fd7216c',
 'results.jsonl':'8bb884b0d378907407d3487184bb122153024d20bc6efc685aa557413b114e3f',
 'inference-trace.jsonl':'cd92817dd83d741074eff8eca13670e5a55185e7592b349d7e95fcf11323cbb9',
 'candidates.jsonl':'04d7a971c55d09c1c6d1f9c37a323e9a78d4ef0a5b0d6cc983ea7eeb26313ee1'};
export async function verifySeed(){
 for(const [n,h]of Object.entries(SEED_HASHES))assert.equal(sha256(await fs.readFile(path.join(SEED_DIR,n))),h);
 const continuation=await readJson(path.join(SEED_DIR,'plan.json'));await verifyContinuationPlan(continuation);
 const original=await verifyOriginal(),plan=continuation.basePlan,report=await readJson(path.join(SEED_DIR,'report.json'));
 const requests=await readJsonl(path.join(SEED_DIR,'requests.jsonl')),traces=await readJsonl(path.join(SEED_DIR,'inference-trace.jsonl'));
 const rows=await readJsonl(path.join(SEED_DIR,'results.jsonl'));const reconstructed=[...original.rows];
 assert.equal(report.totalRequests,68);assert.equal(report.baseCompleted,57);assert.equal(report.repairsMade,0);
 assert.equal(report.status,'stopped');assert.equal(report.stopReason,'truncated-or-empty-response');assert.deepEqual(requests,report.requests);
 assert.equal(requests.length,58);assert.equal(requests.at(-1).finishReason,'length');
 for(let i=0;i<57;i++){
   const unit=plan.units[i+10],req=requests[i];assert.equal(req.requestIndex,i+11);assert.equal(req.httpStatus,200);assert.equal(req.finishReason,'stop');assert.equal(req.resolvedModel,unit.model);
   const response=traces.find(t=>t.kind==='response'&&t.requestIndex===req.requestIndex),parsed=parseModelAnswers(response.content,unit.questions);
   for(const q of unit.questions){const answer=normalizeFull(q,parsed.get(q.id));reconstructed.push({id:q.id,answer,...validateFull(q,answer),runId:report.runId,requestIndex:req.requestIndex,stage:'base',model:unit.model,sourceFile:q.file_name,sourceUnitIndex:unit.requestIndex,provenance:VERSION,mediaSha256:unit.mediaSha256,promptSha256:unit.promptSha256});}
 }
 assert.deepEqual(rows,reconstructed);assert.equal(rows.length,688);assert.deepEqual(auditFullResults(plan,rows),report.audit);
 return{plan,report,rows};
}
