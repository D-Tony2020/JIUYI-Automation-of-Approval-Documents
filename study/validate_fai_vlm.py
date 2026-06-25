# -*- coding: utf-8 -*-
"""多模态 FAI 抽取盲测：渲染生久图纸 → qwen-vl-max(官方DashScope) → 抽FAI → 对标golden算召回。

红线：仅走阿里云 DashScope 官方第一方端点(经老板+客户授权)，不进训练、不经中转站。
"""
import sys, io, os, glob, re, zipfile, json, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import fitz, openpyxl, requests
from hitl.ole_assemble import extract_embedded_pdf

API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL = "qwen-vl-max"
CASES = sorted([p for p in glob.glob(r"案例材料\承认书\参考用承诺书集\*.xlsx")
                if "~$" not in os.path.basename(p)])

PROMPT = """你是工程图纸尺寸抽取专家。附图是生久公司的产品工程图纸(导线/连接器类),可能含改版履历页+几何主图页。

任务:抽取该产品的【首件检验(FAI)受检尺寸】。优先从图纸的【检查表/检验规格/SPECIFICATION/CTQ/FAI 表格】读取;若无此表,取几何视图上标注的主要功能尺寸(形如 470±8、98±5、1.5±0.5)。

必须排除:
1. 通用公差表/未注公差表(按尺寸段给默认公差的表,如 "0.5~3 ±0.1 / 3~6 ±0.2 / 6~30 ±0.3")
2. 未注角度公差(±1°)、表面处理、材料、净重、比例、PIN脚序号等非受检尺寸

每个尺寸给:标称值、上公差、下公差(对称公差则上下相等),单位mm纯数字。

严格只输出JSON,无任何解释或markdown:
{"品号":"","版本":"","名称":"","FAI尺寸":[{"标称":470,"上":8,"下":8}]}"""


def drawing_bin(g):
    z = zipfile.ZipFile(g); names = set(z.namelist())
    sheets = re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"',
                        z.read("xl/workbook.xml").decode("utf-8", "ignore"))
    rel = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"',
                          z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "ignore")))
    for nm, rid in sheets:
        if "图纸" not in nm:
            continue
        wsf = rel[rid]; wsf = ("xl/" + wsf) if not wsf.startswith("xl/") else wsf
        relf = f"xl/worksheets/_rels/{os.path.basename(wsf)}.rels"
        if relf in names:
            bins = [os.path.basename(t) for t in re.findall(r'Target="([^"]+)"',
                    z.read(relf).decode("utf-8", "ignore")) if "embeddings/oleObject" in t]
            if bins:
                return bins[0]
    return None


def golden_fai(g):
    wb = openpyxl.load_workbook(g, data_only=True)
    fws = [wb[s] for s in wb.sheetnames if "FAI" in s]
    if not fws:
        return []
    f = fws[0]; out = []
    for r in range(9, 45):
        try:
            b, c, d = float(f.cell(r, 2).value), float(f.cell(r, 3).value), float(f.cell(r, 4).value)
        except (TypeError, ValueError):
            continue
        out.append((c, round(d - c, 3), round(c - b, 3)))
    return out


def render_pages(g, code):
    b = drawing_bin(g)
    if not b:
        return []
    pdf = f"本单输入/_fai_{code}.pdf"
    extract_embedded_pdf(g, b, pdf)
    d = fitz.open(pdf)
    imgs = [pg.get_pixmap(dpi=180).tobytes("png") for pg in d]
    d.close()
    return imgs


def call_vlm(images):
    content = [{"type": "text", "text": PROMPT}]
    for im in images:
        b64 = base64.b64encode(im).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    body = {"model": MODEL, "messages": [{"role": "user", "content": content}],
            "temperature": 0, "max_tokens": 1500}
    s = requests.Session(); s.trust_env = False   # 绕 Clash 代理劫持国内API
    r = s.post(URL, headers={"Authorization": f"Bearer {API_KEY}",
                             "Content-Type": "application/json"}, json=body, timeout=180)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse_json(txt):
    m = re.search(r"\{.*\}", txt.strip(), re.S)
    return json.loads(m.group(0) if m else txt)


def main():
    if not API_KEY:
        print("❌ DASHSCOPE_API_KEY 未设置"); return
    print(f"=== 多模态FAI盲测 ({MODEL}) | {len(CASES)}案 ===\n")
    tot = rec = 0
    for g in CASES:
        code = re.sub(r"[^A-Za-z0-9]", "", os.path.basename(g))[:10]
        fai = golden_fai(g)
        imgs = render_pages(g, code)
        if not imgs:
            print(f"⚠️ {code}: 无图纸OLE"); continue
        try:
            data = parse_json(call_vlm(imgs))
        except Exception as e:
            print(f"❌ {code}: 调用/解析失败 {str(e)[:100]}"); continue
        vlm = data.get("FAI尺寸", [])
        misses = []
        matched = 0
        for (c, t1, t2) in fai:
            hit = any(abs(float(d.get("标称", -9)) - c) < 0.05
                      and abs(float(d.get("上", -9)) - t1) < 0.1
                      and abs(float(d.get("下", -9)) - t2) < 0.1 for d in vlm)
            matched += 1 if hit else 0
            tot += 1; rec += 1 if hit else 0
            if not hit:
                misses.append(f"{c}±({t1}/{t2})")
        flag = "✅" if (matched == len(fai) and fai) else "❌"
        extra = len(vlm) - matched
        print(f"{flag} {code}: 品号{data.get('品号','')} 版本{data.get('版本','')} | "
              f"golden{len(fai)} VLM抽{len(vlm)} 召回{matched}/{len(fai)}"
              f"{' 缺['+','.join(misses)+']' if misses else ''}"
              f"{f' +{extra}多抽' if extra > 0 else ''}")
    print(f"\n===== 多模态FAI召回 {rec}/{tot} ({rec*100//tot if tot else 0}%) =====")


if __name__ == "__main__":
    main()
