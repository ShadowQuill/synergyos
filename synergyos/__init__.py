"""灵犀 · 自进化协作智能体（SynergyOS）

以用户为中心的多角色 AI 智能体网络：双脑协作 + 冷启动偏好锚定 +
自适应生长与修复 + 智能节律控制。
"""
from .core.engine import ENGINE, BaseEngine, MockEngine, OpenAIEngine, build_engine
from .core.bus import BUS, EventBus, EventType, Event
from .core.profile import (
    Profiler, UserProfile, COLD_START_QUESTIONS,
)
from .core.brain import LeftBrain, RightBrain, arbitrate, LeftArtifacts, Observation
from .core.reflexion import ReflexionLoop, ReflexionResult
from .core.pause import PauseController, PauseHorizon
from .core.orchestrator import SynergyOS

__version__ = "0.1.0"
__all__ = [
    "ENGINE", "BaseEngine", "MockEngine", "OpenAIEngine", "build_engine",
    "BUS", "EventBus", "EventType", "Event",
    "Profiler", "UserProfile", "COLD_START_QUESTIONS",
    "LeftBrain", "RightBrain", "arbitrate", "LeftArtifacts", "Observation",
    "ReflexionLoop", "ReflexionResult",
    "PauseController", "PauseHorizon",
    "SynergyOS",
]
