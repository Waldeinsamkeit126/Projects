# Projects

个人竞赛、智能体实验与学习项目合集。

A collection of competition experiments, AI-agent projects, and learning tools across Kaggle, Tianchi, and personal exploration.

这里保留的不只是提交代码，也包括实验记录、评测工具和部分历史产物。各项目在根目录并列维护，依赖和运行方式相互独立。

## 项目导航

| 项目 | 方向 | 内容与入口 |
| --- | --- | --- |
| [Biohub Cell Tracking](Biohub-Cell-Tracking/) | 细胞检测与追踪 · Kaggle | Notebook、诊断结果与提交实验的去重归档；先阅读恢复说明。 |
| [Kaggriculture](kaggriculture-agent-archive/) | 博弈智能体 · Kaggle | 候选策略、闭环对战评测、实验报告、提交包与来源记录。 |
| [Tianchi Table Recognition](tianchi-table-recognition/) | 复杂表格识别 · 天池 | 识别实验、工作数据与历史输出的项目快照。 |
| [AFAC2026 FinixDoc](afac2026-finixdoc/) | 金融文档还原 · 天池 | 文档切块、OCR、表格结构还原、评测与实验记录。 |
| [BenchFlow Agent Skill Lift](benchflow-agent-skill-lift/) | 智能体技能评测 | 科学时间序列校验技能的比赛提交包与小型测试数据。 |
| [AgentSkills](AgentSkills/) | 智能体工具 | 科学时间序列校验技能目录。 |
| [Digit Recognizer](DigitRecognizer/) | 图像分类 · Kaggle | 手写数字识别的 CNN 实验脚本与提交结果。 |
| [Titanic](Titanic/) | 表格分类 · Kaggle | 生存预测实验代码与提交结果。 |
| [MathAnalysisLocal](MathAnalysisLocal/) | 本地 RAG · 学习工具 | 面向数学分析教材的检索与本地模型问答原型。 |

## 使用方式

1. 从上表进入所需项目，优先阅读该目录的说明。
2. 按项目配置独立环境；本仓库没有统一的安装或运行命令。
3. 修改示例中的本机路径，自行准备合法获取的数据、模型和必要凭据。
4. 将历史提交和实验结果视为记录，而不是当前榜单成绩或开箱即用的保证。

仓库含较大的历史产物。只浏览代码时可直接使用 GitHub 网页，或使用 Git 的部分克隆与稀疏检出；无需下载全部归档。

## 归档与来源

- Biohub 使用分卷 ZIP 和 SHA-256 文件清单保存去重后的文件，恢复方式见其目录说明。
- Kaggriculture 与天池表格项目从独立归档仓库迁入；这是文件快照整合，不代表原仓库的完整提交历史、Issues 或 Releases 已迁移。
- 项目说明与 `SOURCE.md` 等来源记录优先于本页摘要。不同目录可能保留不同阶段的代码和结果。
- 历史记录不一定包含完整运行环境、全部比赛数据或在 Kaggle 上运行的最终版本。

## 使用边界

不要提交 API Key、访问令牌、私人凭据或禁止公开的比赛数据。复用第三方代码、模型与数据时，请遵守各自的许可证和赛事规则；本仓库不对第三方内容统一重新授权。
