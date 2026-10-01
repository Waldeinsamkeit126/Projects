import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { normalizeQuestion, normalizeAnswer, validateForInference, buildPrompt, resolveMediaFiles } from "../run.mjs";
import { sha256, makeCacheIdentity, checkCache, inferenceSourceHash } from "../reliability.mjs";
import { inspectStructureConsistency } from "../structure-consistency.mjs";

const [reportArgument, cacheArgument] = process.argv.slice(2);
if (!reportArgument || !cacheArgument) throw new Error("Usage: node check-resume.mjs RUN_REPORT CACHE_DIRECTORY");
const report = JSON.parse(await fs.readFile(path.resolve(reportArgument), "utf8"));
if (!report.questionsJsonPath || !report.noExport) throw new Error("只检查 JSON 开发集的无导出运行，不处理正式测试工作簿");
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const sourceHash = await inferenceSourceHash(root);
const inputBytes = await fs.readFile(report.questionsJsonPath);
if (sourceHash !== report.sourceHash || sha256(inputBytes) !== report.inputSha256) throw new Error("推理代码或问题清单已变更，不能假定旧缓存可用于原样续跑");
const questions = JSON.parse(inputBytes).questions.map(normalizeQuestion);
const { resolved, unresolved } = await resolveMediaFiles(questions, report.mediaDir);
if (unresolved.length) throw new Error("开发集媒体文件缺失");
const groups = new Map();
for (const question of questions) {
  const file = resolved.get(question.file_name);
  if (!groups.has(file)) groups.set(file, []);
  groups.get(file).push(question);
}
const details = [];
const cachedResults = [];
for (const [mediaPath, group] of groups) {
  const model = path.extname(mediaPath).toLowerCase() === ".pdf" ? report.models.pdf : report.models.image;
  const identity = makeCacheIdentity({ mediaBytes: await fs.readFile(mediaPath), questions: group, prompt: buildPrompt(group), sourceHash,
    options: { baseUrl: report.endpoint, model, maxCompletionTokens: report.maxCompletionTokens,
      maxAttempts: report.maxAttempts ?? 1, enableThinking: report.enableThinking, refreshStructure: report.refreshStructure,
      checkFullCoverage: report.checkFullCoverage, checkStructureConsistency: report.checkStructureConsistency } });
  let cache = { reusable: false };
  try {
    const cached = JSON.parse(await fs.readFile(path.join(path.resolve(cacheArgument), `${path.basename(mediaPath)}-${identity.digest}.json`), "utf8"));
    cache = checkCache(cached, identity, group, normalizeAnswer, (q, answer) => validateForInference(q, answer, report));
  } catch (error) { if (error.code !== "ENOENT" && !(error instanceof SyntaxError)) throw error; }
  const pending = cache.reusable ? cache.repairQuestions.length : group.length;
  if (cache.reusable) cachedResults.push(...cache.resultsById.values());
  details.push({ source: path.basename(mediaPath), total: group.length, cachedValid: group.length - pending, pending });
}
console.log(JSON.stringify({ sourceHash, unchangedInference: true, requestsMade: 0,
  cachedValid: details.reduce((sum, item) => sum + item.cachedValid, 0),
  pending: details.reduce((sum, item) => sum + item.pending, 0),
  pendingSources: details.filter((item) => item.pending).length,
  cachedConsistency: report.checkStructureConsistency ? inspectStructureConsistency(questions, cachedResults, normalizeAnswer, (q, a) => validateForInference(q, a, {})) : null,
  resumeOptions: { maxAttempts: report.maxAttempts ?? 1, maxCompletionTokens: report.maxCompletionTokens,
    checkFullCoverage: Boolean(report.checkFullCoverage), checkStructureConsistency: Boolean(report.checkStructureConsistency) }, details }, null, 2));
