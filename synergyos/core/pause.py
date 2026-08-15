"""智能节律控制（Smart Pause Control）。

内置"认知停时（Pause Horizon）"预测：在长耗时任务中预估最佳暂停节点，
也能随时响应用户暂停指令，优雅保存状态并生成阶段性简报。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .bus import BUS, EventType


@dataclass
class PauseHorizon:
    """一个预测的停时点。"""
    at_progress: float          # 0..1 进度阈值
    reason: str                 # 为何在此暂停最好
    reached: bool = False


class PauseController:
    def __init__(self):
        self.horizons: List[PauseHorizon] = []
        self.paused: bool = False
        self.pause_requested: bool = False
        self.snapshot: Optional[dict] = None
        self._progress: float = 0.0
        self._progress_getter: Optional[Callable[[], float]] = None

    def set_progress_source(self, getter: Callable[[], float]) -> None:
        self._progress_getter = getter

    def predict_horizons(self, stages: List[str]) -> None:
        """根据阶段列表预测若干停时点（每阶段结尾）。"""
        n = len(stages)
        for i, s in enumerate(stages):
            p = (i + 1) / n
            reason = f"完成阶段『{s}』，适合检查中间结果"
            h = PauseHorizon(at_progress=p, reason=reason)
            self.horizons.append(h)
        BUS.publish(EventType.PAUSE_HORIZON, "pause",
                    f"预测到 {len(self.horizons)} 个最佳停时点", stages=stages)

    def _current_progress(self) -> float:
        if self._progress_getter:
            self._progress = self._progress_getter()
        return self._progress

    def set_progress(self, p: float) -> None:
        self._progress = max(0.0, min(1.0, p))

    def request_pause(self) -> None:
        """用户主动请求暂停。"""
        self.pause_requested = True
        BUS.publish(EventType.PAUSE, "pause", "用户请求暂停，准备优雅保存状态")

    def tick(self, stage_name: str = "") -> bool:
        """每个协作步骤调用一次：返回 True 表示应在此暂停。"""
        if self.pause_requested and not self.paused:
            self._do_pause(stage_name)
            return True
        p = self._current_progress()
        for h in self.horizons:
            if not h.reached and p >= h.at_progress:
                h.reached = True
                BUS.publish(EventType.PAUSE_HORIZON, "pause",
                            f"到达停时点({h.at_progress:.0%})：{h.reason}")
                # 仅预测与提示，不强制中断；除非用户已请求暂停
        return self.paused

    def _do_pause(self, stage_name: str) -> None:
        self.paused = True
        self.snapshot = {"stage": stage_name, "progress": self._current_progress(),
                         "at": time.time()}
        briefing = self.stage_briefing()
        BUS.publish(EventType.PAUSE, "pause",
                    f"已暂停于阶段『{stage_name}』，状态已保存", briefing=briefing)

    def stage_briefing(self) -> str:
        p = self._current_progress()
        done = sum(1 for h in self.horizons if h.reached)
        return (f"阶段简报：进度 {p:.0%}，已观测 {done}/{len(self.horizons)} 个停时点。"
                f"恢复后可从快照继续。")

    def resume(self) -> None:
        self.paused = False
        self.pause_requested = False
        BUS.publish(EventType.RESUME, "pause", "已恢复，从快照继续")

    @property
    def is_paused(self) -> bool:
        return self.paused
