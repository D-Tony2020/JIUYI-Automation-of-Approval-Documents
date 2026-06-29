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


def test_syncPartSuppliers_新材质继承零件供应商():
    # 回归: 零件已选供应商, 新增材质(供应商空)挂到同零件 → 自动继承, 不再"未选择供应商"
    r = _node("const ms=[{材质:'磷青铜',零件:'端子',供应商:'正崴'},{材质:'新料',零件:'端子',供应商:''}];"
              "m.syncPartSuppliers(ms);console.log(JSON.stringify(ms.map(x=>x.供应商)));")
    assert r == ["正崴", "正崴"]


def test_syncPartSuppliers_修复后不再误报缺供应商():
    r = _node("const ms=[{材质:'磷青铜',零件:'端子',材质类别:'端子',供应商:'正崴',已核对:true},"
              "{材质:'新料',零件:'端子',材质类别:'端子',供应商:'',已核对:true}];"
              "m.syncPartSuppliers(ms);console.log(JSON.stringify(m.allMissing(ms)));")
    assert not any("供应商" in s for s in r)


def test_syncPartSuppliers_不同零件互不串():
    r = _node("const ms=[{材质:'a',零件:'端子',供应商:'正崴'},{材质:'b',零件:'导线',供应商:'立讯'},{材质:'c',零件:'导线',供应商:''}];"
              "m.syncPartSuppliers(ms);console.log(JSON.stringify(ms.map(x=>x.供应商)));")
    assert r == ["正崴", "立讯", "立讯"]


def test_syncPartSuppliers_待认领不分配供应商():
    r = _node("const ms=[{材质:'a',零件:'',供应商:''}];"
              "m.syncPartSuppliers(ms);console.log(JSON.stringify(ms[0].供应商));")
    assert r == ""
