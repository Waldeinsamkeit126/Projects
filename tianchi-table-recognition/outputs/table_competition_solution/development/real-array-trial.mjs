import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { normalizeQuestion, resolveMediaFiles, parseModelAnswers } from "../run.mjs";
import { sha256, inferenceSourceHash, assertUniqueQuestions, assertProvider, SYSTEM_PROMPT } from "../reliability.mjs";
import { createRedactor, protectResult } from "../inference-trace.mjs";
import { publicArrayQuestions, buildValueArrayPrompt, normalizeValueArray, validateValueArray } from "./array-value-contract.mjs";

export const VERSION = "official-array-stratified-pilot-v1";
const directory = path.dirname(fileURLToPath(import.meta.url)), root = path.dirname(directory);
const testsPath = "D:/tests.xlsx";
const mediaDir = path.resolve(root, "../../work/competition_data/multimodal_table_recognition/files");
const endpointDefault = "https://dashscope.aliyuncs.com/compatible-mode/v1";
const strata = ["image/extract", "image/thinking", "pdf/extract", "pdf/thinking"];
const settings = { imageModel: "qwen3-vl-plus", pdfModel: "qwen3.8-max", maxCompletionTokens: 4096,
  temperature: 0, enableThinking: false, maxAttempts: 1, maxRequests: 4, maxQuestionsPerFile: 3,
  concurrency: 1, automaticFallback: false };
const kind = (name) => path.extname(name).toLowerCase() === ".pdf" ? "pdf" : "image";
const stableKey = (q) => sha256(JSON.stringify([VERSION, q.file_name, q.question_type, q.question, q.table_hint]));

export async function readOfficialMetadata() {
  const bytes = await fs.readFile(testsPath);
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(testsPath));
  const metadata = (await wb.inspect({ kind: "sheet", include: "id,name" })).ndjson.trim().split("\n").map(JSON.parse);
  const sheetInfo = metadata.find((r) => r.kind === "sheet" && r.index === 0);
  const match = /:G(\d+)$/.exec(sheetInfo?.range ?? "");
  if (!match || Number(match[1]) !== 909) throw new Error("正式题表范围改变，需重新核对");
  const rows = wb.worksheets.getItemAt(0).getRange("A1:F909").values;
  const headers = rows.shift();
  if (headers.join("|") !== "id|file_name|question_type|question|table_hint|answer_format") throw new Error("题目元数据列不匹配");
  const questions = rows.map((row) => normalizeQuestion(Object.fromEntries(headers.map((h, i) => [h, row[i]]))));
  assertUniqueQuestions(questions);
  if (questions.length !== 908 || sha256(await fs.readFile(testsPath)) !== sha256(bytes)) throw new Error("题表在读取中发生变化");
  // Answer column G is never retrieved, logged or included in model input.
  return { questions, inputSha256: sha256(bytes), source: { path: testsPath, sheet: sheetInfo.name, range: "A2:F909", answerColumnRead: false } };
}

// Deterministic metadata-only stratification. No images, predictions, labels or leaderboard feedback select questions.
export function selectRealArrayUnits(rawQuestions, resolved) {
  const questions = rawQuestions.map(normalizeQuestion);
  assertUniqueQuestions(questions);
  const arrays = publicArrayQuestions(questions.filter((q) => q.answer_format === "json_array"));
  const usedPaths = new Set(), units = [], counts = {};
  for (const stratum of strata) {
    const candidates = arrays.filter((q) => `${kind(q.file_name)}/${q.question_type}` === stratum);
    counts[stratum] = candidates.length;
    const groups = new Map();
    for (const q of candidates) {
      const mediaPath = resolved.get(q.file_name);
      if (!mediaPath) throw new Error("正式数组题源文件未解析");
      if (usedPaths.has(mediaPath)) continue;
      if (!groups.has(mediaPath)) groups.set(mediaPath, []);
      groups.get(mediaPath).push(q);
    }
    // Prefer files with more questions within this stratum to cover up to three per request.
    // Hash is a deterministic tie-break, not evidence used to guess any answer.
    const eligible = [...groups.entries()].sort((a, b) => Math.min(3, b[1].length) - Math.min(3, a[1].length)
      || sha256(JSON.stringify([VERSION, a[1].map(stableKey).sort()])).localeCompare(sha256(JSON.stringify([VERSION, b[1].map(stableKey).sort()]))));
    if (!eligible.length) throw new Error(`缺少独立源文件分层：${stratum}`);
    const [mediaPath, peers] = eligible[0];
    const selected = peers.sort((a, b) => stableKey(a).localeCompare(stableKey(b)) || a.id.localeCompare(b.id)).slice(0, 3);
    usedPaths.add(mediaPath);
    units.push({ stratum, mediaPath, mediaKind: kind(selected[0].file_name),
      model: kind(selected[0].file_name) === "pdf" ? settings.pdfModel : settings.imageModel, questions: selected });
  }
  return { units, arrayQuestions: arrays.length, strata: counts };
}

async function sourceHash() {
  const candidate = await Promise.all(["array-value-contract.mjs", "real-array-trial.mjs", "real-array-trial.ps1"]
    .map(async (name) => [name, sha256(await fs.readFile(path.join(directory, name)))]));
  return sha256(JSON.stringify({ core: await inferenceSourceHash(root), candidate }));
}

export async function createRealArrayPlan() {
  const metadata = await readOfficialMetadata();
  const { resolved, unresolved } = await resolveMediaFiles(metadata.questions, mediaDir);
  if (unresolved.length) throw new Error("正式题目存在未解析媒体路径");
  const selected = selectRealArrayUnits(metadata.questions, resolved);
  const mediaRoot = await fs.realpath(mediaDir);
  for (const unit of selected.units) {
    unit.mediaPath = await fs.realpath(unit.mediaPath);
    if (path.dirname(unit.mediaPath) !== mediaRoot || !/\.(pdf|png|jpe?g|webp)$/i.test(unit.mediaPath)) throw new Error("媒体越出正式目录或类型不支持");
    const bytes = await fs.readFile(unit.mediaPath);
    if (bytes.length > 20 * 1024 * 1024) throw new Error("试验单文件超过保守的 20 MiB 限制");
    unit.mediaBytes = bytes.length;
    unit.mediaSha256 = sha256(bytes);
    unit.promptSha256 = sha256(buildValueArrayPrompt(unit.questions));
  }
  const payload = { version: VERSION, sourceHash: await sourceHash(), inputSha256: metadata.inputSha256, source: metadata.source,
    mediaDir: mediaRoot, settings, selection: { seed: VERSION, algorithm: "one-distinct-file-per-stratum; capped-count descending, metadata hash tie-break; up to 3 questions",
      arrayQuestions: selected.arrayQuestions, strata: selected.strata }, units: selected.units,
    proposedMaxRequests: 4, selectedQuestions: selected.units.reduce((n, u) => n + u.questions.length, 0),
    readsPriorAnswers: false, referenceLabelsAvailable: false, exportAllowed: false, submissionAllowed: false,
    note: "Official-data format/inference pilot only; no ground-truth accuracy, historical answer import, XLSX export or automatic submission. Plan is not spending authorization." };
  return { ...payload, digest: sha256(JSON.stringify(payload)) };
}

export async function verifyRealArrayPlan(plan) {
  if (JSON.stringify(await createRealArrayPlan()) !== JSON.stringify(plan)) throw new Error("正式数组计划、输入、媒体或代码指纹变化，拒绝执行");
}

export function makeMediaBlock(unit, bytes) {
  if (unit.mediaKind === "pdf") return { type: "file", file: { file_data: `data:application/pdf;base64,${bytes.toString("base64")}`, filename: "source.pdf" } };
  const mime = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp" }[path.extname(unit.mediaPath).toLowerCase()];
  if (!mime) throw new Error("不支持的图片类型");
  return { type: "image_url", image_url: { url: `data:${mime};base64,${bytes.toString("base64")}` } };
}

export async function executeRealArrayPlan(plan, options = {}) {
  await verifyRealArrayPlan(plan);
  if (options.dryRun || !options.allowPaid) return { mode: "dry-run", apiRequests: 0, planDigest: plan.digest,
    proposedMaxRequests: 4, selectedQuestions: plan.selectedQuestions, units: plan.units.map((u) => ({ stratum: u.stratum, model: u.model, questions: u.questions.length, mediaBytes: u.mediaBytes })) };
  if (!Number.isSafeInteger(options.maxRequests) || options.maxRequests < 1 || options.maxRequests > 4) throw new Error("显式请求额度必须为 1 到 4");
  if (!options.apiKey) throw new Error("缺少进程凭证");
  const baseUrl = options.baseUrl || endpointDefault;
  assertProvider(baseUrl, [settings.imageModel, settings.pdfModel]);
  const redact = createRedactor(options.apiKey);
  const outputRoot = path.resolve(options.outputRoot ?? path.join(root, "real-array-runs"));
  const runId = `${new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-")}-${crypto.randomBytes(4).toString("hex")}`;
  await fs.mkdir(outputRoot, { recursive: true });
  await fs.writeFile(path.join(outputRoot, `${plan.digest}.started.json`), JSON.stringify({ runId, planDigest: plan.digest, maxRequests: options.maxRequests }), { flag: "wx" });
  const runDir = path.join(outputRoot, runId); await fs.mkdir(runDir);
  await fs.writeFile(path.join(runDir, "plan.json"), JSON.stringify(plan, null, 2), { flag: "wx" });
  const requests = [], results = [];
  let stopReason = null;
  const append = async (name, data) => fs.appendFile(path.join(runDir, name), JSON.stringify(redact(data)) + "\n");
  for (const unit of plan.units) {
    if (requests.length >= options.maxRequests) { stopReason = "request-cap"; break; }
    const event = { requestIndex: requests.length + 1, stratum: unit.stratum, model: unit.model,
      questionIds: unit.questions.map((q) => q.id), status: "prepared", apiRequestMade: false, usage: null };
    try {
      const bytes = await fs.readFile(unit.mediaPath), prompt = buildValueArrayPrompt(unit.questions);
      if (sha256(bytes) !== unit.mediaSha256 || sha256(prompt) !== unit.promptSha256) throw new Error("本次媒体或提示指纹改变");
      await append("inference-trace.jsonl", { kind: "request-prepared", timestamp: new Date().toISOString(), ...event, mediaSha256: unit.mediaSha256, promptSha256: unit.promptSha256 });
      requests.push(event); event.apiRequestMade = true; event.status = "error";
      const started = Date.now();
      const response = await (options.fetchImpl ?? fetch)(`${baseUrl.replace(/\/$/, "")}/chat/completions`, {
        method: "POST", redirect: "error", signal: AbortSignal.timeout(180_000),
        headers: { Authorization: `Bearer ${options.apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model: unit.model, temperature: 0, max_completion_tokens: settings.maxCompletionTokens,
          enable_thinking: false, response_format: { type: "json_object" }, messages: [
            { role: "system", content: SYSTEM_PROMPT },
            { role: "user", content: [makeMediaBlock(unit, bytes), { type: "text", text: prompt }] },
          ] }),
      });
      event.httpStatus = response.status;
      if (!response.ok) throw new Error(`API HTTP ${response.status}`);
      let envelope;
      try { envelope = await response.json(); } catch { throw new Error("API 信封不是 JSON"); }
      event.elapsedMs = Date.now() - started;
      const choice = envelope?.choices?.[0], content = choice?.message?.content;
      event.usage = envelope.usage ?? null; event.finishReason = choice?.finish_reason ?? null; event.resolvedModel = envelope.model ?? unit.model;
      await append("inference-trace.jsonl", { kind: "response", ...event, content: typeof content === "string" ? content : null });
      if (event.finishReason !== "stop" || typeof content !== "string") throw new Error("输出截断、停止异常或无正文");
      const answers = parseModelAnswers(content, unit.questions);
      const batch = unit.questions.map((q) => {
        const answer = normalizeValueArray(answers.get(q.id));
        return protectResult({ id: q.id, answer, ...validateValueArray(answer), runId, requestIndex: event.requestIndex,
          model: event.resolvedModel, sourceFile: q.file_name, stratum: unit.stratum,
          provenance: "automated-qwen-official-array-candidate", mediaSha256: unit.mediaSha256, promptSha256: unit.promptSha256 }, options.apiKey);
      });
      for (const row of batch) await append("results.jsonl", row);
      results.push(...batch);
      event.status = batch.every((r) => r.valid) ? "format-passed-not-proven-correct" : "invalid-format";
      await append("requests.jsonl", event);
      if (event.status === "invalid-format") { stopReason = "missing-or-invalid-answer"; break; }
    } catch (error) {
      stopReason = "request-parse-or-audit-error"; event.error = redact(String(error.message));
      await append("requests.jsonl", event);
      break;
    }
  }
  const report = redact({ version: VERSION, runId, planDigest: plan.digest, sourceHash: plan.sourceHash, inputSha256: plan.inputSha256,
    settings, endpoint: baseUrl, maxRequests: options.maxRequests, apiRequests: requests.length, requests,
    status: stopReason ? "stopped" : "completed-candidates-only", stopReason, selectedQuestions: plan.selectedQuestions,
    returnedQuestions: results.length, validQuestions: results.filter((r) => r.valid).length,
    resultPath: path.join(runDir, "results.jsonl"), originalAnswersModified: false,
    exported: false, submitted: false, groundTruthAccuracy: null,
    note: "Formal data has no reference labels here. Format validity is not correctness and cannot be converted to expected leaderboard gain." });
  const reportPath = path.join(runDir, "report.json");
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), { flag: "wx" });
  return { ...report, reportPath };
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
    if (Object.keys(args).length !== 1) throw new Error("计划生成不得同时付费执行");
    const plan = await createRealArrayPlan();
    await fs.writeFile(path.resolve(args["--write-plan"]), JSON.stringify(plan, null, 2), { flag: "wx" });
    console.log(JSON.stringify({ mode: "plan-only", apiRequests: 0, digest: plan.digest, selectedQuestions: plan.selectedQuestions,
      strata: plan.selection.strata, units: plan.units.map((u) => ({ stratum: u.stratum, questions: u.questions.length, model: u.model, mediaBytes: u.mediaBytes })) }, null, 2));
    return;
  }
  if (!args["--plan"]) throw new Error("缺少 --plan");
  const dryRun = Boolean(args["--dry-run"]) || !args["--allow-paid"];
  const result = await executeRealArrayPlan(JSON.parse(await fs.readFile(path.resolve(args["--plan"]))), { dryRun,
    allowPaid: Boolean(args["--allow-paid"]), maxRequests: Number(args["--max-requests"]), apiKey: dryRun ? undefined : process.env.DASHSCOPE_API_KEY,
    baseUrl: dryRun ? undefined : process.env.ALIYUN_BASE_URL || (process.env.ALIYUN_WORKSPACE_ID
      ? `https://${process.env.ALIYUN_WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` : endpointDefault) });
  console.log(JSON.stringify(result, null, 2));
  if (result.status === "stopped") process.exitCode = 2;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch(() => { console.error("真实数组试验未执行或已中止；请检查参数、冻结计划、运行锁和脱敏报告。没有自动重试。"); process.exitCode = 1; });
}
