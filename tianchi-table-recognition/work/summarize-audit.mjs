import fs from "node:fs/promises";

const audit = JSON.parse(await fs.readFile(new URL("./final-audit.json", import.meta.url), "utf8"));
const joined = JSON.parse(await fs.readFile(new URL("./audit-joined-v34.json", import.meta.url), "utf8"));

const scores = {
  v6: 56.6, v7: 56.7, v8: 56.7, v9: 56.7, v10: 57.0,
  v11: 57.5, v12: 58.9, v13: 59.3, v14: 59.7, v15: 59.7,
  v16: 60.0, v17: 60.0, v18: 60.0, v19: 59.8, v20: 59.9,
  v21: 60.0, v22: 60.0, v23: 60.0, v24: 60.0, v25: 60.0,
  v26: 60.1, v27: 60.2, v28: 60.2, v29: 60.4, v30: 60.5,
  v31: 60.5, v32: 60.5, v33: 60.5, v34: 60.5,
};

const rows = [];
for (const item of audit.pairDiffs) {
  const [, to] = item.pair.split("->");
  const from = item.pair.split("->")[0];
  rows.push({
    pair: item.pair,
    scoreDelta: scores[to] != null && scores[from] != null ? +(scores[to] - scores[from]).toFixed(1) : null,
    changeCount: item.diffs.length,
    ids: item.diffs.map((diff) => diff.id),
    byType: Object.groupBy
      ? Object.fromEntries(Object.entries(Object.groupBy(item.diffs, (diff) => diff.type)).map(([key, value]) => [key, value.length]))
      : item.diffs.reduce((acc, diff) => ((acc[diff.type] = (acc[diff.type] ?? 0) + 1), acc), {}),
  });
}

const riskIssueCounts = audit.risks.reduce((acc, risk) => {
  for (const issue of risk.issues) acc[issue] = (acc[issue] ?? 0) + 1;
  return acc;
}, {});
const riskFileCounts = audit.risks.reduce((acc, risk) => {
  acc[risk.file] = (acc[risk.file] ?? 0) + 1;
  return acc;
}, {});

const everChanged = new Set(audit.pairDiffs.flatMap((pair) => pair.diffs.map((diff) => diff.id)));
const thinkingRows = joined.filter((row) => row.question_type === "thinking");
const thinkingBreakdown = thinkingRows.reduce((acc, row) => {
  const extension = /\.pdf$/i.test(row.file_name) ? "pdf" : "image";
  const key = `${extension}:${row.answer_format}`;
  acc[key] = (acc[key] ?? 0) + 1;
  return acc;
}, {});
const unchangedThinking = thinkingRows.filter((row) => !everChanged.has(row.id));
const unchangedBySource = unchangedThinking.reduce((acc, row) => {
  const extension = /\.pdf$/i.test(row.file_name) ? "pdf" : "image";
  acc[extension] = (acc[extension] ?? 0) + 1;
  return acc;
}, {});
await fs.writeFile(
  new URL("./unchanged-thinking-v34.json", import.meta.url),
  JSON.stringify(unchangedThinking.map(({ id, file_name, answer_format, question, answer }) => ({
    id, file_name, answer_format, question, answer,
  })), null, 2),
  "utf8",
);

console.log(JSON.stringify({
  versionChanges: rows,
  riskCount: audit.risks.length,
  thinkingCount: thinkingRows.length,
  thinkingBreakdown,
  unchangedThinkingCount: unchangedThinking.length,
  unchangedThinkingBySource: unchangedBySource,
  unchangedThinkingIds: unchangedThinking.map((row) => row.id),
  riskIssueCounts,
  highestRiskFiles: Object.entries(riskFileCounts).sort((a, b) => b[1] - a[1]).slice(0, 20),
  riskIdsByIssue: Object.fromEntries([...new Set(audit.risks.flatMap((risk) => risk.issues))].map((issue) => [
    issue,
    audit.risks.filter((risk) => risk.issues.includes(issue)).map((risk) => risk.id),
  ])),
}, null, 2));
