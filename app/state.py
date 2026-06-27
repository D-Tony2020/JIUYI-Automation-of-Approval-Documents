# -*- coding: utf-8 -*-
"""确认环① 运行态: `.work/orders/<job>/` 读写。

stage1_drawing.json = 图纸识别确认态(抽取结果+修订值+勾核+豁免)
project.json        = 5步流进度(step)
drawing/            = 本单上传的生久图纸
支持刷新页面/断点续做(读回现场)。
"""
import os
import json

from hitl import userdata

WORK = os.path.join(userdata.work_base(), ".work", "orders")   # 运行态(dev原位/冻结→%APPDATA%, 可写)


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


def materials_list(job):
    """材料文件池真值(materials/*.pdf basename 排序)。与抽取读取同口径。"""
    import glob
    return sorted(os.path.basename(p) for p in glob.glob(os.path.join(materials_dir(job), "*.pdf"))
                  if os.path.isfile(p))


def assert_job(job):
    """job 合法性(防路径穿越): 字符白名单 + 拒 .. 与分隔符。失败返 False(端点判400)。"""
    import re
    job = str(job or "")
    if ".." in job or "/" in job or "\\" in job:
        return False
    return bool(re.fullmatch(r"[\w-]{1,64}", job))


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
