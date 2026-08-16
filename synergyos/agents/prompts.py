"""场景化提示词构造（左脑三类角色）。

把 _scenario_prompts 从原 brain.py 下沉到此，作为各 Agent 共享的提示词工厂。
默认通用版覆盖所有场景；dev（软件研发助手）使用更贴近真实编码的专用版，
让接真模型时产出可运行代码与 pytest 用例。Mock 引擎会按 scenario 自行路由，
这里主要服务 OpenAI 等真实引擎。
"""
from __future__ import annotations

from typing import Optional, Tuple

from ..core.profile import UserProfile


def scenario_prompts(scenario: Optional[str], profile: UserProfile,
                    style_hint: str) -> Tuple[str, str, str]:
    """返回 (architect, programmer, tester) 三套系统提示。"""
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
