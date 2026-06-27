// ⑤照片+总装导出 编排(M2.5)。照片剪贴板/选择 → 预检(全软) → 勾已知悉留痕 → 子进程COM装配导出。
import * as api from "./api.js";
import { ackKey, exportSummary } from "./exportstate.js";
import { renderGate } from "./gate.js";

const S = { job: null, photos: [], warnings: [], trace: [], acked: new Set() };
const $ = (id) => document.getElementById(id);

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  if (!job) { $("workspace").innerHTML = "<p class='tip'>缺 job 参数(?job=…)</p>"; return; }
  S.job = job;
  $("photofile").addEventListener("change", (e) => onPick([...e.target.files]));
  const drop = $("photodrop");
  drop.addEventListener("paste", onPaste);
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("drag-over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("drag-over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("drag-over"); onPick([...e.dataTransfer.files].filter((f) => f.type.startsWith("image/"))); });
  $("gatebtn").onclick = onExport;
  try {
    S.photos = (await api.listPhotos(job)).photos || [];
  } catch { /* 新单 */ }
  await loadPreflight();
  render();
}

async function onPaste(e) {
  const items = [...(e.clipboardData || {}).items || []].filter((it) => it.type.startsWith("image/"));
  if (!items.length) return;
  e.preventDefault();
  const files = items.map((it, i) => {
    const b = it.getAsFile();
    return new File([b], `paste_${Date.now()}_${i}.png`, { type: b.type || "image/png" });
  });
  await onPick(files);
}

async function onPick(files) {
  if (!files.length) return;
  setBusy(`上传 ${files.length} 张…`);
  try { S.photos = (await api.uploadPhotos(S.job, files)).photos || S.photos; }
  finally { setBusy(""); }
  await loadPreflight();
  render();
}

async function delPhoto(name) {
  S.photos = (await api.deletePhoto(S.job, name)).photos || [];
  await loadPreflight();
  render();
}

async function loadPreflight() {
  try {
    const pf = await api.exportPreflight(S.job);
    S.warnings = pf.warnings || []; S.trace = pf.trace || [];
  } catch { S.warnings = []; S.trace = []; }
}

function render() {
  // 照片缩略图
  $("photogrid").innerHTML = S.photos.map((n) =>
    `<div class="photo-thumb"><img src="${api.photoUrl(S.job, n)}" alt="${esc(n)}"><button class="x" data-del="${esc(n)}">×</button></div>`).join("")
    || `<div class="drag-hint">还没照片 · 选择文件或 Ctrl+V 粘贴</div>`;
  // 软预警 + 已知悉勾
  $("warnings").innerHTML = S.warnings.length ? S.warnings.map((w) => {
    const k = ackKey(w), on = S.acked.has(k);
    return `<label class="warn-item ${on ? "acked" : ""}"><input type="checkbox" data-ack="${esc(k)}" ${on ? "checked" : ""}>
      <span class="warn-type">${esc(w.类型)}</span> ${esc(w.文案)} <em>已知悉</em></label>`;
  }).join("") : `<div class="all-ok">✓ 无预警，齐套</div>`;
  // 溯源表
  $("trace").innerHTML = `<table class="trace"><tr><th>零件</th><th>材质</th><th>报告编号</th><th>报告日期</th><th>供应商</th></tr>`
    + S.trace.map((t) => `<tr><td>${esc(t.零件)}</td><td>${esc(t.材质)}</td><td>${esc(t.报告编号)}</td><td>${esc(t.报告日期) || "—"}</td><td>${esc(t.供应商)}</td></tr>`).join("")
    + `</table>`;
  bind();
  refresh();
}

function bind() {
  document.querySelectorAll("[data-del]").forEach((el) => el.onclick = () => delPhoto(el.dataset.del));
  document.querySelectorAll("[data-ack]").forEach((el) => el.onchange = () => {
    el.checked ? S.acked.add(el.dataset.ack) : S.acked.delete(el.dataset.ack);
    api.exportAcknowledge(S.job, [...S.acked]).catch(() => {});
    render();
  });
}

function refresh() {
  const sm = exportSummary(S.warnings, [...S.acked]);
  const unacked = sm.total - sm.acked;
  const miss = [];                                          // ⑤全软门: 未知悉预警/照片<2 都是软chips
  if (unacked > 0) miss.push({ t: `${unacked}条预警待知悉`, hard: false });
  if (S.photos.length < 2) miss.push({ t: `照片仅${S.photos.length}张(建议≥2)`, hard: false });
  renderGate({
    summaryId: "summary", btnId: "gatebtn",
    missing: miss,
    doneText: `齐套无预警 · 照片 ${S.photos.length} 张`,
    nextLabel: unacked > 0 ? `带预警导出(${unacked}条未知悉) →` : "总装导出承认书 →",
    rule: "全软门：可带预警导出",
  });
  $("gatebtn").classList.toggle("blocked", unacked > 0);    // 有未知悉→橙警示(仍可点)
}

async function onExport() {
  if (S.photos.length === 0 && !confirm("未贴样品照片，仍要导出吗？(样品照片是承认书必备项)")) return;  // 0照片二次确认(老板拍板)
  setBusy("总装导出中（段一填格 → WPS 嵌 OLE，约 30–60 秒）…");
  $("gatebtn").disabled = true;
  try {
    const r = await api.exportAssemble(S.job, [...S.acked]);
    setBusy("");
    $("summary").innerHTML = `✅ 导出完成：OLE ${r.ole} 个 · <a href="${api.downloadUrl(S.job)}" download>下载承认书</a> · 已打开输出目录`;
  } catch (e) { setBusy(""); alert("导出失败：" + e.message); }
  finally { $("gatebtn").disabled = false; }
}

function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
