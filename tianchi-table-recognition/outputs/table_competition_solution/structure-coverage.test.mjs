import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { inferStructureScope, inspectFullCoverage } from "./structure-coverage.mjs";
import { normalizeQuestion, normalizeAnswer, validateAnswer, validateForInference, processGroup, main } from "./run.mjs";
import { coverageCases, coverageSources } from "./development/coverage-cases.mjs";

const full = { id: "synthetic-span", file_name: "synthetic.png", question_type: "structure", answer_format: "json", question: "恢复完整表格结构" };
const enabled = { checkFullCoverage: true };
const cell = (text, row, col, rowspan = 1, colspan = 1) => ({ text, row, col, rowspan, colspan });
const correct = { row_count: 2, col_count: 2, cells: [cell("组", 0, 0, 2), cell("数量", 0, 1), cell("0", 1, 1)] };
const incomplete = { ...correct, cells: correct.cells.map((c, i) => i ? { ...c } : { ...c, rowspan: 1 }) };

test("coverage scope requires an explicit full structure request", () => {
  for (const question of ["恢复完整表格结构", "输出整张表格的结构", "cells包含所有单元格", "Return the complete table structure"]) {
    assert.equal(inferStructureScope({ ...full, question }), "full");
  }
  assert.equal(inferStructureScope({ ...full, question: "分析表格" }), "unspecified");
  assert.equal(inferStructureScope({ ...full, question_type: "extract" }), "not-applicable");
  assert.equal(inferStructureScope({ ...full, answer_format: "string" }), "not-applicable");
});

test("partial and negative wording takes precedence over full dimensions", () => {
  for (const question of ["仅恢复表头行结构；尺寸为完整表格", "只输出第一行", "不要恢复完整表格结构", "Return header only with full table dimensions", "Do not recover the full table structure"]) {
    assert.equal(inferStructureScope({ ...full, question, structure_scope: "full" }), "partial");
  }
});

test("explicit metadata survives normalization without importing expected answers", () => {
  const q = normalizeQuestion({ ...full, structure_scope: "partial", expected: correct });
  assert.equal(q.structure_scope, "partial");
  assert.equal(q.expected, undefined);
  assert.equal(normalizeQuestion({ ...full, structure_scope: "guess" }).structure_scope, undefined);
  assert.equal(inferStructureScope({ ...full, question: "输出结构", structure_scope: "full" }), "full");
});

test("vertical and horizontal merges cover every logical slot", () => {
  assert.equal(validateForInference(full, JSON.stringify(correct), enabled).valid, true);
  const horizontal = { row_count: 2, col_count: 3, cells: [cell("标题", 0, 0, 1, 3), cell("甲", 1, 0), cell("", 1, 1), cell("乙", 1, 2)] };
  const report = validateForInference(full, JSON.stringify(horizontal), enabled);
  assert.equal(report.valid, true);
  assert.equal(report.coverage.coveredSlots, "6");
});

test("span gaps are opt-in failures with exact coordinates and no mutation", () => {
  const answer = JSON.stringify(incomplete), snapshot = JSON.stringify(incomplete);
  assert.equal(validateAnswer(full, answer).valid, true);
  assert.equal(validateForInference(full, answer).valid, true);
  const report = validateForInference(full, answer, enabled);
  assert.equal(report.valid, false);
  assert.equal(report.coverage.missingSlots, "1");
  assert.deepEqual(report.coverage.firstGaps, [{ row: 1, col: 0, height: 1, width: 1 }]);
  assert.match(report.error, /重新查看原图/);
  assert.equal(JSON.stringify(incomplete), snapshot);
});

test("partial or ambiguous structure is not forced to tile the whole table", () => {
  for (const question of ["仅恢复表头行结构", "表格结构是什么？"]) {
    assert.equal(validateForInference({ ...full, question }, JSON.stringify(incomplete), enabled).valid, true);
  }
});

test("an explicit blank cell is covered; an omitted blank is a gap", () => {
  const blank = { row_count: 1, col_count: 2, cells: [cell("数据", 0, 0), cell("", 0, 1)] };
  assert.equal(validateForInference(full, JSON.stringify(blank), enabled).valid, true);
  blank.cells.pop();
  assert.equal(validateForInference(full, JSON.stringify(blank), enabled).valid, false);
});

test("huge merged rectangles use exact area arithmetic without grid allocation", () => {
  const large = { row_count: 1_000_000_000, col_count: 1_000_000_000, cells: [cell("合并", 0, 0, 1_000_000_000, 1_000_000_000)] };
  assert.equal(validateForInference(full, JSON.stringify(large), enabled).coverage.totalSlots, "1000000000000000000");
  large.cells[0].colspan--;
  const report = validateForInference(full, JSON.stringify(large), enabled);
  assert.equal(report.coverage.missingSlots, "1000000000");
  assert.deepEqual(report.coverage.firstGaps, [{ row: 0, col: 999999999, height: 1000000000, width: 1 }]);
});

test("overlap and out-of-bounds fail before area calculation", () => {
  const overlap = { ...correct, cells: [...correct.cells, cell("重复", 0, 1)] };
  const invalid = { ...correct, cells: [cell("越界", 0, 0, 3, 2)] };
  for (const table of [overlap, invalid]) {
    const report = validateForInference(full, JSON.stringify(table), enabled);
    assert.equal(report.valid, false);
    assert.equal(report.coverage, undefined);
  }
});

test("gap diagnostics are bounded to four examples", () => {
  const sparse = { row_count: 1, col_count: 12, cells: [0, 2, 4, 6, 8, 10].map((col) => cell("x", 0, col)) };
  const report = inspectFullCoverage(sparse);
  assert.equal(report.missingSlots, "6");
  assert.equal(report.firstGaps.length, 4);
});

test("new independent fixtures include complete, partial, blank and multi-table cases", () => {
  assert.equal(coverageSources.length, 4);
  assert.equal(coverageCases().length, 12);
  for (const q of coverageCases()) {
    const answer = normalizeAnswer(q, q.expected);
    assert.equal(validateForInference(q, answer, enabled).valid, true, q.id);
    if (q.structure_scope === "full") assert.equal(inspectFullCoverage(q.expected).complete, true, q.id);
    if (q.structure_scope === "partial") assert.equal(inspectFullCoverage(q.expected).complete, false, q.id);
  }
});

async function withMockedGroup(answers, options, action) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-coverage-"));
  const mediaPath = path.join(dir, "synthetic.png");
  await fs.writeFile(mediaPath, "synthetic-only-no-real-image");
  const original = globalThis.fetch;
  const bodies = [];
  globalThis.fetch = async (_url, init) => {
    const body = JSON.parse(init.body);
    bodies.push(body);
    const answer = answers[bodies.length - 1];
    assert.notEqual(answer, undefined, "unexpected extra transport call");
    const content = typeof answer === "string" ? answer : JSON.stringify({ answers: [{ id: full.id, answer }] });
    return new Response(JSON.stringify({ choices: [{ message: { content } }] }), { status: 200 });
  };
  try {
    const opts = { apiKey: "dummy-not-a-real-key", baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1", modelImage: "qwen-primary", modelPdf: "qwen-primary", maxAttempts: 1, maxCompletionTokens: 8192,
      requestState: { attempts: 0, maxRequests: 2 }, ...options };
    await action(await processGroup(opts, mediaPath, [full]), bodies);
  } finally {
    globalThis.fetch = original;
    await fs.unlink(mediaPath);
    await fs.rmdir(dir);
  }
}

test("a coverage failure requests visual recheck and retains both answers", async () => {
  await withMockedGroup([incomplete, correct], enabled, (results, bodies) => {
    assert.equal(bodies.length, 2);
    assert.equal(results[0].valid, true);
    assert.deepEqual(JSON.parse(results[0].answer), correct);
    assert.deepEqual(results[0].validationHistory.map((v) => v.valid), [false, true]);
    assert.deepEqual(JSON.parse(results[0].validationHistory[0].answer), incomplete);
    assert.match(bodies[1].messages[1].content[1].text, /row=1,col=0/);
    assert.equal(bodies[1].messages[1].content[0].type, "image_url");
    assert.equal(bodies.every((b) => b.max_completion_tokens === 8192), true);
  });
});

test("disabled guard keeps the baseline request and answer unchanged", async () => {
  await withMockedGroup([incomplete], {}, (results, bodies) => {
    assert.equal(bodies.length, 1);
    assert.equal(results[0].valid, true);
    assert.equal(results[0].validationHistory.length, 1);
    assert.equal(results[0].validationHistory[0].stage, "initial");
    assert.deepEqual(JSON.parse(results[0].answer), incomplete);
  });
});

test("request cap prevents paid retry and never fills a missing cell automatically", async () => {
  await withMockedGroup([incomplete], { ...enabled, requestState: { attempts: 0, maxRequests: 1 } }, (results, bodies) => {
    assert.equal(bodies.length, 1);
    assert.equal(results[0].valid, false);
    assert.match(results[0].error, /请求次数上限/);
    assert.deepEqual(JSON.parse(results[0].answer), incomplete);
  });
});

test("malformed batch JSON repair respects the configured token ceiling", async () => {
  await withMockedGroup(["{broken", correct], enabled, (results, bodies) => {
    assert.equal(results[0].valid, true);
    assert.equal(bodies.length, 2);
    assert.deepEqual(bodies.map((b) => b.max_completion_tokens), [8192, 8192]);
  });
});

test("CLI coverage option survives reports, cache reuse and cache revalidation", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "table-coverage-e2e-"));
  const questionsPath = path.join(dir, "questions.json"), stateDir = path.join(dir, "cache");
  await fs.writeFile(path.join(dir, full.file_name), "synthetic-only");
  await fs.writeFile(questionsPath, JSON.stringify({ questions: [full] }));
  const original = { fetch: globalThis.fetch, log: console.log, code: process.exitCode,
    apiKey: process.env.DASHSCOPE_API_KEY, base: process.env.ALIYUN_BASE_URL };
  const logs = [], bodies = [];
  console.log = (...args) => logs.push(args.join(" "));
  process.env.DASHSCOPE_API_KEY = "dummy-coverage-key-only";
  process.env.ALIYUN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1";
  globalThis.fetch = async (_url, init) => {
    bodies.push(JSON.parse(init.body));
    const answer = bodies.length === 1 ? incomplete : correct;
    return new Response(JSON.stringify({ choices: [{ message: { content: JSON.stringify({ answers: [{ id: full.id, answer }] }) } }], usage: { total_tokens: 10 } }), { status: 200 });
  };
  const argv = ["--allow-paid", "--questions-json", questionsPath, "--media", dir, "--state", stateDir, "--no-export", "--max-requests", "2", "--max-attempts", "1", "--max-completion-tokens", "8192", "--check-full-coverage"];
  try {
    await main({ argv, experimentRoot: dir });
    assert.equal(bodies.length, 2);
    await main({ argv, experimentRoot: dir });
    assert.equal(bodies.length, 2, "validated candidate cache should be reused");
    const [cacheName] = await fs.readdir(stateDir), cachePath = path.join(stateDir, cacheName);
    const cache = JSON.parse(await fs.readFile(cachePath, "utf8"));
    cache.results[0].answer = JSON.stringify(incomplete);
    cache.results[0].valid = true;
    await fs.writeFile(cachePath, JSON.stringify(cache));
    await main({ argv, experimentRoot: dir });
    assert.equal(bodies.length, 3, "cached valid flag must not bypass coverage revalidation");
    const entries = (await fs.readFile(path.join(dir, "experiments.jsonl"), "utf8")).trim().split("\n").map(JSON.parse);
    assert.equal(entries.length, 3);
    for (const entry of entries) {
      const report = JSON.parse(await fs.readFile(entry.reportPath, "utf8"));
      assert.equal(report.checkFullCoverage, true);
      assert.deepEqual(report.structureScopes, { full: 1 });
      assert.equal(report.valid, 1);
      assert.equal(report.invalid, 0);
      assert.equal(report.outputPath, null);
      assert.equal(entry.leaderboardScore, null);
    }
    assert.equal(entries[1].requestSummary.attempts, 0);
    assert.equal(logs.join("\n").includes("dummy-coverage-key-only"), false);
    // Keep uniquely named temporary evidence; do not recursively delete an arbitrary directory.
  } finally {
    globalThis.fetch = original.fetch; console.log = original.log; process.exitCode = original.code;
    for (const [key, value] of [["DASHSCOPE_API_KEY", original.apiKey], ["ALIYUN_BASE_URL", original.base]]) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  }
});
