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

PROVIDER, MODEL = "qwen", "qwen3.7-plus"        # qwen3.7-plus(多模态+深度思考, 抽取关思考); 旧路径 qwen-plus
_CAS = re.compile(r"\d{2,7}-\d{2}-\d")
_CACHE = os.path.join(ROOT, ".work", "material_cache")


def _extract_key(text, kind, provider, model):
    """抽取缓存键: md5(provider|model|kind|text)。并入模型→换模型不复用旧模型缓存(防口径污染)。"""
    import hashlib
    return hashlib.md5(("|".join((provider, model or "", kind, text))).encode("utf-8")).hexdigest()[:16]


def _cached_extract(text, kind, provider, model):
    """qwen 抽取磁盘缓存(键含模型), 重跑/e2e 不重烧 token。kind=msds|rohs。"""
    import json
    if provider == "mock":
        return _ex.extract_msds(text, provider) if kind == "msds" else _ex.extract_rohs(text, provider)
    h = _extract_key(text, kind, provider, model)
    cf = os.path.join(_CACHE, f"{kind}_{h}.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    r = _ex.extract_msds(text, provider, model) if kind == "msds" else _ex.extract_rohs(text, provider, model)
    os.makedirs(_CACHE, exist_ok=True)
    json.dump(r, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
    return r


def is_extract_cached(text, kind="msds", provider=PROVIDER, model=MODEL):
    """该文本的抽取是否已在磁盘缓存(预检用: 判这一把要不要实时调用)。键须与 _cached_extract 一致。"""
    h = _extract_key(text, kind, provider, model)
    return os.path.exists(os.path.join(_CACHE, f"{kind}_{h}.json"))


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
    """msds/rohs 抽取 dict → 材质提议(归一)。纯函数。

    B 段只产 材质原文 + 成分 + 报告(去供应商: 供应商是部件级、操作员零件级手填)。
    材质=B原文(BOM页 resolve→标准名+派生类别/零件); 成份每项标 无CAS(BOM页标黄交人工删)。
    """
    row = _asm.assemble_row(msds, rohs or {}, "", "", msds.get("material_name", ""))
    raw = (msds.get("material_name") or "").strip()
    成份 = []
    for c in row["成份"]:
        cas = (c.get("CAS") or "").strip()
        成份.append({**c, "无CAS": (not cas or cas in ("/", "-"))})
    return {
        "材质": raw,                             # B原文; BOM页操作员改/字典 resolve→标准名
        "材质原文": raw,                          # 简称字典记忆键 + 溯源
        "成份": 成份,                            # [{成份名称, CAS, 重量%, 无CAS}]
        "RoHS": row["RoHS"],                     # 10项归一(enrich_rohs 后填)
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


def candidate_msds(materials_dir):
    """材料堆 → 过文本门(C分类材质表 + 文件名判真MSDS + MSDS关键词)的候选, 零 qwen 调用。
    → [(base, txt, full)]。供 B提议前的预检/选材, 也被 propose_bom_from_pile 复用。"""
    import glob
    from hitl.file_router import route
    out = []
    for f in sorted(glob.glob(os.path.join(materials_dir, "*.pdf"))):
        base = os.path.basename(f)
        if "材质表" not in route(base) or not is_msds_name(base):   # 只取真MSDS(排REACH/SVHC/ROHS报告)
            continue
        txt, full = pdf_text_for_llm(f)
        if not is_msds(full, min_cas=0):                 # 文件名已强过滤报告, 内容门只确认MSDS关键词;
            continue                                     # 简单料(07CU锡线写"Sn-0.7Cu"非CAS号)0个可识CAS也别漏
        out.append((base, txt, full))
    return out


def propose_bom_from_pile(materials_dir, provider=PROVIDER, model=MODEL):
    """files-first·B提议引擎: 材料堆 → C分类 → 真MSDS(内容确认) → B提议材质清单。

    返回 [{材质,供应商,供应商原文,成份,RoHS,报告编号,报告日期,源文件}]。
    RoHS 配对(MSDS↔RoHS报告)留 slice4 报告块确认。零件/材质类别由操作员在编辑器填。
    """
    props = []
    for base, txt, _full in candidate_msds(materials_dir):
        try:
            prop = to_proposal(_cached_extract(txt, "msds", provider, model))
        except Exception:
            continue
        prop["源文件"] = base
        props.append(prop)
    return props


# RoHS 有害物质名 → 材质表 M-V 列 key。顺序敏感: PBDE 在 PBB 前(避免 'pbb' 误匹 'pbde' 不会, 但保险);
# 注意只在"无CAS行"上匹配(有CAS的铅/汞是真合金成分, 非RoHS声明)。
_ROHS_SUBSTANCE = [
    (("pbde", "多溴二苯醚", "二苯醚"), "PBDEs"),
    (("pbb", "多溴联苯", "联苯"), "PBBs"),
    (("dehp",), "DEHP"), (("dibp",), "DIBP"), (("bbp",), "BBP"), (("dbp",), "DBP"),
    (("六价", "六價", "cr6", "cr(vi)", "cr六", "hexavalent"), "Cr6+"),
    (("镉", "鎘", "(cd)", "cd)", "cadmium"), "Cd"),
    (("铅", "鉛", "(pb)", "pb)", "lead"), "Pb"),
    (("汞", "(hg)", "hg)", "mercury"), "Hg"),
]


def _rohs_key(name):
    n = str(name or "").lower().replace(" ", "")
    for kws, key in _ROHS_SUBSTANCE:
        if any(k.replace(" ", "") in n for k in kws):
            return key
    return None


def _rohs_val(raw):
    """RoHS 声明值清洗: 〈/＜→<; ND/未检出→ND; 空→ND。"""
    s = str(raw or "").strip().replace("〈", "<").replace("＜", "<").replace(" ", "")
    if not s or s.upper() in ("ND", "N.D.", "未检出", "未檢出", "/", "-"):
        return "ND"
    return s


def rohs_from_msds_components(components):
    """无第三方 RoHS 报告时, 从材质 MSDS 自带的 RoHS 符合性声明行(无CAS的有害物质行)派生 RoHS dict。

    PVC MSDS 末尾常附 RoHS 声明表(鎘〈5ppm/鉛〈50ppm/PBB ND...), 被当成分过抽; 这里把它正用为 M-V 填充。
    只取无CAS行(有CAS=真成分, 如磷青铜的铅 CAS 7439-92-1)。
    """
    out = {}
    for c in components or []:
        cas = str(c.get("cas") or c.get("CAS") or "").strip()
        if cas and cas not in ("/", "-"):
            continue
        k = _rohs_key(c.get("name") or c.get("成份名称") or "")
        if k and k not in out:
            out[k] = _rohs_val(c.get("weight_pct_raw") or c.get("重量%") or "")
    return out


def enrich_rohs(materials, materials_dir, provider=PROVIDER, model=MODEL):
    """给材质填 10 项 RoHS 值(材质表 M-V 列)。原地改 materials 并返回。

    三级填充(老板拍板): ① 第三方 RoHS 报告(最权威) > ② 该材质 MSDS 自带 RoHS 符合性声明 > ③ ND(保证 M-V 不空白)。
    豁免材质不进材质表, 跳过。
    """
    from hitl.material_table import ROHS_KEYS, normalize_date, normalize_rohs
    for m in materials:
        if m.get("豁免"):
            continue
        filled = {}
        fz = m.get("files") or {}
        rf = fz.get("RoHS") or []
        rf = [rf] if isinstance(rf, str) else rf
        rpdf = os.path.join(materials_dir, rf[0]) if rf else None
        if rpdf and os.path.exists(rpdf):                 # ① 第三方报告
            try:
                txt, _ = pdf_text_for_llm(rpdf)
                r = _cached_extract(txt, "rohs", provider, model)
                rin = r.get("rohs", {}) if isinstance(r, dict) else {}
                for k in ROHS_KEYS:
                    cell = rin.get(k, "")
                    v = normalize_rohs(cell.get("result", "") if isinstance(cell, dict) else cell)
                    if v:
                        filled[k] = v
                if filled and isinstance(r, dict):
                    m["报告编号"] = m.get("报告编号") or (r.get("report_number") or "").strip()
                    m["报告日期"] = m.get("报告日期") or normalize_date(r.get("report_date_raw", ""))
            except Exception:
                pass
        if len(filled) < len(ROHS_KEYS):                  # ② MSDS 自带 RoHS 声明(无报告或报告缺项)
            src = (m.get("源文件") or "").strip()
            mp = os.path.join(materials_dir, src) if src else None
            if mp and os.path.exists(mp):
                try:
                    mtxt, _ = pdf_text_for_llm(mp)
                    msds = _cached_extract(mtxt, "msds", provider, model)
                    for k, v in rohs_from_msds_components(msds.get("components", [])).items():
                        filled.setdefault(k, v)
                except Exception:
                    pass
        cur = m.get("RoHS") or {}                         # ③ 仍空→ND(无声明的材质如磷青铜全ND)
        m["RoHS"] = {k: (filled.get(k) or cur.get(k) or "ND") for k in ROHS_KEYS}
    return materials
