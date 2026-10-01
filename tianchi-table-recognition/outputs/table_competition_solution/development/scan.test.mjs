import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { scanSources, scanCases, publicScanQuestions, scanDatasetVersion } from "./scan-cases.mjs";
import { makeScanSvg, seededNoise, renderScanSource, renderScanDataset } from "./scan-render.mjs";
import { normalizeAnswer, validateAnswer, validateForInference } from "../run.mjs";
import { inspectFullCoverage } from "../structure-coverage.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";
import { sha256 } from "../reliability.mjs";

test("all eight source tables are bounded, non-overlapping and cover every grid slot", () => {
  assert.equal(scanSources.length, 6);
  assert.equal(scanSources.reduce((n, s) => n + s.tables.length, 0), 8);
  for (const source of scanSources) for (const table of source.tables) {
    const query = { question_type: "structure", answer_format: "json" };
    assert.equal(validateAnswer(query, normalizeAnswer(query, table)).valid, true, source.id);
    assert.equal(inspectFullCoverage(table).complete, true, source.id);
    for (const cell of table.cells) assert.equal(typeof cell.text, "string");
    assert.doesNotThrow(() => makeScanSvg(source));
  }
});

test("sixty unique questions are split by source, with clean/scan pairs kept together", () => {
  const cases = scanCases();
  assert.equal(cases.length, 60); assert.equal(new Set(cases.map((q) => q.id)).size, 60);
  const development = new Set(scanCases({ split: "development" }).map((q) => q.sourceId));
  const validation = new Set(scanCases({ split: "validation" }).map((q) => q.sourceId));
  assert.equal(development.size, 3); assert.equal(validation.size, 3);
  for (const id of development) assert.equal(validation.has(id), false);
  for (const pairId of new Set(cases.map((q) => q.pairId))) {
    const pair = cases.filter((q) => q.pairId === pairId);
    assert.equal(pair.length, 2); assert.equal(pair[0].split, pair[1].split);
    assert.deepEqual(pair[0].expected, pair[1].expected);
    assert.equal(pair[0].question, pair[1].question);
  }
});

test("all references pass strict validation, positive/negative evaluator controls are 60/0", () => {
  const cases = scanCases();
  for (const q of cases) assert.equal(validateForInference(q, normalizeAnswer(q, q.expected), { checkFullCoverage: true }).valid, true, q.id);
  const score = (answer) => scoreObservedDevelopment(cases, cases.map((q) => ({ id: q.id, answer: answer(q) })), normalizeAnswer, validateAnswer);
  assert.equal(score((q) => q.expected).correct, 60);
  assert.equal(score(() => "WRONG-REFERENCE-CONTROL").correct, 0);
  assert.equal(score(() => "").missing, 60);
});

test("header references do not cross into body and deliberately omit full-grid coverage", () => {
  for (const source of scanSources) {
    const item = scanCases().find((q) => q.sourceId === source.id && q.structure_scope === "partial");
    assert.ok(item.expected.cells.length > 0);
    assert.ok(item.expected.cells.every((cell) => cell.row + cell.rowspan <= source.headerRows));
    assert.equal(inspectFullCoverage(item.expected).complete, false);
  }
});

test("public inference questions use an allow-list and never include labels or evidence", () => {
  const allowed = new Set(["id", "file_name", "table_hint", "question_type", "answer_format", "question", "structure_scope"]);
  const output = publicScanQuestions(scanCases().map((q) => ({ ...q, secretReference: "DO-NOT-EXPORT" })));
  for (const item of output) for (const key of Object.keys(item)) assert.ok(allowed.has(key), key);
  assert.equal(JSON.stringify(output).includes("DO-NOT-EXPORT"), false);
});

test("independent coordinate and arithmetic checks agree with manually authored labels", () => {
  const at = (id, row, col) => {
    const s = scanSources.find((s) => s.id === id), t = s.tables[s.target];
    return t.cells.find((c) => row >= c.row && row < c.row + c.rowspan && col >= c.col && col < c.col + c.colspan).text;
  };
  const checks = {
    "ss-budget": [String(Number(at("ss-budget", 4, 6))), at("ss-budget", 3, 1), String((Math.round(Number(at("ss-budget", 3, 6)) * 100) - Math.round(Number(at("ss-budget", 3, 3)) * 100)) / 100)],
    "ss-assembly": [at("ss-assembly", 4, 2), at("ss-assembly", 3, 5), String(Number(at("ss-assembly", 2, 3)) + Number(at("ss-assembly", 5, 3)))],
    "ss-warehouse": [at("ss-warehouse", 2, 2), at("ss-warehouse", 4, 1), String([1, 2, 3, 4].reduce((n, r) => n + Number(at("ss-warehouse", r, 2)), 0))],
    "ss-production": [at("ss-production", 3, 5), at("ss-production", 2, 1), String(Number(at("ss-production", 2, 4)) - Number(at("ss-production", 2, 5)))],
    "ss-measurement": [at("ss-measurement", 6, 4), [4, 5].map((r) => ({ 编号: at("ss-measurement", r, 1), 读数: at("ss-measurement", r, 2) })), String((Math.round(Number(at("ss-measurement", 6, 2)) * 10) + Math.round(Number(at("ss-measurement", 6, 3)) * 10)) / 10)],
    "ss-inspection": [at("ss-inspection", 3, 2), at("ss-inspection", 2, 4), String([1, 2, 3, 4].reduce((n, r) => n + Number(at("ss-inspection", r, 2)), 0))],
  };
  for (const source of scanSources) assert.deepEqual(source.questions.map((q) => q.expected), checks[source.id], source.id);
});

test("seeded degradation is deterministic and independent from reference answers", async () => {
  const bytes = Buffer.alloc(100, 127);
  assert.deepEqual(seededNoise(bytes, 101, 3), seededNoise(bytes, 101, 3));
  assert.notDeepEqual(seededNoise(bytes, 101, 3), seededNoise(bytes, 102, 3));
  assert.deepEqual(bytes, Buffer.alloc(100, 127));
  const source = scanSources[0], a = await renderScanSource(source);
  const b = await renderScanSource({ ...source, questions: [] });
  assert.deepEqual(a, b); assert.notDeepEqual(a.clean, a.scan);
});

test("frozen manifest and question files match bytes and reference-free projected questions", async () => {
  const directory = new URL("generated-scan-v1/", import.meta.url);
  const manifest = JSON.parse(await fs.readFile(new URL("manifest.json", directory)));
  assert.equal(manifest.datasetVersion, scanDatasetVersion); assert.equal(manifest.media.length, 12);
  assert.equal(manifest.fixtureSha256, sha256(await fs.readFile(new URL("scan-cases.mjs", import.meta.url))));
  assert.equal(manifest.rendererSha256, sha256(await fs.readFile(new URL("scan-render.mjs", import.meta.url))));
  for (const media of manifest.media) assert.equal(media.sha256, sha256(await fs.readFile(new URL(media.fileName, directory))));
  for (const file of manifest.questionFiles) {
    const bytes = await fs.readFile(new URL(file.name, directory));
    assert.equal(file.sha256, sha256(bytes));
    assert.deepEqual(JSON.parse(bytes).questions, publicScanQuestions(scanCases({ split: file.split, variant: file.variant })));
    assert.equal(file.count, 15);
  }
});

test("rerunning renderer refuses existing frozen directory before modifying it", async () => {
  await assert.rejects(renderScanDataset(), { code: "EEXIST" });
});
