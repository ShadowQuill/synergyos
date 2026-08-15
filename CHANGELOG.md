# Changelog · 灵犀 SynergyOS

本项目遵循语义化版本（SemVer）。所有 notable 变更记录于此。

---

## [v1.0.0] — 2026-08-15

> 首个公开 Release（GitHub）。以 v1.0.0 作为正式版本号，涵盖下方 v0.1.0 → v0.1.1 的全部内容：双脑协作内核、Reflexion 反思自愈、结构化验收（含用户显式排除要素优先级）、5 个应用场景、本地 pre-commit 闸门 + CI + Pages 部署、完整文档与示例。

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
