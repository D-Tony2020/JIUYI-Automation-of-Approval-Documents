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
