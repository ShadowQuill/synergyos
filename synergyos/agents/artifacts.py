"""左脑交付物与右脑观察的共享数据结构。

集中放在 artifacts 模块，供 agents/ 各角色与 brain.py facade 共同引用，
避免 brain <-> agents 之间的循环导入。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class LeftArtifacts:
    """左脑一次执行产出的三类交付物（方案 / 代码 / 测试）。"""
    plan: str = ""
    code: str = ""
    tests: str = ""
    trace: List[str] = field(default_factory=list)


@dataclass
class Observation:
    """右脑对交付物的观察结论。"""
    satisfaction: float = 0.8
    preference_hits: List[str] = field(default_factory=list)
    preference_misses: List[str] = field(default_factory=list)
    note: str = ""
    raw: str = ""
