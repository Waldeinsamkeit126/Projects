import fs from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";
import { verifyFullPlan, auditFullResults, normalizeFull, VERSION } from "./full-candidate.mjs";
import { parseModelAnswers } from "./run.mjs";
import { sha256 } from "./reliability.mjs";

export async function validateCompleteRun(runDir) {
  const read = name => fs.readFile(path.join(runDir, name), "utf8");
  const jsonl = async name => (await read(name)).trim().split(/\r?\n/).map(JSON.parse);
  const plan = JSON.parse(await read("plan.json")), report = JSON.parse(await read("report.json"));
  await verifyFullPlan(plan);
  assert.equal(report.version, VERSION); assert.equal(report.planDigest, plan.digest);
  assert.equal(report.sourceHash, plan.sourceHash); assert.equal(report.inputSha256, plan.inputSha256);
  assert.equal(report.status, "complete-awaiting-export-review"); assert.equal(report.stopReason, null);
  const requests = await jsonl("requests.jsonl"), rows = await jsonl("results.jsonl"), traces = await jsonl("inference-trace.jsonl");
  assert.equal(report.apiRequests, plan.units.length); assert.equal(requests.length, plan.units.length);
  assert.ok(report.apiRequests <= report.maxRequests && report.maxRequests <= plan.settings.maxRequests);
  assert.deepEqual(requests, report.requests);
  const audit = auditFullResults(plan, rows);
  assert.equal(audit.complete, true); assert.deepEqual(audit, report.audit);
  assert.equal(traces.length, plan.units.length * 2);
  for (const [i, unit] of plan.units.entries()) {
    const req = requests[i];
    assert.equal(req.requestIndex, unit.requestIndex); assert.equal(req.httpStatus, 200);
    assert.equal(req.finishReason, "stop"); assert.equal(req.model, unit.model); assert.equal(req.resolvedModel, unit.model);
    assert.equal(req.status, "format-checked-not-proven-correct"); assert.equal(req.apiRequestMade, true);
    assert.deepEqual(req.questionIds, unit.questions.map(q => q.id));
    const prepared = traces.filter(t => t.kind === "request-prepared" && t.requestIndex === req.requestIndex);
    const responses = traces.filter(t => t.kind === "response" && t.requestIndex === req.requestIndex);
    assert.equal(prepared.length, 1); assert.equal(responses.length, 1);
    assert.equal(prepared[0].mediaSha256, unit.mediaSha256); assert.equal(prepared[0].promptSha256, unit.promptSha256);
    assert.equal(responses[0].resolvedModel, unit.model); assert.equal(responses[0].finishReason, "stop");
    const parsed = parseModelAnswers(responses[0].content, unit.questions);
    for (const q of unit.questions) {
      const row = rows.find(r => r.id === q.id);
      assert.equal(row.answer, normalizeFull(q, parsed.get(q.id)));
      assert.equal(row.provenance, VERSION); assert.equal(row.runId, report.runId); assert.equal(row.requestIndex, req.requestIndex);
      assert.equal(row.model, unit.model); assert.equal(row.sourceFile, q.file_name);
      assert.equal(row.mediaSha256, unit.mediaSha256); assert.equal(row.promptSha256, unit.promptSha256);
      assert.ok(row.answer.length <= 32767, "答案超过 Excel 单元格长度，不能截断");
    }
  }
  return { plan, report, rows, audit };
}

export async function exportCompleteRun(runDir) {
  const { plan, report, rows } = await validateCompleteRun(runDir);
  const output = path.join(runDir, "submission-full-automated-20260919.xlsx");
  try { await fs.access(output); throw new Error("提交文件已存在，禁止覆盖"); } catch (e) { if (e.code !== "ENOENT") throw e; }
  assert.equal(sha256(await fs.readFile(plan.templatePath)), plan.templateSha256);
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(plan.templatePath));
  const sheets = (await wb.inspect({ kind: "sheet", include: "id,name" })).ndjson.trim().split("\n").map(JSON.parse).filter(r => r.kind === "sheet");
  assert.equal(sheets.length, 1); assert.equal(sheets[0].range, "A1:B1");
  const sheet = wb.worksheets.getItemAt(0); assert.deepEqual(sheet.getRange("A1:B1").values, [["id", "answer"]]);
  const byId = new Map(rows.map(r => [r.id, r.answer]));
  const values = plan.questionOrder.map(id => [id, byId.get(id)]);
  // Template schema and styles retained. Answers are exact machine-readable strings, not formulas.
  sheet.getRange("A2:B909").values = values.map(row => row.map(v => v.startsWith("=") ? "'" + v : v));
  wb.recalculate();
  assert.deepEqual(sheet.getRange("A2:B909").values, values);
  assert.ok(sheet.getRange("A1:B909").formulas.flat().every(v => !v));
  const preview = await wb.render({ sheetName: sheets[0].name, range: "A1:B7", scale: 1.5 });
  await fs.writeFile(path.join(runDir, "submission-preview.png"), new Uint8Array(await preview.arrayBuffer()), { flag: "wx" });
  const blob = await SpreadsheetFile.exportXlsx(wb);
  const bytes = new Uint8Array(await blob.arrayBuffer());
  assert.ok(bytes.length < 100 * 1024 * 1024);
  await fs.writeFile(output, bytes, { flag: "wx" });
  const reread = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
  const saved = reread.worksheets.getItemAt(0);
  assert.deepEqual(saved.getUsedRange(true).values, [["id", "answer"], ...values]);
  assert.ok(saved.getRange("A1:B909").formulas.flat().every(v => !v));
  const exportReport = { runId: report.runId, planDigest: plan.digest, output, bytes: bytes.length,
    sha256: sha256(bytes), questionCount: values.length, rereadVerified: true, submitted: false,
    groundTruthAccuracy: null, resultsSha256: sha256(await fs.readFile(path.join(runDir, "results.jsonl"))) };
  await fs.writeFile(path.join(runDir, "export-report.json"), JSON.stringify(exportReport, null, 2), { flag: "wx" });
  return exportReport;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  if (process.argv.length !== 3) throw new Error("仅接收一个完整运行目录");
  console.log(JSON.stringify(await exportCompleteRun(path.resolve(process.argv[2])), null, 2));
}
