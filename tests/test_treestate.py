# -*- coding: utf-8 -*-
"""M2.4 文件树纯逻辑 app/web/js/treestate.js 的 node 单测(防前后端口径漂移)。

filetreeMissing 须镜像后端 rules.validate_filetree(MSDS必有或豁免)。
"""
import json
import os
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _node(body):
    src = "import('./app/web/js/treestate.js').then(async (m) => {\n" + body + "\n});"
    r = subprocess.run(["node", "--input-type=module", "-e", src],
                       capture_output=True, text=True, cwd=ROOT, encoding="utf-8")
    if r.returncode != 0:
        pytest.skip("node 不可用或导入失败: " + (r.stderr or "")[:200])
    return json.loads(r.stdout.strip())


_BOM = ("{materials:["
        "{材质:'PVC',零件:'导线',files:{MSDS:'PVC.pdf',RoHS:['PVC_R.pdf'],REACH:[],SVHC:[],其他:[]}},"
        "{材质:'镀锡铜',零件:'导线',files:{MSDS:'DXT.pdf',RoHS:['DXT_R.pdf'],REACH:['DXT_RE.pdf'],SVHC:[],其他:[]}},"
        "{材质:'磷铜',零件:'端子',files:{MSDS:'LT.pdf',RoHS:[],REACH:[],SVHC:[],其他:[]}}],"
        "unlinked_files:[{文件:'红-CANEC.pdf',类型:'RoHS'}]}")


def test_planTree分组与槽():
    r = _node(f"const t=m.planTree({_BOM});console.log(JSON.stringify("
              "{order:t.order,parts:t.parts,n:t.materials.length,"
              "pvcK:t.materials[0].slots.K.length,dxtL:t.materials[1].slots.L.length,unl:t.unlinked.length}));")
    assert r["order"] == ["导线", "端子"]
    assert r["parts"]["导线"] == [0, 1] and r["parts"]["端子"] == [2]
    assert r["pvcK"] == 1 and r["dxtL"] == 1 and r["unl"] == 1


def test_slotState():
    r = _node("const COLS=(await import('./app/web/js/treestate.js')).COLS;"
              "const K=COLS[0],Y=COLS[2];"
              "console.log(JSON.stringify({"
              "ok:m.slotState({files:{MSDS:'a.pdf'}},K),"
              "todo:m.slotState({files:{}},Y),"
              "exempt:m.slotState({豁免:true,files:{}},K)}));")
    assert r["ok"] == "ok" and r["todo"] == "todo" and r["exempt"] == "exempt"


def test_filetreeMissing缺MSDS():
    r = _node("console.log(JSON.stringify(m.filetreeMissing({materials:[{材质:'锡',files:{MSDS:''}}]})));")
    assert any("缺MSDS" in s for s in r)


def test_filetreeMissing豁免放行():
    r = _node("console.log(JSON.stringify(m.filetreeMissing({materials:[{材质:'锡',files:{MSDS:''},豁免:true}]})));")
    assert r == []


def test_filetreeMissing第三方缺不拦():
    r = _node(f"console.log(JSON.stringify(m.filetreeMissing({_BOM})));")
    assert r == []                                   # 磷铜无RoHS/REACH 但有MSDS→软放


def test_filetreeMissing齐全():
    r = _node("console.log(JSON.stringify(m.filetreeMissing({materials:[{材质:'PVC',files:{MSDS:'a.pdf'}}]})));")
    assert r == []


def test_materialMsds列表形式():
    r = _node("console.log(JSON.stringify(m.materialMsds({files:{MSDS:['x.pdf']}})));")
    assert r == "x.pdf"
