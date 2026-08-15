"""灵犀 SynergyOS 核心模块单元测试（零依赖：仅标准库 unittest）。

运行：
  python3 -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

# 测试全程强制 Mock 引擎：即便项目根 .env 含真实 Key，也不触发真实 API 调用。
os.environ["SYNERGYOS_FORCE_MOCK"] = "1"

from synergyos.core.engine import (
    ENGINE, MockEngine, OpenAIEngine, build_engine, EngineConfig,
)
from synergyos.core.bus import EventBus, EventType
from synergyos.core.profile import Profiler, UserProfile, COLD_START_QUESTIONS
from synergyos.core.brain import LeftBrain, RightBrain, arbitrate, Observation, LeftArtifacts, _scenario_prompts
from synergyos.cli import _strip_fence, _emit
from synergyos.core.reflexion import ReflexionLoop, ReflexionResult
from synergyos.core.pause import PauseController
from synergyos.core.orchestrator import SynergyOS
from synergyos.core.report import build, to_markdown, to_html
from synergyos.core.scenarios import (
    SCENARIOS, VALID_SCENARIOS, get_scenario,
    mock_architect, mock_programmer, mock_tester,
)


class TestEngine(unittest.TestCase):
    def test_mock_is_offline(self):
        self.assertFalse(MockEngine().is_real())
        self.assertFalse(ENGINE.is_real())

    def test_mock_returns_text(self):
        out = MockEngine().complete("sys", "user task", role="programmer")
        self.assertIsInstance(out, str)
        self.assertGreater(len(out), 0)

    def test_role_routing_distinct(self):
        e = MockEngine()
        self.assertNotEqual(
            e.complete("s", "t", role="architect"),
            e.complete("s", "t", role="tester"),
        )

    def test_openai_engine_is_real(self):
        self.assertTrue(OpenAIEngine(EngineConfig(api_key="sk-test")).is_real())

    def test_load_dotenv_reads_key_and_base_url(self):
        # 锁定 .env 加载：零依赖从临时 .env 注入 DeepSeek 配置
        import synergyos.core.engine as eng_mod
        keys = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")
        saved = {k: os.environ.pop(k, None) for k in keys}
        try:
            with tempfile.TemporaryDirectory() as d:
                with open(os.path.join(d, ".env"), "w", encoding="utf-8") as f:
                    f.write('OPENAI_API_KEY=sk-dottest\n'
                            'OPENAI_BASE_URL=https://api.deepseek.com/v1\n'
                            'OPENAI_MODEL=deepseek-chat\n')
                cwd = os.getcwd()
                os.chdir(d)
                try:
                    eng_mod._load_dotenv()
                finally:
                    os.chdir(cwd)
            self.assertEqual(os.environ.get("OPENAI_API_KEY"), "sk-dottest")
            self.assertEqual(os.environ.get("OPENAI_BASE_URL"),
                             "https://api.deepseek.com/v1")
            self.assertEqual(os.environ.get("OPENAI_MODEL"), "deepseek-chat")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_build_engine_defaults_to_mock(self):
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            self.assertIsInstance(build_engine(), MockEngine)
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old

    def test_build_engine_switches_to_openai(self):
        old = os.environ.get("OPENAI_API_KEY")
        force_mock = os.environ.pop("SYNERGYOS_FORCE_MOCK", None)
        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            eng = build_engine()
            self.assertIsInstance(eng, OpenAIEngine)
            self.assertTrue(eng.is_real())
        finally:
            if old is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old
            if force_mock is not None:
                os.environ["SYNERGYOS_FORCE_MOCK"] = force_mock


class TestBus(unittest.TestCase):
    def test_publish_and_history(self):
        b = EventBus()
        b.publish(EventType.INFO, "t", "hello")
        self.assertEqual(len(b.history()), 1)
        self.assertEqual(b.history()[0].message, "hello")

    def test_subscribe_callback(self):
        b = EventBus()
        seen = []
        b.subscribe(lambda ev: seen.append(ev.message))
        b.publish(EventType.INFO, "t", "x")
        self.assertEqual(seen, ["x"])


class TestProfile(unittest.TestCase):
    def test_cold_start_anchors(self):
        p = Profiler()
        self.assertTrue(p.is_cold)
        answers = {q["id"]: 0 for q in COLD_START_QUESTIONS}
        prof = p.run_cold_start(answers)
        self.assertFalse(p.is_cold)
        self.assertEqual(prof.communication_style, COLD_START_QUESTIONS[0]["options"][0])

    def test_learn_boosts_confidence(self):
        p = Profiler()
        before = p.profile.confidence["aesthetic"]
        p.profile.learn("aesthetic", "科技蓝数据风", weight=0.2)
        self.assertGreater(p.profile.confidence["aesthetic"], before)
        self.assertEqual(p.profile.learned_signals, 1)


class TestBrain(unittest.TestCase):
    def test_left_execute(self):
        a: LeftArtifacts = LeftBrain().execute(
            "写一个去重函数", UserProfile(), "")
        self.assertTrue(a.plan and a.code and a.tests)

    def test_right_observe(self):
        obs: Observation = RightBrain().observe(
            "task", LeftBrain().execute("t", UserProfile(), ""), UserProfile())
        self.assertIsInstance(obs.satisfaction, float)
        self.assertGreaterEqual(obs.satisfaction, 0.0)

    def test_arbitrate(self):
        good = arbitrate(LeftArtifacts(), Observation(satisfaction=0.9))
        self.assertFalse(good["should_revise"])
        bad = arbitrate(LeftArtifacts(), Observation(satisfaction=0.5))
        self.assertTrue(bad["should_revise"])


class TestReflexion(unittest.TestCase):
    def test_heal_preference_error(self):
        rl = ReflexionLoop()
        rl.heal(ReflexionResult(verdict="preference_error"))
        self.assertGreater(rl.weights["observer"], 1.0)

    def test_heal_logic_error(self):
        rl = ReflexionLoop()
        rl.heal(ReflexionResult(verdict="logic_error"))
        self.assertGreater(rl.weights["tester"], 1.0)

    def test_heal_pass_no_change(self):
        rl = ReflexionLoop()
        rl.heal(ReflexionResult(verdict="pass"))
        self.assertEqual(rl.weights["observer"], 1.0)


class TestPause(unittest.TestCase):
    def test_predict_horizons(self):
        pc = PauseController()
        pc.predict_horizons(["a", "b", "c"])
        self.assertEqual(len(pc.horizons), 3)

    def test_request_pause_stops_tick(self):
        pc = PauseController()
        pc.request_pause()
        self.assertTrue(pc.tick("stage"))
        self.assertTrue(pc.is_paused)

    def test_stage_briefing(self):
        pc = PauseController()
        pc.set_progress(0.5)
        self.assertIn("50%", pc.stage_briefing())


class TestOrchestrator(unittest.TestCase):
    def test_full_run_structure(self):
        os_sys = SynergyOS(bus=EventBus())
        r = os_sys.run("写一个去重函数", profile_answers=None)
        self.assertEqual(r["task"], "写一个去重函数")
        self.assertIn("profile", r)
        self.assertIn("artifacts", r)
        self.assertTrue(r["artifacts"]["code"])
        self.assertIn("weights", r)
        self.assertFalse(r["paused"])

    def test_paused_branch(self):
        os_sys = SynergyOS(bus=EventBus())
        os_sys.pause.request_pause()
        r = os_sys.run("task")
        self.assertTrue(r["paused"])
        self.assertIn("briefing", r)


class TestPersistence(unittest.TestCase):
    def test_profile_persists_across_instances(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "sub", "profile.json")
        # 第一个实例：冷启动并落盘
        os1 = SynergyOS(profile_path=path)
        self.assertTrue(os1.profiler.is_cold)
        os1.run("写一个去重函数")
        self.assertTrue(os.path.exists(path))
        # 第二个实例：应从磁盘加载，不再冷启动
        os2 = SynergyOS(profile_path=path)
        self.assertFalse(os2.profiler.is_cold)
        self.assertGreater(os2.profiler.profile.learned_signals, 0)
        # 静默学习也应写回
        before = os2.profiler.profile.confidence.get("aesthetic", 0)
        os2.profiler.profile.learn("aesthetic", "科技蓝数据风", weight=0.1)
        os2.profiler.save()
        os3 = SynergyOS(profile_path=path)
        self.assertGreater(os3.profiler.profile.confidence.get("aesthetic", 0), before)

    def test_no_persist_when_path_none(self):
        os_sys = SynergyOS(profile_path=None)
        self.assertIsNone(os_sys.profiler.path)
        os_sys.run("task")
        # 不写任何文件（家目录不受影响，这里仅校验 path 为 None）
        self.assertIsNone(os_sys.profiler.path)


class TestReport(unittest.TestCase):
    def _run(self):
        os_sys = SynergyOS(bus=EventBus())
        result = os_sys.run("写一个去重函数")
        return os_sys, result

    def test_build(self):
        os_sys, result = self._run()
        rep = build(os_sys, result)
        self.assertIn("timeline", rep)
        self.assertIn("rounds", rep)
        self.assertIn("profile", rep)

    def test_markdown(self):
        os_sys, result = self._run()
        md = to_markdown(build(os_sys, result))
        self.assertIn("灵犀", md)
        self.assertIn("双脑协作", md)

    def test_html(self):
        os_sys, result = self._run()
        html = to_html(build(os_sys, result))
        self.assertIn("<html", html)
        self.assertIn("冷启动偏好锚定", html)


class TestScenarios(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(set(VALID_SCENARIOS),
                         {"paas", "biz", "dev", "code-review", "data-analysis"})
        for k in VALID_SCENARIOS:
            self.assertIsNotNone(get_scenario(k))
            self.assertTrue(SCENARIOS[k].task_hint)

    def test_mock_outputs_are_scenario_specific(self):
        self.assertIn("周报", mock_programmer("paas", "生成周报"))
        self.assertIn("pandas", mock_programmer("biz", "分析销售额"))
        self.assertIn("dedupe", mock_programmer("dev", "实现去重函数"))
        self.assertIn("代码评审报告", mock_programmer("code-review", "审查函数"))
        self.assertIn("销售数据分析", mock_programmer("data-analysis", "分析销售额"))
        self.assertIn("steps", mock_architect("biz", "分析销售额"))
        self.assertIn("cases", mock_tester("dev", "实现去重函数"))

    def test_engine_routes_by_scenario(self):
        e = MockEngine()
        plan = e.complete("你是架构师", "用户任务:实现去重函数", role="architect", scenario="dev")
        self.assertIn("steps", plan)
        code = e.complete("你是程序员", "用户任务:实现去重函数", role="programmer", scenario="dev")
        self.assertIn("def dedupe", code)

    def test_observer_not_misrouted_by_code_keyword(self):
        # 修复潜伏 bug：observer 的 prompt 含「代码」不应被路由到 programmer
        obs = RightBrain(MockEngine()).observe(
            "分析销售额", LeftArtifacts(plan="x", code="y", tests="z"), UserProfile())
        self.assertNotEqual(obs.note, "(右脑返回未结构化，已保守评分)")
        self.assertIsInstance(obs.satisfaction, float)

    def test_orchestrator_carries_scenario(self):
        os_sys = SynergyOS(bus=EventBus())
        result = os_sys.run("实现去重函数", scenario="dev")
        self.assertEqual(result["scenario"], SCENARIOS["dev"].title)
        self.assertIn("dedupe", result["artifacts"]["code"])

    def test_report_includes_scenario(self):
        os_sys = SynergyOS(bus=EventBus())
        result = os_sys.run("分析销售额并生成可视化图表", scenario="biz")
        rep = build(os_sys, result)
        self.assertEqual(rep["scenario"], SCENARIOS["biz"].title)
        self.assertIn(SCENARIOS["biz"].title, to_markdown(rep))


class TestDevPrototype(unittest.TestCase):
    """软件研发助手（真实产品原型楔子）相关：专用提示词 / 围栏剥离 / emit 落盘。"""

    def _prof(self):
        return UserProfile()

    def test_dev_prompts_are_specialized(self):
        arch, code, test = _scenario_prompts("dev", self._prof(), "")
        self.assertIn("架构师", arch)
        self.assertIn("pytest", test)
        self.assertIn("代码块", code)

    def test_non_dev_uses_generic_prompts(self):
        arch, code, test = _scenario_prompts("biz", self._prof(), "")
        self.assertNotIn("pytest", test)

    def test_strip_fence(self):
        self.assertEqual(_strip_fence("```python\ndef f():\n    pass\n```"),
                         "def f():\n    pass\n")
        self.assertEqual(_strip_fence("plain text"), "plain text")

    def test_emit_writes_files(self):
        with tempfile.TemporaryDirectory() as d:
            arts = {"plan": '{"task":"x"}', "code": "```python\ndef f():\n    pass\n```",
                    "tests": "```python\ndef test_f():\n    assert f() is None\n```"}
            written = _emit(d, "测试任务 abc", arts, "dev")
            self.assertEqual(len(written), 4)
            sol = os.path.join(d, "测试任务_abc", "solution.py")
            self.assertTrue(os.path.exists(sol))
            with open(sol, encoding="utf-8") as f:
                self.assertNotIn("```", f.read())
            self.assertTrue(os.path.exists(os.path.join(d, "测试任务_abc", "tests.py")))
            self.assertTrue(os.path.exists(os.path.join(d, "测试任务_abc", "plan.json")))


class TestVerify(unittest.TestCase):
    def test_module_for_detects_class_import(self):
        from synergyos.core.verify import _module_for, strip_fence
        code = "class Foo:\n    pass\n"
        tests = "import pytest\nfrom foo_mod import Foo\n\ndef test_foo():\n    assert Foo()\n"
        self.assertEqual(_module_for(code, tests), "foo_mod")
        # 不应把 import time 这类标准库误判为交付模块
        self.assertIsNone(_module_for(code, "import time\nimport pytest\n"))
        self.assertEqual(strip_fence("```python\nx=1\n```"), "x=1\n")
        self.assertEqual(strip_fence("plain"), "plain")

    def test_verify_fixes_failing_then_passes(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        buggy = "def add(a, b):\n    return a + b + 1\n"
        tests = "from solution import add\n\ndef test_add():\n    assert add(1, 1) == 2\n    assert add(0, 0) == 0\n"

        class FakeEngine(BaseEngine):
            def complete(self, system, user, *, role="assistant", temperature=None, **kw):
                # 反思修复：返回去掉 +1 的正确实现
                return "```python\ndef add(a, b):\n    return a + b\n```"

        res = verify_and_fix({"plan": "", "code": buggy, "tests": tests},
                             FakeEngine(), max_fix=2)
        self.assertTrue(res["enabled"])
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 1)
        self.assertIn("return a + b", res["fixed_code"])

    def test_verify_fixes_contradictory_test(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # 实现正确（f(x)=x*2），但测试断言写错（期望 5）。修复器应修正测试而非实现。
        code = "def f(x):\n    return x * 2\n"
        tests = "from solution import f\n\ndef test_f():\n    assert f(2) == 5\n"

        class FakeEngine(BaseEngine):
            def complete(self, system, user, *, role="assistant",
                         temperature=None, **kw):
                return ("```python\nfrom solution import f\n\n"
                        "def test_f():\n    assert f(2) == 4\n```")

        res = verify_and_fix({"plan": "", "code": code, "tests": tests},
                             FakeEngine(), max_fix=2)
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 1)
        self.assertIn("== 4", res.get("fixed_tests") or "")

    def test_verify_skipped_without_tests(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        class FakeEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("真实引擎不应被调用")

        res = verify_and_fix({"plan": "", "code": "x=1", "tests": ""}, FakeEngine())
        self.assertFalse(res["enabled"])
        self.assertIn("reason", res)

    def test_verify_structural_passes_when_markers_present(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("已通过时不应调用修复器")

        arts = {
            "plan": '{"task":"x","steps":["a","b"],"acceptance":"含全部章节"}',
            "code": "本周完成 进行中 风险 下周重点",  # 命中全部 paas 必备要素
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="paas")
        self.assertTrue(res["enabled"])
        self.assertEqual(res["kind"], "structural")
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 0)
        self.assertIsNone(res["fixed_code"])

    def test_verify_structural_fixes_missing(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # 第一轮：缺失章节；修复器补全含全部必备要素的交付物
        class FakeEngine(BaseEngine):
            def complete(self, system, user, *, role="assistant",
                         temperature=None, **kw):
                return ("```markdown\n# 本周完成\n- 完成路线图评审\n"
                        "# 进行中\n- 看板重构\n# 风险\n- 支付联调延期\n"
                        "# 下周重点\n- 计费全量\n```")

        arts = {
            "plan": '{"task":"周报","steps":["收集","组织"],"acceptance":"结构分点"}',
            "code": "# 周报\n随便写点，没章节",
            "tests": "",
        }
        res = verify_and_fix(arts, FakeEngine(), scenario="paas", max_fix=2)
        self.assertTrue(res["enabled"])
        self.assertEqual(res["kind"], "structural")
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 1)
        self.assertIn("本周完成", res["fixed_code"])

    def test_verify_structural_uses_biz_markers(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # biz 必备要素为 图表/可视化、趋势/建模、数据/销售额；只给数据不给图表→应判未覆盖
        class FakeEngine(BaseEngine):
            def complete(self, system, user, *, role="assistant",
                         temperature=None, **kw):
                return ("```python\nimport pandas as pd\ndf = pd.DataFrame(...)\n"
                        "render_chart(df, title='上半年销售额')\n"
                        "q2_growth = 0.27  # 环比增长趋势\n"
                        "model = fit_trend(df)\n```")

        arts = {
            "plan": '{"task":"销售分析","steps":["清洗","建模"],"acceptance":"含图表"}',
            "code": "df = pd.read_csv('sales.csv')\nmonthly = df.groupby('month').sum()",
            "tests": "",
        }
        res = verify_and_fix(arts, FakeEngine(), scenario="biz", max_fix=2)
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 1)
        self.assertIn("chart", res["fixed_code"].lower())

    def test_verify_structural_respects_user_exclusion(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # 用户显式排除「风险」「下周」，交付物只含本周完成/进行中。
        # 验收应：尊重用户，不强制补全，passed=True 且 skipped 含这俩组，修复器不被调用。
        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("用户已排除的要素不应触发修复器")

        arts = {
            "task": "帮我写一份极简周报，只列本周完成和进行中两件事就够了，不要写风险和下周计划",
            "plan": '{"task":"周报","steps":["收集","组织"],"acceptance":"结构分点"}',
            "code": "## 本周完成\n- 上线计费灰度\n\n## 进行中\n- 看板重构（70%）\n",
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="paas")
        self.assertTrue(res["enabled"])
        self.assertEqual(res["kind"], "structural")
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 0)
        self.assertIsNone(res["fixed_code"])
        skipped = res.get("skipped") or []
        self.assertTrue(any("风险" in s for s in skipped))
        self.assertTrue(any("下周" in s for s in skipped))
        # 用户要求的要素已覆盖，不应出现在 skipped 里
        self.assertFalse(any("本周完成" in s for s in skipped))

    def test_verify_structural_exclusion_requires_signal(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # 同样缺风险/下周，但 task 没有排除信号 → 仍判缺失，需反思补全（修复器被调用）。
        class FakeEngine(BaseEngine):
            def complete(self, system, user, *, role="assistant",
                         temperature=None, **kw):
                return ("```markdown\n## 本周完成\n- 上线灰度\n## 进行中\n- 看板重构\n"
                        "## 风险\n- 无\n## 下周重点\n- 全量发布\n```")

        arts = {
            "task": "帮我写一份周报",  # 无排除信号
            "plan": '{"task":"周报","steps":["收集"],"acceptance":"含全部章节"}',
            "code": "## 本周完成\n- 上线灰度\n\n## 进行中\n- 看板重构\n",
            "tests": "",
        }
        res = verify_and_fix(arts, FakeEngine(), scenario="paas", max_fix=2)
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 1)
        self.assertFalse(res.get("skipped"))  # 未被排除，无 skipped

    def test_verify_structural_exclusion_beats_wordplay(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # 真实模型常见话术：用户排除风险/下周，模型写「未包含风险与下周计划」——
        # 这句话里恰好含「风险」「下周」二字，若先判覆盖会被误判为「已覆盖」。
        # 重构后：task 含排除信号即优先归 skipped，不受文字游戏干扰。
        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("文字游戏不应骗过排除判定、更不应触发修复器")

        arts = {
            "task": "帮我写周报，不要写风险和下周计划",
            "plan": '{"task":"周报","steps":["收集"],"acceptance":"极简"}',
            "code": ("## 本周完成\n- 上线灰度\n\n## 进行中\n- 看板重构\n\n"
                     "（本份周报严格遵循指令，未包含风险与下周计划。）\n"),
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="paas")
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 0)
        skipped = res.get("skipped") or []
        # 即使 code 里出现「风险」「下周」字眼，也应判定为用户排除项
        self.assertTrue(any("风险" in s for s in skipped))
        self.assertTrue(any("下周" in s for s in skipped))

    def test_verify_structural_biz_excludes_only_chart_not_data(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        # biz：「分析销售额…不用画」。用户只排除图表，数据要素是任务天然核心，
        # 不应被误判为排除项（修复前「数据」组 exclude 词含「销售额/分析」会误触发）。
        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("已通过不应调用修复器")

        arts = {
            "task": "分析一下这周销售额，上周50万这周62万，涨了24，帮我出个简单分析就行，不用画",
            "plan": '{"task":"销售分析","steps":["清洗"],"acceptance":"含数据"}',
            "code": "df = pd.read_csv('sales.csv')\nmonthly = df.groupby('month').sum()\nq2_growth = 0.24  # 环比增长趋势，已完成数据/销售额分析\n",
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="biz")
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 0)
        skipped = res.get("skipped") or []
        self.assertTrue(any("图表" in s for s in skipped))
        self.assertFalse(any("数据" in s for s in skipped))  # 数据组不应被误判

    def test_verify_structural_code_review_passes(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("已通过不应调用修复器")

        # code-review 默认 mock 交付物覆盖 问题清单/严重性/建议/结论 四要素
        arts = {
            "task": "审查这段去重函数并指出问题与改进",
            "plan": '{"task":"评审","steps":["定位问题"],"acceptance":"四要素齐全"}',
            "code": (
                "# 代码评审报告\n## 问题清单\n- 未处理非可哈希元素\n"
                "## 严重性\n- 高：运行时崩溃\n## 修复建议\n- 加类型校验\n"
                "## 结论\n整体简洁，建议补充校验后合入。\n"
            ),
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="code-review")
        self.assertTrue(res["passed"])
        self.assertEqual(res["fixes"], 0)
        self.assertEqual(res["kind"], "structural")

    def test_verify_structural_code_review_excludes_suggestion(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("已通过不应调用修复器")

        # 用户「不用给修复建议」→ 仅建议组归 skipped，其余要素仍须覆盖才算通过
        # （任务不含「只列出」限定信号，故问题/严重性/结论按模板必备校验）
        arts = {
            "task": "审查这段去重函数，不用给修复建议",
            "plan": '{"task":"评审","steps":["定位问题"],"acceptance":"要素齐全"}',
            "code": (
                "# 代码评审报告\n## 问题清单\n- 未处理非可哈希元素\n"
                "## 严重性\n- 高：运行时崩溃\n## 结论\n建议补充校验后合入。\n"
            ),
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="code-review")
        self.assertTrue(res["passed"])
        skipped = res.get("skipped") or []
        self.assertTrue(any("建议" in s for s in skipped))
        self.assertFalse(any("问题" in s for s in skipped))
        self.assertFalse(any("严重性" in s for s in skipped))
        self.assertFalse(any("结论" in s for s in skipped))

    def test_verify_structural_data_analysis_excludes_chart(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("已通过不应调用修复器")

        # data-analysis：「不用画图」→ 仅图表组归 skipped（数据/趋势/结论仍须覆盖）
        # 任务不含结论词、无「只列出」限定信号，避免误判核心要素被排除
        arts = {
            "task": "分析上半年销售额，不用画图",
            "plan": '{"task":"分析","steps":["清洗","探索"],"acceptance":"三要素齐全"}',
            "code": (
                "# 上半年销售数据分析\n## 数据\n- 已剔除异常值\n"
                "## 趋势\n- Q2 环比 +27%\n## 关键结论\n- 华东区增长最快\n"
            ),
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="data-analysis")
        self.assertTrue(res["passed"])
        skipped = res.get("skipped") or []
        self.assertTrue(any("图表" in s for s in skipped))
        self.assertFalse(any("数据" in s for s in skipped))
        self.assertFalse(any("趋势" in s for s in skipped))
        self.assertFalse(any("结论" in s for s in skipped))

    def test_verify_structural_strong_exclusion_is_scoped(self):
        from synergyos.core.verify import verify_and_fix
        from synergyos.core.engine import BaseEngine

        class NeverCalledEngine(BaseEngine):
            def complete(self, *a, **k):
                raise AssertionError("已通过不应调用修复器")

        # 回归：用户「给出关键结论，不用画图」——强排除信号「不用」只作用于其后作用域
        # （画图），不应污染同句的「关键结论」（结论组须保留，不得标为已省略）。
        arts = {
            "task": "分析上半年销售额数据，给出关键结论，不用画图",
            "plan": '{"task":"分析","steps":["清洗","探索"],"acceptance":"三要素齐全"}',
            "code": (
                "# 上半年销售数据分析\n## 数据\n- 已剔除异常值\n"
                "## 趋势\n- Q2 环比 +27%\n## 关键结论\n- 华东区增长最快\n"
            ),
            "tests": "",
        }
        res = verify_and_fix(arts, NeverCalledEngine(), scenario="data-analysis")
        self.assertTrue(res["passed"])
        skipped = res.get("skipped") or []
        self.assertTrue(any("图表" in s for s in skipped))
        # 关键回归断言：结论组不得因「不用」信号被误判为省略
        self.assertFalse(any("结论" in s for s in skipped))
        self.assertFalse(any("数据" in s for s in skipped))
        self.assertFalse(any("趋势" in s for s in skipped))

    def test_check_structural_negation_aware_no_false_coverage(self):
        from synergyos.core.verify import _check_structural

        # 根治：交付物用「未包含风险」「未包含下周」话术规避，但用户未显式排除
        # → 风险/下周必须被判定为【缺失(issues)】，而非被裸子串匹配误判为已覆盖。
        code = "本周完成 x\n进行中 y\n（本报告未包含风险与下周计划，仅列前两项）"
        issues, skipped = _check_structural(code, "", "paas", task="帮我写份极简周报")
        self.assertFalse(skipped)  # 用户未排除 → 无 skipped
        self.assertTrue(any("风险" in s for s in issues))  # 风险正确判缺失
        self.assertTrue(any("下周" in s for s in issues))  # 下周正确判缺失
        # 本周完成 / 进行中 仍应判已覆盖（正文正常出现）
        self.assertFalse(any("本周" in s for s in issues))
        self.assertFalse(any("进行中" in s for s in issues))

    def test_check_structural_negation_aware_genuine_coverage_holds(self):
        from synergyos.core.verify import _check_structural

        # 反向保证：正文确有「风险与阻塞」标题时，应判已覆盖，不因否定感知误杀。
        code = "## 本周完成\n- 上线灰度\n## 进行中\n- 看板重构\n## 风险与阻塞\n- 联调延期已升级\n## 下周重点\n- 全量发布"
        issues, skipped = _check_structural(code, "", "paas", task="生成周报")
        self.assertFalse(issues)
        self.assertFalse(skipped)

    def test_check_structural_negation_aware_english(self):
        from synergyos.core.verify import _check_structural

        # 英文否定词也应触发否定感知：「no chart generated」不应算已覆盖图表。
        code = "df = pd.read_csv('sales.csv')\nq2_growth = 0.24  # no chart generated"
        issues, skipped = _check_structural(code, "", "biz", task="分析销售额")
        self.assertTrue(any("图表" in s for s in issues))  # 图表正确判缺失
        self.assertFalse(any("数据" in s for s in issues))  # 数据组命中 df/sales → 已覆盖


if __name__ == "__main__":
    unittest.main()
