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

export function downloadUrl(job) {
  return `/api/export/${job}/download`;
}

export function photoUrl(job, name) {
  return `/api/order/${job}/photos/raw?name=${encodeURIComponent(name)}`;  // 预览(若需), 当前用本地 blob 预览
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
