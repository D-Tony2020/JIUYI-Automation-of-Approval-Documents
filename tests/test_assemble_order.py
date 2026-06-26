# -*- coding: utf-8 -*-
"""M2.4 段二装配 hitl/assemble_order 纯函数单测(COM 装配由 run_m24_e2e --com 验)。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl.assemble_order import count_specs_by_sheet, dims_from_stage1


def test_dims_from_stage1_无豁免全取():
    s1 = {"dimensions": [{"中心": 470, "上": 8, "下": 8}, {"中心": 98, "上": 5, "下": 5}]}
    assert dims_from_stage1(s1) == [(470, 8, 8), (98, 5, 5)]


def test_dims_from_stage1_豁免跳过不写():
    s1 = {"dimensions": [{"中心": 470, "上": 8, "下": 8}, {"中心": 98, "上": 5, "下": 5},
                         {"中心": 1.5, "上": 0.5, "下": 0.5}],
          "exemptions": [{"序号": 1}]}                  # 豁免第2个尺寸(98)
    assert dims_from_stage1(s1) == [(470, 8, 8), (1.5, 0.5, 0.5)]   # 98 跳过不写FAI


def test_count_specs_by_sheet():
    specs = [{"sheet": "7.材质成分展开表 "}, {"sheet": "7.材质成分展开表 "}, {"sheet": "8.材质证明书"}]
    assert count_specs_by_sheet(specs) == {"7.材质成分展开表 ": 2, "8.材质证明书": 1}


def test_count_specs_空():
    assert count_specs_by_sheet([]) == {}
