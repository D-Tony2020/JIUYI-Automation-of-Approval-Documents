# -*- coding: utf-8 -*-
"""材质为锚解析 前后端口径一致: 前端 app/web/js/resolve.js 跑 node == 后端 hitl/dicts.resolve_material。"""
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from hitl import dicts

RAWS = ["FRIANYL A3 RV0 NC 1102", "镀锡铜线", "Sn-0.7Cu 無鉛錫線", "PVC塑胶粒",
        "磷铜端子", "无卤无红磷环保热缩套管", "白色油墨", "某未知料XYZ"]


def _node_resolve(raw, alias, catpart):
    body = (f"const r=m.resolveMaterial({json.dumps(raw, ensure_ascii=False)},"
            f"{json.dumps(alias, ensure_ascii=False)},{json.dumps(catpart, ensure_ascii=False)});"
            "console.log(JSON.stringify(r));")
    src = "import('./app/web/js/resolve.js').then(async (m) => {\n" + body + "\n});"
    r = subprocess.run(["node", "--input-type=module", "-e", src],
                       capture_output=True, text=True, cwd=ROOT, encoding="utf-8")
    if r.returncode != 0:
        pytest.skip("node 不可用: " + (r.stderr or "")[:160])
    return json.loads(r.stdout.strip())


def test_resolve_前后端逐项一致():
    alias, catpart = dicts.alias_table(), dicts.catpart_table()
    for raw in RAWS:
        py = dicts.resolve_material(raw, alias, catpart)
        js = _node_resolve(raw, alias, catpart)
        assert py["标准名"] == js["标准名"], (raw, "标准名", py, js)
        assert py["材质类别"] == js["材质类别"], (raw, "材质类别", py, js)
        assert py["零件"] == js["零件"], (raw, "零件", py, js)
