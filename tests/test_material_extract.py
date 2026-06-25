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
    assert prop["材质"] == "Sn-0.7Cu無鉛錫線"
    assert prop["供应商"] == "兴鸿泰"                       # 繁体别名归一 興鴻泰→兴鸿泰
    锡 = [c for c in prop["成份"] if "錫" in c["成份名称"]][0]
    assert 锡["CAS"] == "7440-31-5"                         # '7440-31- 5' 去空格
    assert 锡["重量%"] == "0.993"                           # '99.3wt%' ÷100
    assert prop["RoHS"]["Pb"] == "63"                       # 有数值照填(非因Pass写ND)
    assert prop["报告日期"] == "2025.06.30"                 # 'Jun 30, 2025' 归一
    assert prop["报告编号"] == "SZXEC25002243403"


def test_无RoHS时成分仍提议():
    prop = to_proposal(_load("msds_extract.json"))
    assert prop["材质"] and prop["成份"]
    assert all(v == "" for v in prop["RoHS"].values())     # 无报告 → RoHS 十项空


def test_is_msds判别():
    assert is_msds("材料安全数据表 成份组成: 锡 7440-31-5, 铜 7440-50-8 wt%")
    assert not is_msds("产品图纸 只有一个编号 7440-31-5 无成分表")   # <2 CAS
