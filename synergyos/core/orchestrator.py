"""顶层编排：分工 - 协作 - 反思。

把冷启动偏好锚定、双脑协作、反思性修复、智能节律控制串成一条完整链路。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .engine import ENGINE, BaseEngine
from .bus import BUS, EventType
from .profile import Profiler, UserProfile, COLD_START_QUESTIONS
from .brain import LeftBrain, RightBrain, arbitrate
from .reflexion import ReflexionLoop
from .pause import PauseController
from .scenarios import get_scenario


class SynergyOS:
    def __init__(self, engine: BaseEngine = ENGINE, bus=BUS, profile_path: Optional[str] = None):
        self.engine = engine
        self.bus = bus
        self.left = LeftBrain(engine)
        self.right = RightBrain(engine)
        self.reflex = ReflexionLoop(engine)
        self.pause = PauseController()
        self.profiler = Profiler(path=profile_path)
        # 累积每轮协作明细，供报告生成器取数
        self.rounds: List[Dict] = []
        self.pref_hits: List[str] = []
        self.pref_misses: List[str] = []

    # ---- 阶段：冷启动锚定 ----
    def _cold_start(self, answers: Optional[Dict[str, int]]):
        self.bus.publish(EventType.COLD_START, "orchestrator", "启动冷启动偏好锚定")
        if self.profiler.is_cold:
            if answers:
                self.profiler.run_cold_start(answers)
            else:
                # 无答案时以中性默认值锚定，保证链路可跑
                defaults = {q["id"]: 1 for q in COLD_START_QUESTIONS}
                self.profiler.run_cold_start(defaults)
        else:
            self.bus.publish(EventType.COLD_START, "orchestrator",
                             "已存在用户画像，跳过冷启动探测")

    # ---- 主流程 ----
    def run(self, task: str, profile_answers: Optional[Dict[str, int]] = None,
            pause_request_at: Optional[float] = None,
            scenario: Optional[str] = None) -> Dict:
        stages = ["冷启动锚定", "左脑执行", "右脑观察", "仲裁修订", "反思修复", "交付"]
        self.pause.predict_horizons(stages)
        self.pause.set_progress(0.0)

        # 1. 冷启动
        self._cold_start(profile_answers)
        self.pause.set_progress(1 / len(stages))
        if self._maybe_pause("冷启动锚定"):
            self.profiler.save()
            return self._paused_result(task)

        profile = self.profiler.profile
        style_hint = f"请贴合用户审美偏好：{profile.aesthetic}。"

        # 2-4. 协作 + 仲裁 + 反思（可能多轮）
        best = None
        last_obs = None
        scenario_meta = get_scenario(scenario)
        self._scenario_title = scenario_meta.title if scenario_meta else None
        if scenario_meta:
            self.bus.publish(EventType.INFO, "orchestrator",
                             f"应用场景：{scenario_meta.title}")
        for rnd in range(self.reflex.max_rounds):
            self.bus.publish(EventType.INFO, "orchestrator", f"—— 第 {rnd + 1} 轮协作 ——")
            artifacts = self.left.execute(task, profile, style_hint, scenario=scenario)
            obs = self.right.observe(task, artifacts, profile)
            arb = arbitrate(artifacts, obs)
            last_obs = obs
            self.pref_hits.extend(obs.preference_hits)
            self.pref_misses.extend(obs.preference_misses)

            # 偏好信号回灌画像（后台静默学习）
            if obs.preference_hits or obs.preference_misses:
                self.profiler.learn_from_feedback(
                    {k: getattr(profile, k, "") for k in obs.preference_hits},
                    obs.preference_misses)

            self.pause.set_progress((rnd + 2) / len(stages))
            if self._maybe_pause("左脑执行/右脑观察"):
                self.profiler.save()
                return self._paused_result(task, artifacts, obs)

            # 反思
            result = self.reflex.evaluate(task, artifacts.trace, obs)
            self.reflex.heal(result)
            self.rounds.append({
                "round": rnd + 1, "obs": obs, "arb": arb, "reflex": result,
            })
            self.pause.set_progress((rnd + 3) / len(stages))
            if self._maybe_pause("反思修复"):
                return self._paused_result(task, artifacts, obs)

            best = artifacts
            if result.verdict == "pass":
                self.bus.publish(EventType.INFO, "orchestrator",
                                 "反思通过，无需再修。")
                break
            else:
                self.bus.publish(EventType.INFO, "orchestrator",
                                 f"需软修复（{result.verdict}），准备下一轮。")

        # 5. 交付
        self.profiler.save()
        self.pause.set_progress(1.0)

        # 真实验证 + 反思自愈：真实模型下按场景验收——
        #   dev：把 solution+tests 真跑 pytest，失败自动修复实现；
        #   paas/biz：结构化验收（plan 合法性 + 交付物必备要素），缺失自动补全。
        verification = None
        if ENGINE.is_real() and best and best.code.strip():
            from .verify import verify_and_fix
            verification = verify_and_fix(
                {"plan": best.plan, "code": best.code, "tests": best.tests, "task": task},
                ENGINE, scenario=scenario, max_fix=3,
            )
            if verification.get("fixed_code"):
                best.code = verification["fixed_code"]
            if verification.get("fixed_tests"):
                best.tests = verification["fixed_tests"]
            if verification.get("fixed_code") or verification.get("fixed_tests"):
                self.bus.publish(EventType.REFLEXION, "verifier",
                                 f"反思自愈：重跑测试后修正交付物（{verification['fixes']} 次），"
                                 f"{'全部通过' if verification['passed'] else '仍有失败，需人工复核'}")
            elif verification.get("passed"):
                self.bus.publish(EventType.REFLEXION, "verifier",
                                 "反思验证：生成代码一次通过全部测试 ✅")
            else:
                self.bus.publish(EventType.REFLEXION, "verifier",
                                 f"反思验证：修复 {verification['fixes']} 次后仍失败，请人工复核。")

        self.bus.publish(EventType.DELIVER, "orchestrator", "灵犀交付最终结果",
                         satisfaction=last_obs.satisfaction if last_obs else None)
        return {
            "task": task,
            "scenario": scenario_meta.title if scenario_meta else None,
            "profile": profile.to_dict(),
            "artifacts": {
                "plan": best.plan if best else "",
                "code": best.code if best else "",
                "tests": best.tests if best else "",
            },
            "satisfaction": last_obs.satisfaction if last_obs else None,
            "weights": dict(self.reflex.weights),
            "verification": verification,
            "paused": False,
        }

    def _maybe_pause(self, stage: str) -> bool:
        if self.pause.tick(stage):
            return True
        return False

    def _paused_result(self, task, artifacts=None, obs=None) -> Dict:
        return {
            "task": task,
            "scenario": getattr(self, "_scenario_title", None),
            "paused": True,
            "briefing": self.pause.stage_briefing(),
            "snapshot": self.pause.snapshot,
            "artifacts": {
                "plan": artifacts.plan if artifacts else "",
                "code": artifacts.code if artifacts else "",
                "tests": artifacts.tests if artifacts else "",
            } if artifacts else {},
            "weights": dict(self.reflex.weights),
        }
