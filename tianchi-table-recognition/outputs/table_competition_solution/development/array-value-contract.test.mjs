import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { buildPrompt, normalizeAnswer, validateAnswer } from "../run.mjs";
import { inferenceSourceHash } from "../reliability.mjs";
import { publicArrayQuestions, buildValueArrayPrompt, normalizeValueArray, validateValueArray,
  scoreValueArrayContract, VALUE_ARRAY_RULE } from "./array-value-contract.mjs";
import { createArrayPlan, verifyArrayPlan, executeArrayPlan } from "./array-value-trial.mjs";

const dir = path.dirname(fileURLToPath(import.meta.url));
const questions = JSON.parse(await fs.readFile(path.join(dir, "array-value-questions.json"))).questions;
const references = JSON.parse(await fs.readFile(path.join(dir, "array-value-references.json"))).references;
const key = "synthetic-test-credential-never-real";
const expected = new Map(references.map((r) => [r.id, r.expected]));
const validContent = (qs) => JSON.stringify({ answers: qs.map((q) => ({ id: q.id, answer: expected.get(q.id) })) });
const fakeResponse = (qs, { content = validContent(qs), finish = "stop", status = 200 } = {}) => new Response(JSON.stringify({
  model: "qwen-mock-only", choices: [{ finish_reason: finish, message: { content, reasoning_content: "MUST_NOT_LOG_REASONING" } }],
  usage: { prompt_tokens: 10, completion_tokens: 20, total_tokens: 30 },
}), { status });
async function fixture() {
  return { plan: await createArrayPlan(), outputRoot: await fs.mkdtemp(path.join(os.tmpdir(), "array-value-test-")) };
}
async function paid(f, fetchImpl, extra = {}) {
  return executeArrayPlan(f.plan, { allowPaid: true, maxRequests: 2, apiKey: key, outputRoot: f.outputRoot, fetchImpl, ...extra });
}

test("official illustrated value array accepted by candidate, rejected by unchanged v3", () => {
  const example = '[1,"销售额","产品销售表"]';
  assert.equal(validateValueArray(example).valid, true);
  assert.equal(validateAnswer(questions[0], example).valid, false);
  assert.equal(validateAnswer(questions[0], '[{"商品编号":"001"}]').valid, true);
  assert.equal(validateValueArray('[{"商品编号":"001"}]').valid, false);
});

test("format paragraph is the only prompt change, payload allowlist strips labels", () => {
  const raw = questions.map((q) => ({ ...q, expected: "SECRET_REFERENCE_SENTINEL", answer: "OLD_ANSWER_SENTINEL" }));
  const prompt = buildValueArrayPrompt(raw), oldLines = buildPrompt(publicArrayQuestions(raw)).split("\n"), newLines = prompt.split("\n");
  assert.equal(oldLines.length, newLines.length);
  assert.equal(oldLines.filter((line, i) => line !== newLines[i]).length, 1);
  assert.ok(newLines.includes(VALUE_ARRAY_RULE));
  assert.ok(!prompt.includes("SECRET_REFERENCE_SENTINEL"));
  assert.ok(!prompt.includes("OLD_ANSWER_SENTINEL"));
  assert.ok(!prompt.includes("不得直接输出字符串数组"));
});

test("invalid/null/nested/object array values never auto-flatten or pass", () => {
  for (const raw of [[null], [{ a: 1 }], [[1]], [NaN], [Infinity], {}, "undefined", "[1,]", null]) {
    assert.equal(validateValueArray(normalizeValueArray(raw)).valid, false, String(raw));
  }
  assert.equal(normalizeValueArray([{ a: 1 }]), '[{"a":1}]');
  assert.equal(validateValueArray("[]").valid, true); // Empty results can be meaningful, not a universal error.
});

test("normalization preserves value types, leading zeros, blanks, duplicates and order", () => {
  const value = ["001", 0, "", false, "12.50", "x", "x", 7];
  assert.deepEqual(JSON.parse(normalizeValueArray(value)), value);
  assert.equal(normalizeValueArray('```json\n[ 1, "001", "" ]\n```'), '[1,"001",""]');
});

test("synthetic references: ten positive and zero negative controls, no official accuracy claim", () => {
  const positives = scoreValueArrayContract(references, references.map((q) => ({ id: q.id, answer: q.expected })));
  assert.equal(positives.correct, 10); assert.equal(positives.valid, 10);
  assert.match(positives.metric, /not official/);
  const negatives = scoreValueArrayContract(references, references.map((q) => ({ id: q.id, answer: ["WRONG"] })));
  assert.equal(negatives.correct, 0); assert.equal(negatives.valid, 10);
  assert.equal(scoreValueArrayContract(references, []).missing, 10);
});

test("strict score does not equate changed types, reordered values or redacted outputs", () => {
  const refs = [{ id: "one", expected: [1, "001"] }];
  for (const answer of [["1", "001"], ["001", 1], [1, 1]]) {
    assert.equal(scoreValueArrayContract(refs, [{ id: "one", answer }]).correct, 0);
  }
  assert.equal(scoreValueArrayContract(refs, [{ id: "one", answer: refs[0].expected, answerRedacted: true }]).correct, 0);
  assert.throws(() => scoreValueArrayContract(refs, [{ id: "unknown", answer: [] }]), /未知/);
  assert.throws(() => scoreValueArrayContract(refs, [{ id: "one", answer: [] }, { id: "one", answer: [] }]), /重复/);
});

test("public questions reject mixed formats, duplicates and missing required data", () => {
  assert.throws(() => publicArrayQuestions([...questions, questions[0]]));
  assert.throws(() => publicArrayQuestions([{ ...questions[0], answer_format: "json" }]));
  assert.throws(() => publicArrayQuestions([{ ...questions[0], question: "" }]));
});

test("frozen plan includes media/prompt/reference hashes and protects legacy core", async () => {
  const plan = await createArrayPlan();
  await verifyArrayPlan(plan);
  assert.equal(plan.units.length, 2); assert.equal(plan.units.flatMap((u) => u.questions).length, 10);
  assert.equal(plan.referenceLabelsTransmitted, false);
  assert.equal(await inferenceSourceHash(path.dirname(dir)), "46e0dce366c7c49df4bab25c7c9dfb201d46c2ddbbe0c83bbab790e6f6b21898");
  for (const change of [(p) => p.settings.maxAttempts++, (p) => p.units[0].mediaSha256 = "changed", (p) => p.referenceSha256 = "changed"]) {
    const changed = structuredClone(plan); change(changed);
    await assert.rejects(verifyArrayPlan(changed), /指纹/);
  }
});

test("default and explicit dry-run never fetch, need a key, or create a run lock", async () => {
  const f = await fixture(); let calls = 0;
  for (const opts of [{}, { allowPaid: true, dryRun: true }]) {
    const r = await executeArrayPlan(f.plan, { ...opts, outputRoot: f.outputRoot, fetchImpl: () => { calls++; } });
    assert.equal(r.apiRequests, 0);
  }
  assert.equal(calls, 0); assert.deepEqual(await fs.readdir(f.outputRoot), []);
});

test("paid gates reject absent quota/key and non-Aliyun provider before fetch", async () => {
  const f = await fixture(); let calls = 0;
  for (const extra of [{ maxRequests: undefined }, { maxRequests: 3 }, { maxRequests: 0 }, { apiKey: "" }, { baseUrl: "https://example.com/compatible-mode/v1" }]) {
    await assert.rejects(paid(f, () => { calls++; }, extra));
  }
  assert.equal(calls, 0); assert.deepEqual(await fs.readdir(f.outputRoot), []);
});

test("successful two-request mock contains only public questions, bounded settings and image", async () => {
  const f = await fixture(); let calls = 0;
  const report = await paid(f, async (url, init) => {
    assert.equal(url, "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions");
    assert.equal(init.redirect, "error");
    const body = JSON.parse(init.body), unit = f.plan.units[calls++];
    assert.equal(body.max_completion_tokens, 4096); assert.equal(body.temperature, 0); assert.equal(body.enable_thinking, false);
    assert.equal(body.messages[1].content.length, 2);
    assert.equal(body.messages[1].content[1].text, buildValueArrayPrompt(unit.questions));
    assert.equal(body.messages[1].content[1].text.includes('"expected"'), false);
    return fakeResponse(unit.questions);
  });
  assert.equal(calls, 2); assert.equal(report.validQuestions, 10); assert.equal(report.modelAccuracy, null);
  assert.equal(report.submitted, false); assert.equal(report.exported, false);
  const runDir = path.dirname(report.reportPath);
  const trace = await fs.readFile(path.join(runDir, "inference-trace.jsonl"), "utf8");
  assert.ok(!trace.includes(key)); assert.ok(!trace.includes("MUST_NOT_LOG_REASONING"));
  const rows = (await fs.readFile(report.resultPath, "utf8")).trim().split("\n").map(JSON.parse);
  assert.equal(scoreValueArrayContract(references, rows).correct, 10);
  await assert.rejects(paid(f, () => { calls++; }), /EEXIST/);
  assert.equal(calls, 2);
});

test("one-request cap leaves second image uncalled", async () => {
  const f = await fixture(); let calls = 0;
  const report = await paid(f, async () => fakeResponse(f.plan.units[calls++].questions), { maxRequests: 1 });
  assert.equal(calls, 1); assert.equal(report.apiRequests, 1); assert.equal(report.stopReason, "request-cap");
  assert.equal(report.returnedQuestions, 5);
});

test("HTTP, network, truncation, parse, duplicate and missing answers stop after one attempt", async () => {
  for (const failure of ["http", "network", "length", "parse", "duplicate", "missing", "object"]) {
    const f = await fixture(); let calls = 0;
    const report = await paid(f, async () => {
      calls++;
      const qs = f.plan.units[0].questions;
      if (failure === "network") throw new Error("simulated network failure");
      if (failure === "http") return fakeResponse(qs, { status: 402 });
      if (failure === "length") return fakeResponse(qs, { finish: "length" });
      if (failure === "parse") return fakeResponse(qs, { content: "not-json" });
      if (failure === "duplicate") return fakeResponse(qs, { content: validContent([qs[0], qs[0]]) });
      if (failure === "missing") return fakeResponse(qs, { content: validContent(qs.slice(1)) });
      return fakeResponse(qs, { content: JSON.stringify({ answers: qs.map((q) => ({ id: q.id, answer: [{ value: "x" }] })) }) });
    });
    assert.equal(calls, 1, failure); assert.equal(report.status, "stopped", failure);
    assert.equal(report.apiRequests, 1, failure);
  }
});

test("credential-looking response is redacted and cannot pass format or be exported", async () => {
  const f = await fixture();
  const report = await paid(f, async () => fakeResponse(f.plan.units[0].questions, { content: JSON.stringify({ answers: f.plan.units[0].questions.map((q) => ({ id: q.id, answer: [key] })) }) }));
  assert.equal(report.apiRequests, 1); assert.equal(report.validQuestions, 0);
  const rows = await fs.readFile(report.resultPath, "utf8");
  assert.ok(!rows.includes(key)); assert.match(rows, /answerRedacted/);
  const trace = await fs.readFile(path.join(path.dirname(report.reportPath), "inference-trace.jsonl"), "utf8");
  assert.ok(!trace.includes(key));
});

test("audit-write failure after response stops before any second request", async () => {
  const f = await fixture(); let calls = 0;
  await assert.rejects(paid(f, async () => {
    calls++;
    const runName = (await fs.readdir(f.outputRoot)).find((name) => !name.endsWith(".json"));
    // A directory at the append path simulates denied audit logging, without deleting anything.
    await fs.mkdir(path.join(f.outputRoot, runName, "requests.jsonl"));
    return fakeResponse(f.plan.units[0].questions);
  }));
  assert.equal(calls, 1);
});

test("legacy normalization and object-reference behavior are unchanged", () => {
  const original = [{ code: "001", count: 3 }];
  const old = normalizeAnswer(questions[0], original);
  assert.equal(old, '[{"code":"001","count":"3"}]');
  assert.equal(validateAnswer(questions[0], old).valid, true);
  assert.equal(normalizeValueArray(original), '[{"code":"001","count":3}]');
});

test("offline evaluator verifies frozen references and reports mock predictions separately from controls", async () => {
  const f = await fixture(); let calls = 0;
  const report = await paid(f, async () => fakeResponse(f.plan.units[calls++].questions));
  const scorePath = path.join(path.dirname(report.reportPath), "mock-score.json");
  execFileSync(process.execPath, [path.join(dir, "array-value-evaluate.mjs"), report.reportPath, scorePath], { stdio: "pipe" });
  const evaluated = JSON.parse(await fs.readFile(scorePath));
  assert.equal(evaluated.score.correct, 10); assert.equal(evaluated.score.total, 10);
  assert.equal(evaluated.controls.positive, 10); assert.equal(evaluated.controls.negative, 0);
  assert.equal(evaluated.evaluationApiRequests, 0); assert.equal(evaluated.leaderboardScore, null);
  assert.equal(calls, 2); assert.equal(evaluated.submitted, false);
});
