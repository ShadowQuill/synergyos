"""量化评测 CLI 入口：`python3 -m synergyos.eval`。

离线确定性评测（默认 Mock 引擎，零 token）；传入真实 engine 即启用自进化收益对比。
"""
from __future__ import annotations

import argparse
import tempfile

from .runner import run_eval, print_report


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="synergyos.eval",
        description="灵犀 SynergyOS · 量化评测基准（必备要素完整率 / 满意度 / 经验召回率）",
    )
    p.add_argument("--no-learning", action="store_true",
                   help="关闭软学习经验积累（不统计经验召回率）")
    p.add_argument("--learning-dir", default=".eval_cache",
                   help="软学习经验目录（默认 .eval_cache）")
    p.add_argument("--cases", default=None,
                   help="可选的评测集 JSON 路径（默认内置 EVAL_CASES）")
    p.add_argument("--real", action="store_true",
                   help="用真实模型引擎评测（消耗 token；默认 Mock 离线确定性）")
    args = p.parse_args(argv)

    learning_dir = None if args.no_learning else args.learning_dir
    engine = None
    if args.real:
        from ..core.engine import build_engine
        engine = build_engine()
    rep = run_eval(engine=engine, learning_dir=learning_dir)
    print(print_report(rep))
    return rep


if __name__ == "__main__":
    main()
