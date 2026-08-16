"""仲裁器（Arbitrator）。

将左脑产出与右脑观察融合，给出是否修订及原因。作为独立组件，
与四个角色 Agent 并列，构成灵犀的「分工 - 协作 - 仲裁」骨架。
"""
from __future__ import annotations

from .artifacts import LeftArtifacts, Observation
from ..core.bus import BUS, EventType


class Arbitrator:
    """融合左脑产出与右脑观察，决定交付还是修订。"""

    def __init__(self, bus=BUS):
        self.bus = bus

    def decide(self, artifacts: LeftArtifacts, obs: Observation) -> dict:
        should_revise = obs.satisfaction < 0.75 or bool(obs.preference_misses)
        reason = ("满意度足够且无偏好误判，直接交付。" if not should_revise
                  else ("满意度偏低，需左脑修订。" if obs.satisfaction < 0.75
                        else "存在偏好误判，需按画像修订。"))
        self.bus.publish(EventType.ARBITRATE, "arbitrator",
                         f"仲裁：{'修订' if should_revise else '通过'} —— {reason}")
        return {"should_revise": should_revise, "reason": reason}
