"""双脑协作（Dual-Brain Collaboration）。

左脑（执行者）：architect -> programmer -> tester，专注"如何把事做对"。
右脑（观察者）：基于用户画像构建偏好信号、评分满意度、检测偏好误判，
              专注"如何让用户满意"。
仲裁：将左脑产出与右脑观察融合，必要时令左脑修订。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .engine import ENGINE, BaseEngine
from .bus import BUS, EventType
from .profile import UserProfile


# ---------------- 左脑：执行者 ----------------

@dataclass
class LeftArtifacts:
    plan: str = ""
    code: str = ""
    tests: str = ""
    trace: List[str] = field(default_factory=list)


class LeftBrain:
    """执行链路：需求拆解 -> 编码 -> 测试。"""

    def __init__(self, engine: BaseEngine = ENGINE):
        self.engine = engine

    def execute(self, task: str, profile: UserProfile,
                style_hint: str = "", scenario: Optional[str] = None) -> LeftArtifacts:
        a = LeftArtifacts()
        marker = f"用户任务:{task}"
        sys_arch, sys_code, sys_test = _scenario_prompts(scenario, profile, style_hint)
        a.plan = self.engine.complete(sys_arch, f"{marker}\n任务：{task}",
                                      role="architect", scenario=scenario)
        a.trace.append("architect: 产出实施方案")

        a.code = self.engine.complete(sys_code, f"{marker}\n方案：\n{a.plan}\n\n任务：{task}",
                                      role="programmer", scenario=scenario)
        a.trace.append("programmer: 产出实现代码")

        a.tests = self.engine.complete(sys_test, f"{marker}\n代码：\n{a.code}",
                                       role="tester", scenario=scenario)
        a.trace.append("tester: 产出测试用例")

        for t in a.trace:
            BUS.publish(EventType.LEFT_STEP, "left", t)
        return a


# ---------------- 场景化提示词（真模型驱动；Mock 引擎另有内置路由） ----------------

def _scenario_prompts(scenario: Optional[str], profile: UserProfile,
                     style_hint: str):
    """返回 (architect, programmer, tester) 三套系统提示。

    默认通用版覆盖所有场景；dev（软件研发助手）使用更贴近真实编码的专用版，
    让接真模型时产出可运行代码与 pytest 用例。Mock 引擎会按 scenario 自行路由，
    这里主要服务 OpenAI 等真实引擎。
    """
    base_arch = ("你是灵犀左脑·架构师，负责把用户任务拆解为可执行步骤。"
                 "输出 JSON：task/steps/acceptance/style_hint。")
    base_code = ("你是灵犀左脑·程序员，依据方案编写高质量、可运行的 Python 实现。"
                 f"用户偏好：沟通风格={profile.communication_style}，详细度={profile.detail_level}。"
                 f"{style_hint}")
    base_test = "你是灵犀左脑·测试员，针对代码生成覆盖典型与边界场景的测试用例（JSON）。"

    if scenario != "dev":
        return base_arch, base_code, base_test

    sys_arch = (
        "你是灵犀·软件研发助手 的「架构师」子智能体。请把用户需求拆解为可执行的工程方案，"
        "严格输出 JSON，字段：task / steps / interface（输入输出的契约与类型）/ "
        "edge_cases（边界与异常）/ acceptance（验收标准）/ style_hint。"
        "steps 要具体到函数签名与算法选择，不要写代码。"
    )
    sys_code = (
        "你是灵犀·软件研发助手 的「程序员」子智能体。依据上方方案，用 Python 实现一个单一模块。"
        "要求：① 仅输出代码，用 ```python 代码块包裹；② 含类型注解与中文 docstring；"
        "③ 处理空输入、非法类型等边界；④ 命名清晰、可读、可运行。"
        f"用户偏好：沟通风格={profile.communication_style}，详细度={profile.detail_level}。{style_hint}"
    )
    sys_test = (
        "你是灵犀·软件研发助手 的「测试员」子智能体。针对上方代码，用 pytest 编写测试用例，"
        "要求：① 仅输出代码，用 ```python 代码块包裹；② 覆盖典型场景与边界/异常场景；"
        "③ 使用 assert 表达期望。不要写解释，只写测试代码。"
    )
    return sys_arch, sys_code, sys_test


# ---------------- 右脑：观察者 ----------------

@dataclass
class Observation:
    satisfaction: float = 0.8
    preference_hits: List[str] = field(default_factory=list)
    preference_misses: List[str] = field(default_factory=list)
    note: str = ""
    raw: str = ""


class RightBrain:
    """观察者：基于画像给交付物打分并提炼偏好信号。"""

    def __init__(self, engine: BaseEngine = ENGINE):
        self.engine = engine

    def observe(self, task: str, artifacts: LeftArtifacts,
                profile: UserProfile) -> Observation:
        prof = json.dumps(profile.to_dict(), ensure_ascii=False)
        sys_obs = ("你是灵犀右脑·观察者，基于用户偏好画像评估交付物。"
                   "输出 JSON：satisfaction(0-1)/preference_hits/preference_misses/note。"
                   "preference_hits 是命中用户偏好的维度名，preference_misses 是未命中的。")
        user = (f"用户画像：{prof}\n\n任务：{task}\n\n"
                f"方案：{artifacts.plan}\n\n代码：{artifacts.code}")
        raw = self.engine.complete(sys_obs, user, role="observer")
        obs = self._parse(raw)
        BUS.publish(EventType.RIGHT_OBSERVE, "right",
                    f"右脑评分 满意度={obs.satisfaction:.2f} | {obs.note}",
                    satisfaction=obs.satisfaction)
        if obs.preference_hits:
            BUS.publish(EventType.PREFERENCE, "right",
                        f"偏好命中：{', '.join(obs.preference_hits)}",
                        hits=obs.preference_hits)
        if obs.preference_misses:
            BUS.publish(EventType.PREFERENCE, "right",
                        f"偏好未命中：{', '.join(obs.preference_misses)}",
                        misses=obs.preference_misses)
        return obs

    def _parse(self, raw: str) -> Observation:
        try:
            d = json.loads(raw)
            return Observation(
                satisfaction=float(d.get("satisfaction", 0.8)),
                preference_hits=list(d.get("preference_hits", [])),
                preference_misses=list(d.get("preference_misses", [])),
                note=str(d.get("note", "")),
                raw=raw,
            )
        except Exception:
            return Observation(satisfaction=0.8, note="(右脑返回未结构化，已保守评分)", raw=raw)


# ---------------- 仲裁 ----------------

def arbitrate(artifacts: LeftArtifacts, obs: Observation) -> Dict:
    """融合左脑产出与右脑观察，给出是否修订及原因。"""
    should_revise = obs.satisfaction < 0.75 or bool(obs.preference_misses)
    reason = ("满意度足够且无偏好误判，直接交付。" if not should_revise
              else ("满意度偏低，需左脑修订。" if obs.satisfaction < 0.75
                    else "存在偏好误判，需按画像修订。"))
    BUS.publish(EventType.ARBITRATE, "arbitrator",
                f"仲裁：{'修订' if should_revise else '通过'} —— {reason}")
    return {"should_revise": should_revise, "reason": reason}
