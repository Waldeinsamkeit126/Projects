# Kaggriculture 冲榜归档

这是 Kaggle **Kaggriculture** 比赛的可复现代码归档。仓库保留了策略源码、候选代理、闭环评测工具、关键实验报告、可直接提交的压缩包，以及比赛环境的核心源码；体积很大的原始数据、在线回放和缓存没有纳入 GitHub。

## 结果摘要

公开榜会随匹配池持续变化，下面是本次迭代过程中观察到的代表性分数，而不是最终榜保证。

| 版本 | 观察分数 | 结论 |
|---|---:|---|
| Exact Indar V1 / E333 | **2504.2** | 本轮最高分；最终重新启用的基线 |
| E328 Indar seat repair | 1787.2 | 座位修复尝试，没有超过原版 |
| E326 wool-near | 1758.0 | 羊毛抢占消融版本 |
| E332 wool + Indar defense | 1579.2 | 0 号位很强，1 号位仍是主要瓶颈 |
| E331 wool + current MoE | 约 1333 | 混合专家未能改善弱座位 |
| E330 wool + V22 | 约 1271 | 早期座位混合版本 |

最重要的经验是：本地闭环评测必须双边换位并使用互斥种子；历史动作的开环重放只能做行为复现，不能作为版本晋级依据。后期实验还暴露出非常明显的座位不对称——若继续参赛，应优先针对 1 号位建立可泛化的市场/开局路由，而不是继续微调 0 号位。

## 仓库结构

- `agents/`：全部候选策略源码，包括 Indar 消融、座位混合、MoE、state-KNN 与早期版本。
- `tools/`：构建、闭环对战、回放分析、线上样本抓取和策略检查脚本。
- `reports/benchmarks/`：后期主要闭环实验与线上分析报告。
- `reports/legacy/`：早期顶层实验结果。
- `submissions/`：提交包、对应源码、公开代理来源说明及历史报告；已移除 `__pycache__`/`.pyc`。
- `environment/`：Kaggriculture 与 Kaggriculture Beginner 的规则、配置和 Python 实现；未保留三个合计约 35 MB 的编译后可视化页面。
- `KEY_ARTIFACTS.md`：最高分包和关键版本的校验信息。

## 快速复现

```powershell
python -m pip install -r requirements.txt
python tools/benchmark_matrix.py --help
python tools/screen_against_baseline.py --help
```

比赛提交包要求 `main.py` 位于归档根目录。最高分基线在：

```text
submissions/public_indar_market_v1/submission.tar.gz
```

## 未归档的内容

为释放空间，以下仅用于临时分析的内容在远端校验后从本地删除：

- `datasets/`：约 2.23 GB；
- `online_episodes*/`：约 3.25 GB；
- Python 缓存、包解压校验目录和编译后的可视化 HTML；
- 其他可由保留代码或提交包重新生成的中间文件。

## 来源与使用范围

部分代理来自公开 Kaggle Notebook。对应作者、Notebook 链接、版本号和哈希保存在各自目录的 `SOURCE.md` 中。本归档不对这些第三方内容重新授权；使用或再分发时请遵守原作者与 Kaggle 的适用条款。
