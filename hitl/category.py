# -*- coding: utf-8 -*-
"""品类词提取（可扩展词典）。封面 D12 用；后续材质表/装配族复用。

规则（老板签认）：取图纸「名称」尾部的品类词。词典外 → 需人工确认，绝不瞎猜。
"""

# 可扩展词典：按《附表-承认之细则》器件类别补充
CATEGORY_DICT = [
    "导线", "漆包线", "扇框", "扇叶", "线架", "马达壳",
    "轴芯", "轴套", "矽钢片", "轴承", "套管", "热缩管",
]


def extract_category(drawing_name):
    """从图纸名称尾部切品类词。

    返回 (品类词, 命中?)：命中→(词, True)；词典外→(None, False) 交人工确认。
    例：'SB120420BLCNR009导线' → ('导线', True)
    """
    name = (drawing_name or "").strip()
    # 取最长匹配，避免 '线' 误命中 '导线'
    hits = [c for c in CATEGORY_DICT if name.endswith(c)]
    if hits:
        return max(hits, key=len), True
    return None, False
