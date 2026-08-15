"""自适应生长与修复（Adaptive Growth & Healing）。

反思性迭代（Reflexion）：当交付偏离预期，自动回溯协作链，
区分"逻辑错误"还是"偏好误判"，动态调整智能体权重，实现无人工干预的软修复。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .engine import ENGINE, BaseEngine
from .bus import BUS, EventType


@dataclass
class ReflexionResult:
    verdict: str = "pass"          # pass | logic_error | preference_error
    error_type: Optional[str] = None
    root_cause: str = ""
    weight_delta: Dict[str, float] = field(default_factory=dict)
    retry: bool = False
    note: str = ""


class ReflexionLoop:
    def __init__(self, engine: BaseEngine = ENGINE, max_rounds: int = 3):
        self.engine = engine
        self.max_rounds = max_rounds
        # 各左脑智能体权重（软修复时动态调整）
        self.weights: Dict[str, float] = {
            "architect": 1.0, "programmer": 1.0, "tester": 1.0,
            "observer": 1.0,
        }

    def evaluate(self, task: str, artifacts_trace: List[str],
                 observation) -> ReflexionResult:
        """复盘一次交付：判断是否通过，若失败归类错误来源。"""
        sys_r = ("你是灵犀的反思器。结合右脑观察与左脑执行轨迹，判断交付是否达标。"
                 "输出 JSON：verdict(pass|logic_error|preference_error)/"
                 "error_type/root_cause/retry(boolean)/note。"
                 "logic_error=左脑逻辑或实现问题；preference_error=右脑判定偏好未命中。")
        user = (f"任务：{task}\n左脑轨迹：{artifacts_trace}\n"
                f"右脑观察：满意度={observation.satisfaction:.2f}，"
                f"偏好未命中={observation.preference_misses}")
        raw = self.engine.complete(sys_r, user, role="reflexion")
        return self._parse(raw, observation)

    def _parse(self, raw: str, observation) -> ReflexionResult:
        try:
            d = json.loads(raw)
            verdict = d.get("verdict", "pass")
            error_type = d.get("error_type")
            # 若右脑有偏好未命中但反思器没说，则归因为偏好误判
            if verdict == "pass" and observation.preference_misses:
                verdict = "preference_error"
                error_type = "preference"
            res = ReflexionResult(
                verdict=verdict,
                error_type=error_type,
                root_cause=str(d.get("root_cause", "")),
                retry=bool(d.get("retry", False)) or verdict != "pass",
                note=str(d.get("note", "")),
            )
        except Exception:
            # 解析失败：以右脑为准
            if observation.preference_misses:
                res = ReflexionResult(verdict="preference_error", error_type="preference",
                                      root_cause="右脑报告偏好未命中", retry=True,
                                      note="(反思器未结构化，按右脑信号处理)")
            else:
                res = ReflexionResult(verdict="pass", retry=False, note="(反思器未结构化，保守通过)")
        BUS.publish(EventType.REFLEXION, "reflexion",
                    f"复盘结论：{res.verdict} | {res.note}", verdict=res.verdict)
        return res

    def heal(self, result: ReflexionResult) -> Dict[str, float]:
        """软修复：依据错误来源调整权重（无人工干预）。"""
        delta: Dict[str, float] = {}
        if result.verdict == "logic_error":
            # 逻辑错 -> 强化测试与编码权重，降架构
            delta = {"tester": +0.1, "programmer": +0.05, "architect": -0.05}
        elif result.verdict == "preference_error":
            # 偏好误判 -> 强化右脑观察权重
            delta = {"observer": +0.15, "architect": +0.05}
        for k, dv in delta.items():
            self.weights[k] = round(max(0.3, min(2.0, self.weights.get(k, 1.0) + dv)), 2)
        if delta:
            BUS.publish(EventType.WEIGHT, "reflexion",
                        f"软修复调权：{delta}", weights=dict(self.weights))
        return dict(self.weights)
