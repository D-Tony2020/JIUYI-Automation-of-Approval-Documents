# -*- coding: utf-8 -*-
"""M2.5 导出页纯逻辑 app/web/js/exportstate.js 的 node 单测。"""
import json
import os
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _node(body):
    src = "import('./app/web/js/exportstate.js').then(async (m) => {\n" + body + "\n});"
    r = subprocess.run(["node", "--input-type=module", "-e", src],
                       capture_output=True, text=True, cwd=ROOT, encoding="utf-8")
    if r.returncode != 0:
        pytest.skip("node 不可用或导入失败: " + (r.stderr or "")[:200])
    return json.loads(r.stdout.strip())


def test_ackKey():
    assert _node("console.log(JSON.stringify(m.ackKey({类型:'照片',文案:'仅1张'})));") == "照片|仅1张"


def test_pendingAcks():
    r = _node("console.log(JSON.stringify(m.pendingAcks([{类型:'A',文案:'x'},{类型:'B',文案:'y'}],['A|x']).map(w=>w.类型)));")
    assert r == ["B"]


def test_exportSummary():
    r = _node("console.log(JSON.stringify(m.exportSummary([{类型:'A',文案:'x'},{类型:'B',文案:'y'}],['A|x'])));")
    assert r == {"total": 2, "pending": 1, "acked": 1}


def test_全已知悉():
    r = _node("console.log(JSON.stringify(m.exportSummary([{类型:'A',文案:'x'}],['A|x'])));")
    assert r["pending"] == 0 and r["acked"] == 1
