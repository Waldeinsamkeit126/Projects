# 同表一致性与推理轨迹：离线完成记录

## 结论

两项改动已实现，97 项自动化测试及原自测通过。对既有清晰组真实输出的只读审计发现 1 组冲突、7 处差异，但未修复答案，也未验证模型提分。本轮真实 API 请求 0 次，没有读取真实凭证、导出比赛 XLSX 或提交比赛；测试中的网络请求全部为模拟。

代码与最终审计完成于 2026-09-17 UTC，文档于北京时间 2026-09-18 整理。历史实验保持原始时间和结果。

## 实现范围

### 同目标表的交叉检查

`structure-consistency.mjs` 只比较同一图片、相同且非空 `table_hint` 的完整结构与明确表头题，核对行列数和表头单元格原点、文字、rowspan、colspan。仅允许唯一完整结构对应一个或多个表头答案；PDF、缺少明确目标、范围不明、缺答或结构格式非法时跳过。不读取参考标签，不猜维度，不改答案。

入口参数 `--check-structure-consistency` 默认关闭。开启后生成 `structure-consistency.json`；存在冲突时阻止 XLSX 导出，无其他格式错误时状态为 `needs-structure-review`，退出码为 2。检查本身不追加模型请求，尚无自动付费复核流程。`valid` 仍是格式校验结果，不能代替结构正确性。

边界：同名多表仍可能有歧义；双方可能共同漏列、错字或错跨度。一致性和覆盖检查都不能证明答案正确，默认开关暂不改变。

### 无条件记录新推理历史

无论检查开关是否开启，新运行均写 `inference-trace.jsonl`；逐题 `validationHistory` 记录初答、批量 JSON 修复、单题重试及备用模型阶段。请求序号、实际模型与答案关联；预算拦截独立标记为未请求，不覆盖已有答案。缓存命中保留来源运行，不计为新调用。

记录成功响应的答案内容、解析与校验结果，但不记录请求头、上游 HTTP 错误正文或 `reasoning_content`。实际密钥、常见令牌模式和敏感字段脱敏；若答案含需脱敏凭证则标为无效并禁止导出。后续干净答案可以替代它，但历史保留脱敏标记。审计写入失败会停止新增请求，共享额度在并发路径再次检查。

这些保护不是“零泄露”保证：日志可能含题目、表格业务数据或未识别的敏感信息，分享前仍需审查。旧运行未记录的初答无法补回。本轮没有修改凭证存储或读取真实密钥。

## 旧真实结果的只读审计

输入运行：`2026-09-17T10-27-31-986Z-daea26a3`。

最终报告：[consistency-audit-v3-final-20260917.json](consistency-audit-v3-final-20260917.json)。审计不使用参考答案，未回写预测或缓存。

- 经费表：完整结构为 8×7，表头为 7×8；加上合并跨度和缺失原点，共 7 处差异，形成 1 组冲突。审计不能单凭矛盾认定哪份正确。
- 装配表：完整结构与表头具有相同的错误跨度，一致性检查未标记冲突。既有覆盖审计能标记 4 格缺口，说明两项检查在该例互补。
- 仓库表：结构题没有答案，跳过比较；没有产生任何新识别结果。

可比较 2 组，冲突 1 组。历史严格成绩仍是全题 5/15、已答题 5/10，不能将检出数转成修复率或天池成绩。

## 验证与兼容性

通过的命令（`node` 为项目现有 bundled runtime）：

```powershell
node --test reliability.test.mjs structure-coverage.test.mjs structure-consistency.test.mjs inference-trace.test.mjs development/scoring.test.mjs development/diagnostics.test.mjs development/scan.test.mjs development/scan-compare.test.mjs
node self-test.mjs
.\run.ps1 --dry-run --questions-json development/generated-scan-v1/questions-development-clean.json --media development/generated-scan-v1 --no-export --check-full-coverage --check-structure-consistency --max-attempts 1 --max-requests 4 --max-completion-tokens 8192
```

97 项测试全部通过，包括新增一致性 8 项、轨迹及端到端 12 项；其他既有测试继续通过。预检识别 15 题、3 个文件，路径未解析数为 0，没有模型调用。新增端到端测试验证冲突拦截导出、缓存复用不追加模型调用、秘密脱敏、审计故障停止及并发请求上限。

当前版本 `reliable-v3-audited`，缓存 schema 3，默认目录 `state-reliable-v3`。新开关和 5 个推理源文件指纹进入缓存身份；相关续跑、审计和配对比较工具已同步。旧 v2 报告被续跑检查拒绝是预期行为，不能绕过，也不应为更新缓存重复付费。

指纹记录：

- 当前 5 个推理源文件拼接 SHA-256：`46e0dce366c7c49df4bab25c7c9dfb201d46c2ddbbe0c83bbab790e6f6b21898`。
- 归档 v2 的 3 个推理源文件拼接 SHA-256：`c3e67b1cc87f5012d184435f1b6f7c6dd66d15f96aa30fa5e72687c2ade4118b`。
- 旧清晰组预测 SHA-256：`e8bf48e9012f54e9f328e0e1458eb40fee87ba0d554b28b5e87d6297125b6ee7`。

v2 归档位于 `baselines/reliable-v2-coverage-20260917/`。已核对归档指纹、旧清晰组和两组覆盖 A/B 预测文件均未改变；冻结数据测试通过。评分规则及参考标签未修改。

## 后续边界

下一步可设计受限、通用的原图复核实验，先冻结策略、停止条件和逐组请求上限，再另行确认付费预算。不能挪用原扫描组未使用额度，不能从本轮离线通过推断修复有效，也不应立即全量重跑。当前尚无新的修复成功率、扫描配对结果或天池分数。
