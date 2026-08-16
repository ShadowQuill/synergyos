"""示例：智能体调工具（MCP 风格工具接口，离线可跑）。

演示「程序员智能体」如何借助内置工具（读文件 / 写文件 / 列目录 / 搜索）
获取上下文后再产出代码——即「智能体 ↔ 工具」的通信闭环。

运行（零依赖、无需 API Key，走 Mock 引擎）：
    python3 examples/99-tools/mcp_tools_demo.py

接入真实模型时，把环境变量 OPENAI_API_KEY 等一设，同一份代码会改为
由真实大模型产出 <tool_call>，执行器协议不变。
"""
from __future__ import annotations

import os
import tempfile

from synergyos.core.engine import ENGINE
from synergyos.core.bus import EventBus
from synergyos.core.profile import UserProfile
from synergyos.agents import ProgrammerAgent, make_builtin_tools, ToolExecutor


def demo_programmer_with_tools() -> None:
    print("=" * 60)
    print("演示 1：程序员智能体调用工具（离线 Mock 触发 web_search）")
    print("=" * 60)
    bus = EventBus()
    tools = make_builtin_tools()
    programmer = ProgrammerAgent(ENGINE, bus=bus)

    task = "分析最近一周的销售额趋势并给出结论"
    plan = '{"task": "销售额趋势分析", "steps": ["检索资料", "建模", "结论"]}'
    code = programmer.act_with_tools(task, plan, UserProfile(),
                                     scenario="biz", tools=tools)
    print("\n>>> 程序员最终产出：\n")
    print(code)
    print("\n>>> 本轮回合中程序员在总线上广播的事件：")
    for ev in bus.history():
        if ev.source == "programmer":
            print(f"  - {ev.message}")


def demo_tool_executor_directly() -> None:
    print("\n" + "=" * 60)
    print("演示 2：直接用 ToolExecutor 走通「解析 → 调用 → 回填」")
    print("=" * 60)
    reg = make_builtin_tools()
    ex = ToolExecutor(reg)

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "demo.txt")
        # 1) 写文件
        w = ex.run_one("write_file", {"path": path, "content": "灵犀 = 双脑协作 + 反思自愈"})
        print(f"  write_file -> {w['output']}")
        # 2) 读文件
        r = ex.run_one("read_file", {"path": path})
        print(f"  read_file -> {r['output']}")
        # 3) 列目录
        ls = ex.run_one("list_dir", {"path": d})
        print(f"  list_dir  ->\n{ls['output']}")
    # 4) 搜索（离线模拟）
    s = ex.run_one("web_search", {"query": "多智能体协作"})
    print(f"  web_search -> {s['output']}")


if __name__ == "__main__":
    demo_programmer_with_tools()
    demo_tool_executor_directly()
