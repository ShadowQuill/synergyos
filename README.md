# 灵犀 · 自进化协作智能体（SynergyOS）

> 心有灵犀一点通 —— 以用户为中心的多角色 AI 智能体网络。
> 从「被动应答」走向「主动共生」：懂得在正确的时间做正确的事，在适当的时候保持沉默。

[![CI](https://github.com/ShadowQuill/synergyos/actions/workflows/ci.yml/badge.svg)](https://github.com/ShadowQuill/synergyos/actions/workflows/ci.yml)
[![Deploy demo](https://github.com/ShadowQuill/synergyos/actions/workflows/pages.yml/badge.svg)](https://github.com/ShadowQuill/synergyos/actions/workflows/pages.yml)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org)

📑 文档导航：[Menu](./menu.md)

## 核心理念
灵犀不只是一个模型，而是一个 **Multi-Agent 网络**，通过「分工-协作-反思」模拟人类顶级团队：
- **左脑（执行者）**：逻辑推理、代码生成、数据分析 —— 专注「如何把事做对」。
- **右脑（观察者）**：基于历史交互构建动态偏好库 —— 专注「如何让用户满意」。

## 四大核心机制
| 机制 | 模块 | 说明 |
|---|---|---|
| 双脑协作 | `core/brain.py` | 左脑 architect→programmer→tester 执行；右脑观察评分；仲裁融合 |
| 冷启动偏好锚定 | `core/profile.py` | 3-5 题最小探测建画像 + 后台静默学习 |
| 自适应生长与修复 | `core/reflexion.py` + `core/verify.py` | Reflexion 回溯协作链；**真实模型下 `verify.py` 真跑 pytest 并自动修复代码**（反思自愈） |
| 智能节律控制 | `core/pause.py` | Pause Horizon 预测停时 + 优雅暂停 + 阶段简报 |

## 运行方式
```bash
# 1) 开箱即跑（Mock 离线引擎，无需任何 API Key）
python3 -m synergyos.cli --auto --task "写一个函数计算斐波那契数列第 n 项"

# 2) 交互式冷启动（终端问 5 道选择题建立画像）
python3 -m synergyos.cli

# 3) 接入真实大模型（零改代码，检测到环境变量即切换）
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini        # 可选
python3 -m synergyos.cli --task "你的任务"

# 4) 导出运行报告（Markdown + HTML，含画像/双脑/反思/节律/时间线）
python3 -m synergyos.cli --auto --task "写一个去重函数" --report
#   仅 HTML：--report-format html   仅 MD：--report-format markdown
#   指定目录：--report-out my_reports

# 5) 安装为命令行工具（pip install 后即可使用 `synergyos` 命令）
pip install -e .
synergyos --auto --task "你的任务"

# 6) 按应用场景真跑（同一套双脑内核，按领域自适应产出）
#    paas=个人助理周报 / biz=商业分析可视化 / dev=软件研发需求到用例
python3 -m synergyos.cli --auto --scenario biz
#    不指定 --task 时，会用各场景的默认任务提示；也可显式给任务：
python3 -m synergyos.cli --scenario dev --task "实现去重并保持顺序的函数"

# 7) 软件研发助手：把架构/代码/用例真落盘为文件（原型要有交付物）
python3 -m synergyos.cli --scenario dev --task "实现去重并保持顺序的函数" --emit ./out
#    生成 ./out/<任务>/plan.json + solution.py + tests.py + README.txt
#    填了 OPENAI_API_KEY 后，此处落盘的就是真实可运行代码（代码零改动）
#    --emit 会自动识别测试 import 的模块名并复制同名副本（如 expiring_lru_cache.py），
#    保证 `cd ./out/<任务> && pytest tests.py` 开箱即跑，无需手动重命名。
#
# 8) 真实验证 + 反思自愈（仅真实模型，按场景分流）：
#    · dev：把生成的 solution+tests 写入临时目录真跑 pytest；失败则两阶段反思修复
#      ——先尝试修正实现，若仍失败说明断言自身与契约矛盾，则强制只修正那条测试断言
#      （如已过期的 key 被断言返回原值 → 改为 is None），最多重试 3 次。
#    · paas / biz：无 pytest 可跑，改用结构化验收——校验交付物是否覆盖场景必备要素
#      （周报须含 本周完成/进行中/风险/下周重点；分析须含 图表/趋势建模/数据），
#      缺失则用模型修复器补全，最多重试 3 次。
#    · 用户显式排除优先级：用户说「不要/不用 X」或「只列/只要 X Y」时，被排除的要素
#      不再强制补全，验收仅诚实标注「⏭ 已按用户要求省略」；且不被「未包含X」等
#      文字游戏干扰。规则：限定包含（只列A B = 包含A、B，排除其余）> 强排除（不要X）
#      > 模板必备要素。
#    （无人工干预的软修复）。CLI 与运行报告都会如实标注「✅ 通过 / ❌ 需人工复核」，
#    而非盲信模型的空壳 verdict。
python3 -m synergyos.cli --scenario dev --task "实现支持过期时间的 LRU 缓存" --emit ./out --report
```

## 应用场景（CLI 真跑）
同一套双脑协作内核（`architect → programmer → tester` + 观察者 + 反思），通过 `--scenario` 参数按领域自适应生成贴合的产出，并真正走完整链路：

| 场景 | 默认任务 | 左脑产出 | 验收方式 |
|---|---|---|---|
| `paas` 个人助理·周报 | 整理本周工作并生成结构化周报 | 周报（完成/进行中/风险/下周重点） | 结构化 |
| `biz` 商业分析·可视化 | 分析上半年销售额并生成可视化图表 | 数据清洗+建模脚本（科技蓝数据风） | 结构化 |
| `dev` 软件研发·需求到用例 | 实现去重并保持顺序的函数 | 代码 + 测试用例 | pytest 实测 |
| `code-review` 软件研发·代码评审 | 审查这段去重函数并指出问题与改进 | 代码评审报告（问题/严重性/建议/结论） | 结构化 |
| `data-analysis` 商业分析·数据洞察 | 分析上半年销售额并给出关键结论 | 数据分析报告（数据/趋势/结论，图表可选） | 结构化 |

> `dev`（软件研发助手）是产品的**楔子场景**：需求 → 架构师拆解 → 程序员编码 → 测试员用例，全程接真模型。专用提示词已强化（架构师输出接口契约/边界、程序员输出可运行模块、测试员输出 pytest），配合 `--emit` 落盘为真实可运行的交付物。其余场景作为"也能做"的延伸。

- 场景化产出由 `core/scenarios.py` 定义，引擎在 `scenario` 参数下按场景路由；接入真实大模型时该 mock 不再生效，改由提示词驱动。
- 产出会进入运行报告（`--report`），报告头显示「应用场景」字段。

## 用户显式排除要素优先级
当用户在任务里**显式排除**某些要素时，灵犀尊重用户意图而非机械套用模板：
- 用户说「**不要 / 不用 X**」（强排除）或「**只列 / 只要 X Y**」（限定包含）时，被排除的要素**不再强制补全**。
- 验收报告诚实标注「⏭ 已按用户要求省略」，而非假装已覆盖。
- 优先级三态：`限定包含（只列 A B = 包含 A、B，排除其余）` > `强排除（不要 X）` > `模板必备要素`。
- 规则用**作用域判定**（强排除信号之后到下一个标点之间才生效），避免跨组污染；覆盖判定升级为**行级否定感知边界匹配**，根除「未包含风险」等文字游戏误判。
- 真实 DeepSeek 验证记录见 [EVIDENCE_EXCLUDE.md](./EVIDENCE_EXCLUDE.md)。

## 偏好持久化（一次提问，终身受用）
用户画像默认落盘到 `~/.synergyos/profile.json`，跨会话静默学习累积：
- 首次运行自动锚定并保存；之后再启动直接加载历史画像，跳过冷启动探测。
- `--no-persist`：关闭持久化，仅本次运行有效（用于演示 / 测试）。
- `--profile-path PATH`：自定义画像文件路径（如团队共享同一画像）。

## 模型接入策略
- 默认 `MockEngine`：规则生成演示内容，全链路离线可跑，**零第三方依赖**。
- 检测到 `OPENAI_API_KEY`（或 `.env` 中的同名变量）时自动切换 `OpenAIEngine`，对接**任意 OpenAI 兼容接口**——OpenAI / **DeepSeek** / 通义 / 本地 Ollama 等，调用方代码零改动。
- 推荐用项目根 `.env` 存放密钥（已纳入 `.gitignore`，不入库、不进命令行历史）：
  ```bash
  # 例：DeepSeek（国内可用，OpenAI 兼容）
  OPENAI_API_KEY=sk-你的deepseek-key
  OPENAI_BASE_URL=https://api.deepseek.com/v1     # DeepSeek；OpenAI 可省略
  OPENAI_MODEL=deepseek-chat                      # 编码推荐 deepseek-chat
  ```
- 使用真实模型需安装 SDK：`pip install openai`（或 `pip install synergyos[openai]`）。未安装时运行会给出清晰提示。
- 切换优先级：`export` 的环境变量 > 运行目录 `.env` > 项目根 `.env`；均无 key 时回退 Mock。
- 验证：`OPENAI_API_KEY=sk-x python3 -c "from synergyos.core.engine import ENGINE; print(ENGINE.is_real())"` 应输出 `True`。

## 可视化演示
浏览器打开 `synergyos/demo/index.html`，可交互体验：双脑协作动画、冷启动问答、软修复调权、节律控制、实时协作时间线，以及「应用场景」区块（个人助理周报 / 商业分析可视化 / 软件研发需求到用例三选一，含专属产出与时间线回放）与运行报告导出。
Logo 源文件见 `synergyos/demo/logo.svg`（莫比乌斯环 + 声波波纹）。

## 在线演示与部署
- **在线演示（GitHub Pages）**：<https://shadowquill.github.io/synergyos/> —— 由 `.github/workflows/pages.yml` 自动把 `synergyos/demo` 部署，push 到 `main` 即更新。
- **CI（持续集成）**：`.github/workflows/ci.yml` 在 push / PR 时自动运行 55 项单测（`SYNERGYOS_FORCE_MOCK=1`，零 token 消耗）。
- **本地提交闸门**：仓库内置 `pre-commit` 钩子，提交前自动跑单测，任一失败即阻断提交，保证上库代码始终绿。
- 启用 Pages：仓库 `Settings → Pages → Build and deployment → Source` 选择 **GitHub Actions** 即可（首次部署需手动开启这一步）。

## 结构
```
synergyos/
├── core/
│   ├── engine.py      模型引擎（Mock / OpenAI 自动切换）
│   ├── bus.py         事件总线（协作过程可观测）
│   ├── profile.py     冷启动偏好锚定 + 静默学习 + 磁盘持久化
│   ├── brain.py       双脑协作（左脑执行 / 右脑观察 / 仲裁）
│   ├── reflexion.py   自适应生长与修复
│   ├── pause.py       智能节律控制
│   ├── scenarios.py   应用场景（paas/biz/dev/code-review/data-analysis）元数据与场景化 mock 产出
│   └── orchestrator.py 分工-协作-反思 顶层编排
│   └── report.py      运行报告生成（Markdown / HTML）
│   └── verify.py      真实验证 + 反思自愈（dev: pytest 实跑+两阶段修复；其余场景: 结构化验收+补全；支持「用户排除要素优先级」与否定感知边界匹配）
├── cli.py             终端演示入口
└── demo/              index.html + logo.svg
```

## 运行报告导出
- CLI：`--report` 把一次运行导出为 `reports/*.md` 与 `reports/*.html`（画像 / 双脑 / 反思 / 节律 / 时间线全链路可观测）。
- 网页：演示页新增「⑤ 运行报告导出」区块，可一键预览（HTML 新标签页）或下载（Markdown），与 CLI 报告同构。

## 测试
零依赖（仅标准库 `unittest`）：
```bash
python3 -m unittest discover -s tests -v
```
覆盖引擎路由、事件总线、冷启动锚定、双脑协作、反思调权、节律控制、编排全链路、报告生成、偏好持久化、应用场景，以及 `verify.py` 的「失败→反思修复→通过」自恢复（dev 两阶段修复 + paas/biz/code-review/data-analysis 结构化验收 + **用户显式排除要素的优先级规则** + **否定感知的边界匹配**），**共 55 项**。

> 测试全程强制 Mock 引擎（`SYNERGYOS_FORCE_MOCK=1`），即使项目根 `.env` 含真实 Key 也不会误打真实 API。接入真实模型时该开关不生效。
