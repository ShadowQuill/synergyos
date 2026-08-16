"""双脑协作（Dual-Brain Collaboration）· 兼容门面。

说明（重构于 P0 改进）：原本写在 brain.py 里的 architect / programmer / tester /
observer / arbitrate 逻辑，已下沉为 `synergyos/agents/` 目录下各自独立的 Agent 类
（ArchitectAgent / ProgrammerAgent / TesterAgent / ObserverAgent / Arbitrator）。
本模块保留对外的同名导出（LeftBrain / RightBrain / arbitrate / _scenario_prompts /
LeftArtifacts / Observation），作为双脑协作的【编排门面】，保证既有 import 与测试
不受影响。新增的「多智能体」结构详见 `synergyos/agents/`。

  · 左脑（执行者）：architect -> programmer -> tester，专注"如何把事做对"。
  · 右脑（观察者）：observer，基于用户画像构建偏好信号、评分满意度。
  · 仲裁：融合左右脑，必要时令左脑修订。
"""
from __future__ import annotations

from typing import Optional

# 从 agents 承接真正的角色实现
from ..agents import (
    LeftArtifacts, Observation,
    ArchitectAgent, ProgrammerAgent, TesterAgent,
    ObserverAgent, Arbitrator, scenario_prompts,
)
from .engine import ENGINE, BaseEngine
from .bus import BUS, EventType
from .profile import UserProfile

# 兼容旧引用：测试从 brain 导入 _scenario_prompts
_scenario_prompts = scenario_prompts


# ---------------- 左脑：执行者（编排门面） ----------------

class LeftBrain:
    """执行链路门面：组合 architect / programmer / tester 三个独立 Agent。"""

    def __init__(self, engine: BaseEngine = ENGINE, bus=BUS, tools=None):
        self.engine = engine
        self.bus = bus
        self.tools = tools
        self.architect = ArchitectAgent(engine, bus=bus)
        self.programmer = ProgrammerAgent(engine, bus=bus)
        self.tester = TesterAgent(engine, bus=bus)

    def execute(self, task: str, profile: UserProfile,
                style_hint: str = "", scenario: Optional[str] = None,
                memory_hint: str = "", experience: str = "") -> LeftArtifacts:
        a = LeftArtifacts()
        a.plan = self.architect.act(task, profile, style_hint, scenario,
                                    memory_hint=memory_hint, experience=experience)
        a.trace.append("architect: 产出实施方案")
        if self.tools:
            a.code = self.programmer.act_with_tools(
                task, a.plan, profile, style_hint, scenario, tools=self.tools,
                experience=experience)
        else:
            a.code = self.programmer.act(
                task, a.plan, profile, style_hint, scenario, experience=experience)
        a.trace.append("programmer: 产出实现代码")
        a.tests = self.tester.act(
            task, a.code, profile, style_hint, scenario, experience=experience)
        a.trace.append("tester: 产出测试用例")
        return a


# ---------------- 右脑：观察者（编排门面） ----------------

class RightBrain:
    """观察者门面：包裹 ObserverAgent。"""

    def __init__(self, engine: BaseEngine = ENGINE, bus=BUS):
        self.engine = engine
        self.bus = bus
        self.observer = ObserverAgent(engine, bus=bus)

    def observe(self, task: str, artifacts: LeftArtifacts,
                profile: UserProfile) -> Observation:
        return self.observer.observe(task, artifacts, profile)


# ---------------- 仲裁（编排门面） ----------------

def arbitrate(artifacts: LeftArtifacts, obs: Observation) -> dict:
    """融合左脑产出与右脑观察，给出是否修订及原因。"""
    return Arbitrator(bus=BUS).decide(artifacts, obs)
