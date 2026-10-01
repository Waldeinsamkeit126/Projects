import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { createRealArrayPlan, verifyRealArrayPlan, executeRealArrayPlan, selectRealArrayUnits, makeMediaBlock } from "./real-array-trial.mjs";
import { buildValueArrayPrompt } from "./array-value-contract.mjs";

const key = "unit-test-key-not-a-real-credential";
const sample = (id, file, type) => ({ id, file_name: file, question_type: type, question: `合成问题 ${id}`,
  table_hint: "合成表", answer_format: "json_array", expected: "REFERENCE_MUST_NOT_APPEAR", answer: "OLD_ANSWER_MUST_NOT_APPEAR" });
const synthetic = [sample("a", "a.png", "extract"), sample("b", "b.png", "thinking"), sample("c", "c.pdf", "extract"), sample("d", "d.pdf", "thinking")];
const resolve = (qs) => new Map(qs.map((q) => [q.file_name, path.resolve(os.tmpdir(), q.file_name)]));
let planPromise;
const plan = () => planPromise ??= createRealArrayPlan();
const outputRoot = () => fs.mkdtemp(path.join(os.tmpdir(), "official-array-test-"));
const answerContent = (qs) => JSON.stringify({ answers: qs.map((q) => ({ id: q.id, answer: ["MOCK_ONLY"] })) });
const response = (qs, { content = answerContent(qs), finish = "stop", status = 200 } = {}) => new Response(JSON.stringify({ model: "qwen-mock-not-real",
  choices: [{ finish_reason: finish, message: { content, reasoning_content: "OMIT_THIS_REASONING" } }], usage: { total_tokens: 5 } }), { status });

test("metadata-only strata selection is deterministic and strips all answer/label fields", () => {
  const more = [...synthetic, ...Array.from({ length: 5 }, (_, i) => sample(`extra-${i}`, "a.png", "extract"))];
  const first = selectRealArrayUnits(more, resolve(more));
  assert.deepEqual(first, selectRealArrayUnits(more.toReversed(), resolve(more)));
  assert.equal(first.units.length, 4); assert.equal(first.units[0].questions.length, 3);
  assert.equal(new Set(first.units.map((u) => u.mediaPath)).size, 4);
  assert.equal(JSON.stringify(first).includes("REFERENCE_MUST_NOT_APPEAR"), false);
  assert.equal(JSON.stringify(first).includes("OLD_ANSWER_MUST_NOT_APPEAR"), false);
  assert.deepEqual(first.units.map((u) => u.model), ["qwen3-vl-plus", "qwen3-vl-plus", "qwen3.8-max", "qwen3.8-max"]);
});

test("unresolved sources and missing strata stop rather than guessing another question", () => {
  assert.throws(() => selectRealArrayUnits(synthetic, new Map()), /未解析/);
  assert.throws(() => selectRealArrayUnits(synthetic.slice(1), resolve(synthetic)), /缺少/);
  assert.throws(() => selectRealArrayUnits([...synthetic, synthetic[0]], resolve(synthetic)), /重复/);
});

test("a physical source is not selected twice when both extraction and reasoning use it", () => {
  const same = [...synthetic, sample("shared", "a.png", "thinking")];
  const selected = selectRealArrayUnits(same, resolve(same));
  assert.equal(new Set(selected.units.map((u) => u.mediaPath)).size, 4);
  assert.equal(selected.units[1].questions.some((q) => q.id === "shared"), false);
});

test("PDF and image transport use documented MIME fields and no semantic filename hints", () => {
  const bytes = Buffer.from("mock");
  assert.deepEqual(makeMediaBlock({ mediaKind: "pdf", mediaPath: "secret-description.pdf" }, bytes), {
    type: "file", file: { file_data: "data:application/pdf;base64,bW9jaw==", filename: "source.pdf" },
  });
  assert.equal(makeMediaBlock({ mediaKind: "image", mediaPath: "picture.JPG" }, bytes).image_url.url, "data:image/jpeg;base64,bW9jaw==");
  assert.throws(() => makeMediaBlock({ mediaKind: "image", mediaPath: "not-an-image.txt" }, bytes));
});

test("official metadata has 99 arrays and four strata without retrieving answer column", async () => {
  const p = await plan();
  assert.equal(p.source.answerColumnRead, false); assert.equal(p.source.range, "A2:F909");
  assert.equal(p.selection.arrayQuestions, 99);
  assert.deepEqual(p.selection.strata, { "image/extract": 6, "image/thinking": 51, "pdf/extract": 33, "pdf/thinking": 9 });
  assert.equal(p.units.length, 4); assert.equal(p.selectedQuestions, 10);
  assert.equal(p.readsPriorAnswers, false); assert.equal(p.exportAllowed, false); assert.equal(p.submissionAllowed, false);
  assert.ok(p.units.every((u) => u.mediaBytes > 0 && u.questions.length <= 3));
});

test("frozen-plan mutation is rejected before any request", async () => {
  const p = structuredClone(await plan()); p.settings.maxRequests = 5;
  await assert.rejects(verifyRealArrayPlan(p), /指纹/);
});

test("default and explicit dry-run are free and create no run files", async () => {
  const dir = await outputRoot(); let calls = 0;
  for (const opts of [{}, { allowPaid: true, dryRun: true }]) {
    const result = await executeRealArrayPlan(await plan(), { ...opts, outputRoot: dir, fetchImpl: () => { calls++; } });
    assert.equal(result.apiRequests, 0); assert.equal(result.selectedQuestions, 10);
  }
  assert.equal(calls, 0); assert.deepEqual(await fs.readdir(dir), []);
});

test("paid path needs explicit quota and key; provider allowlist applies", async () => {
  const dir = await outputRoot(); let calls = 0;
  for (const invalid of [{ maxRequests: 5 }, { maxRequests: 0 }, { maxRequests: undefined }, { apiKey: "" }, { baseUrl: "http://dashscope.aliyuncs.com/compatible-mode/v1" }]) {
    await assert.rejects(executeRealArrayPlan(await plan(), { allowPaid: true, maxRequests: 4, apiKey: key,
      outputRoot: dir, fetchImpl: () => { calls++; }, ...invalid }));
  }
  assert.equal(calls, 0); assert.deepEqual(await fs.readdir(dir), []);
});

test("four-request mock handles PNG/JPEG/PDF and records provenance without accuracy claims", async () => {
  const p = await plan(), dir = await outputRoot(); let calls = 0;
  const report = await executeRealArrayPlan(p, { allowPaid: true, maxRequests: 4, apiKey: key, outputRoot: dir,
    fetchImpl: async (url, init) => {
      assert.equal(url, "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"); assert.equal(init.redirect, "error");
      const unit = p.units[calls++], body = JSON.parse(init.body);
      assert.equal(body.model, unit.model); assert.equal(body.max_completion_tokens, 4096);
      assert.equal(body.messages[1].content[1].text, buildValueArrayPrompt(unit.questions));
      assert.equal(body.messages[1].content[0].type, unit.mediaKind === "pdf" ? "file" : "image_url");
      return response(unit.questions);
    } });
  assert.equal(calls, 4); assert.equal(report.returnedQuestions, 10); assert.equal(report.validQuestions, 10);
  assert.equal(report.groundTruthAccuracy, null); assert.equal(report.submitted, false); assert.equal(report.exported, false);
  const rows = (await fs.readFile(report.resultPath, "utf8")).trim().split("\n").map(JSON.parse);
  assert.ok(rows.every((r) => r.runId === report.runId && r.mediaSha256 && r.promptSha256));
  const trace = await fs.readFile(path.join(path.dirname(report.reportPath), "inference-trace.jsonl"), "utf8");
  assert.ok(!trace.includes(key)); assert.ok(!trace.includes("OMIT_THIS_REASONING"));
  await assert.rejects(executeRealArrayPlan(p, { allowPaid: true, maxRequests: 4, apiKey: key, outputRoot: dir,
    fetchImpl: () => { calls++; } }), /EEXIST/);
  assert.equal(calls, 4);
});

test("smaller approved cap never continues into a third source", async () => {
  const p = await plan(); let calls = 0;
  const report = await executeRealArrayPlan(p, { allowPaid: true, maxRequests: 2, apiKey: key, outputRoot: await outputRoot(),
    fetchImpl: async () => response(p.units[calls++].questions) });
  assert.equal(calls, 2); assert.equal(report.stopReason, "request-cap");
});

test("all errors stop after first request, without fallback, repair or retry", async () => {
  const p = await plan(), qs = p.units[0].questions;
  for (const failure of ["network", "http", "length", "parse", "missing", "object", "unexpected", "secret"]) {
    let calls = 0;
    const report = await executeRealArrayPlan(p, { allowPaid: true, maxRequests: 4, apiKey: key, outputRoot: await outputRoot(),
      fetchImpl: async () => {
        calls++;
        if (failure === "network") throw new Error("network " + key);
        if (failure === "http") return response(qs, { status: 403 });
        if (failure === "length") return response(qs, { finish: "length" });
        if (failure === "parse") return response(qs, { content: "bad" });
        if (failure === "missing") return response(qs.slice(1));
        if (failure === "unexpected") return response([{ id: "not-in-request" }]);
        return response(qs, { content: JSON.stringify({ answers: qs.map((q) => ({ id: q.id, answer: failure === "object" ? [{ key: "MOCK" }] : [key] })) }) });
      } });
    assert.equal(calls, 1, failure); assert.equal(report.status, "stopped", failure); assert.equal(report.apiRequests, 1);
    const files = await fs.readdir(path.dirname(report.reportPath));
    for (const name of files) assert.ok(!(await fs.readFile(path.join(path.dirname(report.reportPath), name), "utf8")).includes(key));
  }
});

test("audit failure aborts before starting a second source", async () => {
  const p = await plan(), dir = await outputRoot(); let calls = 0;
  await assert.rejects(executeRealArrayPlan(p, { allowPaid: true, maxRequests: 4, apiKey: key, outputRoot: dir,
    fetchImpl: async () => {
      calls++;
      const run = (await fs.readdir(dir)).find((name) => !name.endsWith(".json"));
      await fs.mkdir(path.join(dir, run, "requests.jsonl"));
      return response(p.units[0].questions);
    } }));
  assert.equal(calls, 1);
});
