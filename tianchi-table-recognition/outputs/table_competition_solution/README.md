# 知乎知学堂复杂表格识别挑战赛 - 可追溯实验流水线

本地代码负责读取题目、修正数据路径、校验答案、缓存结果并生成提交文件。答题端点限定为指定的阿里云 HTTPS 服务，模型限定 Qwen 系列。这些工程检查不是主办方的合规认证，也不是答案正确性证明。

## 2026-09-14 复盘后的变更

- `run.mjs` 是后续实验入口。禁用 `--base`，不导入历史提交答案。历史 XLSX、缓存和 `work/build-v*.mjs` 保留用于审计，不作为新流程依赖，不应再用逐题硬编码脚本生成正式提交。
- `number` 检查纯数值语法。仅删除完整千分位分组，不推测单位、百分数换算或缺失值。结构坐标越界会报错，不再扩张尺寸使其通过。嵌套 JSON 不再被字符串化掩盖。
- 缓存身份包含媒体、题目、实际提示词、系统提示、代码指纹、端点、模型、思考模式、token 上限和重试设置。旧格式缓存不复用。缓存命中后仍查漏题、重复题号和非法答案。
- 默认不付费调用。需显式 `--allow-paid`；`--max-requests` 限制本轮请求数（包括重试），默认 20。次数上限不是人民币预算，不自动提高 token 上限。
- 每次运行有独立 `runs/<run-id>/manifest.json`、`requests.jsonl`、`results.jsonl`、`run-report.json`。统一摘要写入 `experiments.jsonl`。记录 token、请求耗时和错误，账单未知时金额为 `null`，不伪称免费。
- 只有全部问题处理完成且格式校验通过才导出 XLSX，并复读比较。部分试跑或 `--no-export` 只生成结果和报告。已有输出文件不覆盖。导出不等于提交。
- 提供独立构造的 5 张合成表格、30 道开发题。按源表分为开发集 18 题、留出集 12 题，标签不包含在发给模型的问题文件中。它们只覆盖干净小表，不能代表真实扫描件，也不能换算天池分数。

当前验证：140 项自动化测试通过，原自测也已通过；同表一致性检查、脱敏轨迹、并发请求上限、导出拦截、原图复核、数组格式和正式小批入口测试均使用模拟网络。2026-09-15 的真实 Qwen 结果为旧开发集严格匹配 18/18、旧留出集 10/12。新增 12 题的覆盖检查 A/B 已于 2026-09-17 完成，均严格匹配 12/12，各 4 次请求、报告 token 各 7,252；覆盖触发复核 0 次，只能说明此小样本未见退化，不能证明提分。真实复杂扫描评估尚未进行，当前改进阶段未导出 XLSX 或提交比赛。详见 `development/coverage-experiment-20260916.md`。

## 2026-09-19：真实数组题小批已完成，尚未提交

最新进展：用户批准全量 89 次预算后，独立全题型入口已完成集成、10 项新增模拟测试及冻结预检。真实执行在第 10 批按既定停止条件中止：返回 118 题，117 道格式通过，1 道多值字段产生嵌套数组被拒，另 790 题未调用。用量 68776 token。已保存并核对全部记录，未导出或提交。下一步需用户同意调整停止策略及最多 5 次格式修复额度；不能把未用额度当作绕过停止条件的授权。详见 [全量执行与具体阻碍](development/full-candidate-experiment-20260919.md)。

已登录核实天池最佳 61.2、排名 108；最近线上提交为 9 月 13 日 v47，得分 61.0。提交页当时显示剩余次数 5，xlsx、不超过 100M。最近的新流程实验未产生新比赛提交。

当前官网值数组格式与旧 v3 对象数组规则不一致，已开发独立候选。9 月 18 日在用户批准的 2 次调用内完成合成 10 题试验，真实严格匹配 10/10，报告 token 共 2326，未覆盖历史答案、未提交。详见 [值数组执行记录](development/array-value-experiment-20260918.md)。

用户确认新的 4 次预算后，固定选择图片/PDF、提取/推理四层的 10 道正式数组题，共 4 个源文件。4 次请求均成功，10/10 格式通过、无漏答或截断；报告 token 为输入 23381、输出 565，共 23946。没有参考标签，不能称为真实准确率或确定提分。已核对计划、逐题来源及保存的模型正文，未合并旧人工补丁、未导出或提交。详见 [正式小批执行记录](development/real-array-experiment-20260919.md)。

全题型新候选范围为 908 题、89 个实际源文件批次（65 图片、24 PDF）。原 [全量候选提案](development/full-candidate-proposal-20260919.md) 已获批准并部分执行，以上方最新执行记录为准；旧 `run.ps1` 仍采用对象数组规则，不应直接用于该候选。见 [提交条件](development/real-array-pilot-20260919.md)。

## 2026-09-18：独立原图复核（首表未通过后停止）

新增 `development/structure-review.mjs`：根据既有机器检查选择目标表，携带原图、原问题与冲突/覆盖提示复核，不读取参考答案，不按题号修补。复核候选与原答案分开保存，不写回历史缓存或自动提交。独立入口不改变现有 v3 推理源文件指纹。

冻结计划自动选中两张开发表、四道结构题。用户同意最多 2 次新请求后，首张经费表实际调用 1 次，报告 token 4,191，返回 2 道题但均因 7×7 维度与单元格坐标矛盾而校验失败，严格匹配 0/2；第二张表按停止条件未调用。没有重试、备用模型或追加额度，不采用这批候选。

111 项测试、复核入口 dry-run 和原入口回归 dry-run 均通过。付费运行后再次核对请求/轨迹与指纹，原答案、缓存和历史分数未变，未导出或提交；检查通过不能代替识别正确。方案见 [复核方案与验证记录](development/structure-review-20260918.md)，实际结果见 [执行记录](development/structure-review-experiment-20260918.md)。

## 2026-09-18：同表一致性与审计轨迹（离线完成）

- 当前版本 `reliable-v3-audited`。新增 `--check-structure-consistency`，默认关闭；仅比较同一图片、明确相同目标表的完整结构与表头答案，检查尺寸、文字和合并跨度。PDF、缺少目标提示或范围不明确时跳过。
- 开启后若发现矛盾，生成 `structure-consistency.json` 并阻止导出；检查本身不调用模型、不改答案，也未实现自动付费复核。格式合法与结构一致是不同状态；双方一致仍可能同时错误。
- 不论检查开关是否开启，每次新推理都保存 `inference-trace.jsonl`，逐题保留解析、校验、重试和备用模型轨迹。排除请求头、上游错误正文和思考内容，已知密钥及令牌模式脱敏；日志仍可能含表格业务数据，分享前须检查。
- 对旧清晰组答案只读审计，2 组可比较答案中发现 1 组冲突、7 处差异；装配表的共同错误未被一致性检查发现，但原覆盖检查能标记缺口。原答案、分数不变，不代表修复或提分。
- 本轮实际 API 请求 0 次，未读取真实密钥、未提交。新缓存 schema 为 3，不复用旧版本缓存，不为更新缓存重跑已完成实验。

实现、验证和限制见 [离线完成记录](development/consistency-20260918.md)。

## 2026-09-17：独立扫描退化配对集（清晰组达到上限后停止）

已新增并冻结 `scan-stress-v1`：6 个源页面、8 张表，各有清晰/模拟扫描两版，共 12 张图片、60 条配对题目（30 个独立问题）。按源页面分成开发/验证两组，各 3 个源页面；同源变体不跨组。全部图片已目视检查，数据和启动检查通过。用户确认后清晰开发组实际使用 4 次请求、报告 token 13,772；已答 10/15 题，严格匹配 5/15（已答题 5/10），另 5 题因该组额度耗尽未调用。发现漏列、合并跨度及数值表示问题。按预设条件停止，扫描组/验证组未调用，尚无配对比较。详见 `development/scan-experiment-20260917.md`；原方案保留于 `development/scan-plan-20260917.md`。

## 2026-09-16：完整结构覆盖检查（候选策略）

- 新增可选 `--check-full-coverage`，默认关闭。仅在题目明确要求完整表格结构时检查全部逻辑网格；局部表头题和范围不明确的题目不强制填满。
- 空白单元格也占网格；检查合并跨度造成的空缺，但不自动补单元格、不改跨度或数值。发现空缺后将坐标和原图交回 Qwen 复核，并记录各次答案。初次问答提示词不因该开关改变。
- 已有 12 道留出题的离线审计仅新增标记 1 个已知跨度错误，原始结果和严格分数没有修改。这不是修复成功率或新模型成绩。
- 新增 4 张独立合成图片、12 道题，覆盖三级表头、分组纵向合并、空白与零、同页双表。已目视检查，真实 Qwen 对照组与开启检查组均完成，严格匹配均为 12/12；没有触发覆盖缺口复核，默认仍关闭该检查。
- 批量 JSON 修复现在也遵守指定 token 上限。所有重试仍受本轮请求总上限约束。
- 代码指纹和缓存身份已升级，新增开关纳入身份。旧记录原地保留，新版本不复用旧指纹结果；不要只为填充新缓存而重跑已完成实验。

完整记录及后续对比方案：`development/coverage-20260916.md`。覆盖完整仅是必要条件，无法证明文字、维度或合并边界正确。

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

已提供 Windows 当前账户绑定的加密存储：工作区 `.private/tianchi-bailian.dpapi`。用户已同意使用此位置，实际保存状态以 `.\credentials.ps1 -Action Status` 为准。通过 `run.ps1` 运行时可自动读取，无需把密钥写在命令里；保存、权限、清理和风险边界详见 `CREDENTIALS.md`。此机制不扩大 API 费用授权。

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

优先使用独立开发集，参见 `development/README.md`。若已明确允许正式数据的小规模 API 试跑，可限制请求且不导出提交：

```powershell
.\run.ps1 --allow-paid --limit 10 --concurrency 1 --max-requests 3 --no-export --purpose "bounded-smoke-test"
```

新缓存默认保存在 `state-reliable-v3`。只有完整缓存身份相同且逐题重新校验通过才不发起请求。失败、漏题、参数变化或强制刷新都可能产生新的计费调用。

## 4. 全量运行

```powershell
.\run.ps1 --allow-paid --concurrency 2 --max-requests 120 --purpose "full-automated-baseline"
```

输出包括：

- `runs/<run-id>/submission.xlsx`：仅完整且格式合格、启用的一致性检查无冲突时生成的待审查文件。
- `runs/<run-id>/results.jsonl`：逐题答案、模型和校验状态。
- `runs/<run-id>/run-report.json`：缺失答案、格式错误、缓存及请求统计。
- `runs/<run-id>/inference-trace.jsonl`：脱敏后的请求、响应、解析和校验轨迹；缓存命中标明来源，不计作新调用。
- `runs/<run-id>/structure-consistency.json`：启用同表一致性检查时的只读审计报告。

若报告中的 `invalid` 不为 0，或状态为 `needs-structure-review`，不要直接提交。先核查问题，新的付费复核另行限定预算。

## 可调整参数

```text
--tests PATH          题目 Excel，默认 D:/tests.xlsx
--template PATH       提交模板，默认 D:/submit-template.xlsx
--media DIR           解压后的 files 目录
--output PATH         输出 xlsx
--state DIR           缓存目录；报告另存于独立 runs/<run-id>
--limit N             只处理前 N 题
--concurrency N       并发文件数，默认 2
--model-pdf ID        PDF 模型，默认 qwen3.8-max
--model-image ID      图片模型，默认 qwen3-vl-plus
--max-attempts N      网络调用重试次数，默认 3
--max-completion-tokens N 每次请求的输出 token 上限，所有重试均遵守
--check-full-coverage 检查明确要求完整结构的网格覆盖，默认关闭
--check-structure-consistency 检查同一目标表的完整结构/表头是否矛盾，默认关闭
--dry-run             仅做预检，不调用模型
--allow-paid          显式允许计费 API 请求
--max-requests N      本轮请求数上限，包含重试，默认20
--no-export           仅保存结果和日志，不导出 XLSX
--questions-json PATH 读取 questions 数组（用于独立开发集），不读取其中的答案标签
--purpose TEXT        实验目的，写入记录，不填写密钥或敏感内容
```

## 注意

- 不要人工逐题查看隐藏测试集并填写答案。
- 不要使用文件名或页码规律猜答案。
- 不要把正式测试文件上传到非阿里云模型或第三方闭源服务。
- 默认使用非思考模式，以保持 JSON 输出稳定；后续可以针对 `thinking` 题增加“推理模型 + Qwen Flash 格式修复”的两段式策略。
