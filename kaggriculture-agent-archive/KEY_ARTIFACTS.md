# 关键产物与校验

## 最高分基线

- 文件：`submissions/public_indar_market_v1/submission.tar.gz`
- 本轮观察最高分：`2504.2`
- 来源：Indar Karhana，`Read the Market, Choose the Farm`，Kaggle script version `342221850`
- 包 SHA-256：`a5f0e99ef483408fb524e7ae7c9c2df0c71fd849a30e4fcc54ef50fc166e3ee8`
- `main.py` SHA-256：`d39dba50793d9777c990347443bf0c481c78adaea86055f6f6b0600dcfcd9f2e`
- 包结构：仅包含顶层 `main.py`

`submissions/e333_exact_indar_2504_reactivation.tar.gz` 与上述最高分包内容相同，用于最终重新启用。

## 后期自研版本

| 版本 | 源码 | 提交包 SHA-256 | 备注 |
|---|---|---|---|
| E332 | `agents/seat_hybrids/e332_wool_indar_defense/main.py` | `9434851160b035d297f784c304c767f3e68c5287bea8c6bb4ab02dee6d5998e9` | 0 号位羊毛抢占，1 号位 Exact Indar |
| E331 | `agents/seat_hybrids/e331_wool_current_moe/main.py` | `aca2410e80af8a48f2bbf1e501cfc8253542d0149c4b1faf5ba2ca226b66ccba` | 羊毛 + current-top MoE |
| E330 | `agents/seat_hybrids/e330_wool_v22/main.py` | `1866e74b22a988a86635af91c47ad45591918b2c9d579fe89da8cda8feec5f48` | 羊毛 + V22 |
| E328 | `submissions/e328_indar_seat_repair/main.py` | `6a6eb8e1989ef8fda64a4fb3bad7b538313af6c9791dd29480e88b57a26a013b` | Indar 座位修复 |
| E326 | `agents/indar_ablations/preempt_wool_near/main.py` | `e74e97059845942e6844f7d44b73983cd2da2c7b0abcd1288366c9f40f910dce` | 羊毛邻近抢占消融 |

## 推荐先读的报告

- `reports/benchmarks/e331_vs_e330_isolation.json`
- `reports/benchmarks/e332_vs_e331_isolation.json`
- `reports/benchmarks/e332_e328_equivalence.json`
- `reports/benchmarks/current_top_moe_v1_online.json`
- `tools/BENCHMARK_zh.md`
