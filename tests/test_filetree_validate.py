# -*- coding: utf-8 -*-
"""M2.4 确认环②放行门 app/rules.validate_filetree 单测: MSDS必有(或豁免), 第三方软放。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from app.rules import validate_filetree


def test_msds齐放行():
    assert validate_filetree({"materials": [{"材质": "PVC", "files": {"MSDS": "a.pdf"}}]}) == []


def test_缺msds拦():
    m = validate_filetree({"materials": [{"材质": "PVC", "files": {"MSDS": ""}}]})
    assert any("缺MSDS" in x for x in m)


def test_缺msds可豁免放行():
    assert validate_filetree({"materials": [{"材质": "PVC", "files": {"MSDS": ""}, "豁免": True}]}) == []


def test_第三方缺软放不拦():
    body = {"materials": [{"材质": "PVC", "files": {"MSDS": "a.pdf", "RoHS": [], "REACH": [], "SVHC": []}}]}
    assert validate_filetree(body) == []


def test_msds列表形式也认():
    assert validate_filetree({"materials": [{"材质": "PVC", "files": {"MSDS": ["a.pdf"]}}]}) == []


def test_无材质拦():
    assert validate_filetree({"materials": []}) == ["无材质(先完成BOM脊柱)"]


def test_多材质混合():
    body = {"materials": [
        {"材质": "PVC", "files": {"MSDS": "a.pdf"}},
        {"材质": "锡", "files": {"MSDS": ""}},                 # 缺且未豁免→拦
        {"材质": "PA66", "files": {"MSDS": ""}, "豁免": True},  # 豁免→放
    ]}
    m = validate_filetree(body)
    assert len(m) == 1 and "锡缺MSDS" in m[0]
