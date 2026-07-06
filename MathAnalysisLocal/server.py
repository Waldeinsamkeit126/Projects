from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from rag_core import DEFAULT_INDEX, LocalLLM, TextbookIndex, answer_question


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>数学分析教材助手</title>
  <style>
    :root { color-scheme: light; --ink:#18212f; --muted:#667085; --line:#d9dee8; --paper:#fbfcff; --accent:#0f766e; --soft:#e8f3f1; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: "Segoe UI", system-ui, sans-serif; color:var(--ink); background:#f2f5f9; }
    main { height:100vh; display:grid; grid-template-columns: minmax(0, 1fr) 360px; }
    .chat { display:flex; flex-direction:column; min-width:0; }
    header { padding:18px 24px; border-bottom:1px solid var(--line); background:var(--paper); }
    h1 { margin:0; font-size:20px; font-weight:650; letter-spacing:0; }
    .sub { margin-top:4px; color:var(--muted); font-size:13px; }
    #log { flex:1; overflow:auto; padding:24px; display:flex; flex-direction:column; gap:14px; }
    .msg { max-width:880px; padding:14px 16px; border:1px solid var(--line); border-radius:8px; background:white; white-space:pre-wrap; line-height:1.58; }
    .me { align-self:flex-end; background:var(--soft); border-color:#b8dad5; }
    .bot { align-self:flex-start; }
    form { display:flex; gap:10px; padding:16px 24px 22px; border-top:1px solid var(--line); background:var(--paper); }
    textarea { flex:1; resize:none; min-height:54px; max-height:150px; padding:12px; border:1px solid var(--line); border-radius:8px; font:inherit; line-height:1.45; }
    button { width:92px; border:0; border-radius:8px; background:var(--accent); color:white; font-weight:650; cursor:pointer; }
    button:disabled { opacity:.55; cursor:wait; }
    aside { border-left:1px solid var(--line); background:white; overflow:auto; padding:18px; }
    h2 { font-size:14px; margin:0 0 12px; }
    .source { border:1px solid var(--line); border-radius:8px; padding:12px; margin-bottom:10px; }
    .source strong { display:block; font-size:13px; margin-bottom:6px; }
    .source p { color:var(--muted); font-size:12px; line-height:1.45; margin:0; }
    @media (max-width: 820px) { main { grid-template-columns:1fr; } aside { display:none; } }
  </style>
</head>
<body>
<main>
  <section class="chat">
    <header>
      <h1>数学分析教材助手</h1>
      <div class="sub">仅基于 Zorich Mathematical Analysis I 索引片段回答；本地模型服务负责生成。</div>
    </header>
    <div id="log">
      <div class="msg bot">可以问定义、定理条件、证明思路或例题相关问题。中文提问也可以，我会先尝试转成英文关键词检索教材。</div>
    </div>
    <form id="form">
      <textarea id="q" placeholder="例如：闭区间上连续函数为什么一致连续？"></textarea>
      <button id="send" type="submit">发送</button>
    </form>
  </section>
  <aside>
    <h2>检索来源</h2>
    <div id="sources"></div>
  </aside>
</main>
<script>
const log = document.querySelector("#log");
const form = document.querySelector("#form");
const q = document.querySelector("#q");
const send = document.querySelector("#send");
const sources = document.querySelector("#sources");

function addMsg(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  return div;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = q.value.trim();
  if (!question) return;
  addMsg(question, "me");
  q.value = "";
  send.disabled = true;
  const pending = addMsg("正在检索教材并调用本地模型...", "bot");
  try {
    const res = await fetch("/api/ask", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({question})});
    const data = await res.json();
    pending.textContent = data.answer || data.error || "没有返回内容。";
    sources.innerHTML = "";
    (data.hits || []).forEach((hit, idx) => {
      const item = document.createElement("div");
      item.className = "source";
      item.innerHTML = `<strong>Source ${idx + 1}: ${hit.source} · score ${hit.score}</strong><p>${hit.preview}</p>`;
      sources.appendChild(item);
    });
  } catch (err) {
    pending.textContent = "调用失败：" + err;
  } finally {
    send.disabled = false;
    q.focus();
  }
});
</script>
</body>
</html>
"""


class App:
    def __init__(self, index_path: Path, provider: str, model: str, base_url: str | None):
        self.index = TextbookIndex(index_path)
        self.llm = LocalLLM(provider=provider, model=model, base_url=base_url)


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, HTML, "text/html; charset=utf-8")
            else:
                self._send(404, "Not found", "text/plain")

        def do_POST(self) -> None:
            if self.path != "/api/ask":
                self._send(404, "Not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            question = payload.get("question", "").strip()
            try:
                data = answer_question(question, app.index, app.llm)
                self._send(200, json.dumps(data, ensure_ascii=False), "application/json; charset=utf-8")
            except Exception as exc:
                self._send(
                    500,
                    json.dumps({"error": str(exc), "hits": []}, ensure_ascii=False),
                    "application/json; charset=utf-8",
                )

        def log_message(self, format: str, *args) -> None:
            return

        def _send(self, status: int, body: str, content_type: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local textbook-only math analysis assistant.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--provider", default="ollama", choices=["ollama", "openai", "lmstudio", "llamacpp", "vllm"])
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--base-url", default=None)
    args = parser.parse_args()

    app = App(args.index, args.provider, args.model, args.base_url)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    print(f"Open http://{args.host}:{args.port}")
    print(f"Provider={args.provider}, model={args.model}")
    server.serve_forever()


if __name__ == "__main__":
    main()
