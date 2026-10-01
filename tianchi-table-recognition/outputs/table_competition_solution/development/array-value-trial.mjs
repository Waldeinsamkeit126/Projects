import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { parseModelAnswers } from "../run.mjs";
import { sha256, inferenceSourceHash, SYSTEM_PROMPT, assertProvider } from "../reliability.mjs";
import { createRedactor, protectResult } from "../inference-trace.mjs";
import { ARRAY_CONTRACT_VERSION, RULE_SOURCE, publicArrayQuestions, buildValueArrayPrompt,
  normalizeValueArray, validateValueArray } from "./array-value-contract.mjs";

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(directory);
const settings = Object.freeze({ model: "qwen3-vl-plus", maxCompletionTokens: 4096, temperature: 0,
  enableThinking: false, maxAttempts: 1, concurrency: 1, automaticFallback: false });
const defaultEndpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1";

async function fingerprint() {
  const files = ["array-value-contract.mjs", "array-value-trial.mjs", "array-value-trial.ps1"];
  return sha256(JSON.stringify({ core: await inferenceSourceHash(root),
    candidate: await Promise.all(files.map(async (file) => [file, sha256(await fs.readFile(path.join(directory, file)))])) }));
}

export async function createArrayPlan() {
  const questionBytes = await fs.readFile(path.join(directory, "array-value-questions.json"));
  const questions = publicArrayQuestions(JSON.parse(questionBytes).questions);
  const units = [];
  for (const name of new Set(questions.map((q) => q.file_name))) {
    if (path.basename(name) !== name || !name.endsWith(".png")) throw new Error("试验只允许合成目录内 PNG");
    const mediaPath = await fs.realpath(path.join(directory, "generated", name));
    const mediaRoot = await fs.realpath(path.join(directory, "generated"));
    if (path.dirname(mediaPath) !== mediaRoot) throw new Error("合成图片越出目录");
    const selected = questions.filter((q) => q.file_name === name);
    units.push({ fileName: name, mediaPath, mediaSha256: sha256(await fs.readFile(mediaPath)),
      questions: selected, promptSha256: sha256(buildValueArrayPrompt(selected)) });
  }
  if (units.length !== 2 || questions.length !== 10) throw new Error("本轮固定为两张合成表十题");
  const payload = { version: ARRAY_CONTRACT_VERSION, ruleSource: RULE_SOURCE,
    sourceHash: await fingerprint(), coreSourceHash: await inferenceSourceHash(root),
    questionSha256: sha256(questionBytes),
    // Hash only; labels are not parsed by the inference runner or included in requests.
    referenceSha256: sha256(await fs.readFile(path.join(directory, "array-value-references.json"))),
    settings, units, proposedMaxRequests: 2, referenceLabelsTransmitted: false,
    note: "Synthetic smoke test only, not A/B, not blind validation, no official export/submission. Plan is not spending authorization." };
  return { ...payload, digest: sha256(JSON.stringify(payload)) };
}

export async function verifyArrayPlan(plan) {
  if (JSON.stringify(await createArrayPlan()) !== JSON.stringify(plan)) throw new Error("计划、代码、问题、参考或图片指纹已变更");
}

export async function executeArrayPlan(plan, options = {}) {
  await verifyArrayPlan(plan);
  if (options.dryRun || !options.allowPaid) return { mode: "dry-run", planDigest: plan.digest,
    apiRequests: 0, questionCount: 10, sourceImages: 2, proposedMaxRequests: 2 };
  if (!Number.isSafeInteger(options.maxRequests) || options.maxRequests < 1 || options.maxRequests > 2) {
    throw new Error("必须显式指定本轮请求上限 1 或 2");
  }
  if (!options.apiKey) throw new Error("缺少进程凭证");
  const endpoint = options.baseUrl || defaultEndpoint;
  assertProvider(endpoint, [settings.model]);
  const redact = createRedactor(options.apiKey);
  const outputRoot = path.resolve(options.outputRoot ?? path.join(root, "array-trial-runs"));
  const runId = `${new Date().toISOString().replaceAll(":", "-").replaceAll(".", "-")}-${crypto.randomBytes(4).toString("hex")}`;
  await fs.mkdir(outputRoot, { recursive: true });
  await fs.writeFile(path.join(outputRoot, `${plan.digest}.started.json`), JSON.stringify({ runId, planDigest: plan.digest,
    maxRequests: options.maxRequests }), { flag: "wx" });
  const runDir = path.join(outputRoot, runId);
  await fs.mkdir(runDir);
  await fs.writeFile(path.join(runDir, "plan.json"), JSON.stringify(plan, null, 2), { flag: "wx" });
  const requests = [], results = [];
  let stopReason = null;
  const append = async (name, data) => fs.appendFile(path.join(runDir, name), JSON.stringify(redact(data)) + "\n");
  for (const unit of plan.units) {
    if (requests.length >= options.maxRequests) { stopReason = "request-cap"; break; }
    const event = { requestIndex: requests.length + 1, fileName: unit.fileName, model: settings.model,
      questionIds: unit.questions.map((q) => q.id), status: "prepared", apiRequestMade: false, usage: null };
    try {
      const media = await fs.readFile(unit.mediaPath);
      if (sha256(media) !== unit.mediaSha256) throw new Error("图片在启动后发生变化");
      const prompt = buildValueArrayPrompt(unit.questions);
      if (sha256(prompt) !== unit.promptSha256) throw new Error("提示在启动后发生变化");
      await append("inference-trace.jsonl", { kind: "request-prepared", timestamp: new Date().toISOString(), ...event,
        mediaSha256: unit.mediaSha256, promptSha256: unit.promptSha256 });
      // Exactly one fetch, no retry, repair call, alternate model or continuation.
      requests.push(event); event.apiRequestMade = true; event.status = "error";
      const started = Date.now();
      const response = await (options.fetchImpl ?? fetch)(`${endpoint.replace(/\/$/, "")}/chat/completions`, {
        method: "POST", redirect: "error", signal: AbortSignal.timeout(180_000),
        headers: { Authorization: `Bearer ${options.apiKey}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model: settings.model, temperature: settings.temperature,
          max_completion_tokens: settings.maxCompletionTokens, enable_thinking: false,
          response_format: { type: "json_object" }, messages: [
            { role: "system", content: SYSTEM_PROMPT },
            { role: "user", content: [ { type: "image_url", image_url: { url: `data:image/png;base64,${media.toString("base64")}` } },
              { type: "text", text: prompt } ] },
          ] }),
      });
      event.httpStatus = response.status; event.elapsedMs = Date.now() - started;
      if (!response.ok) throw new Error(`API HTTP ${response.status}`); // Never persist error bodies.
      let envelope;
      try { envelope = await response.json(); } catch { throw new Error("API 响应信封不是 JSON"); }
      const choice = envelope?.choices?.[0];
      event.usage = envelope.usage ?? null; event.finishReason = choice?.finish_reason ?? null;
      event.resolvedModel = envelope.model ?? settings.model;
      const content = choice?.message?.content;
      await append("inference-trace.jsonl", { kind: "response", ...event, content: typeof content === "string" ? content : null });
      if (event.finishReason !== "stop" || typeof content !== "string") throw new Error("输出截断、停止原因异常或无正文");
      const answers = parseModelAnswers(content, unit.questions);
      const batch = unit.questions.map((q) => {
        const answer = normalizeValueArray(answers.get(q.id));
        return protectResult({ id: q.id, answer, ...validateValueArray(answer), model: event.resolvedModel,
          requestIndex: event.requestIndex, provenance: "automated-qwen-value-array-candidate", runId }, options.apiKey);
      });
      for (const result of batch) await append("results.jsonl", result);
      results.push(...batch);
      event.status = batch.every((r) => r.valid) ? "format-passed-not-proven-correct" : "invalid-format";
      await append("requests.jsonl", event);
      if (event.status === "invalid-format") { stopReason = "missing-or-invalid-answer"; break; }
    } catch (error) {
      stopReason = "request-parse-or-audit-error";
      event.error = redact(String(error.message));
      // If logging is unavailable, abort rather than attempting another API request.
      await append("requests.jsonl", event);
      break;
    }
  }
  const report = redact({ version: ARRAY_CONTRACT_VERSION, runId, planDigest: plan.digest, sourceHash: plan.sourceHash,
    endpoint, settings, status: stopReason ? "stopped" : "completed-candidates-only", stopReason,
    apiRequests: requests.length, maxRequests: options.maxRequests, requests, plannedQuestions: 10,
    returnedQuestions: results.length, validQuestions: results.filter((r) => r.valid).length,
    resultPath: path.join(runDir, "results.jsonl"), baselineModified: false, exported: false, submitted: false,
    modelAccuracy: null, note: "Format checks only. Separate frozen-reference evaluation is required." });
  const reportPath = path.join(runDir, "report.json");
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), { flag: "wx" });
  return { ...report, reportPath };
}

async function main(argv) {
  const flags = new Set(["--dry-run", "--allow-paid"]), values = new Set(["--write-plan", "--plan", "--max-requests"]);
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    if (Object.hasOwn(args, key) || (!flags.has(key) && !values.has(key))) throw new Error("未知或重复参数");
    args[key] = flags.has(key) ? true : argv[++i];
    if (!args[key] || String(args[key]).startsWith("--")) throw new Error("参数缺少值");
  }
  if (args["--write-plan"]) {
    if (Object.keys(args).length !== 1) throw new Error("生成计划不能混入执行参数");
    const plan = await createArrayPlan();
    await fs.writeFile(path.resolve(args["--write-plan"]), JSON.stringify(plan, null, 2), { flag: "wx" });
    console.log(JSON.stringify({ mode: "plan-only", apiRequests: 0, digest: plan.digest }));
    return;
  }
  if (!args["--plan"]) throw new Error("缺少 --plan");
  const plan = JSON.parse(await fs.readFile(path.resolve(args["--plan"])));
  const dryRun = Boolean(args["--dry-run"]) || !args["--allow-paid"];
  const result = await executeArrayPlan(plan, { dryRun, allowPaid: Boolean(args["--allow-paid"]),
    maxRequests: Number(args["--max-requests"]), apiKey: dryRun ? undefined : process.env.DASHSCOPE_API_KEY,
    baseUrl: dryRun ? undefined : process.env.ALIYUN_BASE_URL || (process.env.ALIYUN_WORKSPACE_ID
      ? `https://${process.env.ALIYUN_WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1` : defaultEndpoint) });
  console.log(JSON.stringify(result, null, 2));
  if (result.status === "stopped") process.exitCode = 2;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch(() => { console.error("数组试验未执行或中止；请检查参数、计划指纹、单次锁及脱敏记录。未自动重试。"); process.exitCode = 1; });
}
