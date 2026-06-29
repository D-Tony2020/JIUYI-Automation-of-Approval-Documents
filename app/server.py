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
from hitl import userdata
from app import state, rules

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(userdata.resource_base(), "app", "web")   # 静态前端(随程序; dev=app/web, 冻结=_MEIPASS/app/web)
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


@app.post("/api/bom/{job}/extract-more")
def bom_extract_more(job: str):
    """继续上传后再抽(防业务员传一半就确认): 全池重新提议, 按 源文件/材质原文 合并——
    已有(可能已人工编辑)的材质原样保留, 只追加新文件带出的新材质。返回含 _added 计数。"""
    from hitl.material_extract import propose_bom_from_pile
    cached = state.load_json(job, "stage2_bom.json", {}) or {}
    existing = list(cached.get("materials") or [])
    seen_src = {(m.get("源文件") or "").strip() for m in existing if (m.get("源文件") or "").strip()}
    seen_raw = {(m.get("材质原文") or m.get("材质") or "").strip() for m in existing}
    added = 0
    for p in propose_bom_from_pile(state.materials_dir(job)):
        src = (p.get("源文件") or "").strip()
        raw = (p.get("材质原文") or p.get("材质") or "").strip()
        if (src and src in seen_src) or (not src and raw in seen_raw):
            continue                                   # 该源文件/材质已在→不动(保人工编辑)
        p.setdefault("零件", "")
        p.setdefault("材质类别", "")
        p.setdefault("已核对", False)
        existing.append(p)
        added += 1
        if src:
            seen_src.add(src)
        if raw:
            seen_raw.add(raw)
    result = {"job": job, "materials": existing, "confirmed": cached.get("confirmed", False), "_added": added}
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
        from hitl.file_link import link_materials, report_type, learned_slot_assignments
        from hitl.file_router import route as _route
        from hitl.file_account import account_files
        from hitl.material_extract import enrich_rohs
        linked, unlinked = link_materials(state.materials_dir(job), s.get("materials", []))
        enrich_rohs(linked, state.materials_dir(job))        # B 读 RoHS 报告填 10 项值(+报告号/日期)
        s["materials"] = linked
        pg = dict(s.get("部件归属") or {})                    # 无监督命中·横排/页级槽: 学过的料号文件自动归槽(人工优先, 不覆盖)
        for fn, a in learned_slot_assignments(state.materials_dir(job), linked).items():
            pg.setdefault(fn, a)
        s["部件归属"] = pg
        # 零丢失: 覆盖审计算出全部待归位(含 route=∅未识别 + 豁免材质的文件), 统一进认不准/待归位池
        acc = account_files(state.materials_dir(job), linked, s.get("部件归属"),
                            s.get("excluded_files"), state.drawing_pdf(job))
        s["unlinked_files"] = [{"文件": b, "类型": (report_type(b) if _route(b) else "未识别")}
                               for b in acc["pending"]]
    except Exception:
        pass                                     # 链/抽失败不挡放行(M2.4 可纯人工拖)
    try:                                          # 成长: 学材质成份清单 + CAS↔规范名(操作员③确认的最终态, 自动跟踪增删)
        from hitl import dicts as _d
        for m in s.get("materials", []):
            if m.get("豁免"):
                continue
            comps = m.get("成份") or []
            _d.learn_material_comp(m.get("材质"), comps)
            for c in comps:
                _d.learn_cas_name(c.get("CAS") or c.get("cas"), c.get("成份名称") or c.get("成份名"))
    except Exception:
        pass
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


@app.post("/api/bom/{job}/log")
async def bom_log(job: str, request: Request):
    """人工修改审计留痕(append-only, 后端盖时戳): 存 修改记录.json。准入追责可溯。"""
    if not state.assert_job(job):
        raise HTTPException(400, "非法单号")
    body = await request.json()
    log = state.load_json(job, "修改记录.json", []) or []
    log.append({"t": datetime.datetime.now().isoformat(timespec="seconds"),
                "操作": str(body.get("操作", ""))[:40], "详情": str(body.get("详情", ""))[:300]})
    state.save_json(job, "修改记录.json", log)
    return {"ok": True, "n": len(log)}


@app.get("/api/bom/{job}/log")
def bom_log_get(job: str):
    """读本单人工修改记录(审计)。"""
    if not state.assert_job(job):
        raise HTTPException(400, "非法单号")
    return {"log": state.load_json(job, "修改记录.json", []) or []}


# ── M2.4 确认环② 文件树 ────────────────────────────────────
@app.get("/api/filetree/{job}/state")
def filetree_state(job: str):
    """读放置计划现场(断点续做): 优先 stage3_filetree, 回退 stage2_bom(含 files/unlinked_files)。"""
    s = state.load_json(job, "stage3_filetree.json") or state.load_json(job, "stage2_bom.json")
    if not s:
        raise HTTPException(404, "本单未完成BOM脊柱")
    try:                                              # 零丢失: 覆盖审计重算待归位(部件归属/排除变动后实时), 含 route=∅未识别 + 豁免材质文件
        from hitl.file_account import account_files
        from hitl.file_link import report_type
        from hitl.file_router import route as _route
        acc = account_files(state.materials_dir(job), s.get("materials", []), s.get("部件归属"),
                            s.get("excluded_files"), state.drawing_pdf(job))
        s = dict(s, unlinked_files=[{"文件": b, "类型": (report_type(b) if _route(b) else "未识别")}
                                    for b in acc["pending"]],
                 excluded_files=s.get("excluded_files", []), pending_count=len(acc["pending"]))
    except Exception:
        pass
    if s.get("unlinked_files"):                       # 认不准/未识别报告附"建议归属"(BOM材质颜色/token + 横排零件, 操作员一点即挂)
        from hitl.file_link import suggest_unlinked
        s = dict(s, unlinked_files=suggest_unlinked(s.get("materials", []), s["unlinked_files"]))
    try:                                              # 统一卡片模型(部件卡 槽=零件 + 页级单槽卡) + 零件下拉选项
        from hitl.placement_plan import grid_reports, build_cards, stage2_to_nested_bom
        nested, _ = stage2_to_nested_bom(s.get("materials", []))
        po = [p["零件"] for p in nested]
        s = dict(s, cards=build_cards(s, state.materials_dir(job), state.drawing_pdf(job)),
                 grid_reports=grid_reports(state.materials_dir(job), s.get("materials", []), po,
                                           part_assign=s.get("部件归属"), excluded=s.get("excluded_files")),
                 parts=[p["零件"] for p in nested])    # grid_reports 旧字段并存一版兼容
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
            warns = rules.export_preflight(s3, ph, drawing_name=(s1 or {}).get("名称", ""),
                                           category_confirmed=(s1 or {}).get("品类", ""),
                                           materials_dir=state.materials_dir(job),
                                           drawing_pdf=state.drawing_pdf(job)).get("warnings", [])
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
    try:                                              # 成长型: 学习本单确认的全部归位真值→下单无监督命中(目标维度: 材质列/横排槽/排除)
        from hitl import dicts
        _TYP_COL = {"其他": "col:K", "REACH": "col:L", "SVHC": "col:L", "RoHS": "col:Y"}   # MSDS=源, 不学目标
        for m in s.get("materials", []):
            if m.get("豁免"):
                continue
            fz = m.get("files") or {}
            for typ in ("MSDS", "RoHS", "REACH", "SVHC", "其他"):
                v = fz.get(typ)
                for f in ([v] if isinstance(v, str) else (v or [])):
                    if f:
                        dicts.learn_assign(f, 材质=m.get("材质"), 零件=m.get("零件"), 目标=_TYP_COL.get(typ))
        for fn, v in (s.get("部件归属") or {}).items():    # 值支持 {槽,零件}(新)或 零件str(旧)
            槽 = v.get("槽") if isinstance(v, dict) else None
            零件 = v.get("零件") if isinstance(v, dict) else v
            dicts.learn_assign(fn, 零件=零件, 目标=("slot:" + 槽) if 槽 else None)
        for e in (s.get("excluded_files") or []):     # 排除也学(命中侧默认只建议不自动, 见 auto_place_by_learning)
            fn = e.get("文件") if isinstance(e, dict) else e
            if fn:
                dicts.learn_assign(fn, 目标="exclude")
    except Exception:
        pass
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
    """导出预检(全软, 零 COM 快): 软预警(含品类词) + 溯源(含报告日期)。"""
    s = state.load_json(job, "stage3_filetree.json") or state.load_json(job, "stage2_bom.json", {})
    s1 = state.load_json(job, "stage1_drawing.json", {})
    return rules.export_preflight(s, len(state.photos_list(job)),
                                  drawing_name=s1.get("名称", ""), category_confirmed=s1.get("品类", ""),
                                  materials_dir=state.materials_dir(job), drawing_pdf=state.drawing_pdf(job))


@app.get("/api/category/dict")
def category_dict_ep():
    """前端品类词下拉: 内置词典 + 已学品类(去重保序)。"""
    from hitl import category, dicts
    learned = sorted({str(v).strip() for v in dicts.category_dict().values() if str(v).strip()})
    out, seen = [], set()
    for w in list(category.CATEGORY_DICT) + learned:
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return {"categories": out}


@app.post("/api/order/{job}/category")
async def confirm_category(job: str, request: Request):
    """操作员确认封面品类词: 学习库回写(成长型·跨单/色变体) + 写回本单 stage1(本单装配即时命中)。"""
    body = await request.json()
    名称 = str(body.get("名称") or "").strip()
    品类 = str(body.get("品类") or "").strip()
    if not 品类:
        raise HTTPException(400, "品类词不能为空")
    from hitl import dicts
    if 名称:
        dicts.learn_category(名称, 品类)
    s1 = state.load_json(job, "stage1_drawing.json", {})
    s1["品类"] = 品类
    state.save_json(job, "stage1_drawing.json", s1)
    return {"ok": True, "品类": 品类}


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
    if getattr(sys, "frozen", False):
        from hitl.assemble_order import assemble_job          # 冻结exe无 python -m → 进程内装配(无子进程隔离, 但可跑)
        try:
            res = assemble_job(job)
        except Exception as e:
            res = {"ok": False, "err": str(e)[-200:]}
    else:
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
        err = str(res.get("err", "?"))
        raise HTTPException(400 if "品类词" in err else 500, "装配失败: " + err)   # 品类词无来源=软进硬出唯一硬门(400)
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


@app.delete("/api/dict/assign")
async def forget_assign_ep(request: Request):
    """清理归属学习库(可见可清理红线): body={key?, 维度?, 值?} 删整条/某维度/某项。返回更新后全字典。"""
    from hitl import dicts
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    dicts.forget_assign(body.get("key"), body.get("维度"), body.get("值"))
    return dicts.all_dicts()


# ── 材料文件池: 暴露 materials/ 给用户直拖 + 实时跟踪(拖入=UI上传, 同一池) ──────
@app.post("/api/order/{job}/open-materials")
def open_materials(job: str):
    """资源管理器打开本单材料文件池(materials/), 供操作员把散落各处的 MSDS/报告直接拖进来。
    照 export_assemble 的 os.startfile+try/except 静默范式; Windows 本机桌面有效。"""
    if not state.assert_job(job):
        raise HTTPException(400, "非法单号")
    d = state.materials_dir(job)
    try:
        os.startfile(d)                                  # noqa: Windows-only(本产品形态)
        return {"ok": True, "path": d}
    except Exception as e:
        return {"ok": False, "err": str(e), "path": d}


@app.post("/api/order/{job}/open-file")
async def open_file(job: str, request: Request):
    """打开本单某源文件(materials/<name>)给操作员核对——用默认PDF阅读器。
    路径安全: 仅取 basename, 必须确在 materials/ 内, 防穿越。"""
    if not state.assert_job(job):
        raise HTTPException(400, "非法单号")
    body = await request.json()
    name = os.path.basename(str(body.get("name") or ""))       # 只收 basename, 去路径
    d = state.materials_dir(job)
    fp = os.path.join(d, name)
    if not name or os.path.dirname(os.path.abspath(fp)) != os.path.abspath(d) or not os.path.isfile(fp):
        raise HTTPException(404, "源文件不存在")
    try:
        os.startfile(fp)                                       # noqa: Windows-only(本产品形态)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "err": str(e)}


@app.get("/api/order/{job}/pool")
def pool(job: str):
    """材料文件池跟踪: 列 materials/ 现有文件 + 概括识别类型(UI上传/直拖都进同一池, 实时可见)。"""
    if not state.assert_job(job):
        raise HTTPException(400, "非法单号")
    from hitl.file_router import route
    from hitl.material_extract import is_msds_name
    files = []
    for b in state.materials_list(job):
        slots = route(b)
        if "材质表" in slots and is_msds_name(b):
            t = "MSDS(材质源)"
        elif "材质表" in slots:
            t = "材质报告(RoHS/REACH/SVHC)"
        elif "部件承认" in slots:
            t = "部件承认书"
        elif "UL" in slots:
            t = "UL"
        elif "信赖性" in slots:
            t = "信赖性"
        elif "包装" in slots:
            t = "包装"
        elif "出货" in slots:
            t = "出货"
        else:
            t = "未识别"
        files.append({"文件": b, "类型": t, "已识别": bool(slots) or is_msds_name(b)})
    return {"files": files, "count": len(files)}


@app.get("/api/version")
def version_info():
    try:
        import version as _v
        return {"version": _v.VERSION, "app": _v.APP_NAME, "build": _v.BUILD_DATE}
    except Exception:
        return {"version": "?", "app": "久益-承认书自动化", "build": ""}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")   # 前端静态, 必须最后挂
