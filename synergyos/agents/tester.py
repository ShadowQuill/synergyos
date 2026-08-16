"""左脑·测试员智能体（Tester Agent）。

负责针对代码生成测试用例。作为独立 Agent 类，可被单独实例化、测试与组合。
"""
from __future__ import annotations

from typing import Optional

from .base import Agent
from .prompts import scenario_prompts
from ..core.bus import EventType
from ..core.profile import UserProfile


class TesterAgent(Agent):
    name = "tester"
    role = "tester"

    def act(self, task: str, code: str, profile: UserProfile, style_hint: str = "",
            scenario: Optional[str] = None, experience: str = "") -> str:
        """产出测试用例（tests 文本）。experience 为软学习闭环注入的历史经验。"""
        _, _, sys_test = scenario_prompts(scenario, profile, style_hint)
        marker = f"用户任务:{task}"
        user = f"{marker}\n代码：\n{code}"
        if experience:
            user += f"\n\n{experience}"
        tests = self.complete(sys_test, user, scenario=scenario)
        self.bus.publish(EventType.LEFT_STEP, self.name, "测试员：产出测试用例")
        return tests
