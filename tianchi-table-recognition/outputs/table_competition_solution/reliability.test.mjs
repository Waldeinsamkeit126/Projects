import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { normalizeAnswer, validateAnswer, parseModelAnswers, callQwen, processGroup, main } from "./run.mjs";
import { CACHE_SCHEMA, assertProvider, makeCacheIdentity, checkCache, assertUniqueQuestions, summarizeRequests, scoreDevelopment } from "./reliability.mjs";
import { developmentCases, sources } from "./development/fixtures.mjs";

const number = { id: "synthetic-1", question_type: "extract", answer_format: "number" };
const array = { ...number, answer_format: "json_array" };
const structure = { ...number, question_type: "structure", answer_format: "json" };
const endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1";
const fixture = {
  mediaBytes: Buffer.from("synthetic-media"), questions: [number], prompt: "synthetic-prompt-v1", sourceHash: "code-v1",
  options: { baseUrl: endpoint, model: "qwen-test", maxCompletionTokens: 1024, maxAttempts: 1 },
};

for (const value of ["0", "-0", "12", "-12.75", ".5", "+4", "1.2e3", "9007199254740993"]) {
  test(`accept numerical syntax ${value}`, () => assert.equal(validateAnswer(number, value).valid, true));
}
for (const value of ["", " ", "-", "abc", "NaN", "Infinity", "1e309", "0x12", "12元", "12%", "12,34", "1,234,56", "1.2.3", "答案是12"]) {
  test(`reject invalid numerical syntax ${JSON.stringify(value)}`, () => assert.equal(validateAnswer(number, normalizeAnswer(number, value)).valid, false));
}
test("thousands conversion preserves precision and malformed input", () => {
  assert.equal(normalizeAnswer(number, "9,007,199,254,740,993"), "9007199254740993");
  assert.equal(normalizeAnswer(number, "-1,234.50"), "-1234.50");
  assert.equal(normalizeAnswer(number, "12,34,567"), "12,34,567");
});
test("nested JSON is not flattened into apparently valid text", () => {
  for (const value of [{ a: { b: "c" } }, { a: ["b"] }]) {
    assert.equal(validateAnswer(array, normalizeAnswer(array, [value])).valid, false);
  }
  assert.equal(normalizeAnswer(array, [{ a: null, b: 0 }]), '[{"a":"","b":"0"}]');
});
test("normalization does not enlarge a predicted table", () => {
  const answer = { row_count: 1, col_count: 1, cells: [{ text: "x", row: 0, col: 0, rowspan: 2, colspan: 1 }] };
  const normalized = normalizeAnswer(structure, answer);
  assert.deepEqual(JSON.parse(normalized), answer);
  assert.equal(validateAnswer(structure, normalized).valid, false);
});
test("nonempty, safe and nonoverlapping structure", () => {
  const base = { row_count: 2, col_count: 2, cells: [] };
  assert.equal(validateAnswer(structure, JSON.stringify(base)).valid, false);
  base.cells = [{ text: "header", row: 0, col: 0, rowspan: 1, colspan: 2 }];
  assert.equal(validateAnswer(structure, JSON.stringify(base)).valid, true);
  base.cells.push({ text: "overlap", row: 0, col: 1, rowspan: 1, colspan: 1 });
  assert.equal(validateAnswer(structure, JSON.stringify(base)).valid, false);
  base.cells[1].row = 1;
  assert.equal(validateAnswer(structure, JSON.stringify(base)).valid, true);
  base.col_count = Number.MAX_SAFE_INTEGER + 1;
  assert.equal(validateAnswer(structure, JSON.stringify(base)).valid, false);
});
test("duplicate and missing model IDs are rejected", () => {
  assert.throws(() => parseModelAnswers('{"answers":[{"id":"x","answer":"1"},{"id":"x","answer":"2"}]}'));
  assert.throws(() => parseModelAnswers('{"answers":[{"answer":"2"}]}'));
  assert.throws(() => parseModelAnswers("null"));
  assert.throws(() => parseModelAnswers('{"answers":[{"id":"unexpected","answer":"1"}]}', [number]));
  assert.equal(parseModelAnswers('{"answers":[{"id":"x","answer":"0"}]}').get("x"), "0");
});
test("all inference-affecting options invalidate cache", () => {
  const original = makeCacheIdentity(fixture).digest;
  const variants = [
    { prompt: "new prompt" }, { sourceHash: "new code" }, { mediaBytes: Buffer.from("changed") },
    { questions: [{ ...number, question: "changed" }] },
    ...[{ model: "qwen-other" }, { maxCompletionTokens: 2048 }, { enableThinking: true },
      { maxAttempts: 2 }, { refreshStructure: true }, { checkFullCoverage: true }, { checkStructureConsistency: true }, { baseUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1" }]
      .map((option) => ({ options: { ...fixture.options, ...option } })),
  ];
  for (const variant of variants) assert.notEqual(makeCacheIdentity({ ...fixture, ...variant }).digest, original);
  assert.equal(makeCacheIdentity({ ...fixture, options: { ...fixture.options, apiKey: "dummy-not-a-real-key" } }).digest, original);
});
test("legacy, missing, duplicate and invalid cached results are detected", () => {
  const questions = [number, { ...number, id: "synthetic-2" }];
  const identity = makeCacheIdentity({ ...fixture, questions });
  const inspect = (cache) => checkCache(cache, identity, questions, normalizeAnswer, validateAnswer);
  const cache = { schema: CACHE_SCHEMA, digest: identity.digest, provenance: "automated-qwen", results: [{ id: number.id, answer: "1", valid: true }] };
  assert.equal(inspect({ results: cache.results }).reusable, false);
  assert.deepEqual(inspect(cache).repairQuestions.map((q) => q.id), ["synthetic-2"]);
  cache.results.push({ ...cache.results[0] });
  assert.equal(inspect(cache).reusable, false);
  cache.results[1] = { id: "synthetic-2", answer: "abc", valid: true };
  assert.equal(inspect(cache).repairQuestions.length, 1);
  cache.results[1].answer = "2";
  assert.equal(inspect(cache).repairQuestions.length, 0);
});
test("provider restriction rejects misleading domains and non-Qwen models", () => {
  assert.doesNotThrow(() => assertProvider(endpoint, ["qwen3-vl-plus"]));
  assert.doesNotThrow(() => assertProvider("https://test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", ["qwen3.8-max"]));
  for (const url of ["http://dashscope.aliyuncs.com/compatible-mode/v1", endpoint + "?key=secret", "https://dashscope.aliyuncs.com.evil.example/compatible-mode/v1", "https://user:pass@dashscope.aliyuncs.com/compatible-mode/v1"]) assert.throws(() => assertProvider(url, ["qwen-test"]));
  assert.throws(() => assertProvider(endpoint, ["third-party-model"]));
});
test("question schema catches duplicate IDs", () => {
  const question = { ...number, question: "synthetic", file_name: "synthetic.png" };
  assert.doesNotThrow(() => assertUniqueQuestions([question]));
  assert.throws(() => assertUniqueQuestions([question, question]));
});
test("token accounting keeps unknown cost and missing usage explicit", () => {
  const summary = summarizeRequests([{ status: "ok", elapsedMs: 5, usage: { total_tokens: 10 } }, { status: "ok", elapsedMs: 6 }, { status: "error", elapsedMs: 7 }]);
  assert.equal(summary.reportedTotalTokens, 10);
  assert.equal(summary.responsesWithoutUsage, 1);
  assert.equal(summary.failedAttempts, 1);
  assert.equal(summary.costCny, null);
});
test("development evaluation distinguishes format from correctness and missing answers", () => {
  const cases = [{ ...number, expected: "10" }, { ...number, id: "synthetic-2", expected: "0" }];
  const report = scoreDevelopment(cases, [{ id: number.id, answer: "11" }], normalizeAnswer, validateAnswer);
  assert.equal(report.correct, 0); assert.equal(report.formatValid, 1); assert.equal(report.missing, 1);
  assert.throws(() => scoreDevelopment(cases, [{ id: "unrecognized", answer: "1" }], normalizeAnswer, validateAnswer));
});
test("CLI blocks paid execution and historical base before opening any workbook", () => {
  const script = fileURLToPath(new URL("run.mjs", import.meta.url));
  for (const args of [[], ["--base", "historical.xlsx", "--dry-run"], ["--dry-run", "--max-requests", "0"]]) {
    const child = spawnSync(process.execPath, [script, ...args], { encoding: "utf8" });
    assert.equal(child.status, 1);
    assert.match(child.stderr, /默认不调用付费|新流程禁用 --base|必须是正整数/);
  }
});
test("mocked transport enforces request cap, no redirects, and records usage", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-regression-"));
  const mediaPath = path.join(dir, "synthetic.png");
  await fs.writeFile(mediaPath, "synthetic-media-not-real-test-data");
  const original = globalThis.fetch;
  const events = [];
  let actualCalls = 0;
  globalThis.fetch = async (url, init) => {
    actualCalls++;
    assert.equal(init.redirect, "error");
    assert.equal(JSON.parse(init.body).max_completion_tokens, 1024);
    return new Response(JSON.stringify({ choices: [{ message: { content: '{"answers":[{"id":"synthetic-1","answer":"0"}]}' }, finish_reason: "stop" }], usage: { total_tokens: 11 } }), { status: 200 });
  };
  const options = { apiKey: "dummy-not-a-real-key", baseUrl: endpoint, model: "qwen-test", mediaPath, questions: [number], maxAttempts: 1, maxCompletionTokens: 1024, requestState: { attempts: 0, maxRequests: 1 }, onRequest: async (event) => events.push(event) };
  try {
    await callQwen(options);
    await assert.rejects(callQwen(options), /上限/);
    assert.equal(actualCalls, 1); assert.equal(events.length, 1); assert.equal(events[0].usage.total_tokens, 11);
    assert.equal(JSON.stringify(events).includes(options.apiKey), false);
  } finally {
    globalThis.fetch = original;
    await fs.unlink(mediaPath); await fs.rmdir(dir);
  }
});

test("fallback attribution stays per-question and does not invent a title", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-fallback-"));
  const mediaPath = path.join(dir, "synthetic.png");
  await fs.writeFile(mediaPath, "synthetic-only");
  const original = globalThis.fetch;
  let calls = 0;
  const bodies = [];
  globalThis.fetch = async (_url, init) => {
    bodies.push(JSON.parse(init.body)); calls++;
    const answers = calls === 1 ? [{ id: "synthetic-1", answer: "" }, { id: "synthetic-2", answer: "2" }]
      : [{ id: "synthetic-1", answer: calls === 2 ? "" : "1" }];
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ answers }) } }] }), { status: 200 });
  };
  try {
    const results = await processGroup({ apiKey: "dummy-not-a-real-key", baseUrl: endpoint, modelImage: "qwen-primary", modelPdf: "qwen-primary", maxAttempts: 1 }, mediaPath,
      [number, { ...number, id: "synthetic-2" }]);
    assert.equal(results[0].model, "qwen3.8-max");
    assert.equal(results[1].model, "qwen-primary");
    assert.equal(results.every((r) => r.valid), true);
    assert.doesNotMatch(bodies[2].messages[1].content[1].text, /概括.*单据名称/);
  } finally {
    globalThis.fetch = original;
    await fs.unlink(mediaPath); await fs.rmdir(dir);
  }
});

test("HTTP error bodies never appear in logged diagnostics", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-error-"));
  const mediaPath = path.join(dir, "synthetic.png");
  await fs.writeFile(mediaPath, "synthetic-only");
  const original = globalThis.fetch;
  const fakeSecret = "dummy-secret-must-not-be-logged";
  globalThis.fetch = async () => new Response(fakeSecret, { status: 401 });
  const events = [];
  try {
    await assert.rejects(callQwen({ apiKey: fakeSecret, baseUrl: endpoint, model: "qwen-test", mediaPath, questions: [number], maxAttempts: 1,
      onRequest: async (event) => events.push(event) }), (error) => error.message === "阿里云 API HTTP 401");
    assert.equal(events.length, 1);
    assert.equal(JSON.stringify(events).includes(fakeSecret), false);
  } finally {
    globalThis.fetch = original;
    await fs.unlink(mediaPath); await fs.rmdir(dir);
  }
});

test("authentication and billing rejection stops later source requests", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-fatal-http-"));
  const mediaPath = path.join(dir, "synthetic.png");
  await fs.writeFile(mediaPath, "synthetic-only");
  const original = globalThis.fetch;
  try {
    for (const status of [401, 402, 403]) {
      let calls = 0;
      const events = [], requestState = { attempts: 0, maxRequests: 6 };
      globalThis.fetch = async () => { calls++; return new Response("sensitive-body-not-logged", { status }); };
      const options = { apiKey: "dummy-not-real", baseUrl: endpoint, model: "qwen-test", mediaPath, questions: [number], maxAttempts: 3, requestState, onRequest: async (event) => events.push(event) };
      await assert.rejects(callQwen(options), new RegExp(`HTTP ${status}`));
      await assert.rejects(callQwen(options), /本轮停止新增请求/);
      assert.equal(calls, 1); assert.equal(requestState.attempts, 1); assert.equal(events.length, 1);
      assert.equal(JSON.stringify(events).includes("sensitive-body"), false);
    }
  } finally {
    globalThis.fetch = original;
    await fs.unlink(mediaPath); await fs.rmdir(dir);
  }
});

test("synthetic suite covers every source cell without overlap and has source-disjoint splits", () => {
  const cases = developmentCases();
  assert.equal(cases.length, 30);
  for (const source of sources) {
    const predicted = { row_count: source.row_count, col_count: source.col_count, cells: source.cells };
    assert.equal(validateAnswer(structure, JSON.stringify(predicted)).valid, true);
    assert.equal(source.cells.reduce((n, c) => n + c.rowspan * c.colspan, 0), source.row_count * source.col_count);
  }
  const dev = new Set(cases.filter((c) => c.split === "development").map((c) => c.sourceId));
  const holdout = new Set(cases.filter((c) => c.split === "holdout").map((c) => c.sourceId));
  assert.equal([...dev].some((id) => holdout.has(id)), false);
  assert.equal(scoreDevelopment(cases, cases.map((c) => ({ id: c.id, answer: c.expected })), normalizeAnswer, validateAnswer).correct, 30);
});

test("synthetic arithmetic reference values agree with independent calculations", () => {
  const expected = new Map(developmentCases().map((c) => [c.id, c.expected]));
  assert.equal(Number(expected.get("dev-sales-q3")), (1250 * 3 + 725 * 4) / 100);
  assert.equal(Number(expected.get("dev-sales-q4")), (1250 - 725) / 100);
  assert.equal(Number(expected.get("holdout-merged-q3")), (100 - 80) / 80 * 100);
  assert.equal(Number(expected.get("holdout-units-q2")), 1175 * 100);
  assert.equal(Number(expected.get("holdout-units-q4")), (1175 + 925) / 100);
});

test("offline end-to-end writes traceable reports, reuses cache and repairs missing results", async () => {
  // All input is authored synthetic data; the network is replaced, and artifacts use a fresh temp directory.
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-e2e-"));
  const mediaPath = path.join(dir, "synthetic.png");
  const questionsPath = path.join(dir, "questions.json");
  const stateDir = path.join(dir, "state");
  const questions = [number, { ...number, id: "synthetic-2" }].map((q) => ({ ...q, file_name: "synthetic.png", question: "Return the visible synthetic number" }));
  await fs.writeFile(mediaPath, "synthetic-only");
  await fs.writeFile(questionsPath, JSON.stringify({ questions }));
  const original = { fetch: globalThis.fetch, log: console.log, apiKey: process.env.DASHSCOPE_API_KEY, base: process.env.ALIYUN_BASE_URL, code: process.exitCode };
  const logs = [];
  let calls = 0;
  process.env.DASHSCOPE_API_KEY = "dummy-test-key-only";
  process.env.ALIYUN_BASE_URL = endpoint;
  console.log = (...items) => logs.push(items.join(" "));
  globalThis.fetch = async (_url, init) => {
    calls++;
    const prompt = JSON.parse(init.body).messages[1].content[1].text;
    const requested = JSON.parse(prompt.split("问题清单：\n")[1]);
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ answers: requested.map((q) => ({ id: q.id, answer: "3" })) }) } }], usage: { total_tokens: 17 } }), { status: 200 });
  };
  const argv = ["--allow-paid", "--questions-json", questionsPath, "--media", dir, "--state", stateDir, "--no-export", "--max-requests", "1"];
  try {
    await main({ argv, experimentRoot: dir });
    assert.equal(calls, 1);
    await main({ argv, experimentRoot: dir });
    assert.equal(calls, 1, "full cache must not call model");
    const [cacheName] = await fs.readdir(stateDir);
    const cachePath = path.join(stateDir, cacheName);
    const cache = JSON.parse(await fs.readFile(cachePath, "utf8"));
    cache.results.pop();
    await fs.writeFile(cachePath, JSON.stringify(cache));
    await main({ argv, experimentRoot: dir });
    assert.equal(calls, 2, "missing cached question is actually requested");
    assert.equal(JSON.parse(await fs.readFile(cachePath, "utf8")).results.length, 2);
    const entries = (await fs.readFile(path.join(dir, "experiments.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
    assert.equal(entries.length, 3);
    for (const entry of entries) {
      const report = JSON.parse(await fs.readFile(entry.reportPath, "utf8"));
      assert.equal(report.status, "answers-only-no-submission");
      assert.equal(report.valid, 2); assert.equal(report.invalid, 0); assert.equal(report.outputPath, null);
      assert.equal(entry.leaderboardScore, null); assert.equal(entry.requestSummary.costCny, null);
    }
    assert.equal(entries[1].requestSummary.attempts, 0);
    assert.equal(logs.join("\n").includes("dummy-test-key-only"), false);
    // Retain the temp evidence rather than using a recursive deletion.
  } finally {
    globalThis.fetch = original.fetch; console.log = original.log; process.exitCode = original.code;
    for (const [key, value] of [["DASHSCOPE_API_KEY", original.apiKey], ["ALIYUN_BASE_URL", original.base]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});
