# -*- coding: utf-8 -*-
"""确认环① 后端 FastAPI: 薄封装 hitl/drawing_extract + hitl/fai。

端点全部薄封装、复用现有业务核心。前端静态资源挂在 / (放最后, 否则吞 /api)。
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # HITL 根

from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
import fitz

from typing import List

from hitl.drawing_extract import extract as draw_extract
from hitl.fai import spec_limits
from app import state, rules

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(APP_DIR, "web")
app = FastAPI(title="确认环① 图纸识别")


def _dims_to_json(dims):
    """drawing_extract 的 (中心,上,下) → 前端 dict + 派生 LSL/USL(口径=hitl.fai.spec_limits)。"""
    out = []
    for (c, up, lo) in dims:
        lsl, mid, usl = spec_limits((c, up, lo))
        out.append({"中心": c, "上": up, "下": lo, "LSL": lsl, "USL": usl, "中点": mid})
    return out


@app.post("/api/order/upload-drawing")
async def upload_drawing(file: UploadFile = File(...)):
    job = "job_" + uuid.uuid4().hex[:8]
    dest = os.path.join(state.drawing_dir(job), file.filename or "drawing.pdf")
    with open(dest, "wb") as f:
        f.write(await file.read())
    d = fitz.open(dest); pages = d.page_count; d.close()
    state.save_json(job, "project.json", {"job": job, "step": 1, "drawing": os.path.basename(dest)})
    return {"job_id": job, "pages": pages}


@app.post("/api/drawing/{job}/extract")
def do_extract(job: str):
    """qwen-vl 抽 品号/版本/FAI。缓存 stage1_drawing.json 防重复烧 token。"""
    cached = state.load_json(job, "stage1_drawing.json")
    if cached:
        return cached
    pdf = state.drawing_pdf(job)
    if not pdf:
        raise HTTPException(404, "本单无图纸")
    dd = draw_extract(pdf)                       # 官方 DashScope 端点(红线已放行)
    result = {"job": job, "品号": dd["品号"], "版本": dd["版本"], "名称": dd["名称"],
              "dimensions": _dims_to_json(dd["dimensions"]),
              "exemptions": [], "checked": {}, "confirmed": False}
    state.save_json(job, "stage1_drawing.json", result)
    return result


@app.get("/api/drawing/{job}/page/{n}.png")
def page(job: str, n: int):
    """fitz 渲染指定页为 PNG(dpi=220, 确认环专用高清, 供照图核对)。"""
    pdf = state.drawing_pdf(job)
    if not pdf:
        raise HTTPException(404, "本单无图纸")
    d = fitz.open(pdf)
    if n < 0 or n >= d.page_count:
        d.close(); raise HTTPException(404, "页码越界")
    png = d[n].get_pixmap(dpi=220).tobytes("png")
    d.close()
    return Response(png, media_type="image/png")


@app.get("/api/drawing/{job}/state")
def get_state(job: str):
    s = state.load_json(job, "stage1_drawing.json")
    if not s:
        raise HTTPException(404, "本单未抽取")
    return s


@app.post("/api/drawing/{job}/confirm")
async def confirm(job: str, request: Request):
    """落本环最终确认值, 推进第2步。**后端权威校验**(前端门可绕过, 后端兜底)。"""
    body = await request.json()
    missing = rules.validate_confirm(body)
    if missing:
        raise HTTPException(422, "未通过照图核对门: " + " · ".join(missing))
    s = state.load_json(job, "stage1_drawing.json", {})
    s.update(body)
    s["confirmed"] = True
    state.save_json(job, "stage1_drawing.json", s)
    proj = state.load_json(job, "project.json", {"job": job})
    proj["step"] = 2
    state.save_json(job, "project.json", proj)
    return {"ok": True, "step": 2}


# ── M2.3 BOM 脊柱(files-first·B 提议) ──────────────────────────
@app.post("/api/order/{job}/upload-materials")
async def upload_materials(job: str, files: List[UploadFile] = File(...)):
    """批量上传材料 PDF 堆 → 存 materials/ + C 路由分类(file_router)。"""
    from hitl.material_extract import classify_pile
    mdir = state.materials_dir(job)
    saved = []
    for f in files:
        with open(os.path.join(mdir, f.filename or "x.pdf"), "wb") as out:
            out.write(await f.read())
        saved.append(f.filename)
    return {"saved": saved, "classify": classify_pile(mdir)}


@app.post("/api/bom/{job}/extract")
def bom_extract(job: str):
    """B 读 MSDS 提议材质清单(files-first·B 提议)。缓存 stage2_bom.json 防重烧 token。"""
    cached = state.load_json(job, "stage2_bom.json")
    if cached and cached.get("materials"):
        return cached
    from hitl.material_extract import propose_bom_from_pile
    props = propose_bom_from_pile(state.materials_dir(job))
    for p in props:                          # 待操作员填 零件/材质类别 + 报告块核对
        p.setdefault("零件", ""); p.setdefault("材质类别", ""); p.setdefault("已核对", False)
    result = {"job": job, "materials": props, "confirmed": False}
    state.save_json(job, "stage2_bom.json", result)
    return result


@app.get("/api/bom/{job}/state")
def bom_state(job: str):
    s = state.load_json(job, "stage2_bom.json")
    if not s:
        raise HTTPException(404, "本单未提议 BOM")
    return s


@app.post("/api/bom/{job}/confirm")
async def bom_confirm(job: str, request: Request):
    """落 BOM 脊柱, 推进第3步。后端权威校验(齐套+分组+报告块核对)。"""
    body = await request.json()
    missing = rules.validate_bom(body)
    if missing:
        raise HTTPException(422, "BOM 脊柱未齐: " + " · ".join(missing))
    s = state.load_json(job, "stage2_bom.json", {})
    s.update(body); s["confirmed"] = True
    state.save_json(job, "stage2_bom.json", s)
    proj = state.load_json(job, "project.json", {"job": job})
    proj["step"] = 3
    state.save_json(job, "project.json", proj)
    return {"ok": True, "step": 3}


@app.post("/api/bom/{job}/save")
async def bom_save(job: str, request: Request):
    """中途草稿存(不校验), 防刷新丢操作员已填的 零件/类别/勾核。"""
    body = await request.json()
    s = state.load_json(job, "stage2_bom.json", {})
    s.update(body)
    state.save_json(job, "stage2_bom.json", s)
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")   # 前端静态, 必须最后挂
