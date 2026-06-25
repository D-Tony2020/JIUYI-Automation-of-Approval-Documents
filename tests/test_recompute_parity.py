# -*- coding: utf-8 -*-
"""口径一致性: 前端 recompute.js(deriveLimits) **真跑 node** == 后端 hitl/fai.spec_limits。

确认环①的实时重算(前端JS)与FAI规格落档(后端Python)必须字节对齐, 否则操作员看到的
LSL/中心/USL 与最终写进承认书的不一致 = 灾难。本测真执行前端JS, 任一边改公式即红灯。
覆盖对称(98±5)与非对称(35上0下3→中心33.5)两类。
"""
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hitl.fai import spec_limits

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DIMS = [(98, 5, 5), (60, 5, 5), (28, 3, 3), (2, 0.5, 0.5),
        (35, 0, 3), (33.5, 1.5, 1.5), (470, 8, 8), (1.5, 0.5, 0.5)]


def _js_derive(dims):
    """真跑 node 执行前端 deriveLimits, 返回 [{lsl,mid,usl}]。"""
    expr = ("import('./app/web/js/recompute.js').then(m=>{const ds="
            + json.dumps([list(d) for d in dims])
            + ";console.log(JSON.stringify(ds.map(d=>m.deriveLimits(d[0],d[1],d[2]))));})")
    r = subprocess.run(["node", "--input-type=module", "-e", expr],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, "node 执行前端JS失败: " + r.stderr
    return json.loads(r.stdout.strip())


def test_recompute_parity():
    js = _js_derive(DIMS)
    for d, jr in zip(DIMS, js):
        lsl, mid, usl = spec_limits(d)
        assert (jr["lsl"], jr["mid"], jr["usl"]) == (lsl, mid, usl), \
            f"口径漂移 dim={d}: 前端JS={jr} vs 后端spec_limits={(lsl, mid, usl)}"
