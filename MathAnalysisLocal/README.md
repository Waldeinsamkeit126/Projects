# 数学分析教材本地助手

临近期末考试了我课本丢了，，，为了让复习变得稍稍方便一点！


这是一个本地 RAG 原型：先从 Zorich `Mathematical Analysis I` PDF 建立检索索引，再把检索到的教材片段交给本地大模型回答。

## 1. 建立教材索引

使用 Codex 内置 Python：

```powershell
& 'C:\Users\zhhzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\ingest.py
```

默认 PDF 路径是：

```text
C:\Users\zhhzh\Documents\WXWork\1688856959714207\Cache\File\2026-03\Vladimir A. Zorich - Mathematical Analysis I-Springer (2016).pdf
```

## 2. 启动本地模型

推荐方式之一是 Ollama。安装并下载模型后运行：

```powershell
ollama pull qwen2.5:7b
ollama serve
```

也可以用 LM Studio 或 llama.cpp，开启 OpenAI 兼容接口就行。

## 3. 启动网页助手

Ollama：

```powershell
& 'C:\Users\zhhzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\server.py --provider ollama --model qwen2.5:7b
```

LM Studio：

```powershell
& 'C:\Users\zhhzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\server.py --provider lmstudio --model local-model --base-url http://127.0.0.1:1234/v1
```

然后打开：

```text
http://127.0.0.1:8765
```

提问请尽量用英文

## 行为边界

- 只检索本教材索引。
- 回答提示词要求模型只基于检索片段作答。
- 中文问题会先尝试由本地模型改写成英文数学关键词，以便检索英文教材。
- 如果没有检索到依据，助手会明确说明教材索引中没有足够内容。
