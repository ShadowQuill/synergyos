"""左脑·架构师智能体（Architect Agent）。

负责把用户任务拆解为可执行方案（plan）。作为独立的 Agent 类，
它拥有自己的角色身份与提示词工厂，可被单独实例化、测试与组合。
"""
from __future__ import annotations

from typing import Optional

from .base import Agent
from .prompts import scenario_prompts
from ..core.bus import EventType
from ..core.profile import UserProfile


class ArchitectAgent(Agent):
    name = "architect"
    role = "architect"

    def act(self, task: str, profile: UserProfile, style_hint: str = "",
            scenario: Optional[str] = None, memory_hint: str = "",
            experience: str = "") -> str:
        """产出实施方案（plan 文本）。

        memory_hint 为语义记忆层回填的相关知识；experience 为软学习闭环注入的
        历史经验 few-shot（失败模式库 / 相似成功案例）。
        """
        sys_arch, _, _ = scenario_prompts(scenario, profile, style_hint)
        marker = f"用户任务:{task}"
        user = f"{marker}\n任务：{task}"
        if memory_hint:
            user += f"\n\n可参考的既往知识（来自语义记忆层）：\n{memory_hint}"
        if experience:
            user += f"\n\n{experience}"
        plan = self.complete(sys_arch, user, scenario=scenario)
        self.bus.publish(EventType.LEFT_STEP, self.name, "架构师：产出实施方案")
        return plan
