"""语义记忆层（Semantic Memory / Retrieval Layer）。

改进报告 P0：在「偏好记忆」（UserProfile）之外，补一层【长期语义记忆】——
把领域知识、历史交付、设计原则等文档入库，任务来临时按相关性检索并回填，
让智能体具备「记起过去知识」的能力。

设计取舍（零依赖、可离线）：
  · 不引入 numpy / 向量库，用纯标准库实现 TF-IDF + 余弦相似度的关键词检索；
  · 中文无空格，额外加入「字 bigram」分词，提升中文召回；
  · 检索层与「偏好记忆」是两种截然不同的记忆：前者是共享知识库（面向任务），
    后者是用户画像（面向人）。README 中有专门说明。
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CJK = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> List[str]:
    """分词：英文/数字词 + 中文单字 bigram。

    中文没有空格，单纯按字效果差；bigram 能捕捉「灵犀」「自进化」这类相邻组合，
    在不依赖分词器的前提下显著改善中文检索召回。
    """
    text = (text or "").lower()
    tokens: List[str] = list(_TOKEN_RE.findall(text))
    chars = _CJK.findall(text)
    for i in range(len(chars) - 1):
        tokens.append("·".join(chars[i:i + 2]))  # 用 · 连接避免与英文词冲突
    return tokens


@dataclass
class Document:
    doc_id: str
    text: str
    meta: dict = field(default_factory=dict)


class SemanticMemory:
    """轻量 TF-IDF 检索记忆。纯标准库，可持久化到 JSON。"""

    def __init__(self):
        self.docs: Dict[str, Document] = {}
        self._df: Dict[str, int] = {}        # 文档频率
        self._tf: Dict[str, Dict[str, int]] = {}  # doc_id -> {term: count}
        self._n = 0
        self._dirty = False

    # ---- 写入 ----
    def add(self, text: str, doc_id: Optional[str] = None, meta: Optional[dict] = None) -> str:
        doc_id = doc_id or f"doc_{len(self.docs) + 1}"
        toks = tokenize(text)
        tf: Dict[str, int] = {}
        seen = set()
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
            if t not in seen:
                seen.add(t)
                self._df[t] = self._df.get(t, 0) + 1
        self.docs[doc_id] = Document(doc_id, text, meta or {})
        self._tf[doc_id] = tf
        self._n += 1
        self._dirty = True
        return doc_id

    def add_many(self, items: List[str]) -> List[str]:
        return [self.add(it) for it in items]

    # ---- 检索 ----
    def retrieve(self, query: str, top_k: int = 3) -> List[Tuple[Document, float]]:
        if self._n == 0:
            return []
        q_tf = {}
        for t in tokenize(query):
            q_tf[t] = q_tf.get(t, 0) + 1
        q_vec = {t: (c / max(1, len(q_tf))) * math.log((1 + self._n) / (1 + self._df.get(t, 0)) + 1)
                 for t, c in q_tf.items()}
        scored: List[Tuple[Document, float]] = []
        for doc_id, tf in self._tf.items():
            denom = sum(c * c for c in tf.values()) ** 0.5
            if denom == 0:
                continue
            dot = 0.0
            for t, qw in q_vec.items():
                if t in tf:
                    dot += qw * ((tf[t] / denom) * math.log((1 + self._n) / (1 + self._df.get(t, 0)) + 1))
            if dot > 0:
                scored.append((self.docs[doc_id], dot))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def context(self, query: str, top_k: int = 3, sep: str = "\n\n") -> str:
        """检索并以纯文本形式返回相关片段，便于回填给模型提示词。"""
        hits = self.retrieve(query, top_k=top_k)
        if not hits:
            return ""
        return sep.join(f"[记忆 {i+1}] {doc.text}" for i, (doc, _) in enumerate(hits))

    # ---- 持久化 ----
    def to_dict(self) -> dict:
        return {
            "docs": {k: {"doc_id": d.doc_id, "text": d.text, "meta": d.meta}
                     for k, d in self.docs.items()},
        }

    def save(self, path: str) -> None:
        import os
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        self._dirty = False

    @classmethod
    def from_dict(cls, data: dict) -> "SemanticMemory":
        mem = cls()
        for d in (data.get("docs") or {}).values():
            mem.add(d["text"], doc_id=d.get("doc_id"), meta=d.get("meta"))
        mem._dirty = False
        return mem

    @classmethod
    def load(cls, path: str) -> "SemanticMemory":
        try:
            with open(path, encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except Exception:
            return cls()
