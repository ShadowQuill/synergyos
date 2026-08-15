"""应用场景定义（Scenarios）。

同一套双脑协作内核，在不同领域里自适应。每个场景提供：
  · 元数据（标题 / 描述 / 默认任务提示）
  · 各角色的离线 mock 产出（architect / programmer / tester）

引擎在检测到 scenario 参数后，会按场景生成贴合领域的内容，
从而让「分工-协作-反思」在个人助理、商业分析、软件研发中真正落地。
接入真实大模型时，这些 mock 不再生效，改由提示词驱动真模型。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Scenario:
    key: str
    title: str
    desc: str
    task_hint: str
    # 结构化验收必备要素：每个子列表是一组「或」关系 token，交付物命中其一即算覆盖。
    # 仅 paas/biz 等无 pytest 可跑的场景使用（dev 走 pytest 实测）。
    verify_markers: List[List[str]] = field(default_factory=list)
    # 与 verify_markers 同序：每个要素组对应的「用户排除指代词」。当用户在任务中
    # 显式排除该要素（含排除信号 + 下列任一词）时，验收不再强制补全，仅诚实标注省略。
    # 留空则回退到 verify_markers 本身作为排除词。
    verify_excludes: List[List[str]] = field(default_factory=list)


SCENARIOS: Dict[str, Scenario] = {
    "paas": Scenario(
        "paas", "个人助理 · 周报生成",
        "根据你的写作风格自动汇总本周事项、生成周报；写作中途若检测到注意力分散，会主动暂停并保存草稿。",
        "整理本周工作并生成一份结构化周报",
        verify_markers=[
            ["本周完成", "本周工作", "本周进展", "本周总结"],
            ["进行中", "进行中事项", "在办"],
            ["风险", "阻塞", "问题", "风险与阻塞"],
            ["下周重点", "下周计划", "下周安排", "下周"]
        ],
        # 用户可能用来「排除」各要素的口语词（与 markers 同序）
        verify_excludes=[
            ["本周完成", "本周工作", "本周进展", "本周总结"],
            ["进行中", "在办"],
            ["风险", "阻塞", "问题", "风险与阻塞"],
            ["下周", "下周重点", "下周计划", "下周安排"]
        ],
    ),
    "biz": Scenario(
        "biz", "商业分析 · 数据可视化",
        "执行市场数据爬取、清洗、建模与可视化；右脑按你的审美偏好自动调整图表配色与排版。",
        "分析上半年销售额并生成可视化图表",
        verify_markers=[
            ["图表", "可视化", "chart", "柱状图", "折线图", "饼图", "plot", "render"],
            ["趋势", "增长", "环比", "同比", "建模", "模型"],
            ["数据", "销售额", "sales", "df", "清洗", "分析"]
        ],
        # 用户可能用来「排除」各要素的口语词（与 markers 同序）
        verify_excludes=[
            ["图表", "画图", "画", "可视化", "图", "柱状图", "饼图", "折线图", "配图"],
            ["趋势", "增长", "环比", "同比", "建模", "模型"],
            []  # 数据分析任务里「数据」要素几乎不会被用户排除，故不参与排除检测
        ],
    ),
    "dev": Scenario(
        "dev", "软件研发 · 需求到用例",
        "AI 架构师拆解需求 → AI 程序员编码 → AI 测试员生成用例，全程根据代码风格库自适应。",
        "实现去重并保持原顺序的函数",
    ),
    "code-review": Scenario(
        "code-review", "软件研发 · 代码评审",
        "对给定代码做智能诊脉：定位缺陷与风险点、标注严重性、给出可落地的修复建议与总体结论。",
        "审查这段去重函数并指出问题与改进",
        verify_markers=[
            ["问题清单", "问题", "缺陷", "风险点", "不足"],
            ["严重性", "严重", "severity", "等级", "优先级", "级别"],
            ["建议", "修复", "改进", "优化", "fix"],
            ["结论", "总体", "总结", "评价", "评审结论"],
        ],
        # 用户可能用来「排除」各要素的口语词（与 markers 同序）
        verify_excludes=[
            ["问题清单", "问题", "缺陷", "风险点"],
            ["严重性", "严重", "等级", "优先级", "级别"],
            ["建议", "修复建议", "修复", "改进", "优化"],
            ["结论", "总体", "总结", "评价"],
        ],
    ),
    "data-analysis": Scenario(
        "data-analysis", "商业分析 · 数据分析洞察",
        "对数据集做清洗与探索，提炼趋势、分布与关键结论；可视化图表为可选项（用户可要求省略）。",
        "分析上半年销售额并给出关键结论",
        verify_markers=[
            ["数据", "数据集", "样本", "df", "清洗", "预处理"],
            ["趋势", "增长", "下降", "环比", "同比", "分布", "波动"],
            ["结论", "洞察", "insight", "发现", "关键结论"],
            ["图表", "可视化", "chart", "图", "柱状图", "折线图"],
        ],
        # 用户可能用来「排除」各要素的口语词（与 markers 同序）
        verify_excludes=[
            [],  # 数据分析任务里「数据」要素几乎不会被用户排除，故不参与排除检测
            ["趋势", "增长", "下降", "环比", "同比", "分布"],
            ["结论", "洞察", "建议", "关键结论"],
            ["图表", "画图", "画", "可视化", "图", "柱状图", "饼图", "折线图"],
        ],
    ),
}

VALID_SCENARIOS = list(SCENARIOS.keys())


def get_scenario(key: Optional[str]) -> Optional[Scenario]:
    if not key:
        return None
    return SCENARIOS.get(key)


# ---------------- 离线 mock 产出（按场景 + 角色） ----------------

def mock_architect(scenario: str, task: str) -> str:
    if scenario == "paas":
        plan = {
            "task": task,
            "steps": [
                "收集本周待办 / 会议 / 进展",
                "按「有结构分点」风格组织为 4 个主题",
                "自检语气与排版一致性",
            ],
            "acceptance": "周报清晰分点、含风险与下周重点、且风格贴合用户偏好。",
            "style_hint": "遵循用户偏好：沟通风格=有结构分点。",
        }
    elif scenario == "biz":
        plan = {
            "task": task,
            "steps": [
                "爬取市场销售数据",
                "清洗异常值 / 缺失项",
                "建立上半年销售趋势模型",
                "生成可视化图表（科技蓝数据风）",
            ],
            "acceptance": "图表准确反映趋势，配色与排版符合审美偏好。",
            "style_hint": "图表配色遵循 科技蓝数据风。",
        }
    elif scenario == "code-review":
        plan = {
            "task": task,
            "steps": [
                "通读代码，定位缺陷与风险点",
                "按严重性分级（高 / 中 / 低）",
                "给出可落地的修复建议",
                "形成总体评审结论",
            ],
            "acceptance": "评审覆盖问题清单、严重性、修复建议与结论四个要素。",
            "style_hint": "遵循用户偏好：沟通风格=有结构分点。",
        }
    elif scenario == "data-analysis":
        plan = {
            "task": task,
            "steps": [
                "加载数据集并清洗异常值 / 缺失项",
                "探索趋势、分布与波动",
                "提炼关键结论与洞察",
                "（可选）生成可视化图表",
            ],
            "acceptance": "分析覆盖数据、趋势、关键结论三要素，图表为可选项。",
            "style_hint": "图表配色遵循 科技蓝数据风。",
        }
    else:  # dev
        plan = {
            "task": task,
            "steps": [
                "明确接口契约与边界条件",
                "选择数据结构与核心算法",
                "编写实现并处理异常分支",
                "补充单元测试与示例",
            ],
            "acceptance": "函数对典型与边界输入均返回正确结果，且有测试覆盖。",
            "style_hint": "遵循用户代码风格库（命名 / 注释 / 缩进）。",
        }
    return json.dumps(plan, ensure_ascii=False, indent=2)


def mock_programmer(scenario: str, task: str) -> str:
    if scenario == "paas":
        return (
            "# 周报 · 林晓明 第 32 周\n\n"
            "## 本周完成\n"
            "- 完成 Q3 路线图评审\n"
            "- 上线计费模块灰度\n"
            "- 修复 3 个 P1 缺陷\n\n"
            "## 进行中\n"
            "- 数据看板重构（70%）\n"
            "- 客户对账自动化（40%）\n\n"
            "## 风险 / 阻塞\n"
            "- 第三方支付联调延期，已升级协调\n\n"
            "## 下周重点\n"
            "- 计费全量发布\n"
            "- 看板联调\n"
            "- 对账试运行\n"
        )
    if scenario == "biz":
        return (
            "import pandas as pd\n\n"
            "# 1) 清洗：剔除异常值（销售额 < 0 或缺失）\n"
            "df = df[(df.sales >= 0) & df.sales.notna()]\n\n"
            "# 2) 建模：上半年销售额趋势（单位：万元）\n"
            "monthly = [42, 58, 51, 73, 69, 88]\n"
            "q2_growth = (monthly[-1] - monthly[-2]) / monthly[-2]  # 环比 +27%\n\n"
            "# 3) 可视化：科技蓝数据风柱状图（见 render_chart）\n"
            "render_chart(monthly, title='上半年销售额（万元）')\n"
        )
    if scenario == "code-review":
        return (
            "# 代码评审报告 · dedupe()\n\n"
            "## 问题清单\n"
            "- 未处理非可哈希元素（如 dict）的 TypeError 风险\n"
            "- 缺少对 None 输入的防御\n\n"
            "## 严重性\n"
            "- 非可哈希元素：高（运行时崩溃）\n"
            "- None 输入：中（需明确契约）\n\n"
            "## 修复建议\n"
            "- 入参加 `if not isinstance(items, (list, tuple))` 类型校验\n"
            "- 文档补充「元素需可哈希」约束\n\n"
            "## 结论\n"
            "整体实现简洁、时间复杂度 O(n)，建议补充类型校验后合入。\n"
        )
    if scenario == "data-analysis":
        return (
            "# 上半年销售数据分析\n\n"
            "## 数据\n"
            "- 样本：6 个月销售额（单位：万元），已剔除异常值\n"
            "- 数据口径一致，无缺失\n\n"
            "## 趋势\n"
            "- Q2 环比 +27%，整体呈上升态势\n"
            "- 6 月达峰值 88 万，波动可控\n\n"
            "## 关键结论\n"
            "- 增长主要来自华东区，建议加大投放\n"
            "- 下季度预估环比 +15%\n\n"
            "## 图表\n"
            "- 见附图：上半年销售额柱状图（科技蓝数据风）\n"
        )
    return _dev_code(task)


def mock_tester(scenario: str, task: str) -> str:
    if scenario == "paas":
        cases = [
            {"check": "语气符合偏好（有结构分点）", "result": "pass"},
            {"check": "无错别字", "result": "pass"},
            {"check": "排版一致", "result": "pass"},
            {"check": "风险与下周重点已标注", "result": "pass"},
        ]
    elif scenario == "biz":
        cases = [
            {"check": "数据口径一致（万元）", "result": "pass"},
            {"check": "无缺失 / 异常值", "result": "pass"},
            {"check": "图表渲染正确", "result": "pass"},
            {"check": "配色符合 科技蓝数据风", "result": "pass"},
        ]
    elif scenario == "code-review":
        cases = [
            {"check": "问题清单已列出", "result": "pass"},
            {"check": "严重性已分级", "result": "pass"},
            {"check": "修复建议可落地", "result": "pass"},
            {"check": "结论明确", "result": "pass"},
        ]
    elif scenario == "data-analysis":
        cases = [
            {"check": "数据口径一致", "result": "pass"},
            {"check": "趋势已刻画", "result": "pass"},
            {"check": "关键结论已提炼", "result": "pass"},
            {"check": "图表（如要求）已生成", "result": "pass"},
        ]
    else:  # dev
        fn = _dev_fn(task)
        cases = [
            {"case": f"{fn}([1,2,2,3])", "expect": "[1,2,3]"},
            {"case": f"{fn}(['a','a','b'])", "expect": "['a','b']"},
            {"case": f"{fn}([])", "expect": "[]"},
        ]
    return json.dumps({"cases": cases}, ensure_ascii=False, indent=2)


# ---------------- dev 场景的代码启发式（与默认引擎对齐） ----------------

def _dev_fn(task: str) -> str:
    low = task.lower()
    if any(w in low for w in ["斐波那契", "fibonacci", "fib"]):
        return "fibonacci"
    if any(w in low for w in ["去重", "dedup", "unique"]):
        return "dedupe"
    if any(w in low for w in ["排序", "sort"]):
        return "sort_arr"
    return "solve"


def _dev_code(task: str) -> str:
    fn = _dev_fn(task)
    if fn == "dedupe":
        return (
            "def dedupe(items):\n"
            "    \"\"\"去重并保持原顺序，兼容任意可哈希元素。\"\"\"\n"
            "    seen = set()\n"
            "    out = []\n"
            "    for it in items:\n"
            "        if it not in seen:\n"
            "            seen.add(it)\n"
            "            out.append(it)\n"
            "    return out\n"
        )
    if fn == "fibonacci":
        return (
            "def fibonacci(n):\n"
            "    \"\"\"返回斐波那契数列第 n 项（n>=0）。\"\"\"\n"
            "    if not isinstance(n, int) or n < 0:\n"
            "        raise ValueError(\"n 必须为非负整数\")\n"
            "    a, b = 0, 1\n"
            "    for _ in range(n):\n"
            "        a, b = b, a + b\n"
            "    return a\n"
        )
    return (
        f"def {fn}(items):\n"
        f"    \"\"\"{task.strip()} 处理并返回结果。\"\"\"\n"
        f"    return list(items)\n"
    )
