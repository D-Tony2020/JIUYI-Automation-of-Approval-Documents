# -*- coding: utf-8 -*-
"""OLE 放置/路由逻辑的行为单元测试(纯函数, 不碰COM)。

补上"只查计数/能开、漏查放置"的洞。每条测试锚定一个踩过的真 bug:
若当时有这测试, 那 bug 当场红灯。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from hitl.file_router import route
from hitl.ole_placement import ev_col, part_top
from hitl.material_table import OLE_COL
from study.embed_structure import MATCERT_PART_TOPS


# ── B1 路由扇出 ──────────────────────────────────────────────
def test_msds扇出到材质表和材质证明():
    """MSDS 是 1文件→N槽: 既进材质表(成分证据)又进材质证明书(证书)。"""
    slots = route("07CU物質安全資料表无铅锡线 Material Safe Data Sheet.pdf")
    assert "材质表" in slots
    assert "材质证明" in slots


def test_ul94阻燃等级不误判为UL证书():
    """UL94是阻燃等级非UL证书 → 不进UL; SGS报告进材质表。(naive规则曾在此误判)"""
    slots = route("主体SGS  NYLON10T UL94-V0+GLASS FILLED(BK-NL).pdf")
    assert "UL" not in slots
    assert "材质表" in slots


def test_ul证书进UL():
    assert "UL" in route("E326510正崴UL证书2024.pdf")


def test_rohs只进材质表不进材质证明():
    """ROHS报告是成分证据(材质表), 不是材质证明书(那是MSDS策展子集)。"""
    slots = route("镀锡ROHS英文 CANEC26012090003.pdf")
    assert "材质表" in slots
    assert "材质证明" not in slots


def test_供应商承认书进部件承认():
    assert "部件承认" in route("1007系列 承认书(1).pdf")


def test_包装含全角空格也识别():
    """'包 装'中间有全角空格, 去空格后须命中包装。"""
    assert "包装" in route("JY-SOP-P0600 包  装.pdf")


# ── B2 证据列(材质表内 K/L/Y) ────────────────────────────────
def test_msds进K列():
    assert ev_col("PA66 A3RV0 MSDS.pdf") == OLE_COL["MSDS"]


def test_reach进L列():
    assert ev_col("镀锡REACH英文-20260519-.pdf") == OLE_COL["REACH"]


def test_svhc也进L列():
    assert ev_col("锡线SVHC英文版.pdf") == OLE_COL["REACH"]


def test_rohs进Y列():
    assert ev_col("镀锡ROHS英文 CANEC26012090003.pdf") == OLE_COL["RoHS"]


# ── B3 零件类型行(材质证明书按类型对齐, 非按序号) ─────────────
def test_锡落第4类型行():
    """锡是第4类零件→MATCERT_PART_TOPS[3], 即便本单零件少(锡曾落错序号行)。"""
    assert part_top("锡") == MATCERT_PART_TOPS[3]


def test_导线落第1类型行():
    assert part_top("导线") == MATCERT_PART_TOPS[0]


def test_胶座端子落第2类型行():
    assert part_top("胶座端子") == MATCERT_PART_TOPS[1]


def test_热缩管落第3类型行():
    assert part_top("热缩管") == MATCERT_PART_TOPS[2]


# ── B4 文件→料匹配(content_match 的文件名 fallback, bug重灾区) ──
_MATS = [
    {"材质": "PVC", "零件": "导线"}, {"材质": "镀锡铜", "零件": "导线"},
    {"材质": "黑色油墨", "零件": "导线"}, {"材质": "白色油墨", "零件": "导线"},
    {"材质": "PA66", "零件": "胶座端子"}, {"材质": "磷青铜", "零件": "胶座端子"},
    {"材质": "聚烯烃", "零件": "热缩管"}, {"材质": "锡", "零件": "锡"},
]


def _mat(idx):
    return _MATS[idx]["材质"] if idx is not None else None


def test_07CU无铅锡线匹配锡而非镀锡铜():
    """别名泄漏曾让 锡 的别名(07CU/锡线)漏进 镀锡铜(锡⊂镀锡铜)→误判镀锡铜。"""
    from hitl.file_match import match_material
    assert _mat(match_material("07CU物質安全資料表无铅锡线 Material Safe Data Sheet.pdf", _MATS)) == "锡"


def test_热缩管黑色匹配聚烯烃而非黑色油墨():
    """颜色加成不得压过料名命中: '热缩管黑色ROHS' 是热缩管(聚烯烃)的报告, 非黑色油墨。"""
    from hitl.file_match import match_material
    assert _mat(match_material("四川领飞 热缩管黑色ROHS报告 A2250.pdf", _MATS)) == "聚烯烃"


def test_磷铜端子匹配磷青铜():
    from hitl.file_match import match_material
    assert _mat(match_material("磷铜端子MSDS新.pdf", _MATS)) == "磷青铜"


def test_双鸿油墨黑色匹配黑色油墨():
    """无料名直接命中时, 颜色仍是有效信号: '油墨...黑色' → 黑色油墨。"""
    from hitl.file_match import match_material
    assert _mat(match_material("双鸿油墨安全资料表_EN-CN_  黑色.pdf", _MATS)) == "黑色油墨"


# ── B5 材质表落点去重不变式(无两OLE落同格 / 同格堆叠到不同行) ──
def test_材质表落点不落同一格():
    from hitl.ole_placement import mat_anchors_nocrutch
    bom = [{"零件": "导线", "materials": [
        {"材质": "PVC", "blocks": [{"成份": [{"成份名称": "x"}]}]},
        {"材质": "镀锡铜", "blocks": [{"成份": [{"成份名称": "y"}]}]},
    ]}]
    specs = [{"mat_idx": 0, "col": 11}, {"mat_idx": 0, "col": 12}, {"mat_idx": 1, "col": 11}]
    anchors = mat_anchors_nocrutch(bom, specs)
    assert len(anchors) == len(set(anchors))   # 无两OLE落同一(row,col)


def test_材质表同料同列堆叠到不同行():
    """防御: 万一同料同证据列2份(本应去重), 也须堆到不同行(曾因29px<42px重叠)。"""
    from hitl.ole_placement import mat_anchors_nocrutch
    bom = [{"零件": "导线", "materials": [{"材质": "PVC", "blocks": [{"成份": [{"成份名称": "x"}]}]}]}]
    specs = [{"mat_idx": 0, "col": 11}, {"mat_idx": 0, "col": 11}]
    anchors = mat_anchors_nocrutch(bom, specs)
    assert anchors[0] != anchors[1]
