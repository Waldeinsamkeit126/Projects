# Kaggriculture 冲榜包

生成日期：2026-08-01

比赛：[Kaggriculture](https://www.kaggle.com/competitions/kaggriculture)

这是一个无需第三方依赖、可直接提交的策略智能体。它不是公开榜分保证；下述成绩来自 Kaggle 官方 `kaggle-environments==1.32.2` 的本地 720 回合模拟。

## 文件

- `primary/main.py`：主版本，甜瓜单次最多卖 24 单位。
- `alternate_cap12/main.py`：备选版本，单次最多卖 12 单位，市场节奏略保守。
- `primary_submission.tar.gz`：主版本提交包，包根目录为 `main.py`。
- `alternate_cap12_submission.tar.gz`：备选版本提交包。
- `evaluate.py`：多种子、双边换位的本地评测器。
- `reports/`：主版本镜像自博弈和 24 对 12 单位版本的逐局结果。

## 策略概览

- 每天按实际工作量批量雇用廉价农工，避免空地扩张后过度支付人工费。
- 全局分配唯一任务，并用最短路径并行完成种植、浇水、收割、清草和回仓。
- 前中期以约 62% 甜瓜为主，并根据公开对手农田、当前价格和市场拥挤度动态调整。
- 高价、易崩盘的商品分批卖出；最后两天强制收割和清仓，确保收益计入银行余额。
- 第 8 天后在现金留有安全垫时逐步购买土地。

## 本地回测摘要

| 对手/检查 | 局数 | 结果 |
|---|---:|---:|
| 官方 `starter` | 4 | 4 胜，主版本均分 43,909，对手 3,476 |
| 均衡作物压力策略 | 4 | 4 胜，平均分差 +6,726 |
| 保守粮食压力策略 | 4 | 4 胜，平均分差 +17,479 |
| 12 单位成交备选版 | 8 | 6 胜，平均分差 +117 |
| 主版本镜像换位 | 4 | 平均分差 0，双方均分 20,337 |

本地记录的最慢单次 `agent(obs)` 调用约 49 ms，低于比赛的 1 秒行动限制。

## 本地复现

```powershell
python -m pip install -U kaggle-environments
python evaluate.py --agent primary/main.py --opponent self --seeds 8
python evaluate.py --agent primary/main.py --opponent starter --seeds 8
```

## 提交

1. 登录 Kaggle，进入比赛页并点击 **Join Competition** 接受规则。
2. 配置 Kaggle API 凭证，安装 CLI：`python -m pip install kaggle`。
3. 先提交主版本，再提交备选版本：

```powershell
kaggle competitions submit kaggriculture -f primary_submission.tar.gz -m "primary-v1 melon24"
kaggle competitions submit kaggriculture -f alternate_cap12_submission.tar.gz -m "alternate-v1 melon12"
```

比赛每天最多提交 5 个代理，但仅最新 2 个处于活跃匹配和最终评测范围。不要在没有回测的情况下连续覆盖这两个版本。

## 赛程与迭代建议

- 参赛/组队截止：2026-09-23 23:59 UTC。
- 最终提交截止：2026-09-30 23:59 UTC。
- 截止后仍会继续跑对局约两周，并用 Bradley–Terry 锦标赛形成最终榜。
- 榜分是胜负评级，不看终局金币差；应以公开对局回放中的具体克制关系决定下一轮改动。

拿到首轮线上对局后，优先下载 replay 和 agent logs，再针对高分对手的作物结构、首批收割日和倾销节奏做第二轮定向优化。
