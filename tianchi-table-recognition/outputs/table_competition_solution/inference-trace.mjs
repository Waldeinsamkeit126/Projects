export const TRACE_VERSION = "redacted-inference-trace-v1";

export function createRedactor(secret = "") {
  const text = (input) => {
    let value = input;
    if (secret) value = value.replaceAll(secret, "[REDACTED]");
    return value.replace(/\bsk-[A-Za-z0-9._-]{8,}/g, "[REDACTED]")
      .replace(/\bBearer\s+[^\s"'<>]+/gi, "Bearer [REDACTED]");
  };
  const redact = (input) => {
    if (typeof input === "string") return text(input);
    if (Array.isArray(input)) return input.map(redact);
    if (!input || typeof input !== "object") return input;
    return Object.fromEntries(Object.entries(input).map(([key, value]) => [text(key),
      /^(?:authorization|headers|api[_-]?key|access[_-]?token|cookie|secret|reasoning_content)$/i.test(key) ? "[REDACTED]" : redact(value)]));
  };
  return redact;
}

export async function emitTrace(options, event) {
  if (!options.onTrace) return;
  const redact = createRedactor(options.apiKey);
  try { await options.onTrace(redact({ version: TRACE_VERSION, timestamp: new Date().toISOString(), ...event })); }
  catch {
    const message = "推理审计记录写入失败，本轮停止新增请求";
    if (options.requestState) options.requestState.haltReason = message;
    throw new Error(message);
  }
}

export function protectResult(result, secret) {
  const redact = createRedactor(secret), safe = redact(result);
  if (safe.answerRedacted || safe.answer !== result.answer) {
    safe.answerRedacted = true;
    safe.valid = false;
    safe.error = "答案含疑似凭证内容，已脱敏并禁止导出；不得将脱敏占位符当作有效答案";
  }
  return safe;
}
