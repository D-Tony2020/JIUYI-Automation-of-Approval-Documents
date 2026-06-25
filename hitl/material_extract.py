# -*- coding: utf-8 -*-
"""B 段真接入: 材料 PDF → 材质提议(成分/RoHS)。退役 M2.1 的 content_match token 替身。

照搬 study/run_study 验证过的盲测 97% 路径:
  - 文本 = pdfplumber 表格 + 全文(表在前, 封顶14000; MSDS 窄CAS列 pdftotext会截断, 靠表格补)
  - provider=qwen, model=qwen-plus(文本模型, 非 vl)
  - PDF 解析守护线程超时(防本机 pdfplumber/pdftotext 随机挂起)
  - 复用 spike/assemble 确定性后处理(CAS去空格/重量%÷100/RoHS归一/日期/供应商别名)

files-first·B提议: propose_material 读 MSDS → 提议(材质名+归一成分+RoHS+报告), 不含
零件/材质类别(操作员在 BOM 编辑器后填; 见字段来源矩阵)。
"""
import os
import sys
import re
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPIKE = os.path.join(ROOT, "spike")
for _p in (ROOT, _SPIKE):                       # spike 模块用裸名互相 import, 须加 spike/ 到 path
    if _p not in sys.path:
        sys.path.insert(0, _p)

import extract as _ex                           # spike/extract.py
import assemble as _asm                         # spike/assemble.py
from pdf_text import pdf_to_text, pdf_to_table_markdown

PROVIDER, MODEL = "qwen", "qwen-plus"           # 照搬盲测97%路径(文本模型)
_CAS = re.compile(r"\d{2,7}-\d{2}-\d")
_CACHE = os.path.join(ROOT, ".work", "material_cache")


def _cached_extract(text, kind, provider, model):
    """qwen 抽取磁盘缓存(md5 of kind+text), 重跑/e2e 不重烧 token。kind=msds|rohs。"""
    import hashlib
    import json
    if provider == "mock":
        return _ex.extract_msds(text, provider) if kind == "msds" else _ex.extract_rohs(text, provider)
    h = hashlib.md5((kind + "|" + text).encode("utf-8")).hexdigest()[:16]
    cf = os.path.join(_CACHE, f"{kind}_{h}.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    r = _ex.extract_msds(text, provider, model) if kind == "msds" else _ex.extract_rohs(text, provider, model)
    os.makedirs(_CACHE, exist_ok=True)
    json.dump(r, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
    return r


def _safe(fn, timeout=45):
    """守护线程跑 fn, 超时返 None(防本机 pdfplumber/pdftotext 随机挂死)。"""
    res = [None]

    def work():
        try:
            res[0] = fn()
        except Exception:
            pass
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    return res[0]


def pdf_text_for_llm(pdf):
    """喂 LLM 的文本 = pdfplumber表格 + 全文(表在前, 封顶14000)。磁盘缓存(只存成功的)。返回 (txt, full)。"""
    import hashlib
    import json
    key = hashlib.md5((os.path.abspath(pdf) + str(int(os.path.getmtime(pdf)))).encode()).hexdigest()[:16]
    cf = os.path.join(_CACHE, "text", key + ".json")
    if os.path.exists(cf):
        d = json.load(open(cf, encoding="utf-8"))
        return d["txt"], d["full"]
    full = _safe(lambda: pdf_to_text(pdf)) or ""
    tbl = _safe(lambda: pdf_to_table_markdown(pdf) or "") or ""
    txt = ((tbl + "\n\n=== 全文 ===\n" + full) if tbl else full)[:14000]
    if full or tbl:                              # 只缓存成功的(挂起的空结果不固化, 下次重试)
        os.makedirs(os.path.dirname(cf), exist_ok=True)
        json.dump({"txt": txt, "full": full}, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
    return txt, full


def is_msds_name(base):
    """文件名层判真 MSDS(材质自身成分单)。排除 REACH/SVHC/RoHS/SGS 测试报告
    (它们也有一堆 CAS+含量字样, 内容判别拦不住, 会被当成新材质)。"""
    up = base.upper()
    if any(k in up for k in ("REACH", "SVHC", "ROHS", "CANEC")) or "GZP" in up or "SZP" in up:
        return False
    return ("MSDS" in up or "MATERIAL SAFE" in up
            or any(k in base for k in ("物質安全", "物质安全", "安全资料", "安全資料")))


def is_msds(full_text, min_cas=2):
    """文本预判 MSDS 候选: ≥min_cas CAS + 自报 MSDS/物质安全/成分(排除纯 RoHS Test Report)。
    min_cas=1 用于文件名已确认是 MSDS 的场景: 简单料(纯锡焊料 Sn-0.7Cu)只 1 个可识 CAS, 别误伤。"""
    if len(_CAS.findall(full_text)) < min_cas:
        return False
    return bool(re.search(
        r"MSDS|\bSDS\b|Safety Data Sheet|物[质質]安全|材料安全|安全(技术|資料|资料)|"
        r"成分|成份|組成|组成|组份|composition|含量|wt\s*%", full_text, re.I))


def to_proposal(msds, rohs=None):
    """msds/rohs 抽取 dict → 材质提议(归一)。纯函数(零件/材质类别留操作员填)。"""
    row = _asm.assemble_row(msds, rohs or {}, "", "", msds.get("material_name", ""))
    return {
        "材质": (msds.get("material_name") or "").strip(),
        "供应商原文": (msds.get("supplier_name_raw") or "").strip(),
        "供应商": row["原材料供应商"],          # 别名归一后(未命中则原文, 交人工)
        "成份": row["成份"],                     # [{成份名称, CAS(去空格), 重量%(÷100)}]
        "RoHS": row["RoHS"],                     # 10项归一
        "报告编号": row["检测报告编号"],
        "报告日期": row["检测报告日期"],
    }


def propose_material(msds_pdf, rohs_pdf=None, provider=PROVIDER, model=MODEL):
    """B 读 MSDS(+可选RoHS) → 材质提议。供 files-first·B提议 流。"""
    txt, _ = pdf_text_for_llm(msds_pdf)
    msds = _cached_extract(txt, "msds", provider, model)
    rohs = {}
    if rohs_pdf:
        rtxt, _ = pdf_text_for_llm(rohs_pdf)
        rohs = _cached_extract(rtxt, "rohs", provider, model)
    return to_proposal(msds, rohs)


def classify_pile(materials_dir):
    """材料堆 → 按 OLE 槽分类 {槽: [文件名]}(复用 file_router, 含 1文件→N槽 扇出)。"""
    import glob
    from collections import defaultdict
    from hitl.file_router import route
    by = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        for slot in route(os.path.basename(f)):
            by[slot].append(os.path.basename(f))
    return dict(by)


def propose_bom_from_pile(materials_dir, provider=PROVIDER, model=MODEL):
    """files-first·B提议引擎: 材料堆 → C分类 → 真MSDS(内容确认) → B提议材质清单。

    返回 [{材质,供应商,供应商原文,成份,RoHS,报告编号,报告日期,源文件}]。
    RoHS 配对(MSDS↔RoHS报告)留 slice4 报告块确认。零件/材质类别由操作员在编辑器填。
    """
    import glob
    from hitl.file_router import route
    props = []
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        base = os.path.basename(f)
        if "材质表" not in route(base) or not is_msds_name(base):   # 只取真MSDS(排REACH/SVHC/ROHS报告)
            continue
        txt, full = pdf_text_for_llm(f)
        if not is_msds(full, min_cas=0):                 # 文件名已强过滤报告, 内容门只确认MSDS关键词;
            continue                                     # 简单料(07CU锡线写"Sn-0.7Cu"非CAS号)0个可识CAS也别漏
        try:
            prop = to_proposal(_cached_extract(txt, "msds", provider, model))
        except Exception:
            continue
        prop["源文件"] = base
        props.append(prop)
    return props
