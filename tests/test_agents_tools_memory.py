"""灵犀 SynergyOS · 新能力单元测试（零依赖）。

覆盖 P0 三项改进：
  · agents/ 独立 Agent 类（architect / programmer / tester / observer / arbitrator）
  · 工具接口（MCP 风格、零依赖）：Tool / ToolRegistry / ToolExecutor
  · 语义记忆层（SemanticMemory）：TF-IDF 检索

运行：
  python3 -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

# 测试全程强制 Mock 引擎：即便项目根 .env 含真实 Key，也不触发真实 API 调用。
os.environ["SYNERGYOS_FORCE_MOCK"] = "1"

from synergyos.core.engine import MockEngine, ENGINE
from synergyos.core.bus import EventBus, EventType
from synergyos.core.profile import UserProfile
from synergyos.agents import (
    ArchitectAgent, ProgrammerAgent, TesterAgent, ObserverAgent, Arbitrator,
    LeftArtifacts, Observation, scenario_prompts,
)
from synergyos.agents.tools import Tool, ToolRegistry, ToolExecutor, make_builtin_tools
from synergyos.core.memory import SemanticMemory, tokenize


class TestAgents(unittest.TestCase):
    def test_architect_produces_plan(self):
        a = ArchitectAgent(MockEngine())
        plan = a.act("实现去重函数", UserProfile())
        self.assertTrue(plan.strip())

    def test_programmer_act_backward_compatible(self):
        # 无工具路径必须与原 brain.LeftBrain 行为一致（返回非空代码）
        p = ProgrammerAgent(MockEngine())
        code = p.act("实现去重函数", '{"task":"x"}', UserProfile(), scenario="dev")
        self.assertIn("dedupe", code)

    def test_programmer_act_with_tools_runs_tool_loop_offline(self):
        # 离线：MockEngine 在 allow_tools 下返回 web_search 调用，
        # ToolExecutor 执行后程序员再产出最终代码（工具闭环跑通）。
        tools = make_builtin_tools()
        p = ProgrammerAgent(MockEngine(), bus=EventBus())
        code = p.act_with_tools("分析销售额趋势", '{"task":"x"}', UserProfile(),
                                scenario="biz", tools=tools)
        self.assertTrue(code.strip())
        # 工具执行应在总线上留下痕迹
        names = [e.source for e in p.bus.history()]
        self.assertIn("programmer", names)

    def test_tester_produces_tests(self):
        t = TesterAgent(MockEngine())
        tests = t.act("实现去重函数", "def dedupe(items): pass", UserProfile(), scenario="dev")
        self.assertTrue(tests.strip())

    def test_observer_returns_observation(self):
        o = ObserverAgent(MockEngine())
        obs = o.observe("task", LeftArtifacts(plan="x", code="y", tests="z"), UserProfile())
        self.assertIsInstance(obs.satisfaction, float)
        self.assertGreaterEqual(obs.satisfaction, 0.0)

    def test_arbitrator_decides(self):
        arb = Arbitrator(bus=EventBus())
        good = arb.decide(LeftArtifacts(), Observation(satisfaction=0.9))
        self.assertFalse(good["should_revise"])
        bad = arb.decide(LeftArtifacts(), Observation(satisfaction=0.5))
        self.assertTrue(bad["should_revise"])

    def test_scenario_prompts_dev_specialized(self):
        arch, code, test = scenario_prompts("dev", UserProfile(), "")
        self.assertIn("架构师", arch)
        self.assertIn("pytest", test)


class TestTools(unittest.TestCase):
    def test_tool_invoke_is_safe_on_error(self):
        def boom(**kwargs):
            raise RuntimeError("x")
        reg = ToolRegistry().register(Tool("boom", "报错工具", {"type": "object", "properties": {}}, boom))
        ex = ToolExecutor(reg)
        res = ex.run_one("boom", {})
        self.assertFalse(res["ok"])
        self.assertIn("tool_error", res["error"])

    def test_unknown_tool(self):
        ex = ToolExecutor(ToolRegistry())
        res = ex.run_one("nope", {})
        self.assertFalse(res["ok"])
        self.assertIn("未知工具", res["error"])

    def test_parse_and_execute_tool_call(self):
        reg = make_builtin_tools()
        ex = ToolExecutor(reg)
        text = '先看下文件：<tool_call>{"name": "read_file", "arguments": {"path": "/tmp/x.txt"}}</tool_call>'
        calls = ex.parse_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "read_file")
        results, ran = ex.execute(text)
        self.assertTrue(ran)
        self.assertEqual(results[0]["name"], "read_file")
        self.assertIn("不存在", results[0]["output"])

    def test_no_tool_call_returns_empty(self):
        ex = ToolExecutor(make_builtin_tools())
        results, ran = ex.execute("没有任何工具调用的一串普通文本")
        self.assertFalse(ran)
        self.assertEqual(results, [])

    def test_builtin_read_write_roundtrip(self):
        reg = make_builtin_tools()
        ex = ToolExecutor(reg)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.txt")
            w = ex.run_one("write_file", {"path": path, "content": "hello 灵犀"})
            self.assertTrue(w["ok"])
            r = ex.run_one("read_file", {"path": path})
            self.assertIn("hello 灵犀", r["output"])

    def test_builtin_web_search_is_offline_stub(self):
        reg = make_builtin_tools()
        r = ToolExecutor(reg).run_one("web_search", {"query": "双脑协作"})
        self.assertIn("离线模拟", r["output"])

    def test_catalogue_and_schema(self):
        reg = make_builtin_tools()
        self.assertIn("read_file", reg.catalogue())
        schema = reg.schema_json()
        self.assertIn("web_search", schema)


class TestSemanticMemory(unittest.TestCase):
    def test_tokenize_chinese_bigram(self):
        toks = tokenize("灵犀自进化协作智能体")
        self.assertIn("灵·犀", toks)
        self.assertIn("自·进", toks)

    def test_retrieve_ranks_relevant(self):
        mem = SemanticMemory()
        mem.add("灵犀采用双脑协作架构，左脑负责执行，右脑负责观察", doc_id="a")
        mem.add("今天天气晴朗，适合散步", doc_id="b")
        mem.add("语义记忆层用 TF-IDF 做关键词检索，支持中文 bigram 分词", doc_id="c")
        hits = mem.retrieve("双脑协作架构怎么工作", top_k=2)
        self.assertTrue(hits)
        top_id = hits[0][0].doc_id
        self.assertEqual(top_id, "a")  # 最相关的是双脑协作那条

    def test_retrieve_empty_when_no_docs(self):
        self.assertEqual(SemanticMemory().retrieve("x"), [])

    def test_context_returns_text(self):
        mem = SemanticMemory()
        mem.add_many(["苹果是一种水果", "Python 是编程语言", "火箭用于航天"])
        ctx = mem.context("我想学编程语言", top_k=1)
        self.assertIn("Python", ctx)

    def test_save_and_load_roundtrip(self):
        mem = SemanticMemory()
        mem.add("灵犀是自进化协作智能体", doc_id="k1", meta={"tag": "agent"})
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mem.json")
            mem.save(path)
            loaded = SemanticMemory.load(path)
            self.assertEqual(len(loaded.docs), 1)
            self.assertIn("灵犀", loaded.context("自进化"))


if __name__ == "__main__":
    unittest.main()
