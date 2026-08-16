"""右脑·观察者智能体（Observer Agent）。

基于用户偏好画像对左脑交付物打分，并提炼偏好信号（命中 / 未命中）。
这是「双脑协作」里负责「让用户满意」的一侧，作为独立 Agent 类存在。
"""
from __future__ import annotations

import json

from .base import Agent
from .artifacts import Observation, LeftArtifacts
from ..core.bus import EventType
from ..core.profile import UserProfile


class ObserverAgent(Agent):
    name = "observer"
    role = "observer"

    SYS = ("你是灵犀右脑·观察者，基于用户偏好画像评估交付物。"
           "输出 JSON：satisfaction(0-1)/preference_hits/preference_misses/note。"
           "preference_hits 是命中用户偏好的维度名，preference_misses 是未命中的。")

    def observe(self, task: str, artifacts: LeftArtifacts,
                profile: UserProfile) -> Observation:
        prof = json.dumps(profile.to_dict(), ensure_ascii=False)
        user = (f"用户画像：{prof}\n\n任务：{task}\n\n"
                f"方案：{artifacts.plan}\n\n代码：{artifacts.code}")
        raw = self.complete(self.SYS, user)
        obs = self._parse(raw)
        self.bus.publish(EventType.RIGHT_OBSERVE, self.name,
                         f"右脑评分 满意度={obs.satisfaction:.2f} | {obs.note}",
                         satisfaction=obs.satisfaction)
        if obs.preference_hits:
            self.bus.publish(EventType.PREFERENCE, self.name,
                             f"偏好命中：{', '.join(obs.preference_hits)}",
                             hits=obs.preference_hits)
        if obs.preference_misses:
            self.bus.publish(EventType.PREFERENCE, self.name,
                             f"偏好未命中：{', '.join(obs.preference_misses)}",
                             misses=obs.preference_misses)
        return obs

    def _parse(self, raw: str) -> Observation:
        try:
            d = json.loads(raw)
            return Observation(
                satisfaction=float(d.get("satisfaction", 0.8)),
                preference_hits=list(d.get("preference_hits", [])),
                preference_misses=list(d.get("preference_misses", [])),
                note=str(d.get("note", "")),
                raw=raw,
            )
        except Exception:
            return Observation(satisfaction=0.8, note="(右脑返回未结构化，已保守评分)", raw=raw)
