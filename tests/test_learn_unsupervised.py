# -*- coding: utf-8 -*-
"""成长学习红线: 人工归位的知识固化→下次同名/同料号文件无监督命中(自动落位, 不进待归位池)。
守红线: 仅强键+足票才强落; exclude只建议不自动; 定位不到材质降级; 旧档兼容。"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl import dicts


def test_学目标维度_lookup返回(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.learn_assign("C2001&C2002(51005&51006).pdf", 材质="磷青铜", 零件="端子", 目标="col:Y")
    r = dicts.lookup_assign("C2001&C2002(51005&51006).pdf")
    assert r.get("目标") == "col:Y" and r.get("材质") == "磷青铜" and r.get("目标票", 0) >= 1


def test_学一次下次无监督命中_col(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    from hitl.file_link import auto_place_by_learning, link_materials
    dicts.learn_assign("C2001&C2002(51005&51006).pdf", 材质="磷青铜", 零件="端子", 目标="col:Y")  # 单A人工确认
    props = [{"材质": "磷青铜", "源文件": "磷铜端子MSDS.pdf"}]                                      # 单B(下次)有磷青铜
    a = auto_place_by_learning("C2001&C2002(51005&51006).pdf", props)
    assert a and a["动作"] == "col" and a["mi"] == 0 and a["桶"] == "RoHS"
    md = str(tmp_path / "mats")
    os.makedirs(md)
    open(os.path.join(md, "C2001&C2002(51005&51006).pdf"), "w").close()
    open(os.path.join(md, "磷铜端子MSDS.pdf"), "w").close()
    linked, unlinked = link_materials(md, props)
    assert "C2001&C2002(51005&51006).pdf" in linked[0]["files"]["RoHS"]    # 无监督落对列
    assert not any("C2001" in u[0] for u in unlinked)                       # 不再进待归位池


def test_排除类不自动落只建议(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    from hitl.file_link import auto_place_by_learning
    dicts.learn_assign("某废件 C9999.pdf", 目标="exclude")
    assert auto_place_by_learning("某废件 C9999.pdf", []) is None           # 红线: 排除不自动复用


def test_col定位不到材质则降级(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    from hitl.file_link import auto_place_by_learning
    dicts.learn_assign("C2001&C2002(51005&51006).pdf", 材质="磷青铜", 目标="col:Y")
    assert auto_place_by_learning("C2001&C2002(51005&51006).pdf",
                                  [{"材质": "锡", "源文件": "x.pdf"}]) is None  # 本单无磷青铜→不强落


def test_弱键不强落防串味(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    from hitl.file_link import auto_place_by_learning
    dicts.learn_assign("端子.pdf", 材质="磷青铜", 目标="col:Y")              # "端子"纯业务词=弱键
    assert auto_place_by_learning("端子.pdf", [{"材质": "磷青铜", "源文件": "x.pdf"}]) is None


def test_旧档无目标键兼容(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    os.makedirs(str(tmp_path), exist_ok=True)
    json.dump({"51005": {"材质": {"磷青铜": 2}, "零件": {"端子": 1}}},   # 旧档(无'目标'键)
              open(os.path.join(str(tmp_path), "归属学习.json"), "w", encoding="utf-8"), ensure_ascii=False)
    r = dicts.lookup_assign("C2001&C2002(51005&51006).pdf")   # 命中旧键51005, 不应 KeyError
    assert r.get("材质") == "磷青铜" and "目标" not in r


def test_forget清理(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.learn_assign("废件C9999.pdf", 材质="磷青铜", 目标="col:Y")     # 单键 C9999
    assert dicts.lookup_assign("废件C9999.pdf").get("材质") == "磷青铜"
    dicts.forget_assign("C9999")                    # 删整条
    assert not dicts.lookup_assign("废件C9999.pdf").get("材质")
