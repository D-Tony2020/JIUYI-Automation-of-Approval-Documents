# -*- coding: utf-8 -*-
"""品类词: 自动归一(去色) + 内置词典 + 成长型学习 + 软门禁(extract 永不崩, 词典外不瞎猜)。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl.category import normalize_name, extract_category


def test_归一去颜色后缀():
    assert normalize_name("导线（黄）") == "导线"          # 全角括号色
    assert normalize_name("导线(红)") == "导线"            # 半角括号色
    assert normalize_name("导线-黄") == "导线"             # 裸尾色
    assert normalize_name("导线（黄绿米）") == "导线"        # 多色
    assert normalize_name("SB120420BLCNR009导线") == "SB120420BLCNR009导线"  # 无色后缀不动


def test_归一护栏不误剥():
    assert normalize_name("套管(热缩)") == "套管(热缩)"     # 热缩非颜色→不剥(交内置词典/人工另判)
    assert normalize_name("轴套") == "轴套"                # 不剥成 轴
    assert normalize_name("马达壳") == "马达壳"


def test_extract色变体自动命中():
    assert extract_category("导线（黄）") == ("导线", True)
    assert extract_category("SB120420BLCNR009导线") == ("导线", True)
    assert extract_category("导线（红）") == ("导线", True)
    assert extract_category("套管(黑)") == ("套管", True)


def test_extract词典外不瞎猜():
    cat, ok = extract_category("某某连接器XYZ")            # 连接器不在内置词典且未学习
    assert ok is False and cat is None


def test_extract边界不崩():
    assert extract_category("") == (None, False)
    assert extract_category("（黄）") == (None, False)      # 归一后空→不命中, 不崩
    assert extract_category(None) == (None, False)


def test_成长型学习色变体(tmp_path, monkeypatch):
    from hitl import dicts, category
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))      # 隔离到临时目录
    assert category.extract_category("某连接器（黄）")[1] is False   # 学前: 词典外
    dicts.learn_category("某连接器（黄）", "连接器")
    assert category.extract_category("某连接器（黄）") == ("连接器", True)   # 精确命中
    assert category.extract_category("某连接器（红）") == ("连接器", True)   # 去括号弱回退→色变体免重学


def test_fill_cover永不崩词典外(tmp_path, monkeypatch):
    import openpyxl
    from hitl import cover, dicts
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    wb = openpyxl.Workbook()
    ws = wb.active
    exp = cover.fill_cover(ws, {"名称": "全新品类ABC", "品号": "YY60010000", "版本": "A01"})
    assert exp["_unknown_category"] is True and exp["D12"] == "全新品类ABC"   # 暂留归一原文(留痕), 不抛错
    exp2 = cover.fill_cover(ws, {"名称": "导线（黄）", "品号": "YY60010000", "版本": "A01"})
    assert exp2["_unknown_category"] is False and exp2["D12"] == "导线"        # 自动归一命中
    exp3 = cover.fill_cover(ws, {"名称": "导线（黄）", "品类": "导线", "品号": "x", "版本": "A01"})
    assert exp3["D12"] == "导线"                                              # 操作员确认 override
