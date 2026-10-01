import { buildPrompt } from "../run.mjs";

// Isolated experiment: do not silently change v3 caches, references or historical scores.
export const ARRAY_CONTRACT_VERSION = "tianchi-value-array-candidate-v1";
export const RULE_SOURCE = "https://tianchi.aliyun.com/competition/entrance/532510/information";
export const VALUE_ARRAY_RULE = '2. answer_format=json_array：answer 必须为 JSON 数组，元素直接是题目要求的具体值，不额外包装成键值对象。数值、文本、布尔类型遵从题意，不能一律转成字符串；编号、日期及要求保留原格式的值使用字符串。数组内缺失值写空字符串 ""，不写 null。按题目指定的顺序排列，未指定时按表格逐行从左到右、从上到下的阅读顺序排列，保留重复值，不自行排序或去重。';

export function publicArrayQuestions(rows) {
  const ids = new Set();
  return rows.map((row) => {
    if (!row.id || ids.has(row.id) || row.answer_format !== "json_array" || !row.question || !row.file_name) {
      throw new Error("数组试验存在空字段、重复题号或非数组题");
    }
    ids.add(row.id);
    return Object.fromEntries(["id", "file_name", "question_type", "question", "table_hint", "answer_format"]
      .map((key) => [key, String(row[key] ?? "")]));
  });
}

export function buildValueArrayPrompt(rows) {
  const lines = buildPrompt(publicArrayQuestions(rows)).split("\n");
  const indices = lines.flatMap((line, index) => line.startsWith("2. answer_format=json_array：") ? [index] : []);
  if (indices.length !== 1) throw new Error("旧提示词边界变化，拒绝静默替换");
  // Replace only the format paragraph, not question text, other rules or the envelope.
  lines[indices[0]] = VALUE_ARRAY_RULE;
  return lines.join("\n");
}

export function normalizeValueArray(value) {
  if (typeof value === "string") {
    const text = value.trim().replace(/^```(?:json)?\s*([\s\S]*?)\s*```$/i, "$1").trim();
    try { return JSON.stringify(JSON.parse(text)); } catch { return text; }
  }
  // Never flatten objects, coerce types, fill nulls, sort or deduplicate predictions.
  try { return JSON.stringify(value) ?? ""; } catch { return ""; }
}

export function validateValueArray(answer) {
  if (typeof answer !== "string" || !answer.trim()) return { valid: false, error: "缺少数组答案" };
  let values;
  try { values = JSON.parse(answer); } catch { return { valid: false, error: "不是合法 JSON" }; }
  if (!Array.isArray(values)) return { valid: false, error: "答案必须是 JSON 数组" };
  for (const [index, value] of values.entries()) {
    if (!(typeof value === "string" || typeof value === "boolean" || (typeof value === "number" && Number.isFinite(value)))) {
      return { valid: false, error: `第 ${index + 1} 项不是直接值；空缺用空字符串，不能为 null、对象或嵌套数组` };
    }
  }
  return { valid: true };
}

export function scoreValueArrayContract(references, predictions) {
  const byId = new Map();
  const ids = new Set(references.map((r) => r.id));
  if (ids.size !== references.length || !references.length) throw new Error("参考题号为空或重复");
  for (const row of predictions) {
    if (!ids.has(row.id) || byId.has(row.id)) throw new Error("预测题号未知或重复");
    byId.set(row.id, row);
  }
  const details = references.map((reference) => {
    const expected = normalizeValueArray(reference.expected);
    if (!validateValueArray(expected).valid) throw new Error("参考格式不合法");
    const row = byId.get(reference.id);
    const answer = normalizeValueArray(row?.answer);
    const missing = !answer;
    const valid = !row?.answerRedacted && validateValueArray(answer).valid;
    return { id: reference.id, missing, valid, correct: Boolean(!missing && valid && answer === expected) };
  });
  return { metric: "synthetic-value-array-strict-v1 (not official scoring)", total: details.length,
    correct: details.filter((r) => r.correct).length, valid: details.filter((r) => r.valid).length,
    missing: details.filter((r) => r.missing).length, details };
}
