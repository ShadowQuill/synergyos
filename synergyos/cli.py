"""灵犀 CLI 演示：在终端跑通全链路，并以彩色日志展示协作过程。

用法：
  python -m synergyos.cli                      # 交互式冷启动 + 默认任务
  python -m synergyos.cli --task "写一个去重函数"   # 指定任务
  python -m synergyos.cli --auto               # 跳过提问，用默认画像
  python -m synergyos.cli --scenario biz       # 按应用场景真跑（paas/biz/dev）
  python -m synergyos.cli --pause 0.5          # 在 50% 进度时暂停
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import SynergyOS, BUS, EventType
from .core.profile import COLD_START_QUESTIONS
from .core.engine import ENGINE
from .core.report import generate
from .core.scenarios import SCENARIOS, VALID_SCENARIOS
from .core.verify import _module_for


COLORS = {
    EventType.COLD_START: "\033[36m",      # cyan
    EventType.PROFILE_UPDATE: "\033[35m",  # magenta
    EventType.LEFT_STEP: "\033[34m",        # blue
    EventType.RIGHT_OBSERVE: "\033[32m",    # green
    EventType.PREFERENCE: "\033[33m",      # yellow
    EventType.ARBITRATE: "\033[95m",        # bright magenta
    EventType.PAUSE_HORIZON: "\033[90m",   # grey
    EventType.PAUSE: "\033[91m",           # red
    EventType.RESUME: "\033[92m",          # bright green
    EventType.REFLEXION: "\033[96m",       # bright cyan
    EventType.WEIGHT: "\033[93m",          # bright yellow
    EventType.DELIVER: "\033[1;32m",       # bold green
    EventType.INFO: "\033[0m",
}
RESET = "\033[0m"
TAG = {
    EventType.COLD_START: "[冷启动]", EventType.PROFILE_UPDATE: "[画像]",
    EventType.LEFT_STEP: "[左脑]", EventType.RIGHT_OBSERVE: "[右脑]",
    EventType.PREFERENCE: "[偏好]", EventType.ARBITRATE: "[仲裁]",
    EventType.PAUSE_HORIZON: "[停时]", EventType.PAUSE: "[暂停]",
    EventType.RESUME: "[恢复]", EventType.REFLEXION: "[反思]",
    EventType.WEIGHT: "[调权]", EventType.DELIVER: "[交付]",
    EventType.INFO: "[信息]",
}


def _render(ev):
    c = COLORS.get(ev.type, "\033[0m")
    tag = TAG.get(ev.type, "")
    print(f"{c}{tag} {ev.source:<10}{RESET} {ev.message}")


def _strip_fence(text: str) -> str:
    """去掉模型常返回的 ```lang ... ``` 代码围栏，便于落盘为纯文件。

    - 带围栏：去掉首尾围栏，并保证以换行结尾（文本文件规范）。
    - 无围栏（如 Mock 直出）：原样返回，不强行改写。
    """
    s = text.strip()
    if not s.startswith("```"):
        return text
    s = s.split("\n", 1)[1] if "\n" in s else s[3:]
    if s.endswith("```"):
        s = s[: -3]
    return s if s.endswith("\n") else s + "\n"


def _emit(out_dir: str, task: str, artifacts: dict, scenario: str | None):
    """把交付物落盘：plan.json / solution.py / tests.py。返回写入的文件路径列表。"""
    import re
    slug = re.sub(r"\W+", "_", (task or "task"))[:40].strip("_") or "task"
    base = os.path.join(out_dir, slug)
    os.makedirs(base, exist_ok=True)
    written = []
    plan_path = os.path.join(base, "plan.json")
    # 真实模型常把 plan 包在 ```json 围栏里，先去围栏再判断是否为合法 JSON，
    # 避免落盘成 {"raw": "```json ..."} 这种无结构兜底。
    plan_raw = _strip_fence(artifacts["plan"])
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(plan_raw if plan_raw.strip().startswith("{")
                else json.dumps({"raw": plan_raw}, ensure_ascii=False, indent=2))
    written.append(plan_path)
    sol_path = os.path.join(base, "solution.py")
    code_text = _strip_fence(artifacts["code"])
    with open(sol_path, "w", encoding="utf-8") as f:
        f.write(code_text)
    written.append(sol_path)
    # dev 落盘 pytest 用例；其余场景（paas/biz/code-review/data-analysis…）的 tests
    # 是结构化验收 JSON（非可执行），落盘为 checks.json
    if scenario != "dev":
        checks_path = os.path.join(base, "checks.json")
        checks_raw = _strip_fence(artifacts["tests"])
        with open(checks_path, "w", encoding="utf-8") as f:
            f.write(checks_raw if checks_raw.strip().startswith("{")
                    else json.dumps({"raw": checks_raw}, ensure_ascii=False, indent=2))
        written.append(checks_path)
    else:
        test_path = os.path.join(base, "tests.py")
        test_text = _strip_fence(artifacts["tests"])
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(test_text)
        written.append(test_path)
        # 测试常 `from expiring_lru_cache import ExpiringLRUCache` 这样 import 模型自定的
        # 模块名（有时是占位名如 `from your_module import X`），而代码落盘为 solution.py。
        # 按 solution 里定义的类名反查测试导入的模块，复制同名副本，保证
        # `pytest tests.py` 开箱即跑，无需用户手动重命名。
        # （用类名反查并忽略行内注释，避免误把 `import time` 或 `# 替换` 当成交付模块。）
        mod = _module_for(code_text, test_text)
        if mod and mod != "solution":
            target = os.path.join(base, mod + ".py")
            if not os.path.exists(target):
                import shutil
                shutil.copyfile(sol_path, target)
                written.append(target)
    # 场景说明
    meta_path = os.path.join(base, "README.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"灵犀 SynergyOS 交付物\nscenario: {scenario or 'default'}\ntask: {task}\n")
    written.append(meta_path)
    return written


def ask_cold_start() -> dict:
    answers = {}
    print("\n=== 灵犀·冷启动偏好锚定（回答序号即可）===\n")
    for item in COLD_START_QUESTIONS:
        print(f"· {item['q']}")
        for i, opt in enumerate(item["options"]):
            print(f"   {i}. {opt}")
        while True:
            try:
                v = input(f"  → 你的选择(0-{len(item['options']) - 1}): ").strip()
                idx = int(v)
                if 0 <= idx < len(item["options"]):
                    answers[item["id"]] = idx
                    break
            except (ValueError, EOFError):
                pass
            print("  输入无效，请重试。")
    return answers


def main(argv=None):
    p = argparse.ArgumentParser(description="灵犀 SynergyOS 演示")
    p.add_argument("--task", default=None,
                   help="指定任务；不填则按 --scenario 的默认任务提示")
    p.add_argument("--scenario", choices=VALID_SCENARIOS, default=None,
                   help="应用场景：paas=个人助理周报 / biz=商业分析可视化 / dev=软件研发 / code-review=代码评审 / data-analysis=数据分析洞察")
    p.add_argument("--auto", action="store_true", help="跳过提问，用默认画像")
    p.add_argument("--pause", type=float, default=None,
                   help="在指定进度(0-1)时触发用户暂停")
    p.add_argument("--report", action="store_true",
                   help="运行结束后导出结构化报告（Markdown + HTML）")
    p.add_argument("--report-format", choices=["markdown", "html", "both"],
                   default="both", help="报告格式，默认 both")
    p.add_argument("--report-out", default="reports",
                   help="报告输出目录，默认 reports/")
    p.add_argument("--no-persist", action="store_true",
                   help="关闭用户画像持久化（不写磁盘）")
    p.add_argument("--profile-path", default=None,
                   help="指定画像存储路径，默认 ~/.synergyos/profile.json")
    p.add_argument("--emit", metavar="DIR", nargs="?", const="out", default=None,
                   help="将架构/代码/用例落盘为文件（默认 out/，可指定目录）；真模型下产出真实可运行文件")
    args = p.parse_args(argv)

    print("=" * 64)
    print("  灵犀 · 自进化协作智能体  SynergyOS  v0.1.0")
    print("  引擎:", "真实模型" if ENGINE.is_real() else "Mock 离线引擎（无需 API Key）")
    if args.scenario:
        print("  应用场景:", SCENARIOS[args.scenario].title)
    print("=" * 64)

    task = args.task or (SCENARIOS[args.scenario].task_hint
                         if args.scenario else "写一个函数计算斐波那契数列第 n 项")

    BUS.subscribe(_render)

    if args.no_persist:
        profile_path = None
        print("（偏好持久化已关闭，本次运行不落盘）")
    else:
        profile_path = args.profile_path or os.path.expanduser("~/.synergyos/profile.json")
        if os.path.exists(profile_path):
            print(f"已加载历史画像：{profile_path}")
        else:
            print(f"首次运行，画像将保存至：{profile_path}")
    os_sys = SynergyOS(profile_path=profile_path)
    if args.pause is not None:
        # 进度到阈值即请求暂停
        os_sys.pause.set_progress_source(lambda: os_sys.pause._progress)
        orig_tick = os_sys.pause.tick

        def tick_hook(stage=""):
            if (not os_sys.pause.paused and not os_sys.pause.pause_requested
                    and os_sys.pause._current_progress() >= args.pause):
                os_sys.pause.request_pause()
            return orig_tick(stage)

        os_sys.pause.tick = tick_hook

    answers = {} if args.auto else ask_cold_start()

    result = os_sys.run(task, profile_answers=answers or None, scenario=args.scenario)

    print("\n" + "=" * 64)
    print("  交付结果")
    print("=" * 64)
    if result.get("paused"):
        print("⏸ 任务已暂停：", result.get("briefing"))
        print("快照：", json.dumps(result.get("snapshot"), ensure_ascii=False))
    else:
        print("任务：", result["task"])
        print("满意度：", result.get("satisfaction"))
        print("智能体权重：", json.dumps(result.get("weights"), ensure_ascii=False))
        print("\n--- 实施方案 ---\n", result["artifacts"]["plan"])
        print("\n--- 实现代码 ---\n", result["artifacts"]["code"])
        print("\n--- 测试用例 ---\n", result["artifacts"]["tests"])
        print("\n用户画像快照：")
        print(json.dumps(result["profile"], ensure_ascii=False, indent=2))

        v = result.get("verification")
        if v:
            if not v.get("enabled"):
                print(f"\n🔍 真实验证：未启用（{v.get('reason', '非真实模型或缺少代码/用例')}）")
            elif v.get("kind") == "structural":
                # paas / biz：结构化验收
                if v.get("passed"):
                    once = v.get("attempts", 1) == 1
                    print(f"\n🔍 真实验证（结构化验收）：✅ 通过"
                          f"（{'一次通过' if once else f'反思自愈补全 {v.get('fixes')} 次后通过'}"
                          f"，共运行 {v.get('attempts')} 次）")
                    skipped = v.get("skipped") or []
                    if skipped:
                        print(f"   ⏭ 已按用户要求省略：{'；'.join(skipped)}"
                              f"（用户显式排除，不强制补全）")
                else:
                    print(f"\n🔍 真实验证（结构化验收）：❌ 未通过"
                          f"（补全 {v.get('fixes')} 次后仍缺失：{v.get('detail')}，请人工复核）")
            elif v.get("passed"):
                once = v.get("attempts", 1) == 1
                print(f"\n🔍 真实验证（pytest 实测）：✅ 通过（"
                      f"{'一次通过' if once else f'反思自愈修复 {v.get('fixes')} 次后通过'}"
                      f"，共运行 {v.get('attempts')} 次，模块 `{v.get('module')}`）")
            else:
                print(f"\n🔍 真实验证（pytest 实测）：❌ 未通过"
                      f"（修复 {v.get('fixes')} 次后仍失败，请人工复核）")

    if args.report:
        paths = generate(os_sys, result, out_dir=args.report_out,
                         fmt=args.report_format)
        print("\n📄 运行报告已导出：")
        for fmt_, path in paths.items():
            print(f"   · {fmt_}: {path}")

    if args.emit and not result.get("paused"):
        written = _emit(args.emit, result["task"], result["artifacts"], args.scenario)
        print("\n📦 交付物已落盘：")
        for w in written:
            print(f"   · {w}")

    print("\n✅ 灵犀演示完成。")
    return result


if __name__ == "__main__":
    main()
