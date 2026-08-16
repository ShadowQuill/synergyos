"""量化评测运行器（Eval Runner，零依赖、可离线）。

用法：
  from synergyos.eval import run_eval, print_report
  rep = run_eval(learning_dir=".eval_cache")   # Mock 引擎确定性评测
  print_report(rep)

指标（让「自进化收益」可被量化，对应报告 P1#5）：
  · 必备要素完整率  —— 结构化验收（paas/biz）或关键子串（dev）覆盖比例
  · 满意度均值      —— 右脑观察者评分
  · 反思自愈成功率  —— 仅在真实引擎 + 验证启用时统计（Mock 下标记 n/a）
  · 经验召回率      —— 开启 learning 时，第二轮复跑有多少用例检索到了相似历史经验
                       （直接量化「语义记忆层 + 失败模式库」的覆盖能力）

评测默认走 Mock 引擎，零 token、可 CI 复跑；传入真实 engine 即自动启用自进化收益对比。
"""
from __future__ import annotations

import os
import tempfile
from typing import Dict, List, Optional

from ..core.engine import BaseEngine, MockEngine
from ..core.verify import _check_structural
from ..agents.tools import make_builtin_tools
from ..core.orchestrator import SynergyOS
from ..core.learning import FailureLibrary
from .cases import EVAL_CASES


def _completeness(artifacts: Dict, case: Dict) -> float:
    """计算单条用例的必备要素完整率（0~1）。"""
    scenario = case.get("scenario")
    code = artifacts.get("code", "") or ""
    plan = artifacts.get("plan", "") or ""
    if scenario in ("paas", "biz"):
        issues, skipped = _check_structural(
            code, plan, scenario, task=case.get("task", ""))
        # 用空交付物得到「全部必备要素总数」，据此计算覆盖比例
        base_issues, base_skipped = _check_structural("", "", scenario, task=case.get("task", ""))
        total = len(base_issues) + len(base_skipped)
        covered = total - len(issues) - len(skipped)
        if total == 0:
            return 1.0
        return max(0.0, covered / (total - len(skipped)))
    # dev / code-review / data-analysis：关键子串覆盖
    required = case.get("required") or []
    if not required:
        return 1.0 if code.strip() else 0.0
    hay = (code + "\n" + plan).lower()
    cov = sum(1 for r in required if r.lower() in hay)
    return cov / len(required)


def _run_once(cases: List[Dict], engine: BaseEngine, learning_dir: Optional[str],
              workspace: str) -> List[Dict]:
    tools = make_builtin_tools(workspace=workspace) if learning_dir else None
    results = []
    for c in cases:
        os_ = SynergyOS(engine=engine, tools=tools,
                        learning_dir=learning_dir)
        res = os_.run(c["task"], scenario=c.get("scenario"))
        art = res["artifacts"]
        results.append({
            "id": c["id"],
            "scenario": c.get("scenario"),
            "completeness": _completeness(art, c),
            "satisfaction": res.get("satisfaction") or 0.0,
            "verification": res.get("verification"),
            "task": c["task"],
        })
    return results


def run_eval(engine: Optional[BaseEngine] = None,
             learning_dir: Optional[str] = None,
             cases: Optional[List[Dict]] = None,
             two_pass: bool = True) -> Dict:
    """运行评测，返回量化报告字典。

    two_pass=True 且 learning_dir 给定时，会复跑第二轮并统计经验召回率。
    """
    # 默认强制 Mock：基准需确定性 + 零 token，不受本机 .env / 环境变量里的
    # 真实 Key 影响（真实引擎评测请显式传入 engine=build_engine()）。
    engine = engine or MockEngine()
    cases = cases or EVAL_CASES
    tmp_ws = tempfile.mkdtemp(prefix="synergyos_eval_ws_")

    pass1 = _run_once(cases, engine, learning_dir, tmp_ws)
    recall = None
    pass2 = None
    if learning_dir and two_pass:
        # 第二轮：经验库已积累首轮经验，量化「记忆层检索命中」
        pass2 = _run_once(cases, engine, learning_dir, tmp_ws)
        store = SynergyOS(engine=engine, learning_dir=learning_dir).experience_store
        hit = 0
        for c in cases:
            few = FailureLibrary.build_fewshot(store, c["task"])
            if few.strip():
                hit += 1
        recall = hit / len(cases) if cases else 0.0

    def _agg(rows):
        comp = [r["completeness"] for r in rows]
        sat = [r["satisfaction"] for r in rows]
        verifs = [r["verification"] for r in rows if isinstance(r.get("verification"), dict)]
        heal = None
        if verifs:
            passed = [v for v in verifs if v.get("passed")]
            heal = len(passed) / len(verifs)
        return {
            "mean_completeness": round(sum(comp) / len(comp), 3) if comp else 0.0,
            "mean_satisfaction": round(sum(sat) / len(sat), 3) if sat else 0.0,
            "self_heal_rate": (round(heal, 3) if heal is not None else "n/a"),
            "n": len(rows),
        }

    report = {
        "engine_real": engine.is_real(),
        "pass1": _agg(pass1),
        "per_case": pass1,
    }
    if pass2 is not None:
        report["pass2"] = _agg(pass2)
        report["experience_recall"] = recall
    return report


def print_report(rep: Dict) -> str:
    """把评测报告格式化为可读文本。"""
    lines = ["# 灵犀 SynergyOS · 量化评测报告",
             f"- 引擎：{'真实模型' if rep['engine_real'] else 'Mock（离线，零 token）'}"]
    p1 = rep["pass1"]
    lines.append(f"## 第一轮（{p1['n']} 用例）")
    lines.append(f"- 必备要素完整率：{p1['mean_completeness']:.1%}")
    lines.append(f"- 满意度均值：{p1['mean_satisfaction']:.3f}")
    lines.append(f"- 反思自愈成功率：{p1['self_heal_rate']}")
    if "pass2" in rep:
        p2 = rep["pass2"]
        lines.append(f"## 第二轮（经验已积累，{p2['n']} 用例）")
        lines.append(f"- 必备要素完整率：{p2['mean_completeness']:.1%}")
        lines.append(f"- 经验召回率：{rep['experience_recall']:.1%}（检索到相似历史经验的用例占比）")
    lines.append("\n## 逐用例")
    for r in rep["per_case"]:
        lines.append(f"- [{r['id']}|{r['scenario']}] 完整率={r['completeness']:.0%} "
                     f"满意度={r['satisfaction']:.2f}")
    return "\n".join(lines)
