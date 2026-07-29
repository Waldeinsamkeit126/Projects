# AFAC2026 复杂金融文档还原

这是面向天池 AFAC2026 赛题二的可复现工程骨架。原始数据保持只读；API响应按图片内容哈希缓存，失败可断点续跑；密钥只从本地 `.env` 读取。

## 仓库范围

此目录只保存可公开复现的源码、测试、实验脚本和实验记录，不包含赛事数据、
模型权重、API Key、提交 CSV、OCR 缓存或中间证据图。`config.json` 中的
Windows 路径是本地示例，可按实际目录修改。请勿将 `.env`、数据集或赛事
密钥提交到公开仓库。

## 当前能力

- 自动发现并校验200张训练图、200份GT、100张A榜图片和提交模板；
- 安全读取数亿像素官方JPEG的尺寸，不默认解码整图；
- 生成确定性的纵向重叠切块计划；
- 区分长文档与高密表格；高密大表会明确拒绝错误的纵向滑窗方案；
- 调用官方 FinixDoc-VL API，包含超时、重试、原子缓存和响应解析；
- 移除模型外层代码围栏，并保守清理换行；
- 相邻切块边界精确/保守模糊去重；
- 高密表格去除横竖框线后做行列投影，生成约400–500单元格的二维网格块；
- 根据预期坐标合并双层表头、重复行键，并裁掉切片边缘的半列误识别；
- 精确字符Levenshtein、逻辑块顺序和HTML表格拓扑诊断；
- 严格按照官方模板顺序生成CSV，拒绝漏图、多图或错列。

## 初始化

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填写赛事统一 API Key。不要把 `.env` 发给别人或提交到仓库。

## 常用命令

```powershell
# 完整校验数据（不调用API）
python main.py inspect --output D:\AFAC2026\outputs\dataset_report.json

# 查看某张图的切块计划（不调用API）
python main.py plan "D:\AFAC2026\data\...\example.jpg"

# 高密表格的区域、行列和二维切片规模（不调用API）
python main.py table-plan "D:\AFAC2026\data\...\table.jpg"

# 只渲染一个二维切片，不调用API
python main.py render-table-tile "D:\AFAC2026\data\...\table.jpg" `
  --region 0 --row-group 0 --column-group 0 --output tile.jpg

# 单图调用；相同图片默认命中缓存，不会重复请求
python main.py probe "D:\AFAC2026\data\...\example.jpg" --gt "D:\AFAC2026\data\...\example.md"

# 比较已有预测和GT
python main.py evaluate prediction.md ground_truth.md
```

## 安全边界

- 只允许向官方固定 HTTPS 地址上传图片；配置为其他域名时程序直接拒绝。
- 缓存键不包含 API Key，日志也不会打印 API Key。
- 默认并发数为2。实测5路会出现服务端断连，3路在繁忙时会严重排队；后续只允许调度器在1～3路间自适应升降。
- 不对测试集做按文件名硬编码，不使用规定外的大模型。
- 表格GT包含HTML、`rowspan`和`colspan`，不能统一转换为管道Markdown表格。

实测结论和失败策略见 `EXPERIMENTS.md`。

## 本地 tiny OCR 高密表格路线

极端宽表不再依赖数百次 FinixDoc-VL 切片请求。程序使用 CPU 版
PP-OCRv6 tiny（检测与识别合计约 1.5M 参数），把已知网格分成约
400--500 个核心单元格的连续块。每块额外携带一圈重叠单元格，只接收
核心区结果，从而避免首尾字符被裁断。每个切片结果按内容哈希原子缓存，
中断后再次运行会直接复用。

OCR 依赖安装在独立环境，不污染主项目环境：

```powershell
D:\AFAC2026\environment\ocr\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

模型目录默认是 `D:\AFAC2026\models\paddlex\official_models`，其中应有
`PP-OCRv6_tiny_det` 和 `PP-OCRv6_tiny_rec`。运行单张高密表：

```powershell
$env:PADDLE_PDX_CACHE_HOME = 'D:\AFAC2026\models\paddlex'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
D:\AFAC2026\environment\ocr\Scripts\python.exe main.py local-table-ocr `
  "D:\AFAC2026\data\...\example.jpg" `
  --output "D:\AFAC2026\outputs\example.md" `
  --cpu-threads 8
```

PaddlePaddle 3.3.1 在本机必须关闭 MKLDNN；代码已经固定
`enable_mkldnn=False`，不要手工打开。当前默认单进程 8 线程，兼顾速度与
桌面可用性。

## A 榜批量运行

先生成纯离线路由计划；此命令不会调用 API：

```powershell
D:\AFAC2026\environment\ocr\Scripts\python.exe main.py batch-plan `
  --output D:\AFAC2026\outputs\a_batch_plan.json
```

正式运行前，在当前 PowerShell 会话设置 `FINIX_API_KEY`，不要把密钥写进
命令历史、源码或提交文件。默认 API 两路与本地两个进程同时运行；每个本地
进程使用 6 个 CPU 线程：

```powershell
D:\AFAC2026\environment\ocr\Scripts\python.exe main.py batch-run --phase all
```

如果 API 表格结果触发字符上限或未闭合表格告警，使用可恢复的本地修复：

```powershell
D:\AFAC2026\environment\ocr\Scripts\python.exe main.py repair-table-warnings `
  --workers 3 --cpu-threads 4
D:\AFAC2026\environment\ocr\Scripts\python.exe main.py batch-run --phase submission
```

原 API 预测会先备份到 `outputs/repair_backups`。超大单元格会按像素预算
继续细分，核心单元格不重叠，只有一格识别上下文边缘会重叠。

只验证一张图时可使用 `--file-name example.jpg`；可分别用 `--phase api`、
`--phase local` 和 `--phase submission`。结果位于
`D:\AFAC2026\outputs\predictions_A`，状态位于
`D:\AFAC2026\outputs\a_batch_status.json`。任意中断后重跑同一命令即可；
已经完成的整图、纵向块、本地 OCR 块和单图 Markdown 都会命中缓存。
