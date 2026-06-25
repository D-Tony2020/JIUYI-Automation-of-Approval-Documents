# -*- coding: utf-8 -*-
"""BOM 脊柱放行门 app/rules.validate_bom: 每材质 零件+材质类别+供应商 + 已核对(或豁免)。

(零件,材质类别) 是图上没有的不可约人工输入; 这是 M2.3 放行进 M2.4 的门。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.rules import validate_bom

GOOD = {"materials": [
    {"材质": "PVC", "零件": "导线", "材质类别": "线材", "供应商": "正崴", "已核对": True},
    {"材质": "锡", "零件": "锡", "材质类别": "锡丝", "供应商": "兴鸿泰", "已核对": True},
]}


def test_齐全可放行():
    assert validate_bom(GOOD) == []


def test_缺零件拦截():
    b = {"materials": [dict(GOOD["materials"][0], 零件=""), GOOD["materials"][1]]}
    assert any("缺零件" in m for m in validate_bom(b))


def test_缺材质类别拦截():
    b = {"materials": [dict(GOOD["materials"][0], 材质类别=""), GOOD["materials"][1]]}
    assert any("缺材质类别" in m for m in validate_bom(b))


def test_缺供应商拦截():
    b = {"materials": [dict(GOOD["materials"][0], 供应商=""), GOOD["materials"][1]]}
    assert any("缺供应商" in m for m in validate_bom(b))


def test_未核对拦截():
    b = {"materials": [dict(GOOD["materials"][0], 已核对=False), GOOD["materials"][1]]}
    assert any("未核对" in m for m in validate_bom(b))


def test_豁免免核对():
    b = {"materials": [dict(GOOD["materials"][0], 已核对=False, 豁免=True), GOOD["materials"][1]]}
    assert validate_bom(b) == []


def test_空材质拦截():
    assert validate_bom({"materials": []}) != []
