# -*- coding: utf-8 -*-
"""后端权威规则校验(与前端 app/web/js/rules.js 同规则)。

前端放行门可被绕过(直接打 API), 后端 confirm 必须独立权威校验——放行前提是
"操作员逐条声明照图核对过", 后端兜底确认空槽/格式/勾核齐备才落档。
"""
import re

_LABELS = ["品号", "版本", "名称"]
_KEYS = ["id0", "id1", "id2"]


def check_version(v):
    return bool(re.fullmatch(r"[A-Za-z]\d{2}", str(v or "").strip()))   # A01/B02


def check_code(v):
    s = str(v or "").strip()
    return len(s) >= 6 and bool(re.search(r"[A-Za-z]", s)) and bool(re.search(r"\d", s))


def check_name(v):
    return len(str(v or "").strip()) > 0


def check_dim(dim):
    try:
        c = float(dim.get("中心"))
        up = float(dim.get("上"))
        lo = float(dim.get("下", up))
    except (TypeError, ValueError, AttributeError):
        return False
    return up >= 0 and lo >= 0                                          # 公差非负


def validate_confirm(body):
    """返回缺项列表(空=可放行)。三要素 格式+勾核; 尺寸 格式+(勾核 或 豁免)。"""
    missing = []
    checked = body.get("checked") or {}
    for label, key, ok in zip(_LABELS, _KEYS,
                              [check_code(body.get("品号")), check_version(body.get("版本")), check_name(body.get("名称"))]):
        if not ok:
            missing.append(label + "格式异常")
        if not checked.get(key):
            missing.append(label + "未勾核")
    exempt = {e.get("序号") for e in (body.get("exemptions") or [])}
    for i, dim in enumerate(body.get("dimensions") or []):
        if i in exempt:
            continue
        if not check_dim(dim):
            missing.append(f"尺寸{i + 1}公差异常")
        if not checked.get("dim" + str(i)):
            missing.append(f"尺寸{i + 1}未勾核")
    return missing


def validate_bom(body):
    """BOM 脊柱放行门(M2.3): 每材质有 零件+材质类别+供应商 + 已核对(或豁免)。空=放行。

    (零件,材质类别) 是图上没有的不可约人工输入(见字段来源矩阵); 供应商 B 提议+人确认;
    已核对 = 报告块级抽核过。"""
    missing = []
    mats = body.get("materials") or []
    if not mats:
        return ["无材质(先拖材料让B提议)"]
    for i, m in enumerate(mats):
        名 = (m.get("材质") or "").strip() or f"材质{i + 1}"
        for fld in ("零件", "材质类别", "供应商"):
            if not (m.get(fld) or "").strip():
                missing.append(f"{名}缺{fld}")
        if not m.get("已核对") and not m.get("豁免"):
            missing.append(f"{名}未核对")
    return missing


def _msds_of(m):
    fz = m.get("files") or {}
    v = fz.get("MSDS")
    return v if isinstance(v, str) else (v[0] if v else "")


def validate_filetree(body):
    """确认环②放行门(M2.4): 每材质 MSDS 必有(或豁免); RoHS/REACH 缺软放(不拦)。空=放行。

    MSDS=材质自身成分源, 必须有; 第三方报告(RoHS/REACH)缺可勾豁免(符合"允许豁免"设计,
    生久追责时自证)。与前端 treestate.filetreeMissing 同口径。"""
    missing = []
    mats = body.get("materials") or []
    if not mats:
        return ["无材质(先完成BOM脊柱)"]
    for i, m in enumerate(mats):
        名 = (m.get("材质") or "").strip() or f"材质{i + 1}"
        if not _msds_of(m) and not m.get("豁免"):
            missing.append(f"{名}缺MSDS(可豁免)")
    return missing


def _has_file(m, typ):
    fz = m.get("files") or {}
    v = fz.get(typ)
    return bool(v if isinstance(v, str) else (v or []))


def export_preflight(stage3, photos_count, drawing_name="", category_confirmed="",
                     materials_dir=None, drawing_pdf=None):
    """⑤导出预检(M2.5, **全软不硬拦**): 品类词/照片/MSDS/第三方报告/未归位 缺 → 软预警; trace 溯源(含报告日期)。

    老板决: 不做有效期判定(只在 trace 显报告日期); 全软(操作员勾已知悉即可导出)。
    品类词: 名称归一+词典+学习仍未识别且未现场确认 → 软预警(④可内联确认或勾已知悉), 绝不硬挡。
    未归位: 覆盖审计算 pending(含 route=∅未识别 + 豁免材质文件), 红线"每个上传文件都有主"→软强提示, 不静默漏件。
    """
    mats = stage3.get("materials") or []
    warnings = []
    if not str(category_confirmed or "").strip():
        try:
            from hitl.category import extract_category
            _cat, ok = extract_category(drawing_name)
        except Exception:
            ok = True                                  # 取词异常不误报(导出端硬门兜底)
        if not ok and str(drawing_name or "").strip():
            warnings.append({"类型": "品类词", "名称": str(drawing_name),
                             "文案": f"封面品类词未识别：{drawing_name}（已暂留原文，可现场确认归类或勾已知悉导出）"})
    if photos_count < 2:
        warnings.append({"类型": "照片", "文案": f"样品照片仅 {photos_count} 张（建议 ≥2）"})
    for i, m in enumerate(mats):
        名 = (m.get("材质") or "").strip() or f"材质{i + 1}"
        if m.get("豁免"):
            continue
        if not _has_file(m, "MSDS"):
            warnings.append({"类型": "MSDS", "文案": f"{名} 无 MSDS"})
        if not (_has_file(m, "RoHS") or _has_file(m, "REACH") or _has_file(m, "SVHC")):
            warnings.append({"类型": "第三方报告", "文案": f"{名} 无 RoHS/REACH 报告"})
    pending = []
    if materials_dir:                                  # 权威重算(stage3存档的unlinked_files在④归位后会过期)
        try:
            from hitl.file_account import account_files
            pending = account_files(materials_dir, mats, stage3.get("部件归属"),
                                    stage3.get("excluded_files"), drawing_pdf)["pending"]
        except Exception:
            pending = [u.get("文件") for u in (stage3.get("unlinked_files") or [])]
    else:
        pending = [u.get("文件") for u in (stage3.get("unlinked_files") or [])]
    if pending:
        warnings.append({"类型": "未归位", "文案": f"还有 {len(pending)} 份上传文件未归位（④挂到材质列/横排槽，或标记本单不收录）；不处理将不进承认书"})
    trace = [{"零件": m.get("零件", ""), "材质": m.get("材质", ""),
              "报告编号": m.get("报告编号", ""), "报告日期": m.get("报告日期", ""),
              "供应商": m.get("供应商", "")} for m in mats]
    return {"warnings": warnings, "trace": trace}
