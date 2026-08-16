# 示例 99 · 新能力演示（工具接口 & 语义记忆 & 软学习）

这些脚本演示改进报告 P0 / P1 中新增的能力，均**零依赖、无需 API Key、可离线运行**（走 Mock 引擎）。

## 1. 智能体调工具（MCP 风格工具接口）

`python3 mcp_tools_demo.py`

- 演示 `ProgrammerAgent.act_with_tools()`：程序员智能体先用 `web_search` 取上下文，再产出代码（离线 Mock 触发 `<tool_call>` 协议）。
- 演示 `ToolExecutor` 直接走通「解析 → 调用 → 回填」：内置 `read_file` / `write_file` / `list_dir` / `web_search`（离线模拟）。
- 真实化说明：文件读写默认限定在 `--workspace` 沙箱内（越界 / 删除被拒绝）；`web_search` 置 `--online` 或 `SYNERGYOS_ONLINE=1` 时走标准库 `urllib` **真搜**。

## 2. 语义记忆层

`python3 semantic_memory_demo.py`

- 演示 `SemanticMemory` 的 TF-IDF 检索（中文字 bigram 分词），以及 JSON 持久化往返。
- 注意它和 `core/profile.py` 的「偏好记忆」、以及 `core/learning.py` 的「软学习经验库」是三类不同的记忆（详见 README「两种记忆」一节）。

## 3. 软学习闭环（越用越聪明，P1#4）

> 见仓库根 `EVIDENCE.md` 的 v1.2 验收，或用 CLI 直接体验：
> `python3 -m synergyos.cli --auto --scenario dev --learning-dir ./.synergyos_learn --task "实现快速排序"`
> 第二次跑相似任务会检索到首轮经验并作为 few-shot 注入。

## 量化评测基准（P1#5）

`python3 -m synergyos.eval`

- 离线确定性评测 7 个跨场景用例，输出必备要素完整率 / 满意度 / 经验召回率（开启 learning 时），附逐用例明细。

> 接入真实大模型（DeepSeek / 通义 / 智谱 / OpenAI 环境变量）后，上述同一份代码会改为由真实模型产出工具调用与内容，执行器 / 记忆 / 评测协议不变。
