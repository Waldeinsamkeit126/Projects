import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { selectReviewUnits, reviewGuidance, createReviewPlan, verifyReviewPlan, executeReviewPlan, reviewUnit } from "./structure-review.mjs";

const key = "fake-test-key-never-a-real-credential";
const cell = (text = "A", changes = {}) => ({ text, row: 0, col: 0, rowspan: 1, colspan: 1, ...changes });
const table = (rows = 1, cells = [cell()]) => ({ row_count: rows, col_count: 1, cells });
const q = (id, full = true, file = "one.png", hint = "示例目标表") => ({ id, file_name: file, table_hint: hint, question_type: "structure", answer_format: "json",
  structure_scope: full ? "full" : "partial", question: full ? "恢复完整表格结构" : "仅恢复表头结构" });
const questions = [q("f"), q("h", false)];
const predictions = [{ id: "f", answer: JSON.stringify(table()) }, { id: "h", answer: JSON.stringify(table(2)) }];
const content = (qs, value = table()) => JSON.stringify({ answers: qs.map((item) => ({ id: item.id, answer: value })) });

async function fixture({ qs = questions, results = predictions } = {}) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "structure-review-test-"));
  const questionsPath = path.join(dir, "questions.json"), predictionsPath = path.join(dir, "baseline.jsonl");
  await fs.writeFile(questionsPath, JSON.stringify({ questions: qs }));
  await fs.writeFile(predictionsPath, results.map((r) => JSON.stringify(r)).join("\n") + "\n");
  for (const file of new Set(qs.map((item) => item.file_name))) await fs.writeFile(path.join(dir, file), "fake-image-test-only");
  const plan = await createReviewPlan({ questionsPath, predictionsPath, mediaDir: dir });
  return { dir, plan, outputRoot: path.join(dir, "out"), baseline: await fs.readFile(predictionsPath, "utf8") };
}

async function mocked(sequence, fn) {
  const original = globalThis.fetch, bodies = [];
  globalThis.fetch = async (_url, init) => {
    bodies.push(JSON.parse(init.body));
    assert.ok(bodies.length <= sequence.length, "unexpected network retry");
    const next = sequence[bodies.length - 1];
    if (next instanceof Error) throw next;
    if (typeof next === "function") return next();
    return new Response(JSON.stringify({ model: "qwen-test-resolved", id: "mock-review-request", choices: [{ finish_reason: "stop", message: { content: next } }], usage: { total_tokens: 17 } }));
  };
  try { await fn(bodies); } finally { globalThis.fetch = original; }
}

test("review selects conflict and coverage units, excludes labels, and never mutates baseline", () => {
  const qs = [...questions, q("g", true, "two.png"), q("gh", false, "two.png"), { ...q("n"), question_type: "extract", answer_format: "number" }];
  qs[0].expected = "SECRET_REFERENCE_LABEL";
  const gap = table(2), results = [...predictions, { id: "g", answer: gap }, { id: "gh", answer: gap }, { id: "n", answer: "wrong" }];
  const original = JSON.stringify([qs, results]);
  const units = selectReviewUnits(qs, results);
  assert.equal(units.length, 2);
  assert.deepEqual(units.map((u) => u.questions.map((item) => item.id)), [["f", "h"], ["g", "gh"]]);
  assert.equal(units[0].triggers[0].kind, "cross-answer-conflict");
  assert.equal(units[1].triggers[0].kind, "full-grid-gap");
  assert.equal(JSON.stringify(units).includes("SECRET_REFERENCE_LABEL"), false);
  assert.equal(JSON.stringify([qs, results]), original);
  assert.match(reviewGuidance(units[0]), /均非参考标签/);
});

test("review skips PDFs, ambiguous targets, missing/invalid answers and redacted answers", () => {
  for (const changes of [{ file_name: "one.pdf" }, { table_hint: "11" }]) {
    assert.equal(selectReviewUnits(questions.map((item) => ({ ...item, ...changes })), predictions).length, 0);
  }
  assert.equal(selectReviewUnits(questions, [{ id: "f", answer: "bad" }]).length, 0);
  assert.equal(selectReviewUnits(questions, predictions.map((r) => ({ ...r, answerRedacted: true }))).length, 0);
  assert.equal(selectReviewUnits([...questions, q("f2")], [...predictions, { id: "f2", answer: table(2) }]).length, 0);
  assert.throws(() => selectReviewUnits(questions, [...predictions, predictions[0]]), /重复/);
  assert.throws(() => selectReviewUnits(questions, [{ id: "unexpected", answer: "1" }]), /未知/);
});

test("freeze verifies code/input/media identity and rejects changed plan fields", async () => {
  const f = await fixture();
  await verifyReviewPlan(f.plan);
  const changed = structuredClone(f.plan); changed.settings.maxAttempts = 2;
  await assert.rejects(verifyReviewPlan(changed), /指纹已变更/);
  await fs.appendFile(f.plan.inputs.predictionsPath, "\n");
  await assert.rejects(verifyReviewPlan(f.plan), /指纹已变更/);
  const g = await fixture(); await fs.appendFile(g.plan.units[0].mediaPath, "changed");
  await assert.rejects(verifyReviewPlan(g.plan), /指纹已变更/);
});

test("media outside the selected directory is rejected", async () => {
  const f = await fixture();
  const media = path.join(f.dir, "media"); await fs.mkdir(media);
  await fs.writeFile(f.plan.inputs.questionsPath, JSON.stringify({ questions: questions.map((item) => ({ ...item, file_name: "../one.png" })) }));
  await assert.rejects(createReviewPlan({ ...f.plan.inputs, mediaDir: media }), /越出/);
});

test("dry-run defaults to no API and does not create a paid-run directory", async () => {
  const f = await fixture();
  await mocked([], async () => {
    const result = await executeReviewPlan(f.plan, { outputRoot: f.outputRoot });
    assert.equal(result.apiRequests, 0); assert.equal(result.questionCount, 2);
    const explicit = await executeReviewPlan(f.plan, { allowPaid: true, dryRun: true, outputRoot: f.outputRoot });
    assert.equal(explicit.apiRequests, 0);
  });
  await assert.rejects(fs.access(f.outputRoot));
});

test("paid gate requires explicit capped budget and a credential; rejects other providers", async () => {
  const f = await fixture();
  await mocked([], async () => {
    for (const maxRequests of [undefined, 0, 2, 1.5]) {
      await assert.rejects(executeReviewPlan(f.plan, { allowPaid: true, maxRequests, apiKey: key }), /请求上限/);
    }
    await assert.rejects(executeReviewPlan(f.plan, { allowPaid: true, maxRequests: 1 }), /缺少进程凭证/);
    await assert.rejects(executeReviewPlan(f.plan, { allowPaid: true, maxRequests: 1, apiKey: key, baseUrl: "https://example.com" }), /阿里云/);
  });
});

test("one request produces independent candidates, preserves baseline and locks paid replay", async () => {
  const f = await fixture();
  await mocked([content(questions)], async (bodies) => {
    const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot });
    assert.equal(result.status, "completed-candidates-only"); assert.equal(result.requests.attempts, 1);
    assert.equal(result.requests.reportedTotalTokens, 17); assert.equal(result.modelAccuracy, null);
    const candidates = (await fs.readFile(result.resultPath, "utf8")).trim().split("\n").map(JSON.parse);
    assert.equal(candidates.length, 2); assert.equal(candidates[0].model, "qwen-test-resolved");
    assert.equal(candidates[0].provenance, "automated-qwen-review-candidate");
    assert.equal(await fs.readFile(f.plan.inputs.predictionsPath, "utf8"), f.baseline);
    assert.equal(bodies[0].max_completion_tokens, 8192); assert.equal(bodies[0].enable_thinking, false);
    assert.equal(bodies[0].messages[1].content[0].type, "image_url");
    assert.match(bodies[0].messages[1].content[1].text, /最右列/);
    assert.equal((await fs.readFile(result.tracePath, "utf8")).includes(key), false);
    await assert.rejects(executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot }), /EEXIST/);
    assert.equal(bodies.length, 1);
  });
});

test("hard cap stops after one of two selected tables without replacing remaining answers", async () => {
  const qs = [...questions, q("f2", true, "two.png"), q("h2", false, "two.png")];
  const f = await fixture({ qs, results: [...predictions, { id: "f2", answer: table() }, { id: "h2", answer: table(2) }] });
  await mocked([content(questions)], async () => {
    const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot });
    assert.equal(result.stopReason, "request-cap"); assert.equal(result.unattemptedUnits, 1);
    assert.equal(await fs.readFile(f.plan.inputs.predictionsPath, "utf8"), f.baseline);
  });
});

test("malformed JSON, missing IDs and unresolved conflicts stop without repairs or fallback", async () => {
  for (const output of ["not-json", JSON.stringify({ answers: [] }), JSON.stringify({ answers: predictions })]) {
    const f = await fixture();
    await mocked([output], async (bodies) => {
      const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot });
      assert.equal(result.status, "stopped"); assert.equal(bodies.length, 1);
    });
  }
});

test("truncated HTTP success stops even if answer JSON is parseable", async () => {
  const f = await fixture();
  await mocked([() => new Response(JSON.stringify({ choices: [{ finish_reason: "length", message: { content: content(questions) } }], usage: { total_tokens: 10 } }))], async () => {
    const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot });
    assert.equal(result.stopReason, "truncated"); assert.equal(result.outcomes[0].status, "truncated");
    assert.ok((await fs.readFile(result.resultPath, "utf8")).includes('"candidatePassedChecks":false'));
  });
});

test("two successful review units stay within total budget and keep separate request attribution", async () => {
  const qs2 = [q("f2", true, "two.png"), q("h2", false, "two.png")];
  const f = await fixture({ qs: [...questions, ...qs2], results: [...predictions, { id: "f2", answer: table() }, { id: "h2", answer: table(2) }] });
  await mocked([content(questions), content(qs2)], async (bodies) => {
    const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 2, outputRoot: f.outputRoot });
    assert.equal(result.status, "completed-candidates-only"); assert.equal(result.requests.attempts, 2);
    assert.equal(result.unattemptedUnits, 0); assert.equal(bodies.length, 2);
    const candidates = (await fs.readFile(result.resultPath, "utf8")).trim().split("\n").map(JSON.parse);
    assert.deepEqual(candidates.map((r) => r.requestIndex), [1, 1, 2, 2]);
    assert.ok(candidates.every((r) => r.candidatePassedChecks));
    assert.equal((await fs.readdir(path.dirname(result.reportPath))).some((p) => p.endsWith(".xlsx")), false);
  });
});

test("an unresolved first unit stops later tables despite unused quota", async () => {
  const qs2 = [q("f2", true, "two.png"), q("h2", false, "two.png")];
  const f = await fixture({ qs: [...questions, ...qs2], results: [...predictions, { id: "f2", answer: table() }, { id: "h2", answer: table(2) }] });
  await mocked([JSON.stringify({ answers: predictions })], async (bodies) => {
    const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 2, outputRoot: f.outputRoot });
    assert.equal(result.stopReason, "unresolved-checks"); assert.equal(result.unattemptedUnits, 1);
    assert.equal(bodies.length, 1); assert.equal(result.requests.attempts, 1);
  });
});

test("auth/transport errors stop immediately, do not retry, and never record raw secrets", async () => {
  for (const failure of [new TypeError(`transport-${key}`), () => new Response(`UPSTREAM ${key}`, { status: 401 })]) {
    const f = await fixture();
    await mocked([failure], async (bodies) => {
      const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot });
      assert.equal(result.status, "stopped"); assert.equal(bodies.length, 1);
      const serialized = JSON.stringify(result) + await fs.readFile(result.tracePath, "utf8");
      assert.equal(serialized.includes(key), false); assert.equal(serialized.includes("UPSTREAM"), false);
    });
  }
});

test("sensitive answer or trace write failure cannot turn into successful review", async () => {
  const f = await fixture();
  await mocked([content(questions, table(1, [cell(key)]))], async () => {
    const result = await executeReviewPlan(f.plan, { allowPaid: true, apiKey: key, maxRequests: 1, outputRoot: f.outputRoot });
    assert.equal(result.stopReason, "unresolved-checks");
    const saved = await fs.readFile(result.resultPath, "utf8"); assert.equal(saved.includes(key), false);
    assert.ok(saved.includes('"answerRedacted":true'));
  });
  await mocked([content(questions)], async (bodies) => {
    const requestState = { attempts: 0, maxRequests: 2 };
    await assert.rejects(reviewUnit(f.plan.units[0], { apiKey: key, baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", requestState,
      onTrace: async () => { throw new Error("mock audit failure"); } }), /审计记录/);
    assert.match(requestState.haltReason, /审计记录/); assert.equal(bodies.length, 1);
  });
});
