"""消息总线：让双脑协作、反思、暂停等事件可被观测与订阅。

CLI 与演示网页都通过订阅总线来渲染实时协作过程。
"""
from __future__ import annotations

import time
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List


class EventType(str, Enum):
    COLD_START = "cold_start"
    PROFILE_UPDATE = "profile_update"
    LEFT_STEP = "left_step"          # 左脑某智能体产出
    RIGHT_OBSERVE = "right_observe"  # 右脑观察/评分
    PREFERENCE = "preference"        # 偏好信号
    ARBITRATE = "arbitrate"          # 双脑仲裁
    PAUSE_HORIZON = "pause_horizon"  # 预测到停时
    PAUSE = "pause"                  # 实际暂停
    RESUME = "resume"
    REFLEXION = "reflexion"          # 反思复盘
    WEIGHT = "weight"                # 权重调整
    DELIVER = "deliver"              # 最终交付
    INFO = "info"


@dataclass
class Event:
    type: EventType
    source: str                      # 事件来源（agent / module）
    message: str
    data: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class EventBus:
    def __init__(self):
        self._subs: List[Callable[[Event], None]] = []
        self._log: List[Event] = []

    def subscribe(self, cb: Callable[[Event], None]) -> None:
        self._subs.append(cb)

    def publish(self, etype: EventType, source: str, message: str, **data) -> Event:
        ev = Event(type=etype, source=source, message=message, data=data)
        self._log.append(ev)
        for cb in self._subs:
            cb(ev)
        return ev

    def history(self) -> List[Event]:
        return list(self._log)

    def to_json(self) -> str:
        return json.dumps(
            [{"type": e.type.value, "source": e.source, "message": e.message, "data": e.data, "ts": e.ts}
             for e in self._log],
            ensure_ascii=False, indent=2,
        )


# 全局默认总线
BUS = EventBus()
