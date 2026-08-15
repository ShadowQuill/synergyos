"""冷启动偏好锚定（Cold-start Profiling）。

初次任务启动时进行 3-5 题最小化探测，快速建立初始画像；
此后通过 `learn()` 在后台静默更新偏好库，实现免打扰的"一次提问，终身受用"。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from .bus import BUS, EventType

# 最小化探测题（3-5 题即可锚定画像）
COLD_START_QUESTIONS: List[Dict] = [
    {
        "id": "communication_style",
        "q": "你更希望我以什么方式与你沟通？",
        "options": ["简洁直接，少废话", "有结构、分点说明", "细致周到、带背景解释", "轻松随意"],
    },
    {
        "id": "detail_level",
        "q": "产出内容通常要多详细？",
        "options": ["只要结论与关键代码", "结论 + 必要步骤", "完整可复现的过程", "越长越好，含取舍讨论"],
    },
    {
        "id": "aesthetic",
        "q": "图表/界面的审美偏好？",
        "options": ["极简冷淡风", "科技蓝数据风", "温暖柔和", "高对比度醒目"],
    },
    {
        "id": "risk_tolerance",
        "q": "面对不确定时的取值倾向？",
        "options": ["稳健优先，宁可保守", "平衡", "激进尝试新方案"],
    },
    {
        "id": "collaboration",
        "q": "希望我多主动吗？",
        "options": ["我只下指令，你执行", "关键节点给建议", "全程主动共生，帮我预判"],
    },
]


@dataclass
class UserProfile:
    communication_style: str = "有结构、分点说明"
    detail_level: str = "结论 + 必要步骤"
    aesthetic: str = "科技蓝数据风"
    risk_tolerance: str = "平衡"
    collaboration: str = "关键节点给建议"
    # 偏好强度（置信度），接受反馈后逐步逼近 1.0
    confidence: Dict[str, float] = field(default_factory=lambda: {k: 0.5 for k in [
        "communication_style", "detail_level", "aesthetic",
        "risk_tolerance", "collaboration"]})
    learned_signals: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def snapshot(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def learn(self, key: str, value: str, weight: float = 0.15) -> None:
        """后台静默学习：用指数滑动平均更新偏好与置信度。"""
        if not hasattr(self, key):
            return
        setattr(self, key, value)
        cur = self.confidence.get(key, 0.5)
        self.confidence[key] = min(1.0, cur + weight)
        self.learned_signals += 1


class Profiler:
    def __init__(self, profile: Optional[UserProfile] = None, path: Optional[str] = None):
        """path 指定画像落盘位置；传 None 则仅内存、不持久化。"""
        self.path = path
        self.loaded = False
        loaded_profile = self._try_load() if path else None
        self.profile = profile or loaded_profile or UserProfile()
        self.loaded = loaded_profile is not None

    def _try_load(self) -> Optional[UserProfile]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            fields = UserProfile.__dataclass_fields__
            kw = {k: v for k, v in data.items() if k in fields}
            return UserProfile(**kw)
        except Exception:
            return None

    def save(self) -> None:
        """将当前画像写入磁盘（path 为 None 时跳过）。"""
        if not self.path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.profile.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    @property
    def is_cold(self) -> bool:
        """冷启动：尚未加载历史画像，且无累积信号。"""
        return (not self.loaded) and self.profile.learned_signals == 0

    def cold_start_questions(self) -> List[Dict]:
        return COLD_START_QUESTIONS

    def run_cold_start(self, answers: Dict[str, int]) -> UserProfile:
        """根据选择题答案（题号 -> 选项下标）锚定初始画像。"""
        for item in COLD_START_QUESTIONS:
            idx = answers.get(item["id"])
            if idx is None:
                continue
            opt = item["options"][idx] if 0 <= idx < len(item["options"]) else item["options"][0]
            self.profile.learn(item["id"], opt, weight=0.25)
            BUS.publish(EventType.PROFILE_UPDATE, "profiler",
                        f"锚定偏好 {item['id']} = {opt}", key=item["id"], value=opt)
        return self.profile

    def learn_from_feedback(self, preference_signals: Dict[str, str],
                            misses: Optional[List[str]] = None) -> None:
        """右脑反馈驱动的后台静默学习。"""
        for k, v in preference_signals.items():
            self.profile.learn(k, v)
        if misses:
            for k in misses:
                # 偏好未命中 -> 降低该维度置信度，促使后续再探测
                self.profile.confidence[k] = max(0.2, self.profile.confidence.get(k, 0.5) - 0.1)
        BUS.publish(EventType.PROFILE_UPDATE, "profiler",
                    f"静默学习 {len(preference_signals)} 条偏好信号", signals=preference_signals)
