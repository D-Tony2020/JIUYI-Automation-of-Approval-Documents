# -*- coding: utf-8 -*-
"""实证: N 个槽位在嵌入组表里怎么摆(行/网格/间距)。读 部件承认书/材质证明书/UL 的位置。

为"槽位数随BOM变 → 位置也要随之生成"提供布局规律。纯本地、不外发。
"""
import os
import sys
import glob

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from hitl.ole_assemble import com_session

TARGETS = {"3.供应商部件": "部件承认书", "8.材质证明": "材质证明书", "9.UL": "UL", "9.ul": "UL"}


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    cases = sorted([p for p in glob.glob(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                     "案例材料", "承认书", "参考用承诺书集", "*.xlsx"))
        if not os.path.basename(p).startswith("~$")])
    with com_session() as xl:
        for x in cases:
            code = os.path.basename(x)[:10]
            wb = xl.Workbooks.Open(os.path.abspath(x), UpdateLinks=0, ReadOnly=True)
            for sh in wb.Worksheets:
                short = None
                for kw, s in TARGETS.items():
                    if sh.Name.strip().startswith(kw) or kw in sh.Name:
                        short = s
                        break
                if not short:
                    continue
                try:
                    n = sh.OLEObjects().Count
                except Exception:
                    n = 0
                if not n:
                    continue
                boxes = []
                for i in range(1, n + 1):
                    o = sh.OLEObjects().Item(i)
                    boxes.append((round(o.Left), round(o.Top), round(o.Width), round(o.Height)))
                boxes.sort(key=lambda b: (b[1] // 30, b[0]))  # 按行(Top分组)再列(Left)
                # 推断: 行数(distinct Top带) / 每行槽数 / X步距
                tops = sorted({b[1] // 25 for b in boxes})
                lefts = sorted(b[0] for b in boxes)
                dxs = [lefts[i + 1] - lefts[i] for i in range(len(lefts) - 1) if lefts[i + 1] - lefts[i] > 5]
                print(f"{code} [{short:7}] n={n} Top带={len(tops)}行  "
                      f"Left范围[{min(lefts)}~{max(lefts)}] X步距≈{sorted(set(dxs))[:4]}")
                print(f"        boxes={boxes}")
            wb.Close(False)


if __name__ == "__main__":
    main()
