"""量化评测模块（Eval）。"""
from .cases import EVAL_CASES
from .runner import run_eval, print_report

__all__ = ["EVAL_CASES", "run_eval", "print_report"]
