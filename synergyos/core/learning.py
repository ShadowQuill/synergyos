"""软学习闭环（Soft-learning Closure，零依赖、可离线）。

对应改进报告 P1#4 与用户选择的「A 软学习」——让系统「越用越聪明」：

  1. 每次任务记录一条 Experience（成败 / 失败类型 / 用过的工具 / 用户反馈）；
  2. 失败经历聚合成「失败模式库」(FailureLibrary)，产出 few-shot 注入文本，
     回灌给后续相似任务，减少重复犯错；
  3. 反思权重（ReflexionLoop 的策略权重）跨会话持久化，重启后保留 → 真正累积成长；
  4. 新任务检索相似历史，作为 few-shot 经验注入智能体提示词。

诚实声明（README 同步）：这是**经验式软学习**，通过「失败模式库 + few-shot + 权重
跨会话持久化」让系统用一次聪明一点；**不是**梯度 / 参数学习（不微调模型权重），
因此不破坏「零依赖、可离线」的招牌。接入真实大模型后，经验回灌会直接改善生成质量。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from .memory import tokenize


@dataclass
class Experience:
    """一条任务经验记录。"""

    ts: float
    task: str
    scenario: str
    success: bool
    failure_type: Optional[str]
    tools_used: List[str]
    feedback: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Experience":
        return cls(
            ts=float(d.get("ts", 0.0)),
            task=d.get("task", ""),
            scenario=d.get("scenario", ""),
            success=bool(d.get("success", False)),
            failure_type=d.get("failure_type"),
            tools_used=list(d.get("tools_used", []) or []),
            feedback=d.get("feedback", ""),
            notes=d.get("notes", ""),
        )


class ExperienceStore:
    """经验库：追加式记录 + 持久化（JSON）。learning_dir 为 None 时仅内存。"""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.items: List[Experience] = []
        if path:
            self.load(path)

    def record(self, exp: Experience) -> None:
        self.items.append(exp)
        if self.path:
            self.save(self.path)

    def failures(self) -> List[Experience]:
        return [e for e in self.items if not e.success]

    def retrieve_similar(self, task: str, top_k: int = 3) -> List[Experience]:
        """基于词重叠检索相似历史（复用 memory.tokenize 的中文 bigram 分词）。"""
        q = set(tokenize(task))
        if not q:
            return []
        scored = []
        for e in self.items:
            hay = tokenize(f"{e.task} {e.feedback or ''} {e.notes or ''}")
            overlap = len(q & set(hay))
            if overlap:
                scored.append((overlap, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def save(self, path: Optional[str] = None) -> None:
        path = path or self.path
        if not path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self.items], f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        try:
            with open(path, encoding="utf-8") as f:
                self.items = [Experience.from_dict(d) for d in json.load(f)]
        except Exception:
            self.items = []


class FailureLibrary:
    """把失败经历聚合成「失败模式库」，产出可注入提示词的 few-shot 文本。"""

    # 常见失败类型的通用经验建议（经验模板，非模型参数）
    _GENERIC_ADVICE: Dict[str, str] = {
        "verification_failed": "上次因验证未通过而返工：本轮先写清验收点，产出前逐条自查必备要素。",
        "missing_required": "上次漏掉了用户明确要求的要素：本轮先列出用户必备/排除项，对照检查再交付。",
        "tool_error": "上次工具调用出错：本轮调用工具前先确认参数类型与路径落在沙箱内。",
        "off_topic": "上次跑题：本轮紧扣用户任务，避免引入未要求的扩展。",
        "low_satisfaction": "上次满意度偏低：复盘用户偏好画像，对齐其审美与沟通风格。",
        "preference": "上次偏好未命中：本轮多参考右脑（观察者）给出的偏好信号。",
        "logic_error": "上次逻辑/实现有误：本轮多写单元测试自查，边界用例优先。",
    }

    @classmethod
    def build_fewshot(cls, store: ExperienceStore, task: str, top_k: int = 3) -> str:
        """检索相似历史，生成 few-shot 经验注入文本（空则回空串）。"""
        similar = store.retrieve_similar(task, top_k=top_k)
        if not similar:
            return ""
        blocks: List[str] = ["# 历史经验（来自失败模式库，供参考，不必照搬）"]
        for e in similar:
            if e.success:
                tools = "、".join(e.tools_used) if e.tools_used else "无"
                blocks.append(f"- ✅ 相似成功案例：任务「{e.task}」使用工具[{tools}]并成功，可参考其思路。")
            else:
                advice = cls._GENERIC_ADVICE.get(
                    e.failure_type or "", "上次任务未成功，本轮请更谨慎。")
                fb = f"（原反馈：{e.feedback}）" if e.feedback else ""
                blocks.append(f"- ⚠️ 相似失败教训[{e.failure_type or '未知'}]：{advice}{fb}")
        return "\n".join(blocks)


class WeightStore:
    """反思权重跨会话持久化（JSON）。"""

    DEFAULT_WEIGHTS: Dict[str, float] = {
        "architect": 1.0, "programmer": 1.0, "tester": 1.0, "observer": 1.0,
    }

    @staticmethod
    def load(path: str) -> Dict[str, float]:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            w = dict(WeightStore.DEFAULT_WEIGHTS)
            w.update(data.get("weights", {}))
            return w
        except Exception:
            return dict(WeightStore.DEFAULT_WEIGHTS)

    @staticmethod
    def save(path: str, weights: Dict[str, float]) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"weights": weights}, f, ensure_ascii=False, indent=2)
