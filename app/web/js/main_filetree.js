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
              部件归属: s.部件归属 || {}, excluded_files: s.excluded_files || [], 槽布局: s.槽布局 || {} };
    S.cards = s.cards || { parts: [], page: [] };
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
  $("bomtable").innerHTML = (html || "<p class='tip'>无材质</p>") + partsCardsHtml() + pageCardsHtml();
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

function _pChip(f) {   // 部件/页级卡槽内文件chip(可拖出→部件归属源)
  return `<span class="filechip" draggable="true" data-from="部件归属" data-file="${esc(f)}" title="${esc(f)}">${esc(shortName(f))}<button class="x" data-unpart="${esc(f)}">×</button></span>`;
}

function partsCardsHtml() {
  // 部件卡(复用材质卡外观): 标题=分类(部件承认书/UL/信赖性), 槽=零件; 拖入/+选文件; 零件槽可增/删/改。
  const cards = (S.cards && S.cards.parts) || [];
  if (!cards.length) return "";
  return cards.map((c) => {
    const slots = c.slots.map((sl) => {
      const p = sl.零件 || "";
      const chips = (sl.files || []).map(_pChip).join("");
      const empty = sl.files.length ? "" : `<span class="emptyslot opt">拖入 / +选文件</span>`;
      const tools = p ? `<button class="slot-ren" data-renslot="${esc(c.分类)}|${esc(p)}" title="改零件槽名">✎</button>`
        + `<button class="slot-del" data-delslot="${esc(c.分类)}|${esc(p)}" title="删此零件槽">×</button>` : "";
      return `<div class="slot pslot" data-drop="slot:${esc(c.short)}|${esc(p)}" data-st="${sl.files.length ? "ok" : "todo"}">
        <div class="col-label">${esc(p || "未指定零件")} ${tools}</div>${chips}${empty}
        <button class="addslot" data-padd="slot:${esc(c.short)}|${esc(p)}" title="从电脑选文件补到此槽">+ 选文件</button></div>`;
    }).join("");
    return `<div class="card part-card"><div class="mat-row"><span class="matname">${esc(c.分类)} <small>槽=零件</small></span>
      <button class="addpart-slot" data-addslot="${esc(c.分类)}">+ 增零件槽</button></div>
      <div class="slot-grid">${slots}</div></div>`;
  }).join("");
}

function pageCardsHtml() {
  // 页级单槽卡: 包装/出货/图纸 各一槽(不分零件)。
  const cards = (S.cards && S.cards.page) || [];
  if (!cards.length) return "";
  const slots = cards.map((c) => {
    const chips = (c.files || []).map(_pChip).join("");
    const empty = c.files.length ? "" : `<span class="emptyslot opt">拖入 / +选文件</span>`;
    return `<div class="slot pslot" data-drop="page:${esc(c.short)}" data-st="${c.files.length ? "ok" : "todo"}">
      <div class="col-label">${esc(c.分类)}</div>${chips}${empty}
      <button class="addslot" data-padd="page:${esc(c.short)}" title="从电脑选文件补到此槽">+ 选文件</button></div>`;
  }).join("");
  return `<div class="card page-card"><div class="mat-row"><span class="matname">页级文件 <small>包装 / 出货 / 图纸</small></span></div>
    <div class="slot-grid">${slots}</div></div>`;
}

function renderUnlinked(unlinked) {
  // 零丢失·纯拖拽: 待归位文件=可拖chip, 拖进左侧任意卡的任意槽(材质K/L/Y · 部件卡零件槽 · 页级槽); 建议挂=一键捷径; 拖到"本单不收录"区=排除。
  const rows = unlinked.map((u, j) => {
    const s = u.建议;
    const sug = s ? `<button class="sugbtn" data-sug="${j}" title="一点即挂到「${esc(s.材质)}」的 ${esc(s.col)} 列(${s.据 === "色" ? "按颜色" : "按名称"}匹配)">↳建议挂 ${esc(s.材质)}${s.据 === "色" ? " <small>按色</small>" : ""}</button>` : "";
    return `<div class="orphan-card">
      <span class="filechip unl" draggable="true" data-from="unlinked" data-type="${esc(u.类型)}" data-file="${esc(u.文件)}" data-j="${j}" title="${esc(u.文件)}">${esc(shortName(u.文件))} <em>${esc(u.类型)}</em></span>${sug}</div>`;
  }).join("");
  $("unlinked").innerHTML = (rows || `<div class="drag-hint">所有上传文件已归位 ✓</div>`)
    + `<div class="exclude-zone" id="excludezone" data-drop="exclude" title="拖到这里=本单不收录(需填原因·留痕)"><i class="ti ti-archive-off" aria-hidden="true"></i> 拖到此处 = 本单不收录</div>`;
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
  document.querySelectorAll(".slot, .exclude-zone").forEach((el) => {     // 材质槽/部件槽/页级槽/排除区 都是落点
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("drag-over"); });
    el.addEventListener("dragleave", () => el.classList.remove("drag-over"));
    el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("drag-over"); dropTo(el.dataset.drop); });
  });
  const uz = $("unlinked");
  uz.addEventListener("dragover", (e) => { e.preventDefault(); uz.classList.add("drag-over"); });
  uz.addEventListener("dragleave", () => uz.classList.remove("drag-over"));
  uz.addEventListener("drop", (e) => { e.preventDefault(); uz.classList.remove("drag-over"); dropToUnlinked(); });
  document.querySelectorAll("[data-unlink]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); const [i, t, f] = el.dataset.unlink.split("|"); unlinkFile(+i, t, f); });
  document.querySelectorAll("[data-unpart]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); unpartFile(el.dataset.unpart); });
  document.querySelectorAll("[data-exempt]").forEach((el) => el.onclick = () => toggleExempt(+el.dataset.exempt));
  document.querySelectorAll("[data-sug]").forEach((el) => el.onclick = () => attachSuggested(+el.dataset.sug));
  document.querySelectorAll("[data-add]").forEach((el) => el.onclick = (e) => {   // 材质槽 +选文件
    e.stopPropagation(); const [mi, colKey] = el.dataset.add.split("|"); pickFiles({ mi: +mi, colKey }, colKey !== "K");
  });
  document.querySelectorAll("[data-padd]").forEach((el) => el.onclick = (e) => {  // 部件/页级槽 +选文件
    e.stopPropagation(); pickFiles({ padd: el.dataset.padd }, true);
  });
  document.querySelectorAll("[data-addslot]").forEach((el) => el.onclick = () => addPartSlot(el.dataset.addslot));
  document.querySelectorAll("[data-delslot]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); const [c, p] = el.dataset.delslot.split("|"); delPartSlot(c, p); });
  document.querySelectorAll("[data-renslot]").forEach((el) => el.onclick = (e) => { e.stopPropagation(); const [c, p] = el.dataset.renslot.split("|"); renPartSlot(c, p); });
  const ap = $("addpile"); if (ap) ap.onclick = () => pickFiles({ unlinked: true }, true);   // 补文件→待归位池
  $("gatebtn").onclick = onConfirm;
}

// 提交并刷新: 存本单 → 服务端重算 cards/待归位(route在后端) → 重渲染。结构性改动(拖拽/CRUD)走它。
async function commit() {
  try {
    await api.filetreeSave(S.job, { materials: S.bom.materials, unlinked_files: S.bom.unlinked_files,
      部件归属: S.bom.部件归属 || {}, excluded_files: S.bom.excluded_files || [], 槽布局: S.bom.槽布局 || {} });
    const s = await api.filetreeState(S.job);
    S.bom = { materials: s.materials || [], unlinked_files: s.unlinked_files || [],
      部件归属: s.部件归属 || {}, excluded_files: s.excluded_files || [], 槽布局: s.槽布局 || {} };
    S.cards = s.cards || { parts: [], page: [] };
    S.parts = s.parts || [];
    savedTick();
  } catch { /* 离线: 退化为本地渲染 */ }
  render();
}

const _SHORT = { "部件承认书": "部件承认", "UL证明": "UL", "信赖性": "信赖性" };

function _ensureLayout(分类) {
  S.bom.槽布局 = S.bom.槽布局 || {};
  S.bom.槽布局.parts = S.bom.槽布局.parts || {};
  if (!S.bom.槽布局.parts[分类]) {                  // 首次CRUD: 以当前卡的零件槽为基线
    const card = (S.cards.parts || []).find((c) => c.分类 === 分类);
    S.bom.槽布局.parts[分类] = card ? card.slots.map((s) => s.零件).filter(Boolean) : [];
  }
  return S.bom.槽布局.parts[分类];
}

async function addPartSlot(分类) {
  const p = await dlgPrompt({ title: `新增零件槽 — ${分类}`, placeholder: "零件名, 如 导线 / 胶座端子 / 套管",
                              presets: (S.parts || []).concat("其他(填新名)") });
  if (!p) return;
  const arr = _ensureLayout(分类);
  if (!arr.includes(p)) arr.push(p);
  commit();
}

async function renPartSlot(分类, 零件) {
  const np = await dlgPrompt({ title: `改零件槽名 — ${零件}`, presets: (S.parts || []) });
  if (!np || np === 零件) return;
  const arr = _ensureLayout(分类);
  const i = arr.indexOf(零件);
  if (i >= 0) arr[i] = np; else arr.push(np);
  for (const v of Object.values(S.bom.部件归属 || {})) {       // 同步重命名归属
    if (v && typeof v === "object" && v.槽 === _SHORT[分类] && v.零件 === 零件) v.零件 = np;
  }
  commit();
}

function delPartSlot(分类, 零件) {
  const arr = _ensureLayout(分类);
  const i = arr.indexOf(零件);
  if (i >= 0) arr.splice(i, 1);
  for (const [fn, v] of Object.entries(S.bom.部件归属 || {})) {  // 槽内文件→回待归位池(删归属)
    if (v && typeof v === "object" && v.槽 === _SHORT[分类] && v.零件 === 零件) delete S.bom.部件归属[fn];
  }
  commit();
  toast(`已删零件槽「${零件}」，槽内文件回待归位池`, "info");
}

function unpartFile(file) {                          // 部件/页级卡槽内文件移下→回待归位池
  if (S.bom.部件归属) delete S.bom.部件归属[file];
  commit();
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
    setBusy(""); await commit();
    toast(`已添加 ${(r.saved || []).length} 份文件${ctx.unlinked ? "→ 待归位池(请归位)" : ""}`, "ok");
  } catch (e) { setBusy(""); toast("上传失败：" + e.message, "err"); }
}

function placeUploaded(ctx, name) {
  if (ctx.padd) {                                   // 部件/页级卡 +选文件→直接归该槽
    const isPage = ctx.padd.startsWith("page:");
    const [short, 零件] = isPage ? [ctx.padd.slice(5), ""] : ctx.padd.slice(5).split("|");
    S.bom.部件归属 = S.bom.部件归属 || {};
    S.bom.部件归属[name] = { 槽: short, 零件: 零件 || "" };
    return;
  }
  if (ctx.unlinked) {                                // 补充→进待归位池, 由拖拽落位
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

function _removeFromSource(d) {
  d = d || S.drag;
  if (d.from === "unlinked") {
    S.bom.unlinked_files = S.bom.unlinked_files.filter((u) => !(u.文件 === d.file && u.类型 === d.type));
  } else if (d.from === "部件归属") {                  // 从部件/页级卡槽拖出
    if (S.bom.部件归属) delete S.bom.部件归属[d.file];
  } else {
    const fz = S.bom.materials[+d.from].files || {};
    if (Array.isArray(fz[d.type])) fz[d.type] = fz[d.type].filter((x) => x !== d.file);
    else if (fz[d.type] === d.file) fz[d.type] = (d.type === "MSDS") ? "" : [];
  }
}

function dropTo(token) {
  if (!S.drag) return;
  const d = S.drag, file = d.file;
  S.drag = null;
  if (token === "exclude") { excludeFile(d); return; }            // 拖到排除区→填原因(异步)
  _removeFromSource(d);
  if (token.startsWith("slot:") || token.startsWith("page:")) {   // 部件卡(分类+零件) / 页级卡(单槽)
    const isPage = token.startsWith("page:");
    const [short, 零件] = isPage ? [token.slice(5), ""] : token.slice(5).split("|");
    S.bom.部件归属 = S.bom.部件归属 || {};
    S.bom.部件归属[file] = { 槽: short, 零件: 零件 || "" };
  } else {                                                        // 材质卡 K/L/Y 列
    const [miStr, colKey] = token.split("|");
    const fz = S.bom.materials[+miStr].files = S.bom.materials[+miStr].files || {};
    const bucket = COL_BUCKET[colKey];
    fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
    if (!fz[bucket].includes(file)) fz[bucket].push(file);
  }
  commit();
}

async function excludeFile(d) {                       // 本单不收录(必填原因·留痕), 然后从源移除
  const reason = await dlgPrompt({ title: `本单不收录「${shortName(d.file)}」原因(必填·留痕)`,
                                   presets: ["与本单无关/误传", "重复件", "作废旧版本"] });
  if (!reason) return;
  _removeFromSource(d);
  S.bom.excluded_files = S.bom.excluded_files || [];
  S.bom.excluded_files.push({ 文件: d.file, 原因: reason });
  try { api.bomLog(S.job, { 动作: "本单不收录", 详情: `${d.file} — ${reason}` }); } catch { /* 留痕失败不挡 */ }
  commit();
}

function attachSuggested(j) {
  const u = S.bom.unlinked_files[j];
  if (!u || !u.建议) return;
  const mi = u.建议.idx, bucket = u.类型 || COL_BUCKET[u.建议.col];   // 落原类型桶(RoHS/SVHC/REACH→对的列)
  const fz = S.bom.materials[mi].files = S.bom.materials[mi].files || {};
  fz[bucket] = Array.isArray(fz[bucket]) ? fz[bucket] : (fz[bucket] ? [fz[bucket]] : []);
  if (!fz[bucket].includes(u.文件)) fz[bucket].push(u.文件);
  commit();
}

function dropToUnlinked() {
  if (!S.drag || S.drag.from === "unlinked") { S.drag = null; return; }
  const d = S.drag; S.drag = null; _removeFromSource(d);
  if (!S.bom.unlinked_files.some((u) => u.文件 === d.file)) S.bom.unlinked_files.push({ 文件: d.file, 类型: d.type });
  commit();
}

function unlinkFile(mi, type, file) {
  const m = S.bom.materials[mi], fz = m.files || {};
  if (Array.isArray(fz[type])) fz[type] = fz[type].filter((x) => x !== file);
  else if (fz[type] === file) fz[type] = (type === "MSDS") ? "" : [];
  if (!S.bom.unlinked_files.some((u) => u.文件 === file)) S.bom.unlinked_files.push({ 文件: file, 类型: type });
  commit();
  toast(`已移下「${shortName(file)}」`, "info", {       // 撤销: 挂回原材质列
    label: "撤销",
    fn: () => {
      const f2 = m.files = m.files || {};
      if (type === "MSDS") f2.MSDS = file;
      else { f2[type] = Array.isArray(f2[type]) ? f2[type] : (f2[type] ? [f2[type]] : []); if (!f2[type].includes(file)) f2[type].push(file); }
      commit();
    },
  });
}

async function toggleExempt(i) {
  const m = S.bom.materials[i];
  if (m.豁免) { delete m.豁免; delete m.豁免原因; }
  else { const r = await dlgPrompt({ title: "豁免原因(必填, 留痕)", presets: EXEMPT_REASONS }); if (!r) return; m.豁免 = true; m.豁免原因 = r; }
  commit();
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
