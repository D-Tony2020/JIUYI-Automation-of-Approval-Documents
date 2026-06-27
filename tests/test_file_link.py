# -*- coding: utf-8 -*-
"""文件↔材质链(hitl/file_link)单测: 报告类型细分 + 报告→材质匹配(回归锁:铜互窜/端子/颜色消歧)。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl.file_link import _ident, _match_report, report_type, suggest_for

import pytest


@pytest.fixture(autouse=True)
def _isolate_learning(monkeypatch):
    # 规则层单测隔离全局成长型 归属学习.json(其随生产使用累积数据会让 suggest_for 走"学"路径, 误破规则断言)。
    from hitl import dicts
    monkeypatch.setattr(dicts, "lookup_assign", lambda *a, **k: {})


def test_report_type():
    assert report_type("镀锡ROHS英文 CANEC26012090003 20260519.pdf") == "RoHS"
    assert report_type("PA66白黑黄绿米 REACH 255项 普通英文 SHAEC.pdf") == "REACH"
    assert report_type("锡线SVHC英文版 SZXEC25002243405.pdf") == "SVHC"
    assert report_type("07CU物質安全資料表无铅锡线 Material Safe Data Sheet.pdf") == "MSDS"
    assert report_type("黑-CANEC25029526001(GZP25-033088).pdf") == "RoHS"  # CANEC/GZP 报告号→RoHS


def test_端子报告不误窜镀锡铜():
    # 端子 报告号 SHAEC26005 含 'C26'(镀锡铜的铜合金码), 不该误吸到镀锡铜
    props = [{"材质": "镀锡铜线", "源文件": "MSDS-镀锡铜线.pdf"},
             {"材质": "磷铜端子", "源文件": "磷铜端子MSDS新.pdf"}]
    ident = [_ident(p) for p in props]
    assert _match_report("端子针 螺丝螺母 镀金锡镍银铜 REACH73项 SHAEC26005175405.pdf", ident) == 1
    assert _match_report("端子 ROHS 普通 英文 SHAEC26005175411.pdf", ident) == 1


def test_镀锡报告归镀锡铜():
    props = [{"材质": "镀锡铜线", "源文件": "MSDS-镀锡铜线.pdf"},
             {"材质": "磷铜端子", "源文件": "磷铜端子MSDS新.pdf"}]
    ident = [_ident(p) for p in props]
    assert _match_report("镀锡ROHS英文 CANEC26012090003 20260519.pdf", ident) == 0
    assert _match_report("镀锡REACH英文-20260519-.pdf", ident) == 0


def test_PA66报告归商品名材质():
    # B提议名是商品名 FRIANYL, 但 MSDS源文件名含 PA66 → 报告(用PA66通用词)能链上
    props = [{"材质": "FRIANYL A3 RV0 NC 1102", "源文件": "PA66 A3RV0 MSDS.pdf"}]
    ident = [_ident(p) for p in props]
    assert _match_report("PA66 ROHS2.0 英文 通用 SHAEC26008284105.pdf", ident) == 0
    assert _match_report("PA66白黑黄绿米 REACH 255项 SHAEC25028572929.pdf", ident) == 0


def test_油墨颜色消歧():
    props = [{"材质": "白色油墨", "源文件": "双鸿油墨安全资料表_EN-CN_白色.pdf"},
             {"材质": "黑色油墨", "源文件": "双鸿油墨安全资料表_EN-CN_黑色.pdf"}]
    ident = [_ident(p) for p in props]
    assert _match_report("白色油墨 ROHS(英文) A2250760240102001.pdf", ident) == 0
    assert _match_report("黑色油墨 ROHS(英文) A2250760240102003.pdf", ident) == 1


def test_无把握返回None():
    props = [{"材质": "PVC塑胶粒", "源文件": "PVC  MSDS.pdf"}]
    ident = [_ident(p) for p in props]
    assert _match_report("红-CANEC25029576401(GZP25-033088).pdf", ident) is None  # 只有色+号→认不准


# ── 建议归属 suggest_for(认不准报告→建议挂哪个材质; token主、颜色兜底) ──
def test_suggest颜色兜底纯色号():
    mats = [{"材质": "白色油墨", "零件": "导线"}, {"材质": "黑色油墨", "零件": "导线"}]
    r = suggest_for("黑-CANEC25029526001(GZP25-033088).pdf", "RoHS", mats)   # 纯色号墨报告
    assert r and r["材质"] == "黑色油墨" and r["据"] == "色" and r["col"] == "Y" and r["idx"] == 1


def test_suggest_token主胜过颜色():
    mats = [{"材质": "黑色油墨", "零件": "导线"},
            {"材质": "镀锡铜", "零件": "导线", "源文件": "镀锡铜MSDS.pdf"}]
    r = suggest_for("镀锡黑色ROHS CANEC.pdf", "RoHS", mats)                   # 含镀锡token + 黑色
    assert r["材质"] == "镀锡铜" and r["据"] == "名"                          # token主, 不被黑色带偏到油墨


def test_suggest无据返None():
    mats = [{"材质": "PVC塑胶粒", "零件": "导线"}]                            # 无红色材质
    assert suggest_for("红-CANEC25029576401(GZP25-033088).pdf", "RoHS", mats) is None


def test_suggest豁免不入选():
    mats = [{"材质": "黑色油墨", "零件": "导线", "豁免": True}]
    assert suggest_for("黑-CANEC25029526001.pdf", "RoHS", mats) is None       # 豁免材质不作建议
