# -*- coding: utf-8 -*-
"""确认环① 运行态: `.work/orders/<job>/` 读写。

stage1_drawing.json = 图纸识别确认态(抽取结果+修订值+勾核+豁免)
project.json        = 5步流进度(step)
drawing/            = 本单上传的生久图纸
支持刷新页面/断点续做(读回现场)。
"""
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # HITL 根
WORK = os.path.join(ROOT, ".work", "orders")


def order_dir(job):
    d = os.path.join(WORK, job)
    os.makedirs(d, exist_ok=True)
    return d


def drawing_dir(job):
    d = os.path.join(order_dir(job), "drawing")
    os.makedirs(d, exist_ok=True)
    return d


def materials_dir(job):
    d = os.path.join(order_dir(job), "materials")
    os.makedirs(d, exist_ok=True)
    return d


def drawing_pdf(job):
    """本单图纸 PDF 路径(取 drawing/ 下第一份)。无则 None。"""
    import glob
    pdfs = sorted(glob.glob(os.path.join(drawing_dir(job), "*.pdf")))
    return pdfs[0] if pdfs else None


def photos_dir(job):
    d = os.path.join(order_dir(job), "photos")
    os.makedirs(d, exist_ok=True)
    return d


def photos_list(job):
    """本单已上传样品照片文件名(排序)。"""
    import glob
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(photos_dir(job), "*"))
                  if os.path.isfile(p))


def save_json(job, name, data):
    with open(os.path.join(order_dir(job), name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load_json(job, name, default=None):
    p = os.path.join(order_dir(job), name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)
