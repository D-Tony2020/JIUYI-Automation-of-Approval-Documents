# -*- coding: utf-8 -*-
"""M2.5 导出预检 app/rules.export_preflight 单测: 全软(永不硬拦) + 溯源含报告日期 + 不做有效期。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from app.rules import export_preflight

_OK = {"材质": "PVC", "零件": "导线", "报告编号": "R1", "报告日期": "2025.06.30", "供应商": "金霖",
       "files": {"MSDS": "a.pdf", "RoHS": ["r.pdf"]}}


def test_照片不足软警():
    r = export_preflight({"materials": [_OK]}, 1)
    assert any(w["类型"] == "照片" for w in r["warnings"])


def test_照片足够无照片警():
    r = export_preflight({"materials": [_OK]}, 2)
    assert not any(w["类型"] == "照片" for w in r["warnings"])


def test_缺MSDS软警():
    r = export_preflight({"materials": [{"材质": "锡", "files": {"MSDS": ""}}]}, 2)
    assert any(w["类型"] == "MSDS" for w in r["warnings"])


def test_缺第三方报告软警():
    r = export_preflight({"materials": [{"材质": "PVC", "files": {"MSDS": "a.pdf", "RoHS": [], "REACH": []}}]}, 2)
    assert any(w["类型"] == "第三方报告" for w in r["warnings"])


def test_豁免不警():
    r = export_preflight({"materials": [{"材质": "锡", "files": {"MSDS": ""}, "豁免": True}]}, 2)
    assert not any(w["类型"] in ("MSDS", "第三方报告") for w in r["warnings"])


def test_未归位软警():
    s3 = {"materials": [_OK], "unlinked_files": [{"文件": "x.pdf", "类型": "RoHS"}]}
    # 无 materials_dir 时回退用 stage3.unlinked_files 算未归位; 类型由"待拖"改"未归位"(零丢失覆盖)
    assert any(w["类型"] == "未归位" for w in export_preflight(s3, 2)["warnings"])


def test_trace含报告日期():
    t = export_preflight({"materials": [_OK]}, 2)["trace"][0]
    assert t["报告日期"] == "2025.06.30" and t["材质"] == "PVC" and t["零件"] == "导线"


def test_全软齐全无警():
    assert export_preflight({"materials": [_OK]}, 2)["warnings"] == []
