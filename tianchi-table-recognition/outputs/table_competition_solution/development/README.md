# 独立合成表格开发集

这些样例从零构造，没有使用正式测试文件、测试答案或榜单反馈。包含订单、库存、英文运输单、合并季度表头、单位换算。5 张 PNG 共 30 题。

开发集为 3 张源表、18 题；留出集为另 2 张源表、12 题。同一表的问题不跨集合。留出集只是按源表隔离的后续检查，并非盲测或真实分布验证。标签是作者自建参考，不是赛事官方答案。

2026-09-15 已完成真实开发集基线：`qwen3-vl-plus` 对 18 题的本地精确匹配为 18/18，无缺失答案。9 道提取、6 道推理、3 道结构题均匹配。开发集只是 3 张清晰小表，不代表真实扫描件或赛事成绩。

同日保持推理代码和参数不变，完成 12 道留出题：严格匹配 10/12，格式合法 12/12。一个结构答案将纵向合并跨度由 2 识别为 1；另一个差异是 `21.0` 与 `21` 的数值表示，并非算术错误。附加数值等价诊断为 11/12，但不替换严格成绩、不修改原答案，也不声称官方评测器采用相同规则。该轮新增 2 次调用，响应报告 token 4,101。详见 `holdout-20260915.md`。此留出集经误差分析后已不再是未查看的验证集；下一轮须另建独立验证样例。

首轮（2026-09-14）发起 3 次请求，2 次成功，1 次 `fetch failed`，返回 12 题，响应报告 token 为 3,301。续跑保留原代码与参数，复用这 12 题缓存，仅新增 1 次请求完成剩余 6 题，响应报告 token 为 1,674。两轮累计尝试 4 次、成功 3 次、失败 1 次；可见响应 token 合计 4,975，账单金额未知。原自检正对照 30/30 仅验证评估器，绝不是模型成绩。

完成记录：`../runs/2026-09-15T04-30-26-116Z-fb4506ac/development-score.json`。过程总结：`baseline-20260915.md`。

2026-09-15 的评估器 v2 将“有结果记录但答案为空”计入缺失答案，另列记录缺失、非空格式错误与合法但不匹配。原始推理文件未修改，已成功结果的缓存身份不变。4 项新增评估器测试通过。

## 无费用检查

在方案目录运行（`node` 使用 `run.ps1` 同一 bundled runtime 路径）：

```powershell
node --test reliability.test.mjs structure-coverage.test.mjs structure-consistency.test.mjs inference-trace.test.mjs development/scoring.test.mjs development/diagnostics.test.mjs development/scan.test.mjs development/scan-compare.test.mjs development/structure-review.test.mjs
node self-test.mjs
node development/render.mjs
node development/evaluate.mjs --split all
.\run.ps1 --questions-json .\development\generated\questions-development.json --media .\development\generated --no-export --dry-run
```

`render.mjs` 将覆盖它自己生成的合成图片与问题清单，不修改正式比赛文件。`fixtures.mjs` 保存参考答案；`generated/questions-*.json` 只含待问问题，禁止把参考标签文件传给推理模型。

## 历史基线实验命令（已完成，不需重复执行）

以下保留用于复现历史基线。当前代码已升级，不能用它无缝续跑旧版本缓存；不要直接重跑已完成的 18 题。后续实验使用下面新增的验证集和固定参数方案。

```powershell
.\run.ps1 --allow-paid --questions-json .\development\generated\questions-development.json --media .\development\generated --no-export --concurrency 1 --max-requests 6 --max-completion-tokens 8192 --state .\development\cache --purpose "synthetic-dev-baseline"
node development/evaluate.mjs --split development --predictions .\runs\实际运行ID\results.jsonl --output .\runs\实际运行ID\development-score.json
```

先固定模型与参数，获得开发集基线，再一次改变一种通用策略；留出集在策略固定后评估。不要把模型产生的答案当参考标签，不按正式题号人工改答案。可再添加独立构造的多表页面、低分辨率、旋转扫描、跨页 PDF 等测试，但应版本化数据和分组，不能拿 30 个简单样例宣称覆盖所有任务。

本地评估使用文本精确匹配；JSON 忽略对象键顺序、保留数组顺序。它不是官方评测器，数值等价格式和结构 cells 顺序的处理可能不同。报告分别给出格式合法数、匹配正确数及缺失数，不用格式合法率冒充识别准确率。

## 续跑前的无费用缓存检查

```powershell
node development/check-resume.mjs runs/实际新版本运行ID/run-report.json state-reliable-v3
```

该检查使用运行报告里的重试设置、token 上限、端点和检查开关重新计算缓存身份，不读取凭证、不调用网络，也不改已有答案。命令中的缓存目录须与该次运行实际使用的目录一致。代码或题目指纹发生变化时会拒绝按原样续跑。当前 v3 拒绝历史 v1/v2 报告是预期行为，不应绕过检查。续跑请求额度必须扣除该实验已用次数，不能每次失败后重新给满额度。

## 新增覆盖策略验证集（2026-09-16）

`coverage-cases.mjs` 独立构造了 4 个新源页面、5 张表、12 道题：4 道完整结构、4 道局部表头、4 道提取。三层表头、横向/纵向合并、空白与零、双表定位均有覆盖，未取用正式测试题。图片位于 `generated-coverage-v1`，已全部目视核对。参考标签不包含在问题清单中，内部范围元数据只供校验使用。

该阶段 64 项自动化测试通过；新旧评估器正/负对照分别为 12/0 与 30/0，仅说明评估器自检通过。新增 12 题的真实 Qwen 对照组和候选组均已完成，严格匹配均为 12/12，各 4 次请求、报告 token 各 7,252。覆盖触发复核 0 次，不能报告策略提升；对比结果见 `coverage-comparison-20260917.json`。先前留出题的只读审计识别了 1 个已知结构缺口，未修改原答案或严格分数；详见 `coverage-audit-20260916.json`。

```powershell
node development/coverage-render.mjs
node development/evaluate.mjs --dataset coverage --split validation
.\run.ps1 --questions-json .\development\generated-coverage-v1\questions-validation.json --media .\development\generated-coverage-v1 --check-full-coverage --max-attempts 1 --max-requests 6 --max-completion-tokens 8192 --no-export --dry-run
```

渲染脚本只更新它自己生成的覆盖样例，不要修改已评估数据的题目、图像或参考标签。受限 API 对比的预设参数、停止条件及局限见 `coverage-20260916.md`；完成记录见 `coverage-experiment-20260916.md`，A/B 合计已用 8 次请求，不重复跑本次实验，未用额度不转为其他实验授权。

## 扫描质量配对集（2026-09-17，清晰组达到上限后停止）

`scan-cases.mjs` 从零构造 6 个源页面、8 张表；`generated-scan-v1` 含清晰/模拟扫描各 6 张 PNG、合计 60 条配对题目。开发/验证各 3 个源页面，每组每版 15 题；配对变体严格同组。退化含缩小、模糊、低对比、轻微倾斜和压缩，是合成模拟而非真实扫描。12 张图均已目视核对。

新增 `scan.test.mjs` 9 项、配对工具 4 项和既有 64 项合计 77 项测试通过。`scan-evaluate.mjs` 使用原严格评分函数，独立入口不改旧评估器；正/负对照 60/0 仅是自检。四份问题文件均通过 dry-run。确认后清晰开发组用满该组 4 次请求，已答 10/15 题，严格匹配 5/15（已答题 5/10）；其余 5 题因额度上限未调用。报告 token 13,772，未导出或提交。扫描组、验证组均未调用，不能报告清晰/扫描差异。

渲染器拒绝覆盖已有 `generated-scan-v1`。变更需新版本，禁止为了正确率修改已评估标签。按已确认方案，清晰组耗尽额度后停止，未启动扫描组，也不挪用其额度。数据与原方案见 `scan-plan-20260917.md`，实际记录与下一步见 `scan-experiment-20260917.md`。不要重跑已完成调用或将缓存格式有效当作答案正确。

字体缓存不可写时，图像渲染可能输出 Fontconfig 警告；当前生成图已目视核对，不影响已确认的文字显示。无需为此修改系统字体或依赖目录。

## 同表一致性与推理轨迹（2026-09-18，离线完成）

当前 `reliable-v3-audited` 的 97 项测试和原自测通过。新增检查默认关闭，启用后只标记同图片、同明确目标表的完整结构/表头矛盾，并拦截导出，不自动调用模型修正。不论检查开关是否开启，都保留新推理的脱敏解析、校验及重试历史；无法补回旧运行未记录的首答。

对旧清晰组结果只读审计发现 1 组冲突、7 处差异，原始结果和严格分数保持不变。共同错误仍可能通过一致性检查，需结合覆盖检查，不能把工程测试或审计检出数当作模型提分。此轮没有付费调用、凭证读取或提交。

缓存 schema 已升为 3，旧记录原地保留，新代码不复用旧缓存；旧 3 个推理源文件归档于 `baselines/reliable-v2-coverage-20260917/`。不要重复已完成实验来填充新缓存。详见 [完成记录](consistency-20260918.md) 和 [最终只读审计](consistency-audit-v3-final-20260917.json)。

## 独立原图复核（2026-09-18，首表未通过后停止）

新增 14 项复核测试，当前共 111 项通过。独立 `structure-review.mjs` 不改现有推理核心或基线结果；只按一致性冲突/覆盖缺口选题，保存可验证的输入、代码、图片和提示词指纹。`run.ps1 --structure-review` 转入该入口，dry-run 不读取加密凭证。

已冻结 `structure-review-plan-20260918.json`，自动选中两张清晰开发表的四道结构题；建议最多新增 2 次调用，每个目标表一次，无重试/备用模型。只生成独立候选，不直接替换历史答案；同一冻结计划有一次性运行锁，异常后不能自动重跑。出现未解决检查、解析错误、截断或请求故障时停止后续表。

用户随后同意最多 2 次新调用。实际首表 1 次请求、报告 token 4,191；返回两道题均有越界结构，严格匹配 0/2，停止后表，剩余额度不挪用。已答题的数值内容有所恢复，但维度和合并表头仍错，不改原答案或分数、不自动采用候选。

新增 `evaluate-structure-review.mjs` 只离线读取冻结参考，按原严格规则对比所选题并单列未执行项，不导入推理程序、不增加 API 请求。该选择针对已分析过的开发集，不是盲测或同预算独立 A/B。方案见 [复核方案](structure-review-20260918.md)，实际结果见 [执行记录](structure-review-experiment-20260918.md)。
