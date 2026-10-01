import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { buildPrompt, normalizeAnswer, validateAnswer, validateForInference, parseModelAnswers, resolveMediaFiles } from "./run.mjs";
import { sha256, inferenceSourceHash, assertProvider, assertUniqueQuestions, SYSTEM_PROMPT } from "./reliability.mjs";
import { inspectStructureConsistency } from "./structure-consistency.mjs";
import { createRedactor, protectResult } from "./inference-trace.mjs";
import { VALUE_ARRAY_RULE, normalizeValueArray, validateValueArray } from "./development/array-value-contract.mjs";
import { readOfficialMetadata, makeMediaBlock } from "./development/real-array-trial.mjs";

export const VERSION = "full-automated-value-array-v1";
const root = path.dirname(fileURLToPath(import.meta.url));
export const SETTINGS = Object.freeze({ imageModel: "qwen3-vl-plus", pdfModel: "qwen3.8-max", maxRequests: 89,
  maxCompletionTokens: 16384, temperature: 0, enableThinking: false, concurrency: 1, maxAttempts: 1,
  automaticFallback: false, checkFullCoverage: true, checkStructureConsistency: true });
const publicKeys = ["id", "file_name", "question_type", "question", "table_hint", "answer_format"];

export function publicQuestions(rows) {
  assertUniqueQuestions(rows);
  return rows.map(q => {
    if (!q.question || !q.file_name || !["json", "json_array", "number", "string"].includes(q.answer_format)) throw new Error("题目元数据不完整或格式未知");
    return Object.fromEntries(publicKeys.map(k => [k, String(q[k] ?? "")]));
  });
}
export function fullPrompt(rows) {
  const lines = buildPrompt(publicQuestions(rows)).split("\n");
  const indices = lines.flatMap((line, i) => line.startsWith("2. answer_format=json_array：") ? [i] : []);
  if (indices.length !== 1) throw new Error("提示规则边界改变");
  lines[indices[0]] = VALUE_ARRAY_RULE;
  return lines.join("\n");
}
export const normalizeFull = (q, value) => q.answer_format === "json_array" ? normalizeValueArray(value) : normalizeAnswer(q, value);
export const validateFull = (q, answer) => q.answer_format === "json_array" ? validateValueArray(answer) : validateForInference(q, answer, SETTINGS);

export async function fullSourceHash() {
  const names = ["full-candidate.mjs", "full-candidate.ps1", "development/array-value-contract.mjs", "development/real-array-trial.mjs"];
  return sha256(JSON.stringify({ core: await inferenceSourceHash(root), files: await Promise.all(names.map(async n => [n, sha256(await fs.readFile(path.join(root, n)))])) }));
}
export async function createFullPlan() {
  const { questions: source, inputSha256, source: sourceRange } = await readOfficialMetadata();
  const questions = publicQuestions(source);
  const mediaDir = await fs.realpath(path.resolve(root, "../../work/competition_data/multimodal_table_recognition/files"));
  const { resolved, unresolved } = await resolveMediaFiles(questions, mediaDir);
  if (unresolved.length) throw new Error("媒体路径缺失");
  const groups = new Map();
  for (const q of questions) {
    const p = await fs.realpath(resolved.get(q.file_name));
    if (path.dirname(p) !== mediaDir) throw new Error("媒体路径越界");
    if (!groups.has(p)) groups.set(p, []);
    groups.get(p).push(q);
  }
  const units = [];
  // Stable workbook order, one physical source per request. No answer-based selection.
  for (const [mediaPath, rows] of groups) {
    const bytes = await fs.readFile(mediaPath);
    if (!/\.(pdf|png|jpe?g|webp)$/i.test(mediaPath) || bytes.length > 20 * 1024 * 1024) throw new Error("媒体类型或大小超限");
    const mediaKind = path.extname(mediaPath).toLowerCase() === ".pdf" ? "pdf" : "image";
    units.push({ requestIndex: units.length + 1, mediaPath, mediaKind, model: mediaKind === "pdf" ? SETTINGS.pdfModel : SETTINGS.imageModel,
      mediaBytes: bytes.length, mediaSha256: sha256(bytes), promptSha256: sha256(fullPrompt(rows)), questions: rows });
  }
  if (questions.length !== 908 || units.length !== 89) throw new Error("全量范围与用户批准的范围不符");
  const payload = { version: VERSION, sourceHash: await fullSourceHash(), inputSha256, source: sourceRange,
    templatePath: "D:/submit-template.xlsx", templateSha256: sha256(await fs.readFile("D:/submit-template.xlsx")),
    settings: SETTINGS, mediaDir, questionCount: questions.length, questionOrder: questions.map(q => q.id), units,
    historicalAnswersImported: false, referenceLabelsAvailable: false, automaticSubmission: false };
  return { ...payload, digest: sha256(JSON.stringify(payload)) };
}
export async function verifyFullPlan(plan) {
  if (JSON.stringify(await createFullPlan()) !== JSON.stringify(plan)) throw new Error("计划、代码、输入或媒体指纹改变");
}
export function auditFullResults(plan, rows) {
  const questions = plan.units.flatMap(u => u.questions), byId = new Map();
  assertUniqueQuestions(questions);
  const expected = new Set(questions.map(q => q.id));
  for (const row of rows) {
    if (!expected.has(row.id) || byId.has(row.id)) throw new Error("结果存在重复或未知题号");
    byId.set(row.id, row);
  }
  const missing = [], invalid = [];
  for (const q of questions) {
    const row = byId.get(q.id);
    if (!row) missing.push(q.id);
    else {
      const v = validateFull(q, row.answer);
      if (!v.valid || row.valid !== true || row.answerRedacted) invalid.push({ id: q.id, error: v.error ?? row.error ?? "无效标记" });
    }
  }
  const consistency = inspectStructureConsistency(questions, rows, normalizeFull, validateAnswer);
  return { complete: missing.length === 0 && invalid.length === 0 && consistency.conflictCount === 0,
    expectedQuestions: questions.length, returnedQuestions: rows.length, missing, invalid, consistency };
}

export async function executeFullPlan(plan, options = {}) {
  await verifyFullPlan(plan);
  if (options.dryRun || !options.allowPaid) return { mode: "dry-run", apiRequests: 0, planDigest: plan.digest,
    questionCount: plan.questionCount, requests: plan.units.length, settings: plan.settings };
  if (!Number.isSafeInteger(options.maxRequests) || options.maxRequests < 1 || options.maxRequests > SETTINGS.maxRequests) throw new Error("缺少合法显式请求上限");
  if (!options.apiKey) throw new Error("缺少进程凭证");
  const baseUrl = options.baseUrl || "https://dashscope.aliyuncs.com/compatible-mode/v1";
  assertProvider(baseUrl, [SETTINGS.imageModel, SETTINGS.pdfModel]);
  const redact = createRedactor(options.apiKey);
  const outputRoot = path.resolve(options.outputRoot ?? path.join(root, "full-candidate-runs"));
  const runId = `${new Date().toISOString().replace(/[:.]/g, "-")}-${crypto.randomBytes(4).toString("hex")}`;
  await fs.mkdir(outputRoot, { recursive: true });
  await fs.writeFile(path.join(outputRoot, `${plan.digest}.started.json`), JSON.stringify({ runId, planDigest: plan.digest, maxRequests: options.maxRequests }), { flag: "wx" });
  const runDir = path.join(outputRoot, runId); await fs.mkdir(runDir);
  await fs.writeFile(path.join(runDir, "plan.json"), JSON.stringify(plan, null, 2), { flag: "wx" });
  const append = async (name, value) => fs.appendFile(path.join(runDir, name), JSON.stringify(redact(value)) + "\n");
  const requests = [], rows = [];
  let stopReason = null;
  for (const unit of plan.units) {
    if (requests.length >= options.maxRequests) { stopReason = "request-cap"; break; }
    const event = { requestIndex: unit.requestIndex, questionIds: unit.questions.map(q => q.id), model: unit.model,
      status: "prepared", apiRequestMade: false, usage: null };
    try {
      const bytes = await fs.readFile(unit.mediaPath), prompt = fullPrompt(unit.questions);
      if (sha256(bytes) !== unit.mediaSha256 || sha256(prompt) !== unit.promptSha256) throw new Error("本批媒体或提示指纹变化");
      await append("inference-trace.jsonl", { kind: "request-prepared", timestamp: new Date().toISOString(), ...event,
        mediaSha256: unit.mediaSha256, promptSha256: unit.promptSha256 });
      requests.push(event); event.apiRequestMade = true; event.status = "error";
      options.onProgress?.({ stage: "request-started", requestIndex: event.requestIndex, total: plan.units.length, questions: unit.questions.length });
      const started = Date.now();
      const response = await (options.fetchImpl ?? fetch)(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
        method: "POST", redirect: "error", signal: AbortSignal.timeout(300_000),
        headers: { Authorization: `Bearer ${options.apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model: unit.model, temperature: 0, max_completion_tokens: SETTINGS.maxCompletionTokens,
          enable_thinking: false, response_format: { type: "json_object" }, messages: [
            { role: "system", content: SYSTEM_PROMPT },
            { role: "user", content: [makeMediaBlock(unit, bytes), { type: "text", text: prompt }] }
          ] })
      });
      event.httpStatus = response.status; event.elapsedMs = Date.now() - started;
      if (!response.ok) throw new Error(`API HTTP ${response.status}`);
      let envelope;
      try { envelope = await response.json(); } catch { throw new Error("API 信封不是 JSON"); }
      const choice = envelope?.choices?.[0], content = choice?.message?.content;
      event.usage = envelope.usage ?? null; event.finishReason = choice?.finish_reason ?? null; event.resolvedModel = envelope.model ?? null;
      await append("inference-trace.jsonl", { kind: "response", ...event, content: typeof content === "string" ? content : null });
      if (event.finishReason !== "stop" || typeof content !== "string") throw new Error("截断、异常停止或无正文");
      if (event.resolvedModel !== unit.model) throw new Error("响应模型与计划不匹配");
      const parsed = parseModelAnswers(content, unit.questions);
      const batch = unit.questions.map(q => {
        const answer = normalizeFull(q, parsed.get(q.id));
        return protectResult({ id: q.id, answer, ...validateFull(q, answer), runId, requestIndex: event.requestIndex,
          model: unit.model, sourceFile: q.file_name, provenance: VERSION, mediaSha256: unit.mediaSha256,
          promptSha256: unit.promptSha256 }, options.apiKey);
      });
      for (const row of batch) await append("results.jsonl", row);
      rows.push(...batch);
      const batchAudit = auditFullResults({ units: [unit] }, batch);
      event.status = batchAudit.complete ? "format-checked-not-proven-correct" : "validation-failed";
      event.invalid = batchAudit.invalid;
      event.structureConflicts = batchAudit.consistency.conflictCount;
      await append("requests.jsonl", event);
      options.onProgress?.({ stage: event.status, requestIndex: event.requestIndex, total: plan.units.length, returnedQuestions: rows.length,
        invalid: batchAudit.invalid.length, structureConflicts: event.structureConflicts, usage: event.usage });
      if (!batchAudit.complete) { stopReason = "missing-invalid-or-inconsistent-answer"; break; }
    } catch (error) {
      stopReason = "request-parse-or-audit-error"; event.error = redact(String(error.message));
      await append("requests.jsonl", event);
      break;
    }
  }
  const audit = auditFullResults(plan, rows);
  const report = redact({ version: VERSION, runId, planDigest: plan.digest, sourceHash: plan.sourceHash, inputSha256: plan.inputSha256,
    status: !stopReason && audit.complete ? "complete-awaiting-export-review" : "stopped", stopReason,
    maxRequests: options.maxRequests, apiRequests: requests.length, requests, audit, exported: false, submitted: false,
    historicalAnswersImported: false, groundTruthAccuracy: null });
  await fs.writeFile(path.join(runDir, "report.json"), JSON.stringify(report, null, 2), { flag: "wx" });
  return { ...report, runDir };
}

async function main(argv) {
  const flags = new Set(["--dry-run", "--allow-paid"]), values = new Set(["--write-plan", "--plan", "--max-requests"]), args = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (Object.hasOwn(args, key) || (!flags.has(key) && !values.has(key))) throw new Error("未知或重复参数");
    args[key] = flags.has(key) ? true : argv[++i];
    if (!args[key] || String(args[key]).startsWith("--")) throw new Error("缺少参数值");
  }
  if (args["--write-plan"]) {
    if (Object.keys(args).length !== 1) throw new Error("冻结计划不能同时付费");
    const plan = await createFullPlan();
    await fs.writeFile(path.resolve(args["--write-plan"]), JSON.stringify(plan, null, 2), { flag: "wx" });
    console.log(JSON.stringify({ mode: "plan-only", apiRequests: 0, digest: plan.digest, questionCount: plan.questionCount, requests: plan.units.length }));
    return;
  }
  if (!args["--plan"]) throw new Error("缺少计划");
  const dryRun = Boolean(args["--dry-run"]) || !args["--allow-paid"];
  const result = await executeFullPlan(JSON.parse(await fs.readFile(path.resolve(args["--plan"]))), {
    dryRun, allowPaid: Boolean(args["--allow-paid"]), maxRequests: Number(args["--max-requests"]),
    apiKey: dryRun ? undefined : process.env.DASHSCOPE_API_KEY,
    baseUrl: dryRun ? undefined : process.env.ALIYUN_BASE_URL || (process.env.ALIYUN_WORKSPACE_ID ? `https://${process.env.ALIYUN_WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` : undefined),
    onProgress: value => console.log(JSON.stringify(value)) });
  console.log(JSON.stringify({ mode: result.mode, status: result.status, apiRequests: result.apiRequests, planDigest: result.planDigest,
    questionCount: result.questionCount, requests: result.mode ? result.requests : undefined, settings: result.settings,
    runDir: result.runDir, stopReason: result.stopReason, returnedQuestions: result.audit?.returnedQuestions,
    missing: result.audit?.missing.length, invalid: result.audit?.invalid, structureConflicts: result.audit?.consistency.conflictCount }, null, 2));
  if (result.status === "stopped") process.exitCode = 2;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch(() => { console.error("全量候选未执行或中止：检查冻结计划、运行锁及脱敏报告；没有自动重试。"); process.exitCode = 1; });
}
