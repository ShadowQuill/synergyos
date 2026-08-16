"""工具接口抽象层（Tool Interface，MCP 风格、零依赖）。

设计目标（对应改进报告 P0：让智能体能调外部工具/API）：

  不引入 mcp SDK，而是用纯标准库实现一套与 MCP「工具调用」语义等价的
  进程内抽象——每个工具自描述（name / description / parameters），
  智能体通过统一的 `<tool_call>` 文本协议请求调用，执行器解析并回调工具函数。
  这样既能讲清楚「智能体 ↔ 工具」的通信底座，又保持离线可跑、零第三方依赖。

协议（模型无关，兼容任意 OpenAI 兼容引擎）：
  智能体在回复中嵌入：
      <tool_call>{"name": "read_file", "arguments": {"path": "x.py"}}</tool_call>
  执行器解析后调用对应工具，并把结果回填给智能体继续推理。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Tool:
    """一个可被智能体调用的工具。

    parameters 用极简 JSON-Schema 子集描述（type / description / required / properties），
    既供执行器做参数提示，也可直接喂给支持 tool schema 的真实模型。
    """
    name: str
    description: str
    parameters: Dict
    fn: Callable[..., str]

    def invoke(self, arguments: Dict) -> (bool, str):
        """执行工具，返回 (是否成功, 输出文本)。

        任何异常都被捕获并转成安全的错误文本（ok=False），绝不抛出到智能体链路外。
        """
        try:
            return True, str(self.fn(**(arguments or {})))
        except Exception as e:  # noqa: BLE001 — 工具失败要被智能体观测到，而非崩溃
            return False, f"[tool_error] {self.name} 执行失败：{type(e).__name__}: {e}"


class ToolRegistry:
    """工具注册表：管理可用工具，并为提示词生成「工具目录」。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> List[Tool]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def catalogue(self) -> str:
        """生成面向模型/用户的工具清单文本。"""
        if not self._tools:
            return "（当前无可用工具）"
        lines = ["以下工具可供调用，按需嵌入 <tool_call> 协议："]
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)

    def schema_json(self) -> str:
        """导出供支持 tool schema 的真实模型使用的 JSON 描述。"""
        defs = []
        for t in self._tools.values():
            defs.append({
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            })
        return json.dumps(defs, ensure_ascii=False, indent=2)


class ToolExecutor:
    """解析智能体产出的 <tool_call> 并回调工具。

    这是「智能体通信底座」的最小可用实现：把自然语言协议翻译成实际函数调用，
    再把结果格式化为可回填的上下文。后续若要对接标准 MCP，只需把 fn 换成
    mcp 客户端的 tool/invoke 即可，协议层不变。
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    @staticmethod
    def parse_tool_calls(text: str) -> List[Dict]:
        """从模型回复中解析所有 <tool_call>...</tool_call> 块。"""
        calls: List[Dict] = []
        start = 0
        marker = "<tool_call>"
        while True:
            i = text.find(marker, start)
            if i == -1:
                break
            j = text.find("</tool_call>", i)
            if j == -1:
                break
            raw = text[i + len(marker):j].strip()
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict) and "name" in payload:
                    calls.append({
                        "name": payload["name"],
                        "arguments": payload.get("arguments", {}) or {},
                    })
            except Exception:
                pass  # 非法的 tool_call 块直接忽略，交还模型自行纠正
            start = j + len("</tool_call>")
        return calls

    def run_one(self, name: str, arguments: Dict) -> Dict:
        tool = self.registry.get(name)
        if tool is None:
            return {"name": name, "ok": False,
                    "error": f"未知工具：{name}", "output": ""}
        ok, output = tool.invoke(arguments)
        return {"name": name, "ok": ok,
                "output": output, "error": "" if ok else output}

    def execute(self, text: str) -> (List[Dict], bool):
        """解析并执行文本中的所有工具调用。返回 (结果列表, 是否真的调用了工具)。"""
        calls = self.parse_tool_calls(text)
        if not calls:
            return [], False
        results = [self.run_one(c["name"], c["arguments"]) for c in calls]
        return results, True

    @staticmethod
    def format_results(results: List[Dict]) -> str:
        """把工具结果格式化为可回填给模型的上下文。"""
        blocks = []
        for r in results:
            if r["ok"]:
                blocks.append(f"## 工具 {r['name']} 返回\n{r['output']}")
            else:
                blocks.append(f"## 工具 {r['name']} 失败\n{r['error']}")
        return "\n\n".join(blocks)
