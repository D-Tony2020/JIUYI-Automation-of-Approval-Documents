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
