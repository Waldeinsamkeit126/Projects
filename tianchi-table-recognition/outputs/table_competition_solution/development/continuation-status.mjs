import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const lock=JSON.parse(await fs.readFile(path.join(root,'continuation-runs/authorization-94-total-20260924.started.json'),'utf8'));
const dir=path.join(root,'continuation-runs',lock.runId);
async function lines(name){try{return(await fs.readFile(path.join(dir,name),'utf8')).trim().split(/\r?\n/).filter(Boolean).map(JSON.parse);}catch(e){if(e.code==='ENOENT')return[];throw e;}}
const requests=await lines('requests.jsonl'), candidates=await lines('candidates.jsonl');
const errors={};for(const r of candidates.filter(r=>!r.valid))errors[r.error??'unknown']=(errors[r.error??'unknown']??0)+1;
let report;try{report=JSON.parse(await fs.readFile(path.join(dir,'report.json'),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
console.log(JSON.stringify({runDir:dir,completedNewRequests:requests.length,latestRequest:requests.at(-1)?.requestIndex,
  returnedBaseQuestions:118+candidates.filter(r=>r.stage==='base').length,invalidCandidateReasons:errors,
  tokens:requests.reduce((n,r)=>n+(r.usage?.total_tokens??0),0),status:report?.status??'running',
  stopReason:report?.stopReason,missing:report?.audit.missing.length,invalid:report?.audit.invalid.length,
  conflicts:report?.audit.consistency.conflictCount},null,2));
