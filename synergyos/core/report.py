"""运行报告生成：把一次全链路运行导出为结构化 Markdown / HTML。

报告从 SynergyOS 实例与 run() 返回的结果中汇总：
  · 冷启动锚定的用户画像与置信度
  · 双脑协作（左脑方案/代码/测试 + 右脑评分/偏好信号 + 仲裁）
  · 自适应生长与修复（每轮反思结论与权重调整）
  · 智能节律控制（预测停时点、是否暂停、阶段简报）
  · 完整协作时间线
"""
from __future__ import annotations

import html as _html
import json
import os
import datetime
from typing import Dict, List

from .bus import BUS, EventType
from .engine import ENGINE

VERDICT_LABEL = {
    "pass": "通过 · 无需修复",
    "logic_error": "逻辑错误 · 软修复",
    "preference_error": "偏好误判 · 软修复",
}


# ---------------- 数据汇总 ----------------

def build(os_sys, result: Dict) -> Dict:
    bus = os_sys.bus
    profile = os_sys.profiler.profile

    timeline = [
        {
            "type": e.type.value,
            "source": e.source,
            "message": e.message,
            "ts": datetime.datetime.fromtimestamp(e.ts).strftime("%H:%M:%S"),
        }
        for e in bus.history()
    ]

    rounds = []
    for i, r in enumerate(getattr(os_sys, "rounds", [])):
        obs = r.get("obs")
        arb = r.get("arb", {})
        ref = r.get("reflex")
        rounds.append({
            "round": r.get("round", i + 1),
            "satisfaction": obs.satisfaction if obs else None,
            "arb_reason": arb.get("reason", ""),
            "arb_revise": arb.get("should_revise", False),
            "verdict": ref.verdict if ref else "pass",
            "reflex_note": ref.note if ref else "",
        })

    return {
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "engine": "真实模型" if ENGINE.is_real() else "Mock 离线引擎（无需 API Key）",
        "task": result.get("task", ""),
        "scenario": result.get("scenario"),
        "paused": result.get("paused", False),
        "briefing": result.get("briefing"),
        "snapshot": result.get("snapshot"),
        "satisfaction": result.get("satisfaction"),
        "weights": result.get("weights", {}),
        "profile": profile.to_dict(),
        "verification": result.get("verification"),
        "artifacts": result.get("artifacts", {}),
        "rounds": rounds,
        "preferences": {
            "hits": list(getattr(os_sys, "pref_hits", [])),
            "misses": list(getattr(os_sys, "pref_misses", [])),
        },
        "horizons": [
            {"at": h.at_progress, "reason": h.reason}
            for h in os_sys.pause.horizons
        ],
        "timeline": timeline,
    }


# ---------------- Markdown 渲染 ----------------

def to_markdown(r: Dict) -> str:
    L: List[str] = []
    L.append(f"# 灵犀 SynergyOS · 运行报告")
    L.append(f"\n> 生成时间：{r['generated_at']}  ｜  引擎：{r['engine']}\n")
    if r.get("scenario"):
        L.append(f"**应用场景：** {r['scenario']}\n")
    L.append(f"## 任务\n\n{r['task']}\n")

    # 用户画像
    L.append("## 一、冷启动偏好锚定（用户画像）\n")
    prof = r["profile"]
    conf = prof.get("confidence", {})
    L.append("| 维度 | 偏好值 | 置信度 |")
    L.append("|---|---|---|")
    for k in ["communication_style", "detail_level", "aesthetic",
              "risk_tolerance", "collaboration"]:
        if k in prof:
            L.append(f"| {k} | {prof[k]} | {conf.get(k, 0):.2f} |")
    L.append(f"\n已学习信号数：`{prof.get('learned_signals', 0)}`\n")

    # 双脑协作
    L.append("## 二、双脑协作\n")
    art = r["artifacts"]
    sat = r["satisfaction"]
    if sat is not None:
        L.append(f"**右脑满意度评分：{sat:.2f}**\n")
    if r["preferences"]["hits"]:
        L.append(f"**偏好命中：** {', '.join(r['preferences']['hits'])}\n")
    if r["preferences"]["misses"]:
        L.append(f"**偏好未命中：** {', '.join(r['preferences']['misses'])}\n")
    L.append("### 左脑 · 实施方案\n")
    L.append(f"```\n{art.get('plan', '').strip()}\n```\n")
    L.append("### 左脑 · 实现代码\n")
    L.append(f"```python\n{art.get('code', '').strip()}\n```\n")
    L.append("### 左脑 · 测试用例\n")
    L.append(f"```\n{art.get('tests', '').strip()}\n```\n")

    # 反思与修复
    L.append("## 三、自适应生长与修复（Reflexion）\n")
    if r["rounds"]:
        L.append("| 轮次 | 满意度 | 仲裁 | 反思结论 | 说明 |")
        L.append("|---|---|---|---|---|")
        for rd in r["rounds"]:
            sat_s = f"{rd['satisfaction']:.2f}" if rd["satisfaction"] is not None else "-"
            arb_s = "修订" if rd["arb_revise"] else "通过"
            L.append(f"| {rd['round']} | {sat_s} | {arb_s} | "
                     f"{VERDICT_LABEL.get(rd['verdict'], rd['verdict'])} | {rd['reflex_note']} |")
        L.append("")
    L.append(f"**软修复后智能体权重：** `{json.dumps(r['weights'], ensure_ascii=False)}`\n")

    # 真实验证 + 反思自愈
    v = r.get("verification")
    if v:
        L.append("\n### 真实验证与反思自愈（Reflexion 落地）\n")
        if not v.get("enabled"):
            L.append(f"- 未启用：{v.get('reason', '非真实模型或缺少代码/用例')}\n")
        elif v.get("kind") == "structural":
            if v.get("passed"):
                once = v.get("attempts", 1) == 1
                skipped = v.get("skipped") or []
                fixes_n = v.get("fixes")
                if skipped:
                    heal = "一次通过" if once else f"反思自愈补全 {fixes_n} 次后通过"
                    L.append(f"- ✅ **通过（结构化验收）**：交付物覆盖了用户要求的必备要素，"
                             f"{heal}（共运行 {v.get('attempts')} 次）。\n"
                             f"- ⏭ **已按用户要求省略**：{ '；'.join(skipped) }"
                             f"（用户显式排除，不强制补全）。\n")
                else:
                    heal = "一次通过" if once else f"反思自愈补全 {fixes_n} 次后通过"
                    L.append(f"- ✅ **通过（结构化验收）**：交付物覆盖全部必备要素，"
                             f"{heal}（共运行 {v.get('attempts')} 次）。\n")
            else:
                L.append(f"- ❌ **未通过（结构化验收）**：反思补全 {v.get('fixes')} 次后仍缺失"
                         f"必备要素，需人工复核。\n")
                if v.get("detail"):
                    L.append(f"```\n{v['detail'].strip()}\n```\n")
        elif v.get("passed"):
            L.append(f"- ✅ **通过（pytest 实测）**：生成代码经 pytest 实测，"
                     f"{'一次通过' if v.get('attempts', 1) == 1 else f'修复 {v.get('fixes')} 次后通过'}"
                     f"（共运行 {v.get('attempts')} 次，模块 `{v.get('module')}`）。\n")
        else:
            L.append(f"- ❌ **未通过（pytest 实测）**：反思修复 {v.get('fixes')} 次后仍失败，需人工复核。\n")
            if v.get("trace"):
                L.append(f"```\n{v['trace'].strip()}\n```\n")

    # 节律控制
    L.append("## 四、智能节律控制（Pause Horizon）\n")
    if r["horizons"]:
        L.append("预测到的停时点：")
        for h in r["horizons"]:
            L.append(f"- {h['at']:.0%} — {h['reason']}")
        L.append("")
    if r["paused"]:
        L.append(f"**本次运行已暂停。** 阶段简报：{r['briefing']}\n")
        L.append(f"快照：```json\n{json.dumps(r['snapshot'], ensure_ascii=False, indent=2)}\n```\n")
    else:
        L.append("本次运行未被中断，已完整交付。\n")

    # 时间线
    L.append("## 五、协作时间线\n")
    L.append("| 时间 | 来源 | 事件 |")
    L.append("|---|---|---|")
    for ev in r["timeline"]:
        L.append(f"| {ev['ts']} | {ev['source']} | {ev['message']} |")
    L.append("")
    L.append("--- \n*本报告由灵犀 SynergyOS 自动生成。*")
    return "\n".join(L)


# ---------------- HTML 渲染 ----------------

def to_html(r: Dict) -> str:
    def esc(s) -> str:
        return _html.escape(str(s))

    def code(s, cls="") -> str:
        return f'<pre class="code {cls}"><code>{esc(s)}</code></pre>'

    # 画像表
    prof = r["profile"]
    conf = prof.get("confidence", {})
    rows = "".join(
        f"<tr><td>{k}</td><td>{esc(prof.get(k,''))}</td>"
        f"<td><div class='bar'><span style='width:{conf.get(k,0)*100:.0f}%'></span></div></td></tr>"
        for k in ["communication_style", "detail_level", "aesthetic",
                  "risk_tolerance", "collaboration"] if k in prof
    )

    # 反思表
    ref_rows = ""
    for rd in r["rounds"]:
        sat = f"{rd['satisfaction']:.2f}" if rd["satisfaction"] is not None else "-"
        arb = "修订" if rd["arb_revise"] else "通过"
        vcls = "ok" if rd["verdict"] == "pass" else "warn"
        ref_rows += (
            f"<tr><td>{rd['round']}</td><td>{sat}</td><td>{arb}</td>"
            f"<td class='{vcls}'>{esc(VERDICT_LABEL.get(rd['verdict'], rd['verdict']))}</td>"
            f"<td>{esc(rd['reflex_note'])}</td></tr>"
        )
    if not ref_rows:
        ref_rows = "<tr><td colspan='5'>（无）</td></tr>"

    # 时间线
    tl = "".join(
        f"<tr><td class='mono'>{esc(ev['ts'])}</td><td>{esc(ev['source'])}</td>"
        f"<td class='ev-{esc(ev['type'])}'>{esc(ev['message'])}</td></tr>"
        for ev in r["timeline"]
    )

    art = r["artifacts"]
    sat = r["satisfaction"]
    sat_badge = (f"<span class='sat'>{sat:.2f}</span>" if sat is not None
                 else "<span class='sat dim'>—</span>")
    hits = ", ".join(r["preferences"]["hits"]) or "无"
    misses = ", ".join(r["preferences"]["misses"]) or "无"

    # 真实验证 + 反思自愈 徽标
    v = r.get("verification")
    verify_html = ""
    if v:
        if not v.get("enabled"):
            verify_html = f"<p class='meta'>真实验证未启用：{esc(v.get('reason',''))}</p>"
        elif v.get("kind") == "structural":
            if v.get("passed"):
                once = v.get("attempts", 1) == 1
                skipped = v.get("skipped") or []
                if skipped:
                    txt = ("✅ 真实验证通过（结构化验收）：交付物覆盖用户要求的必备要素，一次通过"
                           if once else
                           f"✅ 真实验证通过（结构化验收）：反思自愈补全 {v.get('fixes')} 次后全部覆盖"
                           f"（共运行 {v.get('attempts')} 次）")
                    omit = "<br><span class='meta'>⏭ 已按用户要求省略：<b>" + \
                           esc("；".join(skipped)) + "</b>（用户显式排除，不强制补全）</span>"
                    verify_html = f"<p class='ok'>{txt}</p>{omit}"
                else:
                    txt = ("✅ 真实验证通过（结构化验收）：交付物覆盖全部必备要素，一次通过"
                           if once else
                           f"✅ 真实验证通过（结构化验收）：反思自愈补全 {v.get('fixes')} 次后全部覆盖"
                           f"（共运行 {v.get('attempts')} 次）")
                    verify_html = f"<p class='ok'>{txt}</p>"
            else:
                verify_html = (f"<p class='warn'>❌ 真实验证未通过（结构化验收）：反思补全 "
                               f"{v.get('fixes')} 次后仍缺失必备要素，需人工复核。</p>"
                               + (f"<pre class='code'><code>{esc(v.get('detail','').strip())}</code></pre>"
                                  if v.get("detail") else ""))
        elif v.get("passed"):
            once = v.get("attempts", 1) == 1
            txt = ("✅ 真实验证通过：生成代码经 pytest 实测，一次通过"
                   if once else
                   f"✅ 真实验证通过：反思自愈修复 {v.get('fixes')} 次后全部通过"
                   f"（共运行 {v.get('attempts')} 次，模块 {esc(v.get('module',''))}）")
            verify_html = f"<p class='ok'>{txt}</p>"
        else:
            verify_html = (f"<p class='warn'>❌ 真实验证未通过：反思修复 {v.get('fixes')} 次后仍失败，需人工复核。</p>"
                           + (f"<pre class='code'><code>{esc(v.get('trace','').strip())}</code></pre>"
                              if v.get("trace") else ""))
    pause_badge = ("<span class='pill pause'>已暂停</span>" if r["paused"]
                   else "<span class='pill done'>完整交付</span>")

    horizons = "".join(
        f"<li><b>{h['at']:.0%}</b> — {esc(h['reason'])}</li>" for h in r["horizons"]
    ) or "<li>无</li>"

    sat_bar = ""
    if sat is not None:
        sat_bar = f"<div class='bar big'><span style='width:{sat*100:.0f}%'></span></div>"

    snapshot = ""
    if r["paused"]:
        snapshot = (
            f"<p class='brief'>{esc(r['briefing'])}</p>"
            f"<pre class='code'><code>{esc(json.dumps(r['snapshot'], ensure_ascii=False, indent=2))}</code></pre>"
        )

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>灵犀 SynergyOS · 运行报告</title>
<style>
 :root{{--bg:#0b1020;--card:#141b33;--ink:#e8edff;--muted:#9aa6c8;--accent:#4f9dff;--line:#23304f;--ok:#37d39b;--warn:#ffb454;}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;padding:32px}}
 .wrap{{max-width:980px;margin:0 auto}}
 header{{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:24px}}
 h1{{margin:0 0 6px;font-size:26px}}
 .meta{{color:var(--muted);font-size:13px}}
 .pill{{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600}}
 .done{{background:rgba(55,211,155,.15);color:var(--ok)}}
 .pause{{background:rgba(255,180,84,.15);color:var(--warn)}}
 section{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:16px 0}}
 h2{{margin:0 0 12px;font-size:18px;color:var(--accent)}}
 table{{width:100%;border-collapse:collapse;font-size:14px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}}
 th{{color:var(--muted);font-weight:600}}
 .code{{background:#0c1226;border:1px solid var(--line);border-radius:10px;padding:12px;overflow:auto;font:13px/1.5 ui-monospace,Menlo,Consolas,monospace;color:#cdd8ff}}
 .bar{{height:8px;background:#0c1226;border-radius:6px;overflow:hidden;min-width:80px}}
 .bar span{{display:block;height:100%;background:linear-gradient(90deg,var(--accent),#7ce0ff)}}
 .bar.big{{height:14px;margin:6px 0 14px}}
 .sat{{font-size:22px;font-weight:700;color:var(--ok)}}
 .sat.dim{{color:var(--muted)}}
 .ok{{color:var(--ok)}} .warn{{color:var(--warn)}}
 .mono{{font-family:ui-monospace,Menlo,monospace;color:var(--muted)}}
 .brief{{color:var(--warn)}}
 ul{{margin:6px 0;padding-left:20px}} li{{margin:4px 0}}
 .ev-cold_start,.ev-profile_update{{color:var(--accent)}} .ev-left_step{{color:#7ce0ff}}
 .ev-right_observe{{color:var(--ok)}} .ev-arbitrate{{color:#d9a6ff}} .ev-reflexion{{color:#7ce0ff}}
 .ev-pause{{color:var(--warn)}} .ev-deliver{{color:var(--ok)}}
 .grid{{display:flex;gap:16px;flex-wrap:wrap}} .grid>div{{flex:1;min-width:200px}}
</style></head><body><div class="wrap">
<header>
 <h1>灵犀 SynergyOS · 运行报告</h1>
 <div class="meta">生成时间 {esc(r['generated_at'])} ｜ 引擎 {esc(r['engine'])} ｜ {pause_badge}</div>
</header>

<section>
 <h2>任务</h2>
 {f"<p><b>应用场景：</b>{esc(r['scenario'])}</p>" if r.get("scenario") else ""}
 <p>{esc(r['task'])}</p>
 <div class="grid">
  <div>
   <div>右脑满意度评分 {sat_badge}</div>
   {sat_bar}
  </div>
  <div>
   <p>偏好命中：<b>{esc(hits)}</b></p>
   <p>偏好未命中：<b>{esc(misses)}</b></p>
  </div>
 </div>
</section>

<section>
 <h2>一、冷启动偏好锚定（用户画像）</h2>
 <table><thead><tr><th>维度</th><th>偏好值</th><th>置信度</th></tr></thead>
 <tbody>{rows}</tbody></table>
 <p class="meta">已学习信号数：{prof.get('learned_signals',0)}</p>
</section>

<section>
 <h2>二、双脑协作 · 左脑产出</h2>
 <h3>实施方案</h3>{code(art.get('plan','').strip())}
 <h3>实现代码</h3>{code(art.get('code','').strip(),'py')}
 <h3>测试用例</h3>{code(art.get('tests','').strip())}
</section>

<section>
 <h2>三、自适应生长与修复（Reflexion）</h2>
 <table><thead><tr><th>轮次</th><th>满意度</th><th>仲裁</th><th>反思结论</th><th>说明</th></tr></thead>
 <tbody>{ref_rows}</tbody></table>
 <p>软修复后智能体权重：<code>{esc(json.dumps(r['weights'],ensure_ascii=False))}</code></p>
 {verify_html}
</section>

<section>
 <h2>四、智能节律控制（Pause Horizon）</h2>
 <ul>{horizons}</ul>
 {snapshot}
</section>

<section>
 <h2>五、协作时间线</h2>
 <table><thead><tr><th>时间</th><th>来源</th><th>事件</th></tr></thead>
 <tbody>{tl}</tbody></table>
</section>

<p class="meta">本报告由灵犀 SynergyOS 自动生成 · 双脑协作 / 冷启动锚定 / 自适应修复 / 节律控制 全链路可观测。</p>
</div></body></html>"""


# ---------------- 文件写出 ----------------

def generate(os_sys, result: Dict, out_dir: str = "reports",
             fmt: str = "both") -> Dict[str, str]:
    """生成报告文件，返回 {格式: 路径}。"""
    os.makedirs(out_dir, exist_ok=True)
    rep = build(os_sys, result)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: Dict[str, str] = {}

    if fmt in ("markdown", "both"):
        p = os.path.join(out_dir, f"synergyos_report_{stamp}.md")
        with open(p, "w", encoding="utf-8") as f:
            f.write(to_markdown(rep))
        paths["markdown"] = p

    if fmt in ("html", "both"):
        p = os.path.join(out_dir, f"synergyos_report_{stamp}.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(to_html(rep))
        paths["html"] = p

    return paths
