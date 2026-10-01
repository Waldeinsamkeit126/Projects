# 知乎知学堂复杂表格识别挑战赛 - Qwen 首版流水线

这是一个遵守赛题约束的首版自动化方案：所有正式答题请求只调用阿里云百炼中的 Qwen 模型；本地代码负责读取题目、修正数据路径、校验答案、缓存结果并生成提交文件。

## 已确认的数据情况

- `tests.xlsx`：908 道题，涉及 90 个文件。
- 题型：`extract` 617 道、`thinking` 204 道、`structure` 86 道；另有 1 行题型字段错位，程序在运行时归入 `extract`。
- 答案格式：`string` 409、`number` 360、`json_array` 99、`json` 40。
- 媒体包：26 个 PDF（共 41 页）和 66 张图片。
- 原题表前 82 行的 `answer=11` 为占位内容，程序完全忽略原始 `answer` 列。
- `table_hint=11` 被视为空提示。
- 程序自动将 `58.pdf`、`59.pdf`、`0060.pdf` 映射为实际文件 `058.pdf`、`059.pdf`、`060.pdf`，但不会修改原始 Excel。

## 模型策略

- PDF：默认 `qwen3.8-max`，直接使用百炼 PDF 理解接口。
- JPG/PNG/WebP：默认 `qwen3-vl-plus`。
- 每个文件一次批量问答；缺失或格式不合格的题目会单题重试。
- 使用 JSON 输出模式，并在本地再次验证结构恢复 JSON、数组格式、坐标和合并跨度。

官方依据：

- 赛题说明：https://tianchi.aliyun.com/competition/entrance/532510/information
- 百炼 PDF 理解：https://help.aliyun.com/zh/model-studio/pdf-understanding
- 百炼结构化输出：https://help.aliyun.com/zh/model-studio/qwen-structured-output
- Qwen3-VL-Plus：https://help.aliyun.com/zh/model-studio/qwen3-vl-plus

## 1. 先做无费用检查

在 PowerShell 中运行：

```powershell
cd "C:\Users\zhhzh\Documents\Codex\2026-08-26\x20-x20-2\outputs\table_competition_solution"
.\run.ps1 --dry-run
```

这只检查 Excel、媒体路径、题型分布及文件名修正，不调用模型。

## 2. 本机配置百炼凭证

不要把 API Key 发到聊天中。仅在准备运行的 PowerShell 窗口中设置：

```powershell
$env:DASHSCOPE_API_KEY = "你的百炼 API Key"
```

默认使用华北2（北京）的 DashScope 接入地址。若你希望使用业务空间专属域名，可以额外设置业务空间 ID 或完整地址：

```powershell
$env:ALIYUN_WORKSPACE_ID = "你的华北2（北京）业务空间 ID"
# 或者：
$env:ALIYUN_BASE_URL = "https://你的WorkspaceId.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
```

PDF 理解当前要求华北2（北京）地域。API Key 和业务空间应属于同一地域。

## 3. 小规模试跑

建议先处理前 10 题：

```powershell
.\run.ps1 --limit 10 --concurrency 1 --output ".\submission-test.xlsx"
```

运行状态和校验报告保存在 `state` 目录。相同文件、问题和模型的成功结果会缓存，重复运行不会再次计费。

## 4. 全量运行

```powershell
.\run.ps1 --concurrency 2 --output ".\submission.xlsx"
```

输出包括：

- `submission.xlsx`：可提交文件。
- `state/results.jsonl`：逐题答案、模型和校验状态。
- `state/run-report.json`：缺失答案及格式错误汇总。

若报告中的 `invalid` 不为 0，不要直接提交；先修复失败项或重新运行。

## 可调整参数

```text
--tests PATH          题目 Excel，默认 D:/tests.xlsx
--template PATH       提交模板，默认 D:/submit-template.xlsx
--media DIR           解压后的 files 目录
--output PATH         输出 xlsx
--state DIR           缓存及报告目录
--limit N             只处理前 N 题
--concurrency N       并发文件数，默认 2
--model-pdf ID        PDF 模型，默认 qwen3.8-max
--model-image ID      图片模型，默认 qwen3-vl-plus
--max-attempts N      网络调用重试次数，默认 3
--dry-run             仅做预检，不调用模型
```

## 注意

- 不要人工逐题查看隐藏测试集并填写答案。
- 不要使用文件名或页码规律猜答案。
- 不要把正式测试文件上传到非阿里云模型或第三方闭源服务。
- 默认使用非思考模式，以保持 JSON 输出稳定；后续可以针对 `thinking` 题增加“推理模型 + Qwen Flash 格式修复”的两段式策略。
