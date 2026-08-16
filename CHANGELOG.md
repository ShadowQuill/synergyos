# Changelog · 灵犀 SynergyOS

本项目遵循语义化版本（SemVer）。所有 notable 变更记录于此。

---

## [v1.0.0] — 2026-08-15

> 首个公开 Release（GitHub）。以 v1.0.0 作为正式版本号，涵盖下方 v0.1.0 → v0.1.1 的全部内容：双脑协作内核、Reflexion 反思自愈、结构化验收（含用户显式排除要素优先级）、5 个应用场景、本地 pre-commit 闸门 + CI + Pages 部署、完整文档与示例。

---

## [v1.2.0] — 2026-08-16

> 主题：**真能干活 · 多国产引擎 · 软学习闭环 · 量化评测**（改进报告 P0 三项 + 诚实说明 + P1#4/#5/#6）
> 对应 `改进方向_灵犀SynergyOS_2026-08-16.html`。

### Added（新增）
- **真能干活（真实引擎）**：`engine.py` 升级为「真实大模型即开即用」——内置 deepseek / 通义千问(qwen) / 智谱 GLM(glm) / OpenAI 四套预设，`build_engine()` 按 `SYNERGYOS_PROVIDER` 或已配置 Key 自动择优选型（优先 deepseek），均无 Key 时优雅降级 Mock。零改代码接入真实大脑。
- **工具真实化（默认离线、可选联网）**：`agents/tools/builtins.py` 的文件读写**真实副作用**，加 `--workspace` 沙箱（默认 `workspace/` 内、禁删、越界拒绝）；`web_search` 默认离线模拟，置 `--online` 或 `SYNERGYOS_ONLINE=1` 时走标准库 `urllib` 真搜。程序员智能体可真读写工作区。
- **软学习闭环（P1#4，零依赖、可离线）**：`core/learning.py` 实现「越用越聪明」——每次任务记一条经验（成败/失败类型/用过的工具/反馈），失败经历聚合成**失败模式库**，相似历史作为 **few-shot 注入**回灌智能体；反思权重与经验库**跨会话持久化**（重启仍在）。
- **量化评测基准（P1#5）**：`eval/`（cases + runner）内置跨场景评测集，量化「必备要素完整率 / 满意度 / 经验召回率」，让自进化收益可被数字度量。
- 多国产引擎对比（P1#6）即上方引擎预设；CLI / README / EVIDENCE 同步。
- README 新增「两种记忆」「智能体调工具」「自进化 vs 真学习（诚实说明）」「软学习闭环」「量化评测」「多引擎接入」等节；`examples/99-tools/` 提供离线可跑演示。

### Changed（变更）
- `synergyos/__init__.py`：导出 `SemanticMemory`、四个 Agent 类、工具接口、`ExperienceStore`/`FailureLibrary`/`WeightStore` 软学习类。
- `MockEngine`：新增 opt-in 的 `allow_tools` 分支，离线触发 `<tool_call>` 以走通工具闭环。
- `ReflexionLoop`：权重**支持持久化**（默认不写，开启 learning 时落盘）。
- 多智能体（`architect`/`programmer`/`tester`）支持 `experience` few-shot 注入参数。

### Fixed（修复）
- **真实引擎端点被忽略**：`create_engine()` 此前只认预设 `base_url`，导致「把国产模型配在 `OPENAI_*` 变量」的常见用法会拿着 DeepSeek 的 Key 去打 `api.openai.com` 并超时。现支持 `SYNERGYOS_BASE_URL` / `SYNERGYOS_MODEL`（任意 provider）与 `OPENAI_BASE_URL` / `OPENAI_MODEL`（openai provider），且不会串味到其他 provider 的预设。
- **验证/自愈误用模块级引擎**：`orchestrator` 判断是否走「pytest 实测 + 反思自愈」时错用了模块级 `ENGINE` 而非实例引擎，显式传入 Mock 的实例仍会触发真实调用。改为一律以 `self.engine` 为准；`report.py` 的「引擎」字段同样改为按实际运行实例显示。
- **评测基准会误打真实 API**：`run_eval()` 默认引擎改为 `MockEngine()`（不再取模块级 `ENGINE`），基准从此与本机 `.env` 无关，恒定离线秒级；需要真实模型对比时用 `python3 -m synergyos.eval --real`。

### Verified（验证）
- 单测扩展至 **93 项**全绿（零 token），新增覆盖：工具沙箱越界拒绝 / 离线搜索桩 / 软学习经验库 / 失败模式库 / 权重持久化 / 量化评测运行器 / 引擎端点环境变量覆盖 / 验证只跟随实例引擎。
- **真实 DeepSeek 端到端跑通**：`--scenario dev` 全链路 39s 出交付物（plan + solution.py + tests.py + README），pytest 实测 **27/32 通过**——其余 5 条是模型自生成用例与实现规格自相矛盾（要求非 list 入参抛 `TypeError`），系统按设计如实标注「❌ 需人工复核」而非盲信模型。
- 量化评测（离线、Mock）：必备要素完整率 **85.7%**、满意度均值 **0.84**、经验召回率 **100%**，7 用例 0.07s 完成。
- `examples/99-tools/` 两个脚本离线跑通（工具闭环 + 记忆检索 + 软学习回灌）。

---

## [v0.1.1] — 2026-08-15

> 主题：**要素优先级规则 · 场景库扩展 · 验收健壮性增强 · 仓库规范化**

### Added（新增）
- **用户显式排除要素优先级规则**：统一「用户排除要素 vs 场景必备要素」——用户排除优先，验收不再强制补全，报告中诚实标注「⏭ 已按用户要求省略」。
- `scenarios.py` 新增 `verify_excludes` 字段（与 `verify_markers` 同序），承载各要素的排除指代词。
- **场景库扩展**：新增 `code-review`（代码评审）与 `data-analysis`（数据分析洞察）两个场景，复用 `verify` 结构化验收框架。
- `verify.py` 排除信号拆分为**强排除**（不用/不要）与**限定包含**（只列/只要），按作用域判定避免跨组污染。
- `verify.py` 子串匹配升级为**行级否定感知边界匹配**，根除「文字游戏」误判（如「未包含风险」被误判已覆盖）。
- demo 预置 4 场景「用户排除要素」样例，默认载入 paas 示例。
- 本地 `pre-commit` 回归闸门：提交前自动跑 55 项单测（`SYNERGYOS_FORCE_MOCK`，零 token）。
- `.github/workflows/ci.yml`：push/PR 自动跑单测。
- `.github/workflows/pages.yml`：部署 `synergyos/demo` 到 GitHub Pages。
- 文档体系：`menu.md`、`CONTRIBUTING.md`、`examples/` 多场景示例索引、本 `CHANGELOG.md`、`LICENSE`（MIT）。
- `.python-version` 锁定 3.11，与 CI 对齐。

### Changed（变更）
- `cli.py`：`_emit` 落盘分支由 `scenario in ("paas","biz")` 泛化为 `scenario != "dev"`，所有结构化场景均落盘 `checks.json`。
- `cli.py`：`--help` 文案增强（描述 + 用法示例 + epilog）。
- `report.py` / `cli.py`：通过时若存在 `skipped` 显示「⏭ 已按用户要求省略」。

### Fixed（修复）
- **强排除作用域缺陷**：原全局 `hasStrong` 标志导致「不用画图」误伤同句含排除词（如「关键结论」）的其它要素组；改为 `_strong_excluded` 作用域判定。
- **biz 数据组 exclude 过宽**：原 exclude 含「销售额/分析」被误判；数据组改为 `verify_excludes=[]`（永不可排除）。
- **行级否定窗口跨行**：初版固定字符窗口跨行捕获上一行「- 无」误判本行「下周重点」；改为仅当前行前缀。
- **Python 3.11 兼容性**：`cli.py`/`report.py` 的 f-string 内嵌套同型引号在 3.11（CI）报 `SyntaxError`；改用双引号内层 + 中间变量，并用 `python3.10` 编译校验。

### Verified（验证）
- 55 项单测全绿（零 token）。
- 真实 DeepSeek 端到端跑通 paas / biz / code-review / data-analysis 四场景，排除要素场景下均正确标注「⏭ 已省略」。
- CI（Python 3.11）与 GitHub Pages 部署均 success。

---

## [v0.1.0] — 初始版本

> 主题：**双脑协作内核 + Reflexion 反思自愈 + 智能节律控制** 的最小可用闭环。

### Added（新增）
- 双脑协作：左脑（规划/编码）与右脑（观察/反思）分工仲裁。
- 冷启动偏好锚定：冷启动提问 + 偏好持久化（`~/.synergyos/profile.json`）。
- Reflexion 反思自愈：`dev` 场景生成代码后真实 `pytest` 实测，失败则两阶段修复。
- 智能节律控制：进度暂停（`--pause`）与恢复。
- 事件总线 + 彩色日志，终端可视化协作过程。
- 三个基础场景：`paas`（周报）/ `biz`（可视化）/ `dev`（研发）。
- mock 引擎（零 token）+ 真实大模型接入（OpenAI / DeepSeek / 通义 / Ollama）。
- 单测基线、结构化报告（Markdown + HTML）导出。

---

## 版本对照速查

| 版本 | 场景数 | 单测数 | 在线演示 | 排除优先级 |
|------|-------|-------|---------|-----------|
| v0.1.0 | 3 (paas/biz/dev) | ~40 | 否 | 否 |
| v0.1.1 | 5 (+code-review/data-analysis) | 55 | 是（Pages） | 是 |
| v1.2.0 | 5 | 93（+agents/tools/memory/learning/eval/引擎端点） | 是（Pages） | 是 |
