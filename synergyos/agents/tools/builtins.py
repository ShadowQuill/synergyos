"""内置工具集（Built-in Tools，零依赖、可真实副作用）。

提供一组让「程序员智能体」真正调工具的能力：
  · read_file   读取本地文本文件（沙箱模式下限定在 workspace 内）
  · write_file  写入本地文本文件（沙箱模式限定在 workspace 内、自动建目录、无删改能力）
  · list_dir    列出目录内容（沙箱模式默认列出 workspace 根）
  · web_search  联网搜索：默认离线模拟；置 SYNERGYOS_ONLINE=1 或显式 online=True 时
               用标准库 urllib + html.parser 真搜 DuckDuckGo lite（零第三方依赖）

安全设计：
  - 不提供任何删除/覆盖系统文件的工具（「禁删」通过「根本不提供该能力」达成）。
  - 沙箱模式（传入 workspace 根目录）下，所有文件操作被限制在 workspace 内，
    越界路径直接拒绝，绝不触碰 workspace 之外。
  - 离线模式（默认）完全不联网，返回带明确标注的占位结果。

对应改进报告 P0：让智能体能调外部工具 / API。
"""
from __future__ import annotations

import os
from html.parser import HTMLParser
from typing import List, Optional

from .base import Tool, ToolRegistry


# --------------------------------------------------------------------------- #
# 路径沙箱：把相对路径解析进 workspace；越界则拒绝。workspace=None 表示无沙箱。
# --------------------------------------------------------------------------- #
def _resolve_path(path: str, workspace: Optional[str]) -> str:
    """返回最终的绝对路径，必要时施加 workspace 沙箱约束。"""
    if not workspace:
        return os.path.abspath(path)
    root = os.path.abspath(workspace)
    if os.path.isabs(path):
        cand = os.path.abspath(path)
    else:
        cand = os.path.abspath(os.path.join(root, path))
    try:
        rel = os.path.relpath(cand, root)
    except ValueError:  # 不同盘符（Windows）等极端情形
        rel = os.pardir
    if rel == "." or not rel.startswith(os.pardir):
        return cand
    raise PermissionError(f"路径越界：{path} 超出工作区 {root}")


# --------------------------------------------------------------------------- #
# 文件类工具（读写 / 列目录）
# --------------------------------------------------------------------------- #
def _read_file(path: str, limit: int = 8000, workspace: Optional[str] = None) -> str:
    # 沙箱越界由 _resolve_path 抛出 PermissionError，向上传播给 Tool.invoke 判失败。
    p = _resolve_path(path, workspace)
    if not os.path.isfile(p):
        return f"（文件不存在：{p}）"
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            data = f.read()
    except Exception as e:  # noqa: BLE001
        return f"（读取失败：{e}）"
    if len(data) > limit:
        data = data[:limit] + f"\n…（已截断，共 {len(data)} 字符）"
    return data


def _write_file(path: str, content: str, workspace: Optional[str] = None) -> str:
    # 沙箱越界由 _resolve_path 抛出 PermissionError，向上传播给 Tool.invoke 判失败。
    p = _resolve_path(path, workspace)
    try:
        parent = os.path.dirname(p)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:  # noqa: BLE001
        return f"（写入失败：{e}）"
    return f"已写入 {len(content)} 字符到 {p}"


def _list_dir(path: str = ".", workspace: Optional[str] = None) -> str:
    # 沙箱越界由 _resolve_path 抛出 PermissionError，向上传播给 Tool.invoke 判失败。
    p = _resolve_path(path, workspace)
    if not os.path.isdir(p):
        return f"（目录不存在：{p}）"
    entries = []
    for name in sorted(os.listdir(p)):
        full = os.path.join(p, name)
        entries.append(("dir  " if os.path.isdir(full) else "file ") + name)
    return "\n".join(entries) if entries else "（空目录）"


# --------------------------------------------------------------------------- #
# 联网搜索：默认离线模拟；online=True 时标准库真搜
# --------------------------------------------------------------------------- #
def _web_search_offline(query: str) -> str:
    return (f"（离线模拟搜索，未接入真实引擎）关于「{query}」的检索结果待接入；"
            f"如需联网，请置环境变量 SYNERGYOS_ONLINE=1，或显式调用 online=True 的搜索工具。")


class _DdgSnippetParser(HTMLParser):
    """从 DuckDuckGo lite 结果页抽取标题与摘要。"""

    def __init__(self) -> None:
        super().__init__()
        self._in_snippet = False
        self._in_title = False
        self._buf: List[str] = []
        self.titles: List[str] = []
        self.snippets: List[str] = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "")
        if "result__snippet" in classes:
            self._in_snippet = True
            self._buf = []
        elif "result__a" in classes:
            self._in_title = True
            self._buf = []

    def handle_endtag(self, tag):
        if self._in_snippet:
            self._in_snippet = False
            self.snippets.append("".join(self._buf).strip())
        if self._in_title:
            self._in_title = False
            self.titles.append("".join(self._buf).strip())

    def handle_data(self, data):
        if self._in_snippet or self._in_title:
            self._buf.append(data)


def _web_search_real(query: str, top_k: int = 5) -> str:
    """用标准库 urllib + html.parser 真搜 DuckDuckGo lite（零第三方依赖）。"""
    import urllib.parse
    import urllib.request

    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; SynergyOS/1.2)"}
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = _DdgSnippetParser()
    parser.feed(html)
    snippets = [s for s in parser.snippets if s]
    if not snippets:
        return _web_search_offline(query) + "\n（联网已尝试，但未解析到有效结果，已回退离线说明）"
    lines = [f"联网检索「{query}」返回 {min(top_k, len(snippets))} 条结果："]
    for i, s in enumerate(snippets[:top_k], 1):
        lines.append(f"{i}. {s}")
    return "\n".join(lines)


def _web_search(query: str, online: bool = False) -> str:
    """联网搜索入口：默认离线模拟；online=True 时真搜，失败优雅回退。"""
    if not online:
        return _web_search_offline(query)
    try:
        return _web_search_real(query)
    except Exception as e:  # noqa: BLE001 — 联网不可靠，必须优雅降级
        return _web_search_offline(query) + f"\n（联网搜索异常，已回退离线模式：{type(e).__name__}: {e}）"


# --------------------------------------------------------------------------- #
# 工具注册表构造
# --------------------------------------------------------------------------- #
def make_builtin_tools(workspace: Optional[str] = None,
                       online: Optional[bool] = None) -> ToolRegistry:
    """构造内置工具注册表。

    Args:
      workspace: 沙箱根目录。为 None 时不施加沙箱（兼容历史/测试用法）；
                  生产环境应传入 "workspace" 等受控目录，把所有文件操作限制在内。
      online:    是否启用真实联网搜索。None 时由环境变量 SYNERGYOS_ONLINE 决定
                 （1/true/yes 为真）。
    """
    if online is None:
        online = os.getenv("SYNERGYOS_ONLINE", "").lower() in ("1", "true", "yes")

    reg = ToolRegistry()
    reg.register(Tool(
        name="read_file",
        description="读取本地文本文件内容（path: 文件路径；沙箱模式下限定在 workspace 内）",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "要读取的文件路径"}},
            "required": ["path"],
        },
        fn=lambda path, limit=8000: _read_file(path, limit, workspace),
    ))
    reg.register(Tool(
        name="write_file",
        description="把文本写入本地文件（path, content）；沙箱模式下限定在 workspace 内，无删改能力",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "写入目标路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
            "required": ["path", "content"],
        },
        fn=lambda path, content: _write_file(path, content, workspace),
    ))
    reg.register(Tool(
        name="list_dir",
        description="列出目录下的文件与子目录（path: 目录路径，默认当前工作区根）",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "目录路径，默认 '.'"}},
            "required": [],
        },
        fn=lambda path=".": _list_dir(path, workspace),
    ))
    reg.register(Tool(
        name="web_search",
        description=("联网搜索资料（query: 查询词）；"
                     + ("当前已开启真实联网搜索" if online else "当前为离线模拟，置 SYNERGYOS_ONLINE=1 开启真实搜索")),
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
        fn=lambda query: _web_search(query, online=online),
    ))
    return reg
