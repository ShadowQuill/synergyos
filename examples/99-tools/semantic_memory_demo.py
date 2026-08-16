"""示例：语义记忆层（SemanticMemory，离线可跑）。

演示与「偏好记忆」不同的另一类记忆——长期知识检索：
把知识片段入库，任务来临时按 TF-IDF 相关性召回并回填给智能体。

运行（零依赖、无需 API Key）：
    python3 examples/99-tools/semantic_memory_demo.py
"""
from __future__ import annotations

from synergyos.core.memory import SemanticMemory


def demo_retrieval() -> None:
    print("=" * 60)
    print("演示：语义记忆层检索（区分于偏好记忆的长期知识库）")
    print("=" * 60)

    mem = SemanticMemory()
    mem.add_many([
        "灵犀采用双脑协作架构：左脑负责执行（架构师、程序员、测试员），右脑负责观察与偏好评分。",
        "反思自愈（Reflexion）依据 verdict 调整智能体权重，是无人工干预的软修复。",
        "偏好记忆记录用户的沟通风格、详细度与审美偏好，用于个性化输出。",
        "语义记忆层用 TF-IDF 做关键词检索，中文走字 bigram 分词，是 RAG 的雏形。",
        "MCP 风格工具接口让智能体能够读取本地文件、调用搜索等外部能力。",
        "今天天气晴朗，适合去公园散步。",  # 无关噪声，验证检索不会误召回
    ])

    queries = [
        "双脑协作是怎么分工的",
        "智能体怎么调外部工具",
        "长期记忆是怎么检索知识的",
    ]
    for q in queries:
        print(f"\n>>> 查询：{q}")
        for i, (doc, score) in enumerate(mem.retrieve(q, top_k=2), 1):
            print(f"  [{i}] (score={score:.3f}) {doc.text}")

    # 持久化演示
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "memory.json")
        mem.save(p)
        loaded = SemanticMemory.load(p)
        assert len(loaded.docs) == len(mem.docs)
        print(f"\n>>> 持久化往返成功（{len(loaded.docs)} 条文档已落盘并重新加载）")


if __name__ == "__main__":
    demo_retrieval()
