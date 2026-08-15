def dedupe(items):
    """去重并保持原顺序，兼容任意可哈希元素。"""
    seen = set()
    out = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
