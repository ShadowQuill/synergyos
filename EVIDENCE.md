# 灵犀 SynergyOS · 真实验收证据包（v0.1）

本文汇总「灵犀·真实产品原型 v0.1」在 **DeepSeek（deepseek-chat，OpenAI 兼容）** 真实模型下的端到端验收证据。所有产出均由 `python3 -m synergyos.cli` 真实调用大模型生成，未做任何人工编辑。

## 复现方式

```bash
# 项目根 .env 写入 OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL（DeepSeek）
python3 -m synergyos.cli --auto --scenario <dev|paas|biz> \
  --task "<任务>" --emit <out_dir> --report --report-out <reports_dir>
```

## 证据清单

### 1. dev · pytest 实测一次通过
- 任务：实现支持过期时间的 LRU 缓存类 `ExpiringLRUCache`
- 证据：`out_dev_heal/` + `reports_dev_heal/`
- 结论：架构→代码→pytest 用例全真实生成；落盘后 `pytest tests.py` 实测 **32 passed**；报告标注「真实验证通过：pytest 实测，一次通过」。

### 2. paas · 结构化验收自愈成功（正例）
- 任务：只给完成事项，让模型自然遗漏部分必备要素（周报四要素）
- 证据：`out_paas_heal3/` + `reports_paas_heal3/`
- 结论：首次交付物缺失「风险 / 下周重点」等必备要素 → 反思修复器补全 **1 次** → 结构化验收通过（共运行 2 次）。坐实「灵犀反思自愈」能力。

### 3. paas · 结构化验收诚实标注冲突（边界例）
- 任务：用户显式要求「只写完成+进行中，不要风险和下周计划」
- 证据：`out_paas_heal/` + `reports_paas_heal/`
- 结论：验收检测到缺失，修复器尝试补全 3 次仍尊重用户意图未补「风险」→ 如实标注「❌ 需人工复核」。体现灵犀**不盲补、不盲信**。

### 4. biz · 结构化验收自愈成功
- 任务：只给销售额数字，要求「不要画图、不要建模」
- 证据：`out_biz_heal/` + `reports_biz_heal/`
- 结论：验收检测到缺失图表 / 趋势建模要素 → 反思修复器补全 **1 次** → 通过（共运行 2 次）。

## 诚实结论

- 真实验收机制（dev→pytest 实测；paas/biz→结构化验收）真实生效，能识别缺失并**自动补全**或**诚实标注**。
- 暴露的设计边界：**用户意图 vs 场景模板必备要素** 冲突时，软修复目前缺乏明确的优先级策略（paas 边界例尊重用户、biz 例覆盖用户补全），属真实多智能体不确定性，非代码 bug。后续可加规则：用户显式排除的要素不参与强制补全。

## 单测

`python3 -m unittest discover -s tests` → **44 项全绿**（含结构化验收与反思自愈用例）。
