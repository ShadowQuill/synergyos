"""左脑·程序员智能体（Programmer Agent）。

负责依据方案编写实现代码。作为独立 Agent 类，它额外支持【工具调用】：
当持有 ToolRegistry 且以 act_with_tools 方式运行时，会先尝试用工具获取上下文
（读文件 / 搜索等），再把工具结果回填，最终产出代码——这正是「智能体调工具」的演示点。

为保持向后兼容，无工具的 act() 路径与原 brain.LeftBrain 行为完全一致。
"""
from __future__ import annotations

from typing import Optional

from .base import Agent
from .prompts import scenario_prompts
from .tools import ToolRegistry, ToolExecutor
from ..core.bus import EventType
from ..core.profile import UserProfile


class ProgrammerAgent(Agent):
    name = "programmer"
    role = "programmer"

    TOOL_PROTOCOL_HINT = (
        "若完成任务需要读取本地文件或联网检索资料，请先输出一个工具调用：\n"
        '<tool_call>{"name": "工具名", "arguments": {"参数": "值"}}</tool_call>\n'
        "可用工具见下方目录。工具返回后，再据此产出最终代码。"
    )

    def act(self, task: str, plan: str, profile: UserProfile, style_hint: str = "",
            scenario: Optional[str] = None, experience: str = "") -> str:
        """无工具模式：直接依据方案产出代码（与原 brain.LeftBrain 行为一致）。"""
        _, sys_code, _ = scenario_prompts(scenario, profile, style_hint)
        marker = f"用户任务:{task}"
        user = f"{marker}\n方案：\n{plan}\n\n任务：{task}"
        if experience:
            user += f"\n\n{experience}"
        code = self.complete(sys_code, user, scenario=scenario)
        self.bus.publish(EventType.LEFT_STEP, self.name, "程序员：产出实现代码")
        return code

    def act_with_tools(self, task: str, plan: str, profile: UserProfile,
                       style_hint: str = "", scenario: Optional[str] = None,
                       tools: Optional[ToolRegistry] = None,
                       max_tool_rounds: int = 2,
                       experience: str = "") -> str:
        """工具增强模式：先尝试用工具取上下文，再产出代码。

        仅当 tools 非空时进入工具循环；否则退化为 act()。
        """
        if not tools:
            return self.act(task, plan, profile, style_hint, scenario)

        _, sys_code, _ = scenario_prompts(scenario, profile, style_hint)
        marker = f"用户任务:{task}"
        user = f"{marker}\n方案：\n{plan}\n\n任务：{task}"
        if experience:
            user += f"\n\n{experience}"
        sys_full = f"{sys_code}\n\n{self.TOOL_PROTOCOL_HINT}\n\n{tools.catalogue()}"

        ctx_parts: list = []
        code_text = ""
        for idx in range(max_tool_rounds):
            # 首轮允许模型发起工具调用；之后工具结果已回填，模型应直接产出代码，
            # 避免反复请求同一工具陷入循环（贴合真实模型「调用一次→产出」的节奏）。
            if ctx_parts:
                user += "\n\n" + "\n\n".join(ctx_parts)
            resp = self.complete(sys_full, user, scenario=scenario,
                                 allow_tools=(idx == 0))
            results, ran = ToolExecutor(tools).execute(resp)
            if not ran:
                code_text = resp
                break
            ctx_parts.append(ToolExecutor.format_results(results))
            self.bus.publish(EventType.LEFT_STEP, self.name,
                             f"程序员：调用工具 {[r['name'] for r in results]}")
            # 继续循环，让模型在工具结果基础上产出最终代码

        if not code_text:
            # 工具轮结束后补一次纯代码生成（不再允许工具调用，避免死循环）
            code_text = self.complete(
                sys_full, user + "\n\n" + "\n\n".join(ctx_parts), scenario=scenario)
        self.bus.publish(EventType.LEFT_STEP, self.name, "程序员：产出实现代码")
        return code_text
