"""灵犀 SynergyOS · 软学习闭环 与 量化评测 单元测试（零依赖、可离线）。

覆盖改进报告 P1#4（软学习）与 P1#5（量化评测）：
  · ExperienceStore：记录 / 相似检索 / 持久化 roundtrip
  · FailureLibrary.build_fewshot：相似历史经验注入文本
  · WeightStore：反思权重跨会话持久化
  · eval.run_eval：离线确定性评测 + 经验召回率统计

运行：
  python3 -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

# 测试全程强制 Mock 引擎：即便项目根 .env 含真实 Key，也不触发真实 API 调用。
os.environ["SYNERGYOS_FORCE_MOCK"] = "1"

from synergyos.core.learning import (
    Experience, ExperienceStore, FailureLibrary, WeightStore,
)
from synergyos.eval import run_eval, print_report
from synergyos import SynergyOS


class TestExperienceStore(unittest.TestCase):
    def test_record_and_count(self):
        s = ExperienceStore()
        s.record(Experience(ts=1.0, task="实现去重", scenario="dev", success=True,
                             failure_type=None, tools_used=["read_file"], feedback=""))
        self.assertEqual(len(s.items), 1)
        self.assertEqual(len(s.failures()), 0)

    def test_retrieve_similar_by_overlap(self):
        s = ExperienceStore()
        s.record(Experience(ts=1.0, task="实现去重函数", scenario="dev", success=False,
                             failure_type="missing_required", tools_used=[], feedback="漏了要素"))
        s.record(Experience(ts=2.0, task="今天天气好", scenario="biz", success=True,
                             failure_type=None, tools_used=[], feedback=""))
        hits = s.retrieve_similar("写个去重并排序的函数", top_k=1)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].task, "实现去重函数")

    def test_retrieve_returns_empty_when_no_overlap(self):
        s = ExperienceStore()
        s.record(Experience(ts=1.0, task="实现去重函数", scenario="dev", success=True,
                             failure_type=None, tools_used=[], feedback=""))
        self.assertEqual(s.retrieve_similar("天气晴朗适合散步", top_k=3), [])

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "exp.json")
            s = ExperienceStore(path)
            s.record(Experience(ts=1.5, task="t", scenario="dev", success=False,
                                 failure_type="tool_error", tools_used=["write_file"],
                                 feedback="路径越界", notes="沙箱拒绝"))
            # 重新从磁盘加载（模拟重启）
            s2 = ExperienceStore(path)
            self.assertEqual(len(s2.items), 1)
            e = s2.items[0]
            self.assertEqual(e.task, "t")
            self.assertFalse(e.success)
            self.assertEqual(e.failure_type, "tool_error")
            self.assertEqual(e.tools_used, ["write_file"])

    def test_load_nonexistent_keeps_empty(self):
        s = ExperienceStore("/no/such/path/exp.json")
        self.assertEqual(s.items, [])


class TestFailureLibrary(unittest.TestCase):
    def test_build_fewshot_empty_when_no_history(self):
        self.assertEqual(FailureLibrary.build_fewshot(ExperienceStore(), "x"), "")

    def test_build_fewshot_injects_failure_advice(self):
        s = ExperienceStore()
        s.record(Experience(ts=1.0, task="实现去重", scenario="dev", success=False,
                             failure_type="missing_required", tools_used=[],
                             feedback="漏了用户要求的要素"))
        few = FailureLibrary.build_fewshot(s, "写一个去重函数")
        self.assertIn("相似失败教训", few)
        self.assertIn("missing_required", few)
        self.assertIn("漏了用户要求的要素", few)

    def test_build_fewshot_injects_success_case(self):
        s = ExperienceStore()
        s.record(Experience(ts=1.0, task="实现去重", scenario="dev", success=True,
                             failure_type=None, tools_used=["read_file"], feedback=""))
        few = FailureLibrary.build_fewshot(s, "写一个去重函数")
        self.assertIn("相似成功案例", few)
        self.assertIn("read_file", few)


class TestWeightStore(unittest.TestCase):
    def test_load_default_when_missing(self):
        w = WeightStore.load("/no/such/weights.json")
        self.assertEqual(w, WeightStore.DEFAULT_WEIGHTS)

    def test_save_load_roundtrip_merges(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "weights.json")
            custom = dict(WeightStore.DEFAULT_WEIGHTS)
            custom["programmer"] = 1.3
            WeightStore.save(path, custom)
            loaded = WeightStore.load(path)
            self.assertEqual(loaded["programmer"], 1.3)
            # 其余保持默认
            self.assertEqual(loaded["architect"], 1.0)


class TestEvalRunner(unittest.TestCase):
    def test_run_eval_mock_deterministic_with_learning(self):
        with tempfile.TemporaryDirectory() as d:
            rep = run_eval(learning_dir=d)
            self.assertFalse(rep["engine_real"])  # Mock 离线
            self.assertEqual(rep["pass1"]["n"], 7)
            # 第二轮开启 → 经验召回率应为 1.0（所有用例都检索到首轮历史经验）
            self.assertIn("pass2", rep)
            self.assertEqual(rep["experience_recall"], 1.0)
            # 完整率与满意度都应落在合理区间
            self.assertGreaterEqual(rep["pass1"]["mean_completeness"], 0.0)
            self.assertLessEqual(rep["pass1"]["mean_completeness"], 1.0)

    def test_run_eval_report_is_printable(self):
        with tempfile.TemporaryDirectory() as d:
            rep = run_eval(learning_dir=d)
            text = print_report(rep)
            self.assertIn("量化评测报告", text)
            self.assertIn("经验召回率", text)

    def test_eval_without_learning_no_pass2(self):
        rep = run_eval(learning_dir=None)
        self.assertNotIn("pass2", rep)
        self.assertNotIn("experience_recall", rep)


class TestEngineEnvOverride(unittest.TestCase):
    """真实引擎的端点/模型必须尊重环境变量（回归：曾拿 DeepSeek Key 打 api.openai.com）。"""

    def setUp(self):
        self._backup = {k: os.environ.get(k) for k in
                        ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
                         "SYNERGYOS_BASE_URL", "SYNERGYOS_MODEL", "DEEPSEEK_API_KEY")}

    def tearDown(self):
        for k, v in self._backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_openai_provider_respects_openai_base_url_and_model(self):
        from synergyos.core.engine import create_engine
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["OPENAI_BASE_URL"] = "https://api.deepseek.com/v1"
        os.environ["OPENAI_MODEL"] = "deepseek-chat"
        eng = create_engine("openai")
        self.assertEqual(eng.cfg.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(eng.cfg.model, "deepseek-chat")

    def test_generic_env_override_applies_to_any_provider(self):
        from synergyos.core.engine import create_engine
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        os.environ["SYNERGYOS_BASE_URL"] = "http://127.0.0.1:11434/v1"
        os.environ["SYNERGYOS_MODEL"] = "local-model"
        eng = create_engine("deepseek")
        self.assertEqual(eng.cfg.base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(eng.cfg.model, "local-model")

    def test_openai_env_does_not_leak_into_deepseek_preset(self):
        from synergyos.core.engine import create_engine
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        os.environ["OPENAI_BASE_URL"] = "https://api.openai.com/v1"
        os.environ["OPENAI_MODEL"] = "gpt-4o-mini"
        eng = create_engine("deepseek")
        self.assertEqual(eng.cfg.base_url, "https://api.deepseek.com")
        self.assertEqual(eng.cfg.model, "deepseek-chat")

    def test_eval_defaults_to_mock_even_with_real_key_in_env(self):
        # 评测基准必须确定性、零 token：即便环境里有真实 Key，也不得走真实引擎
        os.environ["OPENAI_API_KEY"] = "sk-test"
        rep = run_eval(learning_dir=None)
        self.assertFalse(rep["engine_real"])


class TestLearningIntegration(unittest.TestCase):
    def test_synergyos_records_experience(self):
        with tempfile.TemporaryDirectory() as d:
            ws = os.path.join(d, "ws")
            os.makedirs(ws, exist_ok=True)
            tools = __import__("synergyos.agents.tools", fromlist=["make_builtin_tools"]).make_builtin_tools(workspace=ws)
            os_ = SynergyOS(tools=tools, learning_dir=os.path.join(d, "learn"))
            os_.run("实现快速排序函数", scenario="dev")
            # 经验库落盘
            self.assertEqual(len(os_.experience_store.items), 1)
            e = os_.experience_store.items[0]
            self.assertEqual(e.scenario, "dev")
            self.assertTrue(e.success)
            # 第二轮相似性检索应能命中
            few = FailureLibrary.build_fewshot(os_.experience_store, "实现排序函数")
            self.assertIn("相似成功案例", few)

    def test_verification_follows_instance_engine_not_module_default(self):
        """回归：验证/自愈应看实例引擎，模块级默认引擎为真实时也不得越权触发。"""
        from synergyos.core import orchestrator as orch
        from synergyos.core.engine import MockEngine

        class _FakeReal(MockEngine):
            def is_real(self):
                return True

        original = orch.ENGINE
        orch.ENGINE = _FakeReal()
        try:
            res = SynergyOS(engine=MockEngine()).run("实现快速排序函数", scenario="dev")
            self.assertIsNone(res.get("verification"))
        finally:
            orch.ENGINE = original


if __name__ == "__main__":
    unittest.main()
