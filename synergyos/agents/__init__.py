"""灵犀角色智能体集合（Agents）。

把协作链路中的每个角色实现为独立 Agent 类，让「多智能体」名副其实：
  · ArchitectAgent  左脑·架构师：拆解需求 -> 方案
  · ProgrammerAgent 左脑·程序员：方案 -> 代码（支持工具调用）
  · TesterAgent     左脑·测试员：代码 -> 测试用例
  · ObserverAgent   右脑·观察者：基于画像打分 + 偏好信号
  · Arbitrator      仲裁器：融合左右脑，决定交付/修订
以及共享的 artifacts（数据结构）与 tools（MCP 风格工具接口）。
"""
from __future__ import annotations

from .base import Agent
from .artifacts import LeftArtifacts, Observation
from .prompts import scenario_prompts
from .architect import ArchitectAgent
from .programmer import ProgrammerAgent
from .tester import TesterAgent
from .observer import ObserverAgent
from .arbitrator import Arbitrator
from .tools import Tool, ToolRegistry, ToolExecutor, make_builtin_tools

__all__ = [
    "Agent", "LeftArtifacts", "Observation", "scenario_prompts",
    "ArchitectAgent", "ProgrammerAgent", "TesterAgent",
    "ObserverAgent", "Arbitrator",
    "Tool", "ToolRegistry", "ToolExecutor", "make_builtin_tools",
]
