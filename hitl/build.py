# -*- coding: utf-8 -*-
"""填充流水线：按施工序应用各表 fill。`build_upto(i)` 累积前 i 张表。

- per-Wi 验证：空白参照 = build_upto(i-1)，填入 = build_upto(i)，diff = 第 i 张的格。
  天然干净、可重复跑（每次从治病模板重建，不依赖持久累积文件）。
- W8 总装：build_upto(len(PIPELINE)) + OLE(COM)。

data 单一来源：{"drawing_meta": {名称, 品号, 版本}}。料号 = drawing_meta["品号"]。
"""
from .harness import load_template, save_output, highlight_cell
from . import cover, sample_list, material_table


def _apply_cover(wb, d):
    cover.fill_cover(wb[cover.COVER_SHEET], d["drawing_meta"])


def _apply_sample(wb, d):
    sample_list.fill_sample_list(wb[sample_list.SAMPLE_SHEET], d["drawing_meta"]["品号"])


def _apply_material(wb, d):
    material_table.fill_material_table(wb[material_table.MAT_SHEET], d["bom"], d["product"])


# (阶段名, 应用函数, sheet 名, 目标格集) —— 列表顺序 = 施工序。
# coords=None 表示变行表(材质表)：不做固定 coord 高亮/diff，靠值比对自检。
PIPELINE = [
    ("W1-封面", _apply_cover, cover.COVER_SHEET, {"D12", "D14", "D16"}),
    ("W2-送样目录", _apply_sample, sample_list.SAMPLE_SHEET, sample_list.TARGET_COORDS),
    ("W4-材质表", _apply_material, material_table.MAT_SHEET, None),
]


def build_upto(template, out_path, data, upto, highlight=True):
    """从治病模板重建，应用 PIPELINE[:upto] 的填充并落盘。upto=0 即空白模板。

    highlight=True（开发/手测）：给**所有**已声明的动态格打黄高亮（含未填的，
    空白参照里即"待填格"一眼可见）。W8 最终交付给生久时 highlight=False 出干净本。
    """
    wb = load_template(template)
    for _name, fn, _sheet, _coords in PIPELINE[:upto]:
        fn(wb, data)
    if highlight:
        for _name, _fn, sheet, coords in PIPELINE:
            if not coords:   # 变行表(材质表)无固定目标格, 跳过高亮
                continue
            ws = wb[sheet]
            for coord in coords:
                highlight_cell(ws, coord)
    save_output(wb, out_path)
    return out_path
