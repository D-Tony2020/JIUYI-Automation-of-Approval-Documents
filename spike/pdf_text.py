# -*- coding: utf-8 -*-
"""PDF 文本层抽取。

勘测结论：fitz/PyMuPDF 抽 CTI/部分中文报告会乱码（子集字体 ToUnicode 问题），
故文本层一律走 pdftotext -layout（保留版面、列不错位）。
扫描件无文本层时再用 fitz 栅格化成图片喂视觉模型（本 spike 锡丝两份均为原生文本层，用不到）。
"""
import subprocess


def pdf_to_text(pdf_path: str) -> str:
    """用 pdftotext -layout 抽取文本（UTF-8、保留版面）。"""
    out = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", pdf_path, "-"],
        capture_output=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"pdftotext 失败: {out.stderr.decode('utf-8', 'ignore')}")
    return out.stdout.decode("utf-8", "ignore")


def pdf_to_table_markdown(pdf_path: str, max_pages: int = 3) -> str:
    """自制 MSDS 窄列表格用：pdfplumber 抽表格转 markdown。

    勘测发现 pdftotext -layout 会把 MSDS 成分表的窄 CAS 列换行截断
    （7440-31-5 -> 7440-31-），pdfplumber 表格模式能完整保留（虽含多余空格，
    由 assemble.normalize_cas 修复）。
    """
    import pdfplumber
    md = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:max_pages]:
            for tb in page.extract_tables():
                for row in tb:
                    cells = [(c or "").replace("\n", " ").strip() for c in row]
                    if any(cells):
                        md.append(" | ".join(cells))
    return "\n".join(md)


def pdf_page_to_png(pdf_path: str, page_index: int = 0, dpi: int = 200) -> bytes:
    """扫描件/窄表兜底：用 fitz 把某页栅格化为 PNG 字节（喂视觉模型）。"""
    import fitz
    doc = fitz.open(pdf_path)
    pix = doc[page_index].get_pixmap(dpi=dpi)
    return pix.tobytes("png")
