# 灵犀 SynergyOS · 真实验收证据包（v1.2）

本文汇总「灵犀·自进化协作智能体」在 **真实大模型（DeepSeek deepseek-chat，OpenAI 兼容）** 下的端到端验收证据。所有产出均由 `python3 -m synergyos.cli` / `SynergyOS(...)` **真实调用大模型生成**，未做任何人工编辑。API Key 仅通过环境变量 / `.env` 传入，**绝不入库**。

## 复现方式

```bash
# 多国产引擎任选其一（其余预设同理）
export DEEPSEEK_API_KEY=sk-xxx        # 或 DASHSCOPE_API_KEY / ZHIPU_API_KEY / OPENAI_API_KEY
python3 -m synergyos.cli --auto --scenario <dev|paas|biz|code-review|data-analysis> \
  --task "<任务>" --emit <out_dir> --report --report-out <reports_dir> \
  --workspace ./sandbox --learning-dir ./.synergyos_learn
#   --workspace  程序员文件读写落沙箱（默认 workspace/）
#   --learning-dir  开启软学习闭环（经验库 + 失败模式库 + 权重持久化）
```

## 本轮新增能力验收（v1.2，2026-08-16 真实 DeepSeek 实测）

| 能力 | 验证方式 | 结果 |
|---|---|---|
| 多引擎择优选型 | `DEEPSEEK_API_KEY=... python3 -c "from synergyos.core.engine import ENGINE; print(ENGINE.is_real(), ENGINE.cfg.provider)"` | `True deepseek` |
| 真实大脑端到端 | `SynergyOS(真实引擎).run("实现 Python 去重函数 dedupe，保持原顺序", scenario="dev")` | 产出真实方案 + 可运行代码；满意度 **0.8** |
| 工具真实副作用 + 沙箱 | 程序员 `--workspace ./sandbox` 读写文件 | 真实落盘；越界写入被拒绝（`ok=False`，含「越界」） |
| 软学习闭环 | 开启 `--learning-dir` 跑两次相似任务 | 经验落盘 `experiences.json`；第二轮检索到首轮经验并作为 few-shot 注入（经验召回率 100%） |
| 端点环境变量覆盖 | `OPENAI_API_KEY` + `OPENAI_BASE_URL=https://api.deepseek.com/v1` + `OPENAI_MODEL=deepseek-chat` | 真实命中 DeepSeek 端点并返回内容（修复前会误打 `api.openai.com` 超时） |
| 量化评测（离线基准） | `python3 -m synergyos.eval` | 7 用例 **0.07s** 完成：完整率 **85.7%**、满意度 **0.84**、经验召回率 **100%**；与本机 `.env` 无关，恒定 Mock |

> 真实引擎冒烟命令（单条补全）验证：`完整? True | provider: deepseek | base: https://api.deepseek.com | model: deepseek-chat`，返回"幂等指一个操作执行多次与执行一次结果相同..."等真实内容。

### 真实 DeepSeek 端到端复测（2026-08-16，dev 场景）

- 命令：`python3 -m synergyos.cli --task "实现一个列表去重函数，保持原顺序" --scenario dev --auto --workspace ./sandbox --learning-dir ./.synergyos_learn --emit ./out`
- 耗时 **39s**，落盘 `plan.json / solution.py / tests.py / README.txt` 全部真实生成。
- pytest 实测 **27 passed / 5 failed**：失败 5 条均为模型自生成的异常用例与自身实现规格**自相矛盾**（用例要求非 list 入参抛 `TypeError`，实现选择了宽容处理）。
- 系统按设计**如实标注「❌ 未通过（修复 1 次后仍失败，请人工复核）」**，未把模型的空壳 verdict 当成通过——这正是「诚实验收」而非"演示成功"。

## 历史场景证据（v0.1，仍有效）

### 1. dev · pytest 实测一次通过
- 任务：实现支持过期时间的 LRU 缓存类 `ExpiringLRUCache`
- 结论：架构→代码→pytest 用例全真实生成；落盘后 `pytest tests.py` 实测 **32 passed**；报告标注「真实验证通过：pytest 实测，一次通过」。

### 2. paas · 结构化验收自愈成功（正例）
- 任务：只给完成事项，让模型自然遗漏部分必备要素（周报四要素）
- 结论：首次交付物缺失「风险 / 下周重点」→ 反思修复器补全 **1 次** → 结构化验收通过。坐实「反思自愈」。

### 3. paas · 结构化验收诚实标注冲突（边界例）
- 任务：用户显式要求「只写完成 + 进行中，不要风险和下周计划」
- 结论：修复器尝试补全 3 次仍尊重用户意图未补「风险」→ 如实标注「❌ 需人工复核」。体现**不盲补、不盲信**。

### 4. biz · 结构化验收自愈成功
- 任务：只给销售额数字，要求「不要画图、不要建模」
- 结论：验收检测到缺失图表 / 趋势建模 → 反思修复器补全 **1 次** → 通过。

## 诚实结论

- 真实验收机制（dev→pytest 实测；paas/biz→结构化验收）真实生效，能识别缺失并**自动补全**或**诚实标注**。
- **软学习（v1.2 新增）是经验式、非梯度**：通过失败模式库 + few-shot + 权重跨会话持久化让系统"越用越聪明"，但**不微调模型权重**。这是刻意取舍，也是面试里诚实作答的加分项。
- 单测：`python3 -m unittest discover -s tests` → **93 项全绿**（零 token；CI 强制 Mock，真实 Key 不会误触）。
- 真实模型下的失败会被**如实暴露**（本轮 dev 复测 27/32），不美化、不掩盖；量化评测基准与真实调用严格隔离（基准恒定离线）。
