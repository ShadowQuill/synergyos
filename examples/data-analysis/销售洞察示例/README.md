# 示例：商业分析 · 数据分析洞察（data-analysis）

- **场景**：`data-analysis`
- **任务**：分析上半年销售额并给出关键结论
- **验收要素（verify_markers）**：数据 · 趋势 · 结论 · 图表（可选）

## 这个示例展示什么

`洞察报告.md` 是 data-analysis 场景 mock 引擎产出的洞察报告，覆盖
「数据 → 趋势 → 结论」，结构化验收判定 `passed=True`。本示例按用户「不用画图」
省略了图表，演示可视化为可选项。

## 用户排除要素时（诚实省略）

若用户任务写成「分析上半年销售额，不用画图，给关键结论就行」：
强排除「不用」只作用到图表组，数据/趋势/结论组保留；
验收把「图表」归入 `skipped` 并标注「⏭ 已按用户要求省略」。
本场景「数据」组 `verify_excludes=[]`，永不可被排除。

## 运行

```bash
python -m synergyos.cli --scenario data-analysis --task "分析上半年销售额并给出关键结论" --report
```
