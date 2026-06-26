# -*- coding: utf-8 -*-
"""B段 material_extract: to_proposal 确定性后处理归一 + is_msds 判别。

用 spike/mock 冻结JSON, 不调 qwen(快/确定)。真qwen精度由伪真单e2e(slice5)验。
"""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hitl.material_extract import to_proposal, is_msds

MOCK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spike", "mock")


def _load(name):
    return json.load(open(os.path.join(MOCK, name), encoding="utf-8"))


def test_to_proposal归一锡线():
    prop = to_proposal(_load("msds_extract.json"), _load("rohs_extract.json"))
    assert prop["材质"] == "Sn-0.7Cu無鉛錫線" and prop["材质原文"] == "Sn-0.7Cu無鉛錫線"
    assert "供应商" not in prop                              # B 去供应商(零件级操作员填)
    锡 = [c for c in prop["成份"] if "錫" in c["成份名称"]][0]
    assert 锡["CAS"] == "7440-31-5"                         # '7440-31- 5' 去空格
    assert 锡["重量%"] == "0.993"                           # '99.3wt%' ÷100
    assert 锡["无CAS"] is False                             # 有CAS→不标黄
    assert prop["RoHS"]["Pb"] == "63"                       # 有数值照填(非因Pass写ND)
    assert prop["报告日期"] == "2025.06.30"
    assert prop["报告编号"] == "SZXEC25002243403"


def test_无RoHS时成分仍提议():
    prop = to_proposal(_load("msds_extract.json"))
    assert prop["材质"] and prop["成份"]
    assert all(v == "" for v in prop["RoHS"].values())     # 无报告 → RoHS 十项空


def test_is_msds判别():
    assert is_msds("材料安全数据表 成份组成: 锡 7440-31-5, 铜 7440-50-8 wt%")
    assert not is_msds("产品图纸 只有一个编号 7440-31-5 无成分表")   # <2 CAS


def test_rohs_from_msds_PVC声明():
    # 无第三方RoHS报告时, 从PVC MSDS自带的RoHS符合性声明行(无CAS)派生 M-V(老板拍板: 用MSDS声明)
    from hitl.material_extract import rohs_from_msds_components
    comps = [
        {"name": "聚氯乙烯树脂", "cas": "9002-86-2", "weight_pct_raw": "56.4%"},  # 真成分(有CAS)不当RoHS
        {"name": "鎘(Cd)", "cas": "", "weight_pct_raw": "〈5ppm"},
        {"name": "鉛(Pb)", "cas": "", "weight_pct_raw": "〈50ppm"},
        {"name": "汞(Hg)", "cas": "", "weight_pct_raw": "〈2ppm"},
        {"name": "鉻 Cr 六價", "cas": "", "weight_pct_raw": "〈5ppm"},
        {"name": "PBB", "cas": "", "weight_pct_raw": "ND"},
        {"name": "PBDE", "cas": "", "weight_pct_raw": "ND"},
    ]
    r = rohs_from_msds_components(comps)
    assert r["Cd"] == "<5ppm" and r["Pb"] == "<50ppm" and r["Hg"] == "<2ppm"
    assert r["Cr6+"] == "<5ppm" and r["PBBs"] == "ND" and r["PBDEs"] == "ND"
    assert "DEHP" not in r                                  # 未声明的不派生(交ND兜底)


def test_rohs有CAS的铅不当声明():
    from hitl.material_extract import rohs_from_msds_components
    comps = [{"name": "铅(Pb)", "cas": "7439-92-1", "weight_pct_raw": "<0.005%"}]   # 磷青铜真合金成分
    assert rohs_from_msds_components(comps) == {}            # 有CAS→不当RoHS声明


def test_品号优先生久料号YY():
    from hitl.drawing_extract import _pick_shengjiu_code
    assert _pick_shengjiu_code("SB120420BLCN0009导线 YY60039403") == "YY60039403"   # 两料号并列取YY
    assert _pick_shengjiu_code("yy60039403") == "YY60039403"                         # 大小写归一
    assert _pick_shengjiu_code("SB120420BLCN0009") == "SB120420BLCN0009"             # 无YY→保原值


def test_名称去料号留品类():
    from hitl.drawing_extract import _clean_name
    assert _clean_name("SB120420BLCN0009导线") == "导线"   # 去久益料号串, 留品类(golden材质表A2/FAI均'导线')
    assert _clean_name("导线") == "导线"
