# -*- coding: utf-8 -*-
"""后端权威放行门 app/rules.validate_confirm: 三要素+尺寸 格式 + 勾核/豁免。

放行前提=操作员逐条声明照图核对过; 前端门可绕过(直打API), 后端必须独立兜底。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.rules import validate_confirm

GOOD = {
    "品号": "SB120420BLCN0009", "版本": "A01", "名称": "导线",
    "dimensions": [{"中心": 98, "上": 5, "下": 5}, {"中心": 35, "上": 0, "下": 3}],
    "checked": {"id0": True, "id1": True, "id2": True, "dim0": True, "dim1": True},
    "exemptions": [],
}


def test_全勾核且格式正确可放行():
    assert validate_confirm(GOOD) == []


def test_某尺寸未勾核拦截():
    b = dict(GOOD, checked=dict(GOOD["checked"], dim1=False))
    assert "尺寸2未勾核" in validate_confirm(b)


def test_版本格式异常拦截():
    assert any("版本格式" in m for m in validate_confirm(dict(GOOD, 版本="AA1")))


def test_品号过短拦截():
    assert any("品号格式" in m for m in validate_confirm(dict(GOOD, 品号="X1")))


def test_豁免的尺寸不要求勾核():
    b = dict(GOOD, checked={"id0": True, "id1": True, "id2": True, "dim0": True},
             exemptions=[{"序号": 1, "原因": "该尺寸非受检"}])
    assert validate_confirm(b) == []


def test_公差负值拦截():
    b = dict(GOOD, dimensions=[{"中心": 98, "上": -5, "下": 5}, {"中心": 35, "上": 0, "下": 3}])
    assert any("尺寸1公差" in m for m in validate_confirm(b))
