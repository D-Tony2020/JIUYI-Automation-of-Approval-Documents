# -*- coding: utf-8 -*-
"""品类词提取(自动归一 + 内置词典 + 成长型学习)。封面 D12 用; 后续材质表/装配族复用。

规则(老板签认): 取图纸「名称」尾部的品类词; 词典外→交人工确认, 绝不瞎猜(不做 contains 兜底)。
软进硬出: 来源可软(归一去色/人工确认/学习), D12 出口由上层(assemble 端点)硬断言非空。
"""
import re

# 内置种子词典: 按《附表-承认之细则》器件类别。归一+学习让缺项不再致崩, 此处只决定"自动命中率"。
CATEGORY_DICT = [
    "导线", "漆包线", "扇框", "扇叶", "线架", "马达壳",
    "轴芯", "轴套", "矽钢片", "轴承", "套管", "热缩管",
]

# 颜色/规格修饰白名单: 仅这些尾部修饰可被归一剥离(颜色绝非品类)。受控常量, 实测后再议是否扩。
_QUALIFIERS = (
    "透明", "本色", "米白", "浅灰",                # 多字优先(子串匹配无所谓, 仅判定是否含白名单词)
    "黄", "红", "蓝", "黑", "白", "绿", "棕", "灰", "橙", "紫", "金", "银",
    "粗", "细", "长", "短", "左", "右", "大", "小",
)
_PAREN = re.compile(r"[\s\-_·]*[（(\[【]([^（()）\[\]【】]{1,6})[)）\]】]\s*$")
_BARE = re.compile(r"[\-_·\s]+(" + "|".join(_QUALIFIERS) + r")\s*$")


def normalize_name(name):
    """白名单受控剥尾: 反复剥尾部'括号内颜色/规格修饰'或'裸尾颜色词'。
    护栏: 每步剥后若为空/长度<2/剥后不再 endswith 任一词典词 → 回退不剥
    (防把 套管(热缩)→套管 误归、轴套→轴)。剥不动则原样返回。
    """
    s = (name or "").strip()
    for _ in range(4):                                   # 最多剥 4 层
        m = _PAREN.search(s)
        if m and any(q in m.group(1) for q in _QUALIFIERS):
            cut = s[:m.start()].strip()
        else:
            mb = _BARE.search(s)
            cut = s[:mb.start()].strip() if mb else None
        if cut is None or len(cut) < 2 or not any(cut.endswith(c) for c in CATEGORY_DICT):
            break                                        # 剥后不再命中词典→不安全, 回退
        s = cut
    return s


def extract_category(drawing_name):
    """从图纸名称切品类词。优先级: 归一+内置词典 > 成长型学习库 > (None, False)。

    返回 (品类词, 命中?): 命中→(词, True); 词典外且学习库无→(None, False) 交人工确认。
    例: 'SB120420BLCNR009导线'→('导线',True); '导线（黄）'→归一'导线'→('导线',True);
        '导线（黄）'若品类全新→学习库命中过则返回学习值, 否则(None,False)。
    """
    raw = (drawing_name or "").strip()
    norm = normalize_name(raw)
    hits = [c for c in CATEGORY_DICT if norm.endswith(c)]
    if hits:
        return max(hits, key=len), True                  # 最长匹配, 避免 '线' 误命中 '导线'
    try:                                                 # 内置未命中→查操作员确认过的成长型学习库
        from . import dicts
        learned = dicts.lookup_category(raw)
        if learned:
            return learned, True
    except Exception:
        pass
    return None, False                                   # 绝不 contains 瞎猜
