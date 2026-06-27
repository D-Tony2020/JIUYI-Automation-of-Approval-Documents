# -*- coding: utf-8 -*-
"""确认环① 后端 FastAPI: 薄封装 hitl/drawing_extract + hitl/fai。

端点全部薄封装、复用现有业务核心。前端静态资源挂在 / (放最后, 否则吞 /api)。
"""
import datetime
import json
import os
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # HITL 根

from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
import fitz

from typing import List

from hitl.drawing_extract import extract as draw_extract
from hitl.fai import spec_limits
from app import state, rules

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(APP_DIR, "web")
app = FastAPI(title="确认环① 图纸识别")


@app.middleware("http")
async def _no_cache(request, call_next):
    """开发/手测期: 前端静态不缓存(否则改了 JS 浏览器仍跑旧版, 手测看不到变化)。"""
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


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
    # 文件↔材质链(M2.4 OLE放置据此落K/L/Y格); 认不准的报告留确认环②人工拖
    try:
        from hitl.file_link import link_materials
        from hitl.material_extract import enrich_rohs
        linked, unlinked = link_materials(state.materials_dir(job), s.get("materials", []))
        enrich_rohs(linked, state.materials_dir(job))        # B 读 RoHS 报告填 10 项值(+报告号/日期)
        s["materials"] = linked
        s["unlinked_files"] = [{"文件": b, "类型": t} for b, t in unlinked]
    except Exception:
        pass                                     # 链/抽失败不挡放行(M2.4 可纯人工拖)
    state.save_json(job, "stage2_bom.json", s)
    proj = state.load_json(job, "project.json", {"job": job})
    proj["step"] = 3
    state.save_json(job, "project.json", proj)
    return {"ok": True, "step": 3, "unlinked": len(s.get("unlinked_files", []))}


@app.post("/api/bom/{job}/save")
async def bom_save(job: str, request: Request):
    """中途草稿存(不校验), 防刷新丢操作员已填的 零件/类别/勾核。"""
    body = await request.json()
    s = state.load_json(job, "stage2_bom.json", {})
    s.update(body)
    state.save_json(job, "stage2_bom.json", s)
    return {"ok": True}


# ── M2.4 确认环② 文件树 ────────────────────────────────────
@app.get("/api/filetree/{job}/state")
def filetree_state(job: str):
    """读放置计划现场(断点续做): 优先 stage3_filetree, 回退 stage2_bom(含 files/unlinked_files)。"""
    s = state.load_json(job, "stage3_filetree.json") or state.load_json(job, "stage2_bom.json")
    if not s:
        raise HTTPException(404, "本单未完成BOM脊柱")
    if s.get("unlinked_files"):                       # 认不准报告附"建议归属"(BOM材质颜色/token, 操作员一点即挂)
        from hitl.file_link import suggest_unlinked
        s = dict(s, unlinked_files=suggest_unlinked(s.get("materials", []), s["unlinked_files"]))
    try:                                              # 横排部件报告(部件承认/UL/信赖性) + 建议零件(供④归属选择)
        from hitl.placement_plan import grid_reports, stage2_to_nested_bom
        nested, _ = stage2_to_nested_bom(s.get("materials", []))
        po = [p["零件"] for p in nested]
        s = dict(s, grid_reports=grid_reports(state.materials_dir(job), s.get("materials", []), po),
                 parts=[p["零件"] for p in nested])    # 零件下拉选项
    except Exception:
        pass
    return s


@app.get("/api/orders")
def list_orders():
    """最近本单列表(断点续做首页): 各单品号/名称 + 各步进度 + 续做步。按更新时间倒序。"""
    import glob
    out = []
    for d in sorted(glob.glob(os.path.join(state.WORK, "*"))):
        if not os.path.isdir(d):
            continue
        job = os.path.basename(d)
        if job.startswith(("_", "demo_", "_wf")):           # 跳过临时/测试单
            continue
        s1 = state.load_json(job, "stage1_drawing.json") or {}
        proj = state.load_json(job, "project.json") or {}
        ov = overview(job)
        resume = 4
        for n in ("1", "2", "3", "4"):                       # 续做步=第一个未完成步
            o = ov.get(n)
            if not o or o.get("缺", 0) > 0:
                resume = int(n)
                break
        out.append({"job": job, "品号": s1.get("品号", ""), "名称": s1.get("名称", ""),
                    "overview": ov, "resume": resume, "exported": bool(proj.get("exported")),
                    "updated": os.path.getmtime(d)})
    out.sort(key=lambda x: -x["updated"])
    return out


@app.get("/api/overview/{job}")
def overview(job: str):
    """全流程总进度(供步条缺N徽标+断点续做首页): 各步缺项数+是否完成。各步状态文件不存在则该步缺=null。"""
    out = {}
    s1 = state.load_json(job, "stage1_drawing.json")
    if s1:
        out["1"] = {"缺": len(rules.validate_confirm(s1)), "done": bool(s1.get("confirmed"))}
    s2 = state.load_json(job, "stage2_bom.json")
    if s2:
        out["2"] = {"缺": len(rules.validate_bom(s2)), "done": bool(s2.get("confirmed"))}
    s3raw = state.load_json(job, "stage3_filetree.json")
    s3 = s3raw or s2
    if s3:
        out["3"] = {"缺": len(rules.validate_filetree(s3)), "done": bool((s3raw or {}).get("confirmed_filetree"))}
        try:
            ph = len(state.photos_list(job))
        except Exception:
            ph = 0
        try:
            warns = rules.export_preflight(s3, ph).get("warnings", [])
        except Exception:
            warns = []
        proj = state.load_json(job, "project.json") or {}
        out["4"] = {"缺": len(warns), "done": bool(proj.get("exported"))}
    return out


@app.post("/api/filetree/{job}/save")
async def filetree_save(job: str, request: Request):
    """中途草稿存(不校验), 防刷新丢拖拽纠正。"""
    body = await request.json()
    s = state.load_json(job, "stage3_filetree.json") or state.load_json(job, "stage2_bom.json", {})
    s.update(body)
    state.save_json(job, "stage3_filetree.json", s)
    return {"ok": True}


@app.post("/api/filetree/{job}/confirm")
async def filetree_confirm(job: str, request: Request):
    """落放置计划, 推进第5步。权威校验(每材质 MSDS 必有或豁免)。"""
    body = await request.json()
    missing = rules.validate_filetree(body)
    if missing:
        raise HTTPException(422, "文件树未齐: " + " · ".join(missing))
    s = state.load_json(job, "stage3_filetree.json") or state.load_json(job, "stage2_bom.json", {})
    s.update(body); s["confirmed_filetree"] = True
    state.save_json(job, "stage3_filetree.json", s)
    proj = state.load_json(job, "project.json", {"job": job})
    proj["step"] = 5
    state.save_json(job, "project.json", proj)
    return {"ok": True, "step": 5}


# ── M2.5 ⑤照片 + 总装导出 ──────────────────────────────────
@app.post("/api/order/{job}/upload-photos")
async def upload_photos(job: str, files: List[UploadFile] = File(...)):
    """上传样品照片(剪贴板粘贴/文件选择, 2–4 张) → 存 photos/。"""
    pdir = state.photos_dir(job)
    for f in files:
        with open(os.path.join(pdir, f.filename or "photo.png"), "wb") as out:
            out.write(await f.read())
    return {"photos": state.photos_list(job)}


@app.get("/api/order/{job}/photos")
def list_photos(job: str):
    """已传样品照片(断点续做)。"""
    return {"photos": state.photos_list(job)}


@app.get("/api/order/{job}/photos/raw")
def photo_raw(job: str, name: str):
    """取某张照片原图(刷新后缩略图预览用)。"""
    p = os.path.join(state.photos_dir(job), os.path.basename(name))
    if not os.path.exists(p):
        raise HTTPException(404, "无此照片")
    return FileResponse(p)


@app.delete("/api/order/{job}/photos/{name}")
def delete_photo(job: str, name: str):
    """删某张照片(重传)。"""
    p = os.path.join(state.photos_dir(job), os.path.basename(name))
    if os.path.exists(p):
        os.remove(p)
    return {"photos": state.photos_list(job)}


@app.get("/api/export/{job}/preflight")
def export_preflight_ep(job: str):
    """导出预检(全软, 零 COM 快): 软预警 + 溯源(含报告日期)。"""
    s = state.load_json(job, "stage3_filetree.json") or state.load_json(job, "stage2_bom.json", {})
    return rules.export_preflight(s, len(state.photos_list(job)))


@app.post("/api/export/{job}/acknowledge")
async def export_acknowledge(job: str, request: Request):
    """存已知悉项(防刷新丢)。"""
    body = await request.json()
    proj = state.load_json(job, "project.json", {"job": job})
    proj["acknowledged"] = body.get("acknowledged", [])
    state.save_json(job, "project.json", proj)
    return {"ok": True}


@app.post("/api/export/{job}/assemble")
async def export_assemble(job: str, request: Request):
    """段二总装(子进程跑 COM/WPS + 超时) → 终态承认书。落档 + 开目录 + 留痕 project.json。"""
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    hitl_root = os.path.dirname(APP_DIR)
    try:
        r = subprocess.run([sys.executable, "-m", "hitl.assemble_order", job],
                           cwd=hitl_root, capture_output=True, text=True, timeout=300, encoding="utf-8")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "装配超时(WPS 可能卡), 请重试")
    out = r.stdout or ""
    mk = "@@RESULT@@"
    res = json.loads(out[out.rindex(mk) + len(mk):].strip()) if mk in out else {"ok": False, "err": (r.stderr or "")[-200:]}
    if not res.get("ok"):
        raise HTTPException(500, "装配失败: " + str(res.get("err", "?")))
    proj = state.load_json(job, "project.json", {"job": job})
    proj.update({"step": 5, "exported": True, "out_path": res.get("out"), "ole": res.get("ole"),
                 "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
                 "acknowledged": body.get("acknowledged", proj.get("acknowledged", []))})
    state.save_json(job, "project.json", proj)
    try:
        os.startfile(os.path.dirname(res["out"]))   # Windows 开输出目录
    except Exception:
        pass
    return res


@app.get("/api/export/{job}/download")
def export_download(job: str):
    """下载已导出的终态承认书 xlsx。"""
    proj = state.load_json(job, "project.json", {})
    p = proj.get("out_path")
    if not p or not os.path.exists(p):
        raise HTTPException(404, "尚未导出")
    return FileResponse(p, filename=os.path.basename(p),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── 全局字典(材质简称/类别零件反查/供应商历史) ──────────────
@app.get("/api/dict")
def get_dict():
    """BOM 页一次拉全: {alias, catpart, suppliers}。"""
    from hitl import dicts
    return dicts.all_dicts()


@app.post("/api/dict/learn")
async def learn_dict(request: Request):
    """操作员改材质名/类别/零件/供应商 → 回写学习(全局持久化)。返回更新后全字典。"""
    from hitl import dicts
    body = await request.json()
    for e in body.get("alias", []):
        dicts.learn_alias(e.get("原文"), e.get("std"))
    for e in body.get("catpart", []):
        dicts.learn_catpart(e.get("std"), e.get("材质类别"), e.get("零件"))
    for s in body.get("suppliers", []):
        dicts.add_supplier(s)
    if "part_order" in body:
        dicts.set_part_order(body["part_order"])
    return dicts.all_dicts()


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")   # 前端静态, 必须最后挂
