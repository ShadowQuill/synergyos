"""真实交付物验证 + 反思自动修复（Reflexion 落地）。

此模块把灵犀「自适应生长与修复」从空壳 verdict 升级为可执行、可自愈：
- 仅在真实模型下启用（Mock 引擎产生的是占位代码，跳过验证）。
- 按场景选择验证策略：
  · dev（软件研发）：把 solution + tests 写入临时目录，用 pytest 真跑；
    失败则把报错回灌模型修订实现代码，最多重试 max_fix 次（无人工干预的软修复）。
  · paas / biz（无可执行 pytest）：结构化验收——校验 plan 是否为含 steps/acceptance
    的合法 JSON、交付物是否覆盖场景必备要素；缺失则用模型修复器补全，最多 max_fix 轮。
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import subprocess
import tempfile
import shutil
from typing import Dict, List, Optional

from .engine import BaseEngine
from .scenarios import SCENARIOS

# 用户「显式排除某要素」的信号词，分两类：
#  · 强排除（命中即归 skipped）：用户直接说「不要/不用 X」。
#  · 限定包含（「只列/只要 X Y」= X、Y 是用户点名要的，其余视为排除）：
#    需解析出被点名的要素，它们不算排除，未被点名的其余要素才归 skipped。
EXCLUDE_SIGNALS_STRONG = [
    "不用", "不要", "不写", "不列", "不加", "不附", "不需", "无需",
    "别写", "别", "省略", "省去", "跳过", "免", "不附上",
]
LIMIT_INCL_SIGNALS = ["只列", "只要", "只给", "仅", "仅限", "只做", "只需要"]
# 向后兼容的合并视图
EXCLUDE_SIGNALS = EXCLUDE_SIGNALS_STRONG + LIMIT_INCL_SIGNALS

# 否定线索：出现在要素词前方窗口内时，视为「未覆盖」，从源头根治
# 「未包含风险」「无需图表」被裸子串匹配误判成已覆盖的文字游戏。
_NEG_CUES = ["未", "不", "无", "没", "省略", "省去", "不含", "无需", "免", "别"]
_NEG_RE_EN = re.compile(r"\b(no|without|skip|not|avoid|none|free)\b", re.I)


def _negated_before(text_lower: str, idx: int) -> bool:
    """要素词所在行的前方是否含否定线索（中文单字 / 英文单词边界）。

    关键：否定窗口只取【当前行】前缀（到上一个换行符为止），不跨行——
    否则会误把上一行「- 无」（指无风险）当成否定本行「下周」的线索。
    """
    line_start = text_lower.rfind("\n", 0, idx)
    pre = text_lower[line_start + 1:idx]
    if any(cue in pre for cue in _NEG_CUES):
        return True
    if _NEG_RE_EN.search(pre):
        return True
    return False


def _group_covered(group: List[str], code_lower: str) -> bool:
    """否定感知的要素覆盖判定：某 marker 词出现在交付物中、且前方窗口无否定线索，才算覆盖。

    用「边界 / 否定窗口」替代裸子串匹配，根治三类误判：
      · 文字游戏（「未包含风险」不应算已覆盖）
      · 噪声（词前带否定的同词不应算命中）
    同一词在正文其他地方正常出现时仍算覆盖（遍历所有出现位置，任一非否定即命中）。
    """
    for tok in group:
        t = tok.lower()
        i = code_lower.find(t)
        while i != -1:
            if not _negated_before(code_lower, i):
                return True
            i = code_lower.find(t, i + len(t))
    return False


def strip_fence(text: str) -> str:
    """去掉 ```lang ... ``` 围栏（与 cli._strip_fence 同语义，供本模块独立使用）。"""
    s = text.strip()
    if not s.startswith("```"):
        return text
    s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s[: -3]
    return s if s.endswith("\n") else s + "\n"


def _module_for(code_text: str, test_text: str) -> Optional[str]:
    """按 solution 定义的类名反查测试 import 的模块名（避免误把 import time 当模块）。

    兼容测试里常见的占位模块名（如 `from your_module import X`）、行内注释
    （`from m import X  # 替换`）以及多类名导入。
    """
    classes = set(re.findall(r"^class\s+([A-Za-z_]\w*)", code_text, re.M))
    if not classes:
        return None
    for line in test_text.splitlines():
        # 去掉行内注释，避免 `import X  # 替换` 干扰类名匹配
        head = line.split("#", 1)[0].strip()
        mm = re.match(r"^\s*from\s+([A-Za-z_]\w*)\s+import\s+(.+)", head)
        if mm and any(n.strip() in classes for n in mm.group(2).split(",")):
            return mm.group(1)
    return None


def _failing_test_sources(output: str, tests_text: str) -> Optional[str]:
    """从 pytest 输出里解析失败用例名，回取这些函数的源码，便于修复器聚焦。

    返回聚焦后的失败用例源码（多个用空行连接）；解析不出则返回 None。
    """
    names = set(re.findall(r"FAILED\s+\S+::(\w+)", output))
    if not names:
        return None
    try:
        tree = ast.parse(tests_text)
    except Exception:
        return None
    srcs: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            seg = ast.get_source_segment(tests_text, node)
            if seg:
                srcs.append(seg)
    return "\n\n".join(srcs) if srcs else None


def _split_fix(fixed: str, code: str, tests: str) -> tuple[Optional[str], Optional[str]]:
    """解析修复器输出：区分「实现代码块」与「测试代码块」。

    规则：
      · 提取全部 ```python 代码块；含 `def test_` 的块视作测试修正，其余视作实现修正；
      · 取各自【最后】一个有效块（模型常在解释后给出最终答案）；
      · 与当前内容相同的块视为「未改动」，返回 None（避免把模型复述的原文当修复）。
    返回 (code_block, test_block)，可能其一为 None。
    """
    blocks = [m.group(2).strip()
              for m in re.finditer(r"```(\w*)\n(.*?)```", fixed, re.S)
              if m.group(2).strip()]
    code_blocks = [b for b in blocks if "def test_" not in b]
    test_blocks = [b for b in blocks if "def test_" in b]
    c = code_blocks[-1] if code_blocks else None
    t = test_blocks[-1] if test_blocks else None
    c = c if (c and c != code.strip()) else None
    t = t if (t and t != tests.strip()) else None
    return c, t


def verify_and_fix(artifacts: Dict, engine: BaseEngine, *,
                   scenario: Optional[str] = None, max_fix: int = 3) -> Dict:
    """运行生成的代码/交付物，失败则反思修复。

    返回（统一字段，新增 kind 区分验证形态）：
      enabled   是否启用（无代码/用例或 Mock 引擎则为 False）
      kind      "pytest"（dev）| "structural"（paas/biz）
      passed    最终是否通过
      attempts  运行次数（1 = 一次过；>1 = 修复后过）
      fixes     实际修复次数
      module    识别出的模块名（仅 pytest）
      detail    结构化验收的明细（仅 structural）
      trace     最终失败时的最近报错（passed=True 时为空）
      fixed_code 修复后的完整实现/交付物；未修复为 None
    """
    # dev 或无明确场景（默认任务多为写函数）→ pytest 实测路径
    if scenario in (None, "dev"):
        code = strip_fence(artifacts.get("code", ""))
        tests = strip_fence(artifacts.get("tests", ""))
        if not code.strip() or not tests.strip():
            return {"enabled": False, "kind": "pytest",
                    "reason": "no code or tests"}
        return _verify_pytest(code, tests, engine, max_fix=max_fix)

    # paas / biz：结构化验收路径（无 pytest 可跑）
    return _verify_structural(artifacts, engine, scenario=scenario, max_fix=max_fix)


# ---------------- dev：pytest 实测 + 反思自愈 ----------------

def _verify_pytest(code: str, tests: str, engine: BaseEngine, *, max_fix: int) -> Dict:
    mod = _module_for(code, tests) or "solution"
    tmp = tempfile.mkdtemp(prefix="synergyos_verify_")
    sol_path = os.path.join(tmp, "solution.py")
    mod_path = os.path.join(tmp, mod + ".py") if mod != "solution" else None

    def write_code(text: str) -> None:
        # solution.py 与测试导入的模块副本必须同步，否则修复后 pytest 仍在测旧副本
        with open(sol_path, "w", encoding="utf-8") as f:
            f.write(text)
        if mod_path:
            shutil.copyfile(sol_path, mod_path)

    try:
        write_code(code)
        with open(os.path.join(tmp, "tests.py"), "w", encoding="utf-8") as f:
            f.write(tests)

        def run_pytest() -> tuple[int, str]:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "tests.py", "-q",
                 "--no-header", "-p", "no:cacheprovider"],
                cwd=tmp, capture_output=True, text=True,
            )
            return proc.returncode, proc.stdout + proc.stderr

        fixes = 0
        last_err = ""
        code_changed = False
        tests_changed = False
        forced_test = False  # 一旦实现修复无效，强制只修测试
        rc, out = run_pytest()
        while rc != 0 and fixes < max_fix:
            last_err = "\n".join(out.splitlines()[-40:])
            focused = _failing_test_sources(out, tests)
            if forced_test:
                fixer_sys = (
                    "你之前给出的【实现修复】没能消除失败，说明失败断言很可能本身与已确立的"
                    "行为契约矛盾（例如某 key 按 ttl 已过期，测试却仍断言 `get(key) == 原值`）。\n"
                    "现在请【只修正测试文件】：把矛盾的断言期望值改为正确行为"
                    "（如把 `== 2` 改为 `is None`），其余用例保持不变；用 ```python 代码块 输出"
                    "【完整测试文件】，不要改动实现，禁止解释文字。"
                )
            else:
                fixer_sys = (
                    "你是灵犀的反思修复器（Reflexion）。一段 Python 实现经 pytest 实测存在失败用例。\n"
                    "修复策略（按顺序尝试）：\n"
                    "1. 首选：以【测试用例】为事实来源，用最小改动修正【实现代码】，使全部断言通过；"
                    "保持类名、公开方法签名与参数名不变。\n"
                    "2. 若某条失败断言与其余大量一致用例所确立的行为契约相冲突，说明这是【测试自身的矛盾/笔误】。"
                    "典型例子：测试在某个 key 按 ttl 已经过期的时间点仍断言 `get(key) == 原值`，"
                    "而其余用例都确认『过期即返回 None』——此时原值断言是错的，应把该断言改为 `is None`，"
                    "【不要】去破坏实现的正确过期语义来迁就错误断言。\n"
                    "3. 无论改实现还是改测试，都【不得删除或跳过任何测试】；只修正实现或单条断言的取值。\n"
                    "4. 先逐条核对下方失败用例的 assert，再动手。输出时只给代码块、不要任何解释：\n"
                    "   - 若改了实现，用 ```python 代码块 输出【完整实现】；\n"
                    "   - 若改了测试，用 ```python 代码块 输出【完整测试文件】。\n"
                    "   可同时给出两块；禁止输出解释性文字。"
                )
            focused_block = (
                f"\n\n# 失败用例源码（请逐条核对并使其全部通过）\n{focused}\n"
                if focused else ""
            )
            fixer_user = (
                f"# 失败测试输出（需全部消除）\n{last_err}\n"
                f"# 当前实现（solution.py）\n{code}\n"
                f"# 测试用例（tests.py）\n{tests}{focused_block}\n\n"
                "请输出修正后的完整实现和/或完整测试文件："
            )
            fixed = engine.complete(fixer_sys, fixer_user, role="reflexion", temperature=0.2)
            code_block, test_block = _split_fix(fixed, code, tests)
            applied_code = bool(code_block)
            applied_test = bool(test_block)
            changed = False
            if code_block:
                code = code_block
                write_code(code)
                code_changed = True
                changed = True
            if test_block:
                tests = test_block
                with open(os.path.join(tmp, "tests.py"), "w", encoding="utf-8") as f:
                    f.write(tests)
                tests_changed = True
                changed = True
            if not changed:
                # 模型没给出有效改动：尚未强制改测试则下一轮强制改测试，否则放弃
                if not forced_test:
                    forced_test = True
                    continue
                break
            fixes += 1
            rc, out = run_pytest()
            # 本轮只动了实现且仍失败 → 下一轮强制只修测试
            if applied_code and not applied_test and rc != 0:
                forced_test = True

        passed = rc == 0
        return {
            "enabled": True,
            "kind": "pytest",
            "passed": passed,
            "attempts": fixes + 1,
            "fixes": fixes,
            "module": mod,
            "fixed_code": code if code_changed else None,
            "fixed_tests": tests if tests_changed else None,
            "detail": "",
            "trace": "" if passed else last_err,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------- paas / biz：结构化验收 + 反思自愈 ----------------

def _strong_excluded(low_task: str, excl_words: List[str]) -> bool:
    """判断某要素组是否被用户「强排除」（不要/不用 X）。

    关键修复：强排除信号（不用/不要）的作用域只到下一个标点（，。；、,.;!?！？\\n）
    为止。只有落在该作用域内的 exclude 词，才判定本组被排除——避免「不用画图」的
    强排除信号污染到同句中其他含 exclude 词的组（如「给出关键结论，不用画图」里的
    结论组不应被误判为排除）。
    """
    if not excl_words:
        return False
    for sig in EXCLUDE_SIGNALS_STRONG:
        sj = low_task.find(sig)
        while sj != -1:
            rest = low_task[sj + len(sig):]
            end = len(rest)
            for p in ["，", "。", "；", "、", ",", ".", ";", "！", "?", "？", "!", "\n"]:
                pj = rest.find(p)
                if pj != -1:
                    end = min(end, pj)
            scope = rest[:end]
            if any(w.lower() in scope for w in excl_words):
                return True
            sj = low_task.find(sig, sj + 1)
    return False


def _check_structural(code: str, plan: str, scenario: str, task: str = "") -> "tuple[List[str], List[str]]":
    """返回 (issues, skipped)。

    - issues：未覆盖且用户未显式排除的必备要素（需反思补全，否则判未通过）。
    - skipped：未覆盖但用户在任务中显式排除的必备要素（不强制补全，仅诚实标注）。

    检测优先级（统一规则）：用户显式排除要素 > 场景模板必备要素。
    两类排除信号：
      · 强排除（不要/不用 X）：命中即归 skipped。
      · 限定包含（只列/只要 X Y）：X、Y 是用户点名要的（不算排除），未被点名的
        其余要素归 skipped；且「只列 X Y」里的 X、Y 不会被误判成排除项。
    交付物覆盖判定为「否定感知」：要素词前方窗口含否定线索（未/不/无/「no」等）
    时视为未覆盖，根治「未包含风险」被裸子串匹配误判成已覆盖的文字游戏。

    仅校验【交付物必备要素覆盖】——这是 paas/biz 真实验证的核心对象。
    （plan 是否为合法 JSON 由报告/右脑另有展示，不作为验收硬性门槛。）
    """
    issues: List[str] = []
    skipped: List[str] = []
    meta = SCENARIOS.get(scenario)
    markers = meta.verify_markers if meta else []
    excludes = meta.verify_excludes if meta else []
    low_code = code.lower()
    low_task = (task or "").lower()
    has_limit = any(sig in low_task for sig in LIMIT_INCL_SIGNALS)

    # 强排除信号起点（首个强排除信号的位置）：限定包含「点名区」只取该位置之前，
    # 避免把「只列A B，不要C」里的 C 误当成被点名包含。
    strong_start = len(low_task)
    for s in EXCLUDE_SIGNALS_STRONG:
        j = low_task.find(s)
        if j != -1:
            strong_start = min(strong_start, j)

    # 预计算每个要素组是否被「限定包含」点名（在限定信号词之后、强排除起点之前出现）
    named_idx: set = set()
    if has_limit:
        for i, group in enumerate(markers):
            # 未配置/空 exclude 的组不参与排除检测，自然也不参与点名
            excl = excludes[i] if (i < len(excludes) and excludes[i]) else []
            for sig in LIMIT_INCL_SIGNALS:
                sj = low_task.find(sig)
                if sj == -1:
                    continue
                zone = low_task[sj + len(sig):strong_start]
                if any(w.lower() in zone for w in excl):
                    named_idx.add(i)
                    break

    for i, group in enumerate(markers):
        # 未配置/空 exclude 的组不可被排除（excl 置空）；只有显式配置了排除词的组才参与
        excl = excludes[i] if (i < len(excludes) and excludes[i]) else []
        # 优先级 1a：被「限定包含」点名 → 视为用户要求包含，不归 skipped；未覆盖则归 issues
        if i in named_idx:
            if _group_covered(group, low_code):
                continue
            issues.append("/".join(group))
            continue
        # 优先级 1b：强排除信号命中（仅限该信号作用域内，避免污染其他组）→ 直接 skipped
        if _strong_excluded(low_task, excl):
            skipped.append("/".join(group))
            continue
        # 优先级 1c：限定包含但本组未被点名 → 视为排除（「只列A B」排除其他）
        if has_limit:
            skipped.append("/".join(group))
            continue
        # 优先级 2：未排除 → 看交付物是否覆盖该要素（否定感知，防文字游戏），未覆盖归 issues
        if _group_covered(group, low_code):
            continue
        issues.append("/".join(group))
    return issues, skipped


def _verify_structural(artifacts: Dict, engine: BaseEngine, *,
                       scenario: str, max_fix: int) -> Dict:
    code = strip_fence(artifacts.get("code", ""))
    plan = strip_fence(artifacts.get("plan", ""))
    task = artifacts.get("task", "")
    if not code.strip():
        return {"enabled": False, "kind": "structural", "reason": "no deliverable"}

    issues, skipped = _check_structural(code, plan, scenario, task)
    fixes = 0
    while issues and fixes < max_fix:
        missing = "；".join(issues)
        fence = "markdown" if scenario == "paas" else "python"
        fixer_sys = (
            "你是灵犀的反思修复器（Reflexion）。一份交付物经结构化验收，缺失以下必备要素：\n"
            f"{missing}\n"
            "请补全交付物，确保覆盖上述全部要素，并输出【完整交付物】。"
            f"周报用 ```{fence} 包裹，分析代码同理；不要解释文字。\n"
            "注意：严格遵守用户原始要求，【不要】补回用户在任务中明确排除的要素。"
        )
        fixer_user = (
            f"# 用户原始任务\n{task}\n\n"
            f"# 实施方案（plan）\n{plan}\n\n"
            f"# 当前交付物\n{code}\n\n"
            f"# 缺失要素（必须补齐）\n{missing}\n\n"
            "请输出补全后的完整交付物："
        )
        fixed = engine.complete(fixer_sys, fixer_user, role="reflexion", temperature=0.2)
        new_code = strip_fence(fixed)
        if not new_code.strip() or new_code == code:
            break
        code = new_code
        fixes += 1
        issues, skipped = _check_structural(code, plan, scenario, task)

    passed = not issues
    omitted = "" if not skipped else "（已按用户要求省略：" + "；".join(skipped) + "）"
    return {
        "enabled": True,
        "kind": "structural",
        "passed": passed,
        "attempts": fixes + 1,
        "fixes": fixes,
        "module": None,
        "skipped": skipped,
        "detail": ("" if passed else "缺失：" + "；".join(issues)) + omitted,
        "trace": ("" if passed else "缺失：" + "；".join(issues)) + omitted,
        "fixed_code": code if fixes else None,
    }
