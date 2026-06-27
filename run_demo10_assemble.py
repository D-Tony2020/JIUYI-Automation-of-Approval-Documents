# -*- coding: utf-8 -*-
"""10 伪真单 全量 COM 装配 → 完整承认书(含 OLE) 产出, 供人工眼检 OLE 修复
(材质证明零件标签 / 图纸OLE缩小 / PVC同列多REACH横向错开)。

鲁棒: 每单子进程跑(隔离崩溃) + 360s 超时 + 装配前后强杀 WPS/et(防卡死与文件锁)。
用法: python run_demo10_assemble.py        # 批量(默认10单)
      python run_demo10_assemble.py <code>  # 单单 worker(供批量 spawn)
"""
import glob
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

OUTDIR = os.path.join(ROOT, "产出留档", "demo10_承认书")
PSEUDO = os.path.join(ROOT, "本单输入", "pseudo")
CODES = ["YY60010116", "YY60010118", "YY60010119", "YY60010120", "YY60010121",
         "YY60010122", "YY60010123", "YY60030496", "YY60030529", "YY60030717"]


def _kill_wps():
    for exe in ("et.exe", "wps.exe", "wpscloudsvr.exe", "wpsendsvr.exe", "wpscenter.exe"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, timeout=20)
        except Exception:
            pass


def worker(code):
    from run_demo10_e2e import autonomous
    from hitl.drawing_extract import extract as draw_extract
    from hitl.assemble_order import assemble
    from hitl.category import CATEGORY_DICT, extract_category
    md = os.path.join(PSEUDO, code, "materials")
    stage2 = autonomous(code)
    draws = glob.glob(os.path.join(PSEUDO, code, "drawing", "*.pdf"))
    drawing_pdf = draws[0] if draws else None
    # ①操作员会确认 品号/名称; 批量自主跑→品号取本单code(=生久品号), 名称取可识别品类词(兜底导线)
    meta, dims = {"名称": "导线", "品号": code, "版本": "A01"}, []
    if drawing_pdf:
        try:
            d = draw_extract(drawing_pdf)
            meta["版本"] = d.get("版本") or "A01"
            nm = d.get("名称", "")
            hit = nm if extract_category(nm)[1] else next((c for c in sorted(CATEGORY_DICT, key=len, reverse=True) if c in nm), "")
            if hit:
                meta["名称"] = hit
            dims = list(d.get("dimensions") or [])     # draw_extract 已返回 (中心,+公差,-公差) 元组(对称化), 直灌 fill_fai
        except Exception:
            pass
    os.makedirs(OUTDIR, exist_ok=True)
    outdir = os.path.join(OUTDIR, "_tmp", code)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(OUTDIR, f"{code}_承认书.xlsx")
    r = assemble(stage2, meta, dims, md, drawing_pdf, out, outdir)
    fai_n = -1                                          # 自测: 读回 FAI 实填项数(中心列非空)
    try:
        import openpyxl
        from hitl import fai
        wb = openpyxl.load_workbook(out)
        ws = wb[fai.FAI_SHEET]
        fai_n = sum(1 for row in range(fai.ITEM_ROW0, fai.ITEM_ROWN + 1) if ws.cell(row, 3).value not in (None, ""))
        wb.close()
    except Exception:
        pass
    res = {"code": code, "ok": os.path.exists(out), "mats": len(stage2.get("materials", [])),
           "dims": len(dims), "fai": fai_n,
           **{k: r.get(k) for k in ("ole", "opens", "specs", "by_sheet")}}
    with open(os.path.join(OUTDIR, f"_result_{code}.json"), "w", encoding="utf-8") as f:  # 写文件(COM可能关stdout)
        json.dump(res, f, ensure_ascii=False)


def batch():
    os.makedirs(OUTDIR, exist_ok=True)
    results = []
    for code in CODES:
        _kill_wps()
        rf = os.path.join(OUTDIR, f"_result_{code}.json")
        if os.path.exists(rf):
            os.remove(rf)
        print(f"=== 装配 {code} ===", flush=True)
        try:
            p = subprocess.run([sys.executable, __file__, code], cwd=ROOT,
                               capture_output=True, text=True, timeout=360, encoding="utf-8")
            if os.path.exists(rf):
                res = json.load(open(rf, encoding="utf-8"))
            else:
                res = {"code": code, "ok": False, "err": (p.stderr or p.stdout or "")[-400:]}
        except subprocess.TimeoutExpired:
            _kill_wps()
            res = {"code": code, "ok": False, "err": "超时(WPS卡)"}
        except Exception as e:
            res = {"code": code, "ok": False, "err": str(e)[-200:]}
        results.append(res)
        print(f"  -> {code}: {'OK' if res.get('ok') else '失败'} ole={res.get('ole')} opens={res.get('opens')} {res.get('err', '')}", flush=True)
    _kill_wps()
    ok = [r for r in results if r.get("ok")]
    print(f"\n=== 汇总: {len(ok)}/{len(CODES)} 成功 ===")
    for r in results:
        print(f"  {'OK ' if r.get('ok') else '✗  '}{r['code']}: 材质{r.get('mats')} FAI={r.get('fai')}/{r.get('dims')} OLE={r.get('ole')} 复开={r.get('opens')} {r.get('err', '')}")
    print(f"\n产出目录: {OUTDIR}")
    json.dump(results, open(os.path.join(OUTDIR, "_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        worker(sys.argv[1])
    else:
        batch()
