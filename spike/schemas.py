# -*- coding: utf-8 -*-
"""抽取 schema 与 prompt。每类文档一个 schema，强约束 JSON 输出。

这是产品的核心 IP：把非结构化报告/MSDS 逼成结构化字段。
RoHS 十项严格对齐生久材质表口径：Pb/Cd/Hg/Cr6+/PBBs/PBDEs/DEHP/DBP/BBP/DIBP。
"""

ROHS_KEYS = ["Pb", "Cd", "Hg", "Cr6+", "PBBs", "PBDEs", "DEHP", "DBP", "BBP", "DIBP"]

MSDS_SCHEMA = {
    "type": "object",
    "properties": {
        "material_name": {"type": "string", "description": "产品/材质名称"},
        "supplier_name_raw": {"type": "string", "description": "MSDS 抬头里的供应商全称（原文，可繁体/英文）"},
        "components": {
            "type": "array",
            "description": "成分辨识表里的每一种成份",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "成份名称（原文）"},
                    "cas": {"type": "string", "description": "CAS 号，如 7440-31-5；无则空字符串"},
                    "weight_pct_raw": {"type": "string", "description": "含量原文，如 99.3wt% / <3 / 余量 / balance，保留原貌不要换算"},
                },
                "required": ["name", "cas", "weight_pct_raw"],
            },
        },
    },
    "required": ["material_name", "supplier_name_raw", "components"],
}

ROHS_SCHEMA = {
    "type": "object",
    "properties": {
        "report_number": {"type": "string", "description": "报告编号，如 SZXEC25002243403"},
        "report_date_raw": {"type": "string", "description": "报告签发日期原文，如 Jun 30, 2025"},
        "lab": {"type": "string", "description": "出具机构，如 SGS / CTI华测"},
        "sample_name": {"type": "string"},
        "conclusion": {"type": "string", "description": "Pass / Fail"},
        "rohs": {
            "type": "object",
            "description": "RoHS 十项结果。result 为 'N.D.'/'ND' 或具体数值字符串（非ND照实填，不要写ND）",
            "properties": {k: {
                "type": "object",
                "properties": {"result": {"type": "string"}, "unit": {"type": "string"}},
                "required": ["result"],
            } for k in ROHS_KEYS},
        },
    },
    "required": ["report_number", "report_date_raw", "rohs"],
}

MSDS_PROMPT = (
    "你是工业 MSDS/SDS 成分抽取专家。下面是一份材料 MSDS/SDS 的文本层内容（可能含『表格模式』与『全文』两段，互补）。\n"
    "任务：抽取成分辨识/组成表里**每一种**成份，一个都不能漏。\n"
    "⚠关键（PDF 转文本常见坑）：CAS 列经常与成份名**错行/错列**——CAS 号浮在右侧、上下偏移一两行。\n"
    "  - 按**出现顺序 + 就近原则**把每个 CAS 号对到它的成份；\n"
    "  - 文档里出现的每个 CAS 号都应对到某成份，**不得因排版错位而把成份的 CAS 留空**；\n"
    "  - 经验：成份条数 ≈ 文档中 CAS 号的个数；只有确实没有 CAS 的成份才留空。\n"
    "【必须严格使用下列英文键名，不要改名/翻译，只输出 JSON、不要解释】：\n"
    '{\n'
    '  "material_name": "产品/材质名称",\n'
    '  "supplier_name_raw": "供应商全称(原文,保留繁简)",\n'
    '  "components": [\n'
    '    {"name": "成份名称(原文)", "cas": "CAS号如7440-31-5,确无则空串", "weight_pct_raw": "含量原文如99.3wt%/<3/余量/30-40%,保留原貌不换算"}\n'
    '  ]\n'
    '}\n'
    "\n=== MSDS 文本 ===\n{TEXT}\n"
)

ROHS_PROMPT = (
    "你是第三方检测报告抽取专家。下面是一份 RoHS 测试报告的文本层内容。\n"
    "【必须严格使用下面这些英文键名，不要翻译成中文键、不要改名】，且只输出 JSON、不要解释：\n"
    '{\n'
    '  "report_number": "报告编号",\n'
    '  "report_date_raw": "报告签发日期原文,如 Jun 30, 2025",\n'
    '  "lab": "出具机构", "sample_name": "样品名", "conclusion": "Pass或Fail",\n'
    '  "rohs": {\n'
    '    "Pb": {"result": "数值或ND", "unit": "mg/kg"},\n'
    '    "Cd": {"result":"...","unit":"..."}, "Hg": {"result":"...","unit":"..."}, "Cr6+": {"result":"...","unit":"..."},\n'
    '    "PBBs": {"result":"...","unit":"..."}, "PBDEs": {"result":"...","unit":"..."},\n'
    '    "DEHP": {"result":"...","unit":"..."}, "DBP": {"result":"...","unit":"..."}, "BBP": {"result":"...","unit":"..."}, "DIBP": {"result":"...","unit":"..."}\n'
    '  }\n'
    '}\n'
    "关键规则：result 未检出填 ND；若有具体数值(如 Pb=63)必须照实填该数值，不能因整体 Pass 就写 ND。\n"
    "rohs 的十个键必须正好是 Pb/Cd/Hg/Cr6+/PBBs/PBDEs/DEHP/DBP/BBP/DIBP。\n"
    "\n=== 报告文本 ===\n{TEXT}\n"
)
