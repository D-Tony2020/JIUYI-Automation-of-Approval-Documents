# -*- coding: utf-8 -*-
"""BOM 编辑器纯逻辑 app/web/js/bomstate.js 的 node 单测(防前后端口径漂移)。

可疑判定镜像 spike/assemble normalize; allMissing 镜像后端 rules.validate_bom。
"""
import json
import os
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _node(body):
    src = "import('./app/web/js/bomstate.js').then(async (m) => {\n" + body + "\n});"
    r = subprocess.run(["node", "--input-type=module", "-e", src],
                       capture_output=True, text=True, cwd=ROOT, encoding="utf-8")
    if r.returncode != 0:
        pytest.skip("node 不可用或导入失败: " + (r.stderr or "")[:200])
    return json.loads(r.stdout.strip())


def test_suspect_rohs数值标黄():
    r = _node("console.log(JSON.stringify(m.suspect({材质:'锡',成份:[{成份名称:'锡',CAS:'7440-31-5','重量%':'0.99'}],RoHS:{Pb:'63'}})));")
    assert any("RoHS" in s for s in r)


def test_suspect_缺CAS标黄():
    r = _node("console.log(JSON.stringify(m.suspect({材质:'X',成份:[{成份名称:'a',CAS:'','重量%':'0.5'}],RoHS:{}})));")
    assert any("CAS" in s for s in r)


def test_suspect_重量未归一标黄():
    r = _node("console.log(JSON.stringify(m.suspect({材质:'X',成份:[{成份名称:'a',CAS:'1-2-3','重量%':'56.4'}],RoHS:{}})));")
    assert any("归一" in s for s in r)


def test_suspect_干净料不标黄():
    r = _node("console.log(JSON.stringify(m.suspect({材质:'X',成份:[{成份名称:'a',CAS:'1-2-3','重量%':'0.5'}],RoHS:{Pb:'ND',Cd:'ND'}})));")
    assert r == []


def test_groupByPart待认领():
    r = _node("const x=m.groupByPart([{材质:'a',零件:'导线'},{材质:'b',零件:''}]);console.log(JSON.stringify({u:x.unclaimed,o:x.order}));")
    assert r["u"] == [1] and r["o"] == ["导线"]


def test_detectDups同名():
    r = _node("console.log(JSON.stringify(m.detectDups([{材质:'白色油墨'},{材质:'白色油墨'},{材质:'PVC'}])));")
    assert len(r) == 1 and len(r[0]) == 2


def test_allMissing镜像validate_bom():
    r = _node("console.log(JSON.stringify(m.allMissing([{材质:'PVC',零件:'',材质类别:'',供应商:'',已核对:false}])));")
    assert any("缺零件" in s for s in r) and any("未核对" in s for s in r)


def test_allMissing齐全放行():
    r = _node("console.log(JSON.stringify(m.allMissing([{材质:'PVC',零件:'导线',材质类别:'线材',供应商:'正崴',已核对:true}])));")
    assert r == []


def test_cardState豁免():
    r = _node("console.log(JSON.stringify(m.cardState({材质:'X',豁免:true},0)));")
    assert r == "exempt"
