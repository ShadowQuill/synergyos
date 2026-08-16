"""模型引擎抽象层。

默认使用 MockEngine，无需任何 API Key 即可跑通全链路；当检测到
对应的 API Key 时，自动切换到真实大模型。灵犀采用 **OpenAI 兼容协议**，
因此 DeepSeek / 通义千问(qwen) / 智谱 GLM / OpenAI 均可直接接入——
契合报告「国产模型自主可控」的叙事。

环境变量（也可放在项目根 / 运行目录的 .env）：
  · DEEPSEEK_API_KEY    → deepseek-chat   (https://api.deepseek.com)
  · DASHSCOPE_API_KEY   → qwen-plus       (阿里云百炼兼容端点)
  · ZHIPU_API_KEY       → glm-4-plus      (智谱开放平台)
  · OPENAI_API_KEY      → gpt-4o-mini     (OpenAI)
  · SYNERGYOS_FORCE_MOCK=1  → 强制 Mock（CI / 单测零 token）
  · SYNERGYOS_PROVIDER=<deepseek|qwen|glm|openai>  → 显式指定引擎
  · SYNERGYOS_BASE_URL / SYNERGYOS_MODEL  → 覆盖端点与模型名（任意 provider）
    另：provider=openai 时也尊重 OPENAI_BASE_URL / OPENAI_MODEL，
    因此把国产模型配在 OPENAI_* 变量里（兼容协议常见做法）同样可用。

调用方代码无需任何改动：build_engine() 自动择优选型。
"""
from __future__ import annotations

import os
import json
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from .scenarios import mock_architect, mock_programmer, mock_tester


# ---- 多国产引擎预设（均走 OpenAI 兼容协议）----
PROVIDERS: Dict[str, Dict[str, str]] = {
    "deepseek": {"model": "deepseek-chat",
                 "base_url": "https://api.deepseek.com"},
    "qwen":     {"model": "qwen-plus",
                 "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"},
    "glm":      {"model": "glm-4-plus",
                 "base_url": "https://open.bigmodel.cn/api/paas/v4"},
    "openai":   {"model": "gpt-4o-mini",
                 "base_url": "https://api.openai.com/v1"},
}
# 各引擎对应的 API Key 环境变量名
PROVIDER_ENV: Dict[str, str] = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen":     "DASHSCOPE_API_KEY",
    "glm":      "ZHIPU_API_KEY",
    "openai":   "OPENAI_API_KEY",
}


def _load_dotenv() -> None:
    """零依赖读取 .env（DEEPSEEK_API_KEY / DASHSCOPE_API_KEY / ZHIPU_API_KEY /
    OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 等）。

    仅在不覆盖已有环境变量的前提下写入 os.environ；优先顺序：
    ① 已 export 的环境变量 ② 运行目录 .env ③ 项目根目录 .env。
    """
    candidates = [Path.cwd() / ".env",
                  Path(__file__).resolve().parents[2] / ".env"]
    for p in candidates:
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                os.environ.setdefault(k, v)
            break


@dataclass
class EngineConfig:
    provider: str = "mock"            # mock | openai
    model: str = "mock-1"
    base_url: str = "https://api.openai.com/v1"
    api_key: Optional[str] = None
    temperature: float = 0.7
    # 真实模型下每个角色(架构/编码/测试/观察/反思)都是独立调用，
    # 代码与用例较长，默认给足 4096 避免被截断（DeepSeek 支持 8k 输出）。
    max_tokens: int = 4096


class BaseEngine(ABC):
    """所有模型引擎的统一接口。"""

    @abstractmethod
    def complete(self, system: str, user: str, *, role: str = "assistant",
                 temperature: float | None = None, scenario: Optional[str] = None,
                 **kwargs) -> str:
        """给定系统提示与用户提示，返回文本。role 用于 mock 路由，scenario 用于场景化。"""

    def is_real(self) -> bool:
        return False


class MockEngine(BaseEngine):
    """离线规则引擎。

    依据 role / system 中的关键词，生成贴合场景的演示内容，
    让整个多智能体链路在没有真实模型时也能完整跑通。
    """

    def is_real(self) -> bool:
        return False

    def complete(self, system: str, user: str, *, role: str = "assistant",
                 temperature: float | None = None, scenario: Optional[str] = None,
                 **kwargs) -> str:
        # 工具调用演示（仅当调用方显式 allow_tools 且为程序员角色）：
        # 离线 Mock 返回一个 web_search 工具调用，供 ToolExecutor 走通
        # 「智能体调工具」闭环；不影响任何默认（不带 allow_tools）的路由。
        if kwargs.get("allow_tools") and role == "programmer":
            q = _extract_task(user)
            return ('<tool_call>{"name": "web_search", "arguments": {"query": '
                    + json.dumps(q, ensure_ascii=False) + '}}</tool_call>')
        # 场景化：左脑三类角色按场景生成贴合领域的内容（role 优先）
        if scenario:
            if role == "architect":
                return mock_architect(scenario, _extract_task(user))
            if role == "programmer":
                return mock_programmer(scenario, _extract_task(user))
            if role == "tester":
                return mock_tester(scenario, _extract_task(user))
            # observer / reflexion 与场景无关，落到下方按 role 路由
        # 按 role 权威路由（避免 prompt 含「代码」等词误判右脑）
        if role == "observer":
            return self._observer(system, user)
        if role == "reflexion":
            return self._reflexion(system, user)
        router = (role + " " + system + " " + user).lower()
        if "architect" in router or "拆解" in router or "需求" in router:
            return self._architect(system, user)
        if "programmer" in router or "编码" in router or "代码" in router or "实现" in router:
            return self._programmer(system, user)
        if "tester" in router or "测试" in router or "用例" in router:
            return self._tester(system, user)
        if "observer" in router or "观察" in router or "偏好" in router or "满意" in router:
            return self._observer(system, user)
        if "reflex" in router or "反思" in router or "复盘" in router:
            return self._reflexion(system, user)
        return self._generic(system, user)

    # ---- 各角色规则内容 ----

    def _architect(self, system, user):
        task = _extract_task(user)
        plan = {
            "task": task,
            "steps": [
                "明确输入输出契约与边界条件",
                "选择数据结构与核心算法",
                "编写实现并处理异常分支",
                "补充单元测试与示例",
            ],
            "acceptance": "函数对典型与边界输入均返回正确结果，且有测试覆盖。",
            "style_hint": "遵循用户代码风格库（命名/注释/缩进）。",
        }
        return json.dumps(plan, ensure_ascii=False, indent=2)

    def _programmer(self, system, user):
        task = _clean_task(_extract_task(user))
        fn = _fn_name(task)
        code = (
            f"def {fn}(n):\n"
            f"    \"\"\"{task} 返回第 n 项（n>=0）。\"\"\"\n"
            f"    if not isinstance(n, int) or n < 0:\n"
            f"        raise ValueError(\"n 必须为非负整数\")\n"
            f"    a, b = 0, 1\n"
            f"    for _ in range(n):\n"
            f"        a, b = b, a + b\n"
            f"    return a\n"
        )
        return code

    def _tester(self, system, user):
        fn = _fn_name(_extract_task(user))
        cases = [
            {"case": f"{fn}(0)", "expect": 0},
            {"case": f"{fn}(1)", "expect": 1},
            {"case": f"{fn}(10)", "expect": 55},
            {"case": f"{fn}(-1)", "expect": "raises ValueError"},
        ]
        return json.dumps({"cases": cases}, ensure_ascii=False, indent=2)

    def _observer(self, system, user):
        # 右脑：基于用户画像对交付物打分与偏好信号
        signal = {
            "satisfaction": round(random.uniform(0.72, 0.95), 2),
            "preference_hits": ["detail_level", "communication_style"],
            "preference_misses": [],
            "note": "交付物符合用户偏好画像，建议保持当前策略权重。",
        }
        return json.dumps(signal, ensure_ascii=False, indent=2)

    def _reflexion(self, system, user):
        verdict = {
            "verdict": "pass",
            "error_type": None,
            "root_cause": None,
            "weight_delta": {},
            "retry": False,
        }
        return json.dumps(verdict, ensure_ascii=False, indent=2)

    def _generic(self, system, user):
        return f"[mock] 已收到指令：{user[:60]}…（离线引擎占位回复）"


class OpenAIEngine(BaseEngine):
    """OpenAI 兼容真实引擎，按需懒加载 openai 库。"""

    def __init__(self, cfg: EngineConfig):
        self.cfg = cfg

    def is_real(self) -> bool:
        return True

    def complete(self, system: str, user: str, *, role: str = "assistant",
                 temperature: float | None = None, **kwargs) -> str:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "未安装 openai 库，请执行 `pip install openai`，或移除 API Key 使用 Mock 引擎。"
            ) from e
        client = OpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url)
        resp = client.chat.completions.create(
            model=self.cfg.model,
            temperature=temperature if temperature is not None else self.cfg.temperature,
            max_tokens=self.cfg.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""


def _extract_task(user: str) -> str:
    # 优先识别显式注入的「用户任务:」标记
    for line in user.splitlines():
        if line.strip().startswith("用户任务:"):
            return _clean(line.split(":", 1)[-1])
    for line in user.splitlines():
        low = line.lower()
        if ("任务" in line or "task" in low) and '"' not in line[:line.find("任务") if "任务" in line else line.find("task")]:
            for sep in ["：", ":", "->", "→"]:
                if sep in line:
                    return _clean(line.split(sep, 1)[-1])
    # 退而求其次：取首个看起来像任务的短句
    for line in user.splitlines():
        if "任务" in line or "task" in line.lower():
            for sep in ["：", ":", "->", "→"]:
                if sep in line:
                    return _clean(line.split(sep, 1)[-1])
    return _clean(user.strip().split("\n")[0][:80])


def _clean(s: str) -> str:
    return s.strip().strip('"').strip(",").strip('"').strip()


def _fn_name(task: str) -> str:
    low = task.lower()
    if any(w in low for w in ["斐波那契", "fibonacci", "fib"]):
        return "fibonacci"
    if any(w in low for w in ["去重", "dedup", "unique"]):
        return "dedup"
    if any(w in low for w in ["排序", "sort"]):
        return "sort_arr"
    return "solve"


def _clean_task(task: str) -> str:
    for sep in ["任务：", "任务:", "task:", "task："]:
        if task.startswith(sep):
            return task[len(sep):].strip()
    return task.strip()


def create_engine(provider: str, *, api_key: Optional[str] = None,
                  model: Optional[str] = None,
                  base_url: Optional[str] = None) -> BaseEngine:
    """按预设构造一个 OpenAI 兼容的真实引擎。

    provider ∈ {deepseek, qwen, glm, openai}。api_key / model / base_url 缺省时
    取预设默认值（model/base_url）与对应环境变量（api_key）。
    """
    preset = PROVIDERS.get(provider)
    if preset is None:
        raise ValueError(f"未知引擎 provider：{provider}，可选 {list(PROVIDERS)}")
    api_key = api_key or os.getenv(PROVIDER_ENV[provider])
    if not api_key:
        raise RuntimeError(
            f"未检测到 {PROVIDER_ENV[provider]}；请配置该环境变量，"
            f"或移除以使用 Mock 引擎。")
    # 端点/模型可被环境变量覆盖：
    #   · 通用：SYNERGYOS_BASE_URL / SYNERGYOS_MODEL（对任意 provider 生效）
    #   · openai：额外尊重 OPENAI_BASE_URL / OPENAI_MODEL —— OpenAI 兼容生态的
    #     通行约定，很多用户把国产模型（如 DeepSeek）直接配在 OPENAI_* 变量里，
    #     若忽略这两个变量就会拿着别家的 Key 去打 api.openai.com。
    env_base = os.getenv("SYNERGYOS_BASE_URL")
    env_model = os.getenv("SYNERGYOS_MODEL")
    if provider == "openai":
        env_base = env_base or os.getenv("OPENAI_BASE_URL")
        env_model = env_model or os.getenv("OPENAI_MODEL")
    return OpenAIEngine(EngineConfig(
        provider=provider,
        model=model or env_model or preset["model"],
        base_url=base_url or env_base or preset["base_url"],
        api_key=api_key,
    ))


def available_provider() -> Optional[str]:
    """返回当前环境中已配置 Key 的第一个可用引擎（优先 deepseek）。"""
    _load_dotenv()
    for p in ("deepseek", "qwen", "glm", "openai"):
        if os.getenv(PROVIDER_ENV[p]):
            return p
    return None


def build_engine(provider: Optional[str] = None) -> BaseEngine:
    """按环境变量自动选择引擎。

    优先级：① SYNERGYOS_FORCE_MOCK 强制 Mock；② 显式 SYNERGYOS_PROVIDER；
    ③ 已配置 Key 的引擎（优先 deepseek，贴「国产自主可控」叙事）；
    ④ 都没有则 Mock。
    """
    _load_dotenv()
    # 测试/CI 可通过此开关强制走 Mock，避免误打真实 API（零 token）。
    if os.getenv("SYNERGYOS_FORCE_MOCK"):
        return MockEngine()
    provider = provider or os.getenv("SYNERGYOS_PROVIDER") or available_provider()
    if provider:
        try:
            return create_engine(provider)
        except RuntimeError:
            # Key 缺失等：优雅降级到 Mock，保证链路仍可跑
            return MockEngine()
    return MockEngine()


# 便捷单例
ENGINE: BaseEngine = build_engine()
