"""智能体基类（Agent Base）。

灵犀把协作链路里的每个角色实现为独立的 Agent 类，而非 brain.py 里的一堆函数——
这样「多智能体」是名副其实的：每个角色有清晰的身份（name / role）、
自有工具/记忆接入点，并通过事件总线对外广播自己的行为。

基类只规定最小契约：持有模型引擎与事件总线，提供统一的 complete 辅助。
各角色 Agent 自行定义语义化的 act / observe 等方法。
"""
from __future__ import annotations

from abc import ABC
from typing import Optional

from ..core.engine import BaseEngine
from ..core.bus import EventBus, BUS


class Agent(ABC):
    """所有角色智能体的最小基类。

    name：人类可读角色名（用于事件 source 与日志）。
    role：模型调用时的角色标签（用于 Mock 引擎路由与真实引擎 system 区分）。
    """

    name: str = "agent"
    role: str = "assistant"

    def __init__(self, engine: BaseEngine, bus: Optional[EventBus] = None):
        self.engine = engine
        self.bus: EventBus = bus or BUS

    def complete(self, system: str, user: str, *, temperature: float | None = None,
                 scenario: Optional[str] = None, **kwargs) -> str:
        """统一的模型调用入口；model 调用细节全部下沉到 engine。"""
        return self.engine.complete(
            system, user, role=self.role, temperature=temperature,
            scenario=scenario, **kwargs,
        )
