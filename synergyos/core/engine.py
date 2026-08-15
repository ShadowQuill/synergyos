"""模型引擎抽象层。

默认使用 MockEngine，无需任何 API Key 即可跑通全链路；当检测到
环境变量（OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL）时，
自动切换到 OpenAI 兼容的真实大模型。调用方代码无需任何改动。
"""
from __future__ import annotations

import os
import json
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .scenarios import mock_architect, mock_programmer, mock_tester


def _load_dotenv() -> None:
    """零依赖读取 .env（OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL 等）。

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


def build_engine() -> BaseEngine:
    """按环境变量自动选择引擎。"""
    _load_dotenv()
    # 测试/CI 可通过此开关强制走 Mock，避免误打真实 API。
    if os.getenv("SYNERGYOS_FORCE_MOCK"):
        return MockEngine()
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return OpenAIEngine(EngineConfig(
            provider="openai",
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=api_key,
        ))
    return MockEngine()


# 便捷单例
ENGINE: BaseEngine = build_engine()
