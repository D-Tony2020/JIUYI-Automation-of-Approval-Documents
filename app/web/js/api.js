// 后端 API 薄封装。

async function _json(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

export async function uploadDrawing(file) {
  const fd = new FormData();
  fd.append("file", file);
  return _json("/api/order/upload-drawing", { method: "POST", body: fd });
}

export async function extract(job) {
  return _json(`/api/drawing/${job}/extract`, { method: "POST" });
}

export async function overview(job) {
  return _json(`/api/overview/${job}`);            // 各步缺N(步条徽标/断点续做首页)
}

export async function orders() {
  return _json("/api/orders");                      // 最近本单列表(断点续做首页)
}

export async function getState(job) {
  return _json(`/api/drawing/${job}/state`);
}

export async function confirm(job, payload) {
  return _json(`/api/drawing/${job}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function pageUrl(job, n) {
  return `/api/drawing/${job}/page/${n}.png`;
}

// ── M2.3 BOM 脊柱 ──────────────────────────────────────────
export async function uploadMaterials(job, files) {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  return _json(`/api/order/${job}/upload-materials`, { method: "POST", body: fd });
}

export async function bomExtract(job) {
  return _json(`/api/bom/${job}/extract`, { method: "POST" });
}

export async function bomExtractMore(job) {                 // 继续上传后再抽(合并保留已编辑)
  return _json(`/api/bom/${job}/extract-more`, { method: "POST" });
}

export async function getBomState(job) {
  return _json(`/api/bom/${job}/state`);
}

export async function bomSave(job, payload) {
  return _json(`/api/bom/${job}/save`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}

export async function bomConfirm(job, payload) {
  return _json(`/api/bom/${job}/confirm`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}

// 人工修改审计留痕
export async function bomLog(job, entry) {
  return _json(`/api/bom/${job}/log`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(entry),
  });
}

export async function getBomLog(job) {
  return _json(`/api/bom/${job}/log`);
}

// 材料文件池: 打开文件夹直拖 + 实时跟踪
export async function openMaterials(job) {
  return _json(`/api/order/${job}/open-materials`, { method: "POST" });
}

export async function openMaterialFile(job, name) {       // 打开某源文件给操作员核对
  return _json(`/api/order/${job}/open-file`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }),
  });
}

export async function pool(job) {
  return _json(`/api/order/${job}/pool`);
}

// ── M2.4 确认环② 文件树 ────────────────────────────────────
export async function filetreeState(job) {
  return _json(`/api/filetree/${job}/state`);
}

export async function filetreeSave(job, payload) {
  return _json(`/api/filetree/${job}/save`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}

export async function filetreeConfirm(job, payload) {
  return _json(`/api/filetree/${job}/confirm`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}

// ── M2.5 ⑤照片 + 总装导出 ──────────────────────────────────
export async function uploadPhotos(job, files) {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  return _json(`/api/order/${job}/upload-photos`, { method: "POST", body: fd });
}

export async function listPhotos(job) {
  return _json(`/api/order/${job}/photos`);
}

export async function deletePhoto(job, name) {
  return _json(`/api/order/${job}/photos/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export async function exportPreflight(job) {
  return _json(`/api/export/${job}/preflight`);
}

export async function exportAcknowledge(job, acknowledged) {
  return _json(`/api/export/${job}/acknowledge`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ acknowledged }),
  });
}

export async function exportAssemble(job, acknowledged) {
  return _json(`/api/export/${job}/assemble`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ acknowledged }),
  });
}

export async function categoryDict() {
  return _json(`/api/category/dict`);                    // 品类词下拉: 内置+已学
}

export async function confirmCategory(job, 名称, 品类) {
  return _json(`/api/order/${job}/category`, {            // 确认封面品类词→学习库+写回本单
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ 名称, 品类 }),
  });
}

export function downloadUrl(job) {
  return `/api/export/${job}/download`;
}

export function photoUrl(job, name) {
  return `/api/order/${job}/photos/raw?name=${encodeURIComponent(name)}`;  // 预览(若需), 当前用本地 blob 预览
}

// ── API key 配置(取消环境变量, UI直接填; 存%APPDATA%/config.json) ──
export async function getConfig() {
  return _json("/api/config");                          // {api_key, has_key, saved}
}

export async function saveConfig(api_key) {
  return _json("/api/config", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ api_key }),
  });
}

// ── 全局字典(材质简称/类别零件反查/供应商历史) ──
export async function getDict() {
  return _json("/api/dict");
}

export async function learnDict(payload) {
  return _json("/api/dict/learn", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}
