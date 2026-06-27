// 确认环② 文件树编排(M2.4): 证据文件↔材质↔证据列(K/L/Y) 放置确认 + 拖拽纠正认不准报告 + 豁免。
import * as api from "./api.js";
import { planTree, slotState, filetreeMissing, COLS } from "./treestate.js";
import { renderGate, scrollFirstTodo } from "./gate.js";
import { dlgPrompt, toast, savedTick, EXEMPT_REASONS } from "./dialog.js";

const S = { job: null, bom: { materials: [], unlinked_files: [] }, partOrder: [], gridReports: [], parts: [], drag: null };
const $ = (id) => document.getElementById(id);
let saveTimer = null;

// 证据列 → 拖入时落的 files 桶(放置据此落 K/L/Y; 同 placement_plan.TYPE_COL 反向)
const COL_BUCKET = { K: "其他", L: "REACH", Y: "RoHS" };
// 点槽"+选文件"上传时落的桶: K槽=该材质MSDS(单), L=REACH(多), Y=RoHS(多)
const UPLOAD_BUCKET = { K: "MSDS", L: "REACH", Y: "RoHS" };

async function boot() {
  const job = new URLSearchParams(location.search).get("job");
  if (!job) { $("workspace").innerHTML = "<p class='tip'>缺 job 参数(?job=…)</p>"; return; }
  S.job = job;
  ensureFileInput();                                       // 隐藏文件选择器(点槽/补充文件共用)
  try { S.partOrder = (await api.getDict()).part_order || []; } catch { /* 默认空 */ }   // 继承③零件顺序
  try {
    const s = await api.filetreeState(job);
    S.bom = { materials: s.materials || [], unlinked_files: s.unlinked_files || [],
              部件归属: s.部件归属 || {}, excluded_files: s.excluded_files || [] };
    S.gridReports = s.grid_reports || [];
    S.parts = s.parts || [];
    render();
  } catch (e) {
    $("workspace").innerHTML = `<p class='tip'>读取失败：${esc(e.message)}（请先完成 ③BOM脊柱）</p>`;
  }
}

function render() {
  const tree = planTree(S.bom, S.partOrder);
  let html = "";
  for (const p of tree.order) {
    html += `<div class="part-group"><div class="part-head">▸ ${esc(p)} <small>${tree.parts[p].length}材质</small></div>`;
    for (const mi of tree.parts[p]) html += matRow(tree.materials[mi]);
    html += `</div>`;
  }
  $("bomtable").innerHTML = (html || "<p class='tip'>无材质</p>") + gridReportsHtml();
  renderUnlinked(tree.unlinked);
  $("toolbar").innerHTML = `<span class="tip">绿=已挂证据 · 灰虚=空槽(MSDS必补,第三方可空) · 删除线=豁免 · 点槽内"+选文件"随时从电脑补</span>`
    + `<button id="addpile" class="addpile-btn" title="补部件承认/UL/信赖性等, 进认不准池再归位">+ 补充文件(部件/UL/其他)</button>`;
  bind();
  refresh();
}

function matRow(m) {
  const real = S.bom.materials[m.idx];
  const cells = COLS.map((col) => {
    const st = slotState(real, col);
    const chips = m.slots[col.key].map((f) =>
      `<span class="filechip" draggable="true" data-from="${m.idx}" data-type="${esc(f.类型)}" data-file="${esc(f.文件)}" title="${esc(f.文件)}">${esc(shortName(f.文件))}<button class="x" data-unlink="${m.idx}|${esc(f.类型)}|${esc(f.文件)}">×</button></span>`).join("");
    const must = col.key === "K";                          // MSDS=唯一硬门必补; L/Y第三方可空
    const empty = m.slots[col.key].length ? ""
      : (real.豁免 ? `<span class="emptyslot opt">—</span>`
        : `<span class="emptyslot ${must ? "must" : "opt"}">${must ? "缺 · 必补" : "可空"}</span>`);
    const sst = (st === "todo" && !must && !real.豁免) ? "opt" : st;   // 第三方空=opt(不算缺)
    const add = real.豁免 ? "" : `<button class="addslot" data-add="${m.idx}|${col.key}" title="从电脑选文件补到此槽">+ 选文件</button>`;
    return `<div class="slot" data-drop="${m.idx}|${col.key}" data-st="${sst}"><div class="col-label">${col.key} ${col.label}</div>${chips}${empty}${add}</div>`;
  }).join("");
  return `<div class="card mat-card ${m.豁免 ? "exempt" : ""}" data-st="${m.豁免 ? "exempt" : "ok"}" data-i="${m.idx}">
    <div class="mat-row"><span class="matname">${esc(m.材质)}</span>
      <button class="exbtn" data-exempt="${m.idx}">${m.豁免 ? "取消豁免" : "豁免"}</button></div>
    <div class="slot-grid">${cells}</div>
  </div>`;
}

function gridReportsHtml() {
  // 横排部件报告(部件承认/UL/信赖性)归属选择: 选零件→OLE下方部件标签(线材/端子/套管)+顺序。best-effort预填。
  if (!S.gridReports.length) return "";
  const tl = { 部件承认: "部件承认书", UL: "UL证明", 信赖性: "信赖性" };
  const opts = (cur) => ['<option value="">(选零件)</option>']
    .concat(S.parts.map((p) => `<option ${p === cur ? "selected" : ""}>${esc(p)}</option>`)).join("");
  const rows = S.gridReports.map((g) => {
    const cur = (S.bom.部件归属 || {})[g.文件] || g.建议零件 || "";
    return `<div class="grid-row"><span class="gr-tag">${esc(tl[g.表] || g.表)}</span>`
      + `<span class="gr-file" title="${esc(g.文件)}">${esc(shortName(g.文件))}</span><span class="gr-arrow">→</span>`
      + `<select class="gr-sel" data-grpart="${esc(g.文件)}">${opts(cur)}</select></div>`;
  }).join("");
  return `<div class="grid-reports"><div class="gr-head">⊞ 横排部件报告归属 — 选零件定 OLE 下方标签(线材/端子/套管)与顺序；已 best-effort 预填，请核对</div>${rows}</div>`;
}

function renderUnlinked(unlinked) {
  // 零丢失: 每个待归位文件给三类目标(材质证据列/横排部件槽+零件/本单不收录), 选完一点即归位; 仍可拖到材质列 或 用建议挂。
  const rows = unlinked.map((u, j) => {
    const s = u.建议;
    const sug = s ? `<button class="sugbtn" data-sug="${j}" title="一点即挂到「${esc(s.材质)}」的 ${esc(s.col)} 列(${s.据 === "色" ? "按颜色" : "按名称"}匹配)">↳建议挂 ${esc(s.材质)}${s.据 === "色" ? " <small>按色</small>" : ""}</button>` : "";
    return `<div class="orphan-card">
      <span class="filechip unl" draggable="true" data-from="unlinked" data-type="${esc(u.类型)}" data-file="${esc(u.文件)}" data-j="${j}" title="${esc(u.文件)}">${esc(shortName(u.文件))} <em>${esc(u.类型)}</em></span>
      <span class="orphan-fix">
        <select class="orphan-dest" data-of="${j}">
          <option value="">归到…</option>
          <optgroup label="材质证据列"><option value="col:L">材质 REACH/SVHC列</option><option value="col:Y">材质 RoHS列</option><option value="col:K">材质 MSDS列</option></optgroup>
          <optgroup label="横排部件(选零件)"><option value="slot:部件承认">部件承认书</option><option value="slot:UL">UL证明</option><option value="slot:信赖性">信赖性</option></optgroup>
          <option value="exclude">本单不收录</option>
        </select>
        <select class="orphan-target" data-ot="${j}" style="display:none"></select>
        <button class="passbtn orphan-go" data-go="${j}" disabled>确认</button>
      </span>${sug}
    </div>`;
  }).join("");
  $("unlinked").innerHTML = rows || `<div class="drag-hint">所有上传文件已归位 ✓<br><small>把材质上挂错的也可拖回这里</small></div>`;
}

// ── 拖拽 ────────────────────────────────────────────────────
function bind() {
  document.querySelectorAll(".filechip").forEach((el) => {
    el.addEventListener("dragstart", (e) => {
      S.drag = { from: el.dataset.from, type: el.dataset.type, file: el.dataset.file };
      e.dataTransfer.effectAllowed = "move";
      document.querySelectorAll(".slot, .unlinked-zone").forEach((t) => t.classList.add("drop-active"));  // 拖时所有合法落点持续高亮
    });
    el.addEventListener("dragend", () => document.querySelectorAll(".drop-active").forEach((t) => t.classList.remove("drop-active")));
  });
  document.querySelectorAll(".slot").forEach((el) => {
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("drag-over"); });
    el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
    el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("drag-over"); dropTo(el.dataset.drop); });
  });
  const uz = $("unlinked");
  uz.addEventListener("dragover", (e) => { e.preventDefault(); uz.classList.add("drag-over"); });
  uz.addEventListener("dragleave", () => uz.classList.remove("drag-over"));
  uz.addEventListener("drop", (e) => { e.preventDefault(); uz.classList.remove("drag-over"); dropToUnlinked(); });
  document.querySelectorAll("[data-unlink]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); const [i, t, f] = el.dataset.unlink.split("|"); unlinkFile(+i, t, f); });
  document.querySelectorAll("[data-exempt]").forEach((el) => el.onclick = () => toggleExempt(+el.dataset.exempt));
  document.querySelectorAll("[data-sug]").forEach((el) => el.onclick = () => attachSuggested(+el.dataset.sug));
  document.querySelectorAll(".orphan-dest").forEach((el) => el.onchange = () => {       // 选目标→联动第二下拉(材质/零件)
    const j = el.dataset.of, dest = el.value;
    const tgt = document.querySelector(`.orphan-target[data-ot="${j}"]`);
    const go = document.querySelector(`.orphan-go[data-go="${j}"]`);
    if (!dest || dest === "exclude") { tgt.style.display = "none"; go.disabled = !dest; return; }
    tgt.innerHTML = dest.startsWith("col:")
      ? (S.bom.materials || []).map((m, i) => `<option value="${i}">${esc(m.材质 || ("材质" + (i + 1)))}</option>`).join("")
      : (S.parts || []).map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
    tgt.style.display = ""; go.disabled = false;
  });
  document.querySelectorAll(".orphan-go").forEach((el) => el.onclick = () => {
    const j = el.dataset.go;
    const dest = document.querySelector(`.orphan-dest[data-of="${j}"]`).value;
    const tgt = document.querySelector(`.orphan-target[data-ot="${j}"]`);
    placeOrphan(+j, dest, tgt.value);
  });
  document.querySelectorAll("[data-add]").forEach((el) => el.onclick = (e) => {   // 点槽→选文件补到该材质的K/L/Y
    e.stopPropagation(); const [mi, colKey] = el.dataset.add.split("|"); pickFiles({ mi: +mi, colKey }, colKey !== "K");
  });
  const ap = $("addpile"); if (ap) ap.onclick = () => pickFiles({ unlinked: true }, true);   // 补部件/UL→认不准池
  document.querySelectorAll("[data-grpart]").forEach((el) => el.onchange = () => {   // 横排报告零件归属→标签/顺序
    S.bom.部件归属 = S.bom.部件归属 || {};
    S.bom.部件归属[el.dataset.grpart] = el.value;
    save();
  });
  $("gatebtn").onclick = onConfirm;
}

// ── 随时从电脑补文件(点槽 / 补充) ───────────────────────────
function ensureFileInput() {
  if ($("hiddenfile")) return;
  const inp = document.createElement("input");
  inp.type = "file"; inp.id = "hiddenfile"; inp.accept = ".pdf,.png,.jpg,.jpeg"; inp.style.display = "none";
  inp.addEventListener("change", () => { const fs = [...inp.files]; if (fs.length) onFilePicked(fs); });
  document.body.appendChild(inp);
}

function pickFiles(ctx, multiple) {
  S.uploadCtx = ctx;
  const inp = $("hiddenfile");
  inp.multiple = !!multiple; inp.value = "";       // 清空→重选同名也触发change
  inp.click();
}

async function onFilePicked(files) {
  const ctx = S.uploadCtx;
  if (!ctx) return;
  setBusy(`上传 ${files.length} 份文件…`);
  try {
    const r = await api.uploadMaterials(S.job, files);   // 存 materials/(复用现有端点, 装配按文件名取图标)
    (r.saved || []).forEach((name) => placeUploaded(ctx, name));
    setBusy(""); save(); render();
    toast(`已添加 ${(r.saved || []).length} 份文件${ctx.unlinked ? "→ 认不准池(请归位)" : ""}`, "ok");
  } catch (e) { setBusy(""); toast("上传失败：" + e.message, "err"); }
}

function placeUploaded(ctx, name) {
  if (ctx.unlinked) {                                // 补部件/UL等→进认不准池, 由拖拽/部件归属落位
    if (!S.bom.unlinked_files.some((u) => u.文件 === name)) S.bom.unlinked_files.push({ 文件: name, 类型: "其他" });
    return;
  }
  const fz = S.bom.materials[ctx.mi].files = S.bom.materials[ctx.mi].files || {};
  const bucket = UPLOAD_BUCKET[ctx.colKey];
  if (bucket === "MSDS") { fz.MSDS = name; }          // MSDS 单值
  else {
    fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
    if (!fz[bucket].includes(name)) fz[bucket].push(name);
  }
}

function _removeFromSource() {
  const d = S.drag;
  if (d.from === "unlinked") {
    S.bom.unlinked_files = S.bom.unlinked_files.filter((u) => !(u.文件 === d.file && u.类型 === d.type));
  } else {
    const fz = S.bom.materials[+d.from].files || {};
    if (Array.isArray(fz[d.type])) fz[d.type] = fz[d.type].filter((x) => x !== d.file);
    else if (fz[d.type] === d.file) fz[d.type] = (d.type === "MSDS") ? "" : [];
  }
}

function dropTo(token) {
  if (!S.drag) return;
  const [miStr, colKey] = token.split("|");
  const mi = +miStr, bucket = COL_BUCKET[colKey];
  _removeFromSource();
  const fz = S.bom.materials[mi].files = S.bom.materials[mi].files || {};
  fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
  if (!fz[bucket].includes(S.drag.file)) fz[bucket].push(S.drag.file);
  S.drag = null; save(); render();
}

function attachSuggested(j) {
  const u = S.bom.unlinked_files[j];
  if (!u || !u.建议) return;
  const mi = u.建议.idx, bucket = u.类型 || COL_BUCKET[u.建议.col];   // 落原类型桶(RoHS/SVHC/REACH→对的列)
  S.bom.unlinked_files.splice(j, 1);
  const fz = S.bom.materials[mi].files = S.bom.materials[mi].files || {};
  fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
  if (!fz[bucket].includes(u.文件)) fz[bucket].push(u.文件);
  save(); render();
}

async function placeOrphan(j, dest, target) {        // 待归位文件→三类目标归位(材质列/横排槽+零件/本单不收录)
  const u = S.bom.unlinked_files[j];
  if (!u || !dest) return;
  const file = u.文件;
  if (dest === "exclude") {
    const reason = await dlgPrompt({ title: `本单不收录「${shortName(file)}」原因(必填·留痕)`,
                                     presets: ["与本单无关/误传", "重复件", "作废旧版本"] });
    if (!reason) return;
    S.bom.excluded_files = S.bom.excluded_files || [];
    S.bom.excluded_files.push({ 文件: file, 原因: reason });
    try { api.bomLog(S.job, { 动作: "本单不收录", 详情: `${file} — ${reason}` }); } catch { /* 留痕失败不挡 */ }
  } else if (dest.startsWith("slot:")) {
    if (!target) { toast("请选零件", "err"); return; }
    S.bom.部件归属 = S.bom.部件归属 || {};
    S.bom.部件归属[file] = { 槽: dest.slice(5), 零件: target };       // 救 route=∅: 显式槽+零件→pile_specs放置
  } else if (dest.startsWith("col:")) {
    const bucket = COL_BUCKET[dest.slice(4)], mi = +target;
    const fz = S.bom.materials[mi].files = S.bom.materials[mi].files || {};
    fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
    if (!fz[bucket].includes(file)) fz[bucket].push(file);
  } else { return; }
  S.bom.unlinked_files.splice(j, 1);
  save(); render();
  toast(`已归位「${shortName(file)}」`, "ok");
}

function dropToUnlinked() {
  if (!S.drag || S.drag.from === "unlinked") { S.drag = null; return; }
  const d = S.drag; _removeFromSource();
  if (!S.bom.unlinked_files.some((u) => u.文件 === d.file)) S.bom.unlinked_files.push({ 文件: d.file, 类型: d.type });
  S.drag = null; save(); render();
}

function unlinkFile(mi, type, file) {
  const m = S.bom.materials[mi], fz = m.files || {};
  if (Array.isArray(fz[type])) fz[type] = fz[type].filter((x) => x !== file);
  else if (fz[type] === file) fz[type] = (type === "MSDS") ? "" : [];
  if (!S.bom.unlinked_files.some((u) => u.文件 === file)) S.bom.unlinked_files.push({ 文件: file, 类型: type });
  save(); render();
  toast(`已移下「${shortName(file)}」`, "info", {       // 撤销: 删回认不准池+挂回原材质列
    label: "撤销",
    fn: () => {
      S.bom.unlinked_files = S.bom.unlinked_files.filter((u) => !(u.文件 === file && u.类型 === type));
      const f2 = m.files = m.files || {};
      if (type === "MSDS") f2.MSDS = file;
      else { f2[type] = Array.isArray(f2[type]) ? f2[type] : (f2[type] ? [f2[type]] : []); if (!f2[type].includes(file)) f2[type].push(file); }
      save(); render();
    },
  });
}

async function toggleExempt(i) {
  const m = S.bom.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else { const r = await dlgPrompt({ title: "豁免原因(必填, 留痕)", presets: EXEMPT_REASONS }); if (!r) return; m.豁免 = true; m.豁免原因 = r; }
  save(); render();
}

function refresh() {
  const miss = filetreeMissing(S.bom);                     // 缺MSDS=硬门
  const exN = S.bom.materials.filter((m) => m.豁免).length;
  const unl = S.bom.unlinked_files.length;
  const exclN = (S.bom.excluded_files || []).length;
  S.missing = miss;
  const chips = miss.map((t) => ({ t, hard: true }));
  if (unl) chips.push({ t: `${unl}个上传文件未归位`, hard: false });   // 软门: 强提示不硬挡(红线:绝不静默漏件)
  renderGate({
    summaryId: "summary", btnId: "gatebtn",
    missing: chips,
    doneText: `放置已齐（${S.bom.materials.length}材质${exN ? `·豁免${exN}` : ""}${exclN ? `·不收录${exclN}` : ""}${unl ? `·待归位${unl}` : "·全部已归位✓"}）`,
    nextLabel: "放置已确认 → 第4步 照片导出 →",
    rule: "缺MSDS不可导出；未归位文件不处理将不进承认书", todoSel: ".mat-card[data-st='todo']",
  });
}

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => api.filetreeSave(S.job, S.bom).then(savedTick).catch(() => {}), 800);
}

async function onConfirm() {
  if (S.missing && S.missing.length) { scrollFirstTodo(".mat-card[data-st='todo']"); return; }
  setBusy("提交…");
  try {
    await api.filetreeConfirm(S.job, S.bom);
    setBusy("");
    const next = "index_export.html?job=" + encodeURIComponent(S.job);
    $("summary").innerHTML = `✅ 文件树已确认 · <a href="${next}">进入 ⑤照片+导出 →</a>`;
    $("gatebtn").disabled = true;
    setTimeout(() => { location.href = next; }, 900);
  } catch (e) { setBusy(""); toast("放行被拦：" + e.message, "err"); }
}

function shortName(s) { s = String(s || ""); return s.length > 22 ? s.slice(0, 20) + "…" : s; }
function setBusy(t) { $("busy").textContent = t; $("busy").style.display = t ? "block" : "none"; }
function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

boot();
