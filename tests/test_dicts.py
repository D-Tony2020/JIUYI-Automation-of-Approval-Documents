# -*- coding: utf-8 -*-
"""全局字典层 hitl/dicts 单测: 简称规范化包含匹配 / 材质→类别→零件反查 / 未知留空 / 学习回写。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl import dicts


# ── 简称命中(规范化包含匹配, 用真种子, 只读) ──
def test_std_name_FRIANYL归PA66():
    assert dicts.std_name("FRIANYL A3 RV0 NC 1102") == "PA66"


def test_std_name_锡线归锡():
    assert dicts.std_name("Sn-0.7Cu 無鉛錫線") == "锡"


def test_std_name_镀锡铜不误判锡():
    assert dicts.std_name("镀锡铜线") == "镀锡铜"        # 最长token胜, "镀锡铜">"锡线"


def test_std_name_热缩归聚烯烃():
    assert dicts.std_name("无卤无红磷环保热缩套管") == "聚烯烃"


def test_std_name_未知原样返回():
    assert dicts.std_name("某未知料XYZ") == "某未知料XYZ"


# ── 反查派生 ──
def test_resolve_PA66反查胶座端子():
    r = dicts.resolve_material("FRIANYL A3 RV0")
    assert r["标准名"] == "PA66" and r["材质类别"] == "胶座" and r["零件"] == "胶座端子"


def test_resolve_PVC导线线材():
    assert dicts.resolve_material("PVC塑胶粒") == {"标准名": "PVC", "材质类别": "线材", "零件": "导线"}


def test_resolve_磷铜端子归磷青铜端子():
    r = dicts.resolve_material("磷铜端子")
    assert r["标准名"] == "磷青铜" and r["材质类别"] == "端子" and r["零件"] == "胶座端子"


def test_resolve_未知类别零件留空():
    r = dicts.resolve_material("某未知料")
    assert r["材质类别"] == "" and r["零件"] == ""


# ── 学习回写(tmp 不污染种子) ──
def test_learn_alias与catpart回写(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.learn_alias("某新料原文 V2", "新标准")
    assert dicts.std_name("某新料原文 V2") == "新标准"
    dicts.learn_catpart("新标准", "新类别", "新零件")
    r = dicts.resolve_material("某新料原文 V2")
    assert r["标准名"] == "新标准" and r["材质类别"] == "新类别" and r["零件"] == "新零件"


def test_add_supplier去重(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.add_supplier("新供应商")
    dicts.add_supplier("新供应商")
    assert dicts.supplier_history().count("新供应商") == 1


def test_order_parts按持久化序():
    assert dicts.order_parts(["锡", "导线", "X"], ["导线", "锡"]) == ["导线", "锡", "X"]


def test_set_part_order去重保序(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    assert dicts.set_part_order(["导线", "锡", "导线", " "]) == ["导线", "锡"]
