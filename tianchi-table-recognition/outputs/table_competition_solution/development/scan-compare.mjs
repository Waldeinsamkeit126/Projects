import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { normalizeAnswer, validateAnswer } from "../run.mjs";
import { sha256, inferenceSourceHash } from "../reliability.mjs";
import { scanCases, scanDatasetVersion } from "./scan-cases.mjs";
import { scoreObservedDevelopment } from "./scoring.mjs";

export function compareScanPredictions(cleanPredictions, scanPredictions, split = "development") {
  if (!["development", "validation"].includes(split)) throw new Error("Compare one source-disjoint split at a time.");
  const cleanCases = scanCases({ split, variant: "clean" }), scanQuestions = scanCases({ split, variant: "scan" });
  const clean = scoreObservedDevelopment(cleanCases, cleanPredictions, normalizeAnswer, validateAnswer);
  const scan = scoreObservedDevelopment(scanQuestions, scanPredictions, normalizeAnswer, validateAnswer);
  const scanByPair = new Map(scanQuestions.map((q) => [q.pairId, q]));
  const cleanById = new Map(clean.details.map((d) => [d.id, d])), scanById = new Map(scan.details.map((d) => [d.id, d]));
  const pairs = cleanCases.map((q) => {
    const mate = scanByPair.get(q.pairId);
    assert.deepEqual(q.expected, mate.expected); assert.equal(q.question, mate.question);
    const a = cleanById.get(q.id), b = scanById.get(mate.id);
    return { pairId: q.pairId, sourceId: q.sourceId, category: q.category, cleanId: q.id, scanId: mate.id,
      cleanCorrect: a.correct, scanCorrect: b.correct, cleanOutcome: a.outcome, scanOutcome: b.outcome };
  });
  return { split, clean, scan, pairCount: pairs.length, sourceCount: new Set(pairs.map((p) => p.sourceId)).size,
    cleanCorrectScanWrong: pairs.filter((p) => p.cleanCorrect && !p.scanCorrect).length,
    cleanWrongScanCorrect: pairs.filter((p) => !p.cleanCorrect && p.scanCorrect).length,
    bothCorrect: pairs.filter((p) => p.cleanCorrect && p.scanCorrect).length,
    bothWrong: pairs.filter((p) => !p.cleanCorrect && !p.scanCorrect).length, pairs };
}

async function main(args) {
  const [cleanDir, scanDir, output] = args;
  if (!cleanDir || !scanDir || !output || args.length !== 3) throw new Error("Usage: node scan-compare.mjs CLEAN_RUN_DIR SCAN_RUN_DIR NEW_REPORT_JSON");
  const manifestBytes = await fs.readFile(new URL("generated-scan-v1/manifest.json", import.meta.url));
  const manifest = JSON.parse(manifestBytes);
  const fixtureHash = sha256(await fs.readFile(new URL("scan-cases.mjs", import.meta.url)));
  assert.equal(fixtureHash, manifest.fixtureSha256);
  const sourceHash = await inferenceSourceHash(fileURLToPath(new URL("../", import.meta.url)));
  const load = async (dir, variant) => {
    const report = JSON.parse(await fs.readFile(path.join(dir, "run-report.json")));
    const bytes = await fs.readFile(path.join(dir, "results.jsonl"));
    const queryFile = manifest.questionFiles.find((q) => q.split === "development" && q.variant === variant);
    const questionsPath = fileURLToPath(new URL(`generated-scan-v1/${queryFile.name}`, import.meta.url));
    assert.equal(path.resolve(report.questionsJsonPath), path.resolve(questionsPath));
    assert.equal(report.inputSha256, queryFile.sha256);
    assert.equal(sha256(await fs.readFile(questionsPath)), queryFile.sha256);
    assert.equal(report.sourceHash, sourceHash);
    assert.equal(report.noExport, true); assert.equal(report.outputPath, null);
    assert.equal(report.questionCount, 15); assert.equal(report.maxCompletionTokens, 8192);
    assert.equal(report.maxAttempts, 1); assert.equal(report.maxRequests, 4);
    assert.equal(report.checkFullCoverage, false); assert.equal(report.enableThinking, false);
    assert.equal(report.models.image, "qwen3-vl-plus");
    assert.ok(report.requests.attempts <= 4);
    const requests = (await fs.readFile(path.join(dir, "requests.jsonl"), "utf8")).trim().split(/\r?\n/).filter(Boolean).map((s) => JSON.parse(s));
    assert.equal(requests.length, report.requests.attempts);
    for (const media of manifest.media.filter((m) => m.split === "development" && m.variant === variant)) {
      assert.equal(sha256(await fs.readFile(path.join(report.mediaDir, media.fileName))), media.sha256);
    }
    return { report, predictionsSha256: sha256(bytes), predictions: bytes.toString("utf8").trim().split(/\r?\n/).filter(Boolean).map((s) => JSON.parse(s)), requests };
  };
  const a = await load(cleanDir, "clean"), b = await load(scanDir, "scan");
  for (const key of ["sourceHash", "endpoint", "models", "maxCompletionTokens", "maxAttempts", "enableThinking", "refreshStructure", "checkFullCoverage", "checkStructureConsistency"]) assert.deepEqual(a.report[key], b.report[key], key);
  const comparison = compareScanPredictions(a.predictions, b.predictions);
  const result = { datasetVersion: scanDatasetVersion, generatedAt: new Date().toISOString(), manifestSha256: sha256(manifestBytes),
    fixtureHash, sourceHash, ...comparison,
    cleanRun: { runId: a.report.runId, predictionsSha256: a.predictionsSha256, status: a.report.status, requests: a.report.requests },
    scanRun: { runId: b.report.runId, predictionsSha256: b.predictionsSha256, status: b.report.status, requests: b.report.requests },
    totalRequests: a.report.requests.attempts + b.report.requests.attempts,
    reportedTotalTokens: a.report.requests.reportedTotalTokens + b.report.requests.reportedTotalTokens,
    truncatedResponses: [...a.requests, ...b.requests].filter((r) => r.finishReason === "length").length,
    costCny: null, leaderboardScore: null,
    limitation: "同源图像质量配对的单次试验，不是候选修复收益或确定因果；退化因素混合，只有3个开发源页面。验证集未调用，合成结果不能换算天池成绩。" };
  assert.ok(result.totalRequests <= 8);
  await fs.writeFile(path.resolve(output), JSON.stringify(result, null, 2), { flag: "wx" });
  console.log(JSON.stringify(result, null, 2));
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main(process.argv.slice(2));
