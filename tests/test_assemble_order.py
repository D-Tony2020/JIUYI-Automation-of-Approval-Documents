# -*- coding: utf-8 -*-
"""M2.4 段二装配 hitl/assemble_order 纯函数单测(COM 装配由 run_m24_e2e --com 验)。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl.assemble_order import count_specs_by_sheet


def test_count_specs_by_sheet():
    specs = [{"sheet": "7.材质成分展开表 "}, {"sheet": "7.材质成分展开表 "}, {"sheet": "8.材质证明书"}]
    assert count_specs_by_sheet(specs) == {"7.材质成分展开表 ": 2, "8.材质证明书": 1}


def test_count_specs_空():
    assert count_specs_by_sheet([]) == {}
