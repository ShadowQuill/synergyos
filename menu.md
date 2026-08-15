# 项目导航 · Menu

> 灵犀 SynergyOS 文档与资源索引。新同学从这里出发。

## 快速开始
- [README（项目主页）](./README.md) —— 核心理念、运行机制、安装、应用场景、模型接入、测试
- [在线演示 Demo](https://shadowquill.github.io/synergyos/) —— 浏览器交互体验双脑协作 / 冷启动 / 反思自愈 / 节律控制 / 应用场景 / 报告导出

## 核心能力
- [应用场景](./README.md#应用场景cli-真跑) —— `paas` 周报 / `biz` 分析 / `dev` 研发 / `code-review` 评审 / `data-analysis` 洞察
- [用户显式排除要素优先级](./README.md#用户显式排除要素优先级) —— 用户说「不要 X / 只列 A B」时，被排除要素不再强制补全，仅在报告中诚实标注「⏭ 已按用户要求省略」
- [模型接入策略](./README.md#模型接入策略) —— 零改代码对接 OpenAI / DeepSeek / 通义 / 本地 Ollama

## 真实验证证据
- [EVIDENCE.md](./EVIDENCE.md) —— 双脑 + 反思自愈真实模型验证记录
- [EVIDENCE_EXCLUDE.md](./EVIDENCE_EXCLUDE.md) —— 「用户排除要素优先级」真实 DeepSeek 验证（paas / biz / code-review / data-analysis）

## 本地开发
- 测试：`SYNERGYOS_FORCE_MOCK=1 python3 -m pytest tests/ -q`（55 项，零 token 消耗）
- 提交闸门：仓库内置 `pre-commit` 钩子，提交前自动跑单测，失败阻断提交
- CI：`.github/workflows/ci.yml` —— push / PR 自动跑单测
- 部署：`.github/workflows/pages.yml` —— 将 `synergyos/demo` 部署到 GitHub Pages

## 目录结构
详见 [README · 结构](./README.md#结构)。
