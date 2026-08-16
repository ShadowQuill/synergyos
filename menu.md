# 项目导航 · Menu

> 灵犀 SynergyOS 文档与资源索引。新同学从这里出发。

## 快速开始
- [README（项目主页）](./README.md) —— 核心理念、运行机制、安装、应用场景、模型接入、测试
- [在线演示 Demo](https://shadowquill.github.io/synergyos/) —— 浏览器交互体验双脑协作 / 冷启动 / 反思自愈 / 节律控制 / 应用场景 / 报告导出

## 核心能力
- [应用场景](./README.md#应用场景cli-真跑) —— `paas` 周报 / `biz` 分析 / `dev` 研发 / `code-review` 评审 / `data-analysis` 洞察
- [多智能体实体化](./README.md#四大核心机制) —— `agents/` 下五个独立 Agent 类（架构师/程序员/测试员/观察者/仲裁）
- [智能体调工具（MCP 风格）](./README.md#智能体调工具mcp-风格工具接口零依赖) —— 沙箱文件读写 + 可开关联网搜索，零依赖
- [软学习闭环（越用越聪明）](./README.md#自进化vs真学习诚实说明面试必问) —— 经验库 + 失败模式库 + few-shot + 权重持久化（**非梯度**，诚实说明）
- [量化评测基准](./README.md#量化评测基准eval-集) —— 跨场景评测集，量化必备要素完整率 / 满意度 / 经验召回率
- [用户显式排除要素优先级](./README.md#用户显式排除要素优先级) —— 用户说「不要 X / 只列 A B」时，被排除要素不再强制补全，仅在报告中诚实标注「⏭ 已按用户要求省略」
- [多国产引擎接入](./README.md#模型接入策略多国产引擎零改代码) —— 零改代码对接 DeepSeek / 通义 / 智谱 GLM / OpenAI

## 真实验证证据
- [EVIDENCE.md](./EVIDENCE.md) —— 真实模型端到端验证（含 v1.2 软学习闭环、多引擎择优选型）
- [EVIDENCE_EXCLUDE.md](./EVIDENCE_EXCLUDE.md) —— 「用户排除要素优先级」真实 DeepSeek 验证（paas / biz / code-review / data-analysis）

## 本地开发
- 测试：`SYNERGYOS_FORCE_MOCK=1 python3 -m unittest discover -s tests`（**93 项**，零 token 消耗）
- 量化评测：`python3 -m synergyos.eval`（默认强制 Mock，离线确定性、零 token；`--real` 才用真实模型）
- 版本记录：[CHANGELOG.md](./CHANGELOG.md) —— 当前 **v1.2.0**（真实引擎 / 工具沙箱 / 软学习 / 量化评测）
- 提交闸门：仓库内置 `pre-commit` 钩子，提交前自动跑单测，失败阻断提交
- CI：`.github/workflows/ci.yml` —— push / PR 自动跑单测
- 部署：`.github/workflows/pages.yml` —— 将 `synergyos/demo` 部署到 GitHub Pages

## 目录结构
详见 [README · 结构](./README.md#结构)。
