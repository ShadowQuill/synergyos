"""灵犀量化评测用例集（Eval Dataset）。

覆盖各应用场景，每条用例给出：
  · task        用户任务
  · scenario    应用场景（dev / paas / biz / code-review / data-analysis）
  · required    dev 类用例用于判定「代码完整性」的关键子串（其余场景用结构化验收）

这些用例同时用于：① 离线确定性评测（Mock 引擎，零 token）；② 接入真实引擎后的
自进化收益对比。对应改进报告 P1#5「量化评测基准」。
"""
from __future__ import annotations

from typing import Dict, List

EVAL_CASES: List[Dict] = [
    {"id": "dev-1", "task": "实现 LRU 缓存类", "scenario": "dev",
     "required": ["class", "def"]},
    {"id": "dev-2", "task": "实现快速排序函数", "scenario": "dev",
     "required": ["def", "sort"]},
    {"id": "dev-3", "task": "实现带过期时间的键值缓存", "scenario": "dev",
     "required": ["class", "def"]},
    {"id": "paas-1", "task": "写一份本周 PaaS 平台运营周报", "scenario": "paas",
     "required": []},
    {"id": "biz-1", "task": "写一份销售季度复盘", "scenario": "biz",
     "required": []},
    {"id": "code-review-1", "task": "评审一段 Python 数据预处理代码",
     "scenario": "code-review", "required": []},
    {"id": "data-analysis-1", "task": "分析用户留存数据并给出洞察",
     "scenario": "data-analysis", "required": []},
]
