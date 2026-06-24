# -*- coding: utf-8 -*-
"""W0 模板治病：剥离 dangling 外链 + 把误指外部文件的公式重指回本簿。

病灶（实勘）：空白模板含一个外链，指向另一台机器上另一客户的承认书
`\\\\Desktop-dvuc8fu\\...\\YY60030251承认书.xlsx`，被材质表 2 个公式引用：
  "地址 :"&[1]封面!C27   和   [1]封面!C33
本意是引用本簿封面的地址/邮箱。治法：[1]封面! → 封面!，再剥外链。

手术为 zip 级确定性操作（openpyxl 会原样保留外链，故不用它）。
"""
import os
import re
import zipfile

# 已知需重指的引用（保守：只改确认过的，不瞎替换 [1]）
REPOINT = {
    "[1]封面!": "封面!",
    "[1]附表--器件类别!": "附表--承认之细则!",  # 旧表名→本簿现表名（防御性）
}


def doctor_template(src, dst):
    """剥外链 + 重指公式，产出干净模板。返回 (移除的part列表, 重指次数)。"""
    with zipfile.ZipFile(src) as zin:
        parts = {n: zin.read(n) for n in zin.namelist()}

    removed = []
    repoint_n = 0

    # 1) 删除 externalLinks 部件
    for n in list(parts):
        if n.startswith("xl/externalLinks/"):
            del parts[n]
            removed.append(n)

    # 2) 各 worksheet 公式重指 [1]xxx! → 本簿xxx!
    for n in list(parts):
        if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"):
            x = parts[n].decode("utf-8")
            if "[1]" in x:
                for old, new in REPOINT.items():
                    cnt = x.count(old)
                    if cnt:
                        x = x.replace(old, new)
                        repoint_n += cnt
                parts[n] = x.encode("utf-8")

    # 3) workbook.xml 去掉 <externalReferences>…</externalReferences>
    wb = parts["xl/workbook.xml"].decode("utf-8")
    wb = re.sub(r"<externalReferences>.*?</externalReferences>", "", wb, flags=re.S)
    wb = re.sub(r"<externalReferences\s*/>", "", wb)
    parts["xl/workbook.xml"] = wb.encode("utf-8")

    # 4) workbook.xml.rels 去掉 externalLink 关系
    rels = parts["xl/_rels/workbook.xml.rels"].decode("utf-8")
    rels = re.sub(r"<Relationship[^>]*externalLink[^>]*/>", "", rels)
    parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")

    # 5) [Content_Types].xml 去掉 externalLink override
    ct = parts["[Content_Types].xml"].decode("utf-8")
    ct = re.sub(r"<Override[^>]*externalLink[^>]*/>", "", ct)
    parts["[Content_Types].xml"] = ct.encode("utf-8")

    # 写出
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, data in parts.items():
            zout.writestr(n, data)
    return removed, repoint_n


if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SRC = os.path.join(ROOT, "模板", "承认书空白模板.xlsx")
    DST = os.path.join(ROOT, "模板", "承认书空白模板_治病.xlsx")
    removed, n = doctor_template(SRC, DST)
    print("剥离外链部件:", removed)
    print("重指公式次数:", n)
    # 验证
    with zipfile.ZipFile(DST) as z:
        ext = [x for x in z.namelist() if "externalLink" in x]
        s10 = z.read("xl/worksheets/sheet10.xml").decode("utf-8", "ignore")
        left = re.findall(r"<f>[^<]*\[1\][^<]*</f>", s10)
        repointed = re.findall(r"<f>[^<]*封面![^<]*</f>", s10)
    print("治病后残留 externalLink 部件:", ext or "无")
    print("治病后残留 [1] 公式:", left or "无")
    print("重指后封面!公式:", repointed)
    import openpyxl
    wb = openpyxl.load_workbook(DST)
    print("openpyxl 复检可打开, sheets:", len(wb.sheetnames))
    print("产物:", DST)
