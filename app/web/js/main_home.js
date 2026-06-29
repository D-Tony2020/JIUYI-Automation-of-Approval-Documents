// 断点续做首页: 最近本单列表(读 /api/orders) + 各步进度点 + 继续到续做步。来自 UXUI 评审。
import * as api from "./api.js";

const NUM = ["", "①", "②", "③", "④"];
const PAGE = { 1: "index.html", 2: "index_bom.html", 3: "index_filetree.html", 4: "index_export.html" };
const LBL = ["", "核对图纸", "理材质", "挂文件", "照片导出"];

function esc(s) { return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c])); }

function fmtTime(t) {
  try { const d = new Date(t * 1000); const p = (n) => String(n).padStart(2, "0"); return `${d.getMonth() + 1}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`; } catch { return ""; }
}

async function loadApiConfig() {                          // 首页「API设置」: 预填当前key + 保存到%APPDATA%
  const inp = document.getElementById("apikey"), st = document.getElementById("apikey-status");
  const eye = document.getElementById("apikey-eye"), save = document.getElementById("apikey-save");
  if (!inp) return;
  if (location.hash === "#api") document.getElementById("apicfg").open = true;   // 深链直达设置
  try {
    const c = await api.getConfig();
    inp.value = c.api_key || "";
    st.textContent = c.saved ? "✓ 已保存到本机（跨重装保留）" : (c.has_key ? "随包/环境默认已就绪，可在此覆盖" : "⚠ 未配置，请填入官方通义 key 后保存");
    st.className = "apicfg-status " + (c.has_key ? "ok" : "warn");
  } catch (e) { st.textContent = "读取失败：" + esc(e.message); st.className = "apicfg-status warn"; }
  eye.onclick = () => { inp.type = inp.type === "password" ? "text" : "password"; };
  save.onclick = async () => {
    save.disabled = true; st.textContent = "保存中…"; st.className = "apicfg-status";
    try {
      const r = await api.saveConfig(inp.value.trim());
      st.textContent = r.has_key ? "✓ 已保存到本机" : "已清空（将回退随包/环境默认）";
      st.className = "apicfg-status ok";
    } catch (e) { st.textContent = "保存失败：" + esc(e.message); st.className = "apicfg-status warn"; }
    finally { save.disabled = false; }
  };
}

async function boot() {
  loadApiConfig();
  if (!document.querySelector("link[rel=icon]")) { const l = document.createElement("link"); l.rel = "icon"; l.href = "favicon.svg"; document.head.appendChild(l); }
  fetch("/api/version").then((r) => r.json()).then((v) => {        // 版本号(右上品牌旁)
    const b = document.querySelector(".brand-name"); if (b && v.version) b.innerHTML = `材料承认书自动生成 <small style="color:#9ca3af">v${v.version}</small>`;
  }).catch(() => {});
  const el = document.getElementById("orderlist");
  let list;
  try { list = await api.orders(); } catch (e) { el.innerHTML = `<p class="tip">读取失败：${esc(e.message)}</p>`; return; }
  if (!list.length) { el.innerHTML = `<div class="empty">暂无本单 · 点右上「+ 新建」开始</div>`; return; }
  el.innerHTML = list.map((o) => {
    const dots = [1, 2, 3, 4].map((n) => {
      const x = (o.overview || {})[n] || null;
      const cls = x ? (x.缺 > 0 ? "dot miss" : "dot ok") : "dot";
      return `<span class="${cls}" title="${LBL[n]}${x ? (x.缺 > 0 ? " 缺" + x.缺 : " ✓") : " 未开始"}">${NUM[n]}</span>`;
    }).join("");
    const status = o.exported
      ? `<span class="badge done">已导出</span>`
      : `<span class="badge ing">在第${o.resume}步 ${LBL[o.resume]}</span>`;
    const page = PAGE[o.resume] || "index.html";
    return `<div class="order-card">
      <div class="oc-main">
        <div class="oc-title">${esc(o.品号 || o.job)} <small>${esc(o.名称 || "")}</small></div>
        <div class="oc-steps">${dots} <span class="oc-time">更新 ${fmtTime(o.updated)}</span></div>
      </div>
      <div class="oc-right">${status}
        <a class="contbtn" href="${page}?job=${encodeURIComponent(o.job)}">${o.exported ? "查看" : "继续"} →</a></div>
    </div>`;
  }).join("");
}

boot();
