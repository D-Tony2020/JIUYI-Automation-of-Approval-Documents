# -*- coding: utf-8 -*-
"""成份知识库: 材质成份库(自动跟踪增删) + CAS规范库(双向) + 串成 材质→成份→CAS→规范名 链。"""
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from hitl import dicts


def test_cas规范库双向(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.learn_cas_name("7440-50-8", "铜(Cu)")
    assert dicts.cas_name("7440-50-8") == "铜(Cu)"
    assert dicts.name_cas("铜(Cu)") == "7440-50-8"          # 双向
    dicts.learn_cas_name("junk", "x")
    assert dicts.cas_name("junk") == ""                      # 非法CAS不学
    dicts.learn_cas_name("7440-50-8", "Cu")
    assert dicts.cas_name("7440-50-8") == "铜(Cu)"           # 已登记不被简写覆盖(种子规范优先)


def test_材质成份库自动跟踪增删(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.learn_material_comp("磷青铜", [{"成份名称": "铜", "CAS": "7440-50-8"},
                                        {"成份名称": "锡", "CAS": "7440-31-5"}])
    cs = dicts.material_comps("磷青铜")
    assert len(cs) == 2 and cs[0]["CAS"] == "7440-50-8"
    dicts.learn_material_comp("磷青铜", [{"成份名称": "铜", "CAS": "7440-50-8"}])   # 操作员删了锡
    assert len(dicts.material_comps("磷青铜")) == 1           # 整表替换=跟踪增删


def test_normalize成份名用CAS规范库(tmp_path, monkeypatch):
    monkeypatch.setattr(dicts, "DATA", str(tmp_path))
    dicts.learn_cas_name("7440-50-8", "铜(Cu)")
    from hitl.material_table import normalize_component_name
    assert normalize_component_name("任意材质", "7440-50-8", "Copper") == "铜(Cu)"  # 全局CAS规范库优先于原文


def test_种子已生成可读():
    import json
    seed = os.path.join(ROOT, "hitl", "data")
    comp = json.load(open(os.path.join(seed, "材质成份字典.json"), encoding="utf-8"))
    cas = json.load(open(os.path.join(seed, "CAS规范字典.json"), encoding="utf-8"))
    assert "镀锡铜" in comp and cas.get("7440-50-8") == "铜(Cu)"
