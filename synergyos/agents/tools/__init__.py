"""工具接口包（MCP 风格、零依赖）。

对外导出：
  Tool / ToolRegistry / ToolExecutor —— 工具抽象与执行器
  make_builtin_tools          —— 内置示例工具（读写文件 / 列目录 / 搜索）
"""
from __future__ import annotations

from .base import Tool, ToolRegistry, ToolExecutor
from .builtins import make_builtin_tools

__all__ = ["Tool", "ToolRegistry", "ToolExecutor", "make_builtin_tools"]
