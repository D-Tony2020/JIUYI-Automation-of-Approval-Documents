// 页内小面板, 替换原生 prompt/alert/confirm(无校验·误触取消丢输入·留痕不规范, 合规隐患)。
// 来自 UXUI 设计评审 P1.3。dlgPrompt 支持原因预设单选+必填校验; toast 非阻断提示。
function esc(s) {
  return String(s == null ? "" : s).replace(/[<>&"]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;" }[c]));
}

function _overlay() {
  let o = document.getElementById("dlg-overlay");
  if (!o) { o = document.createElement("div"); o.id = "dlg-overlay"; o.className = "dlg-overlay"; document.body.appendChild(o); }
  return o;
}

/* {title, placeholder, value, presets:[..], required} → Promise<string|null(取消)>。
   presets 给则渲染原因单选(选中即填入输入框, 含'其他'则清空待填)。 */
export function dlgPrompt({ title, placeholder = "", value = "", presets = null, required = true }) {
  return new Promise((resolve) => {
    const o = _overlay();
    const pres = presets
      ? `<div class="dlg-presets">${presets.map((p, i) =>
        `<label><input type="radio" name="dpre" value="${esc(p)}" ${i === 0 ? "checked" : ""}> ${esc(p)}</label>`).join("")}</div>`
      : "";
    o.innerHTML = `<div class="dlg">
      <div class="dlg-title">${esc(title)}</div>${pres}
      <input class="dlg-input" placeholder="${esc(placeholder)}" value="${esc(value)}">
      <div class="dlg-err"></div>
      <div class="dlg-btns"><button class="dlg-cancel">取消</button><button class="dlg-ok">确定</button></div>
    </div>`;
    o.style.display = "flex";
    const inp = o.querySelector(".dlg-input"), err = o.querySelector(".dlg-err");
    const isOther = (s) => s.indexOf("其他") >= 0;
    if (presets) inp.value = isOther(presets[0]) ? "" : presets[0];
    o.querySelectorAll("[name=dpre]").forEach((r) => (r.onclick = () => { inp.value = isOther(r.value) ? "" : r.value; inp.focus(); }));
    const close = (v) => { o.style.display = "none"; o.innerHTML = ""; resolve(v); };
    o.querySelector(".dlg-cancel").onclick = () => close(null);
    const ok = () => { const v = inp.value.trim(); if (required && !v) { err.textContent = "必填"; return; } close(v); };
    o.querySelector(".dlg-ok").onclick = ok;
    inp.onkeydown = (e) => { if (e.key === "Enter") ok(); if (e.key === "Escape") close(null); };
    inp.focus();
  });
}

export function dlgConfirm(msg) {
  return new Promise((resolve) => {
    const o = _overlay();
    o.innerHTML = `<div class="dlg"><div class="dlg-title">${esc(msg)}</div>
      <div class="dlg-btns"><button class="dlg-cancel">取消</button><button class="dlg-ok">确定</button></div></div>`;
    o.style.display = "flex";
    const close = (v) => { o.style.display = "none"; o.innerHTML = ""; resolve(v); };
    o.querySelector(".dlg-cancel").onclick = () => close(false);
    o.querySelector(".dlg-ok").onclick = () => close(true);
  });
}

export function toast(msg, kind = "info", action) {
  // action: {label, fn} → 在 toast 上加按钮(如"撤销"), 该类 toast 停留更久。
  let t = document.getElementById("dlg-toast");
  if (!t) { t = document.createElement("div"); t.id = "dlg-toast"; document.body.appendChild(t); }
  t.className = "dlg-toast " + kind; t.innerHTML = "";
  t.append(document.createTextNode(msg));
  if (action) {
    const b = document.createElement("button");
    b.className = "toast-act"; b.textContent = action.label;
    b.onclick = () => { t.style.display = "none"; action.fn(); };
    t.append(b);
  }
  t.style.display = "block";
  clearTimeout(t._t); t._t = setTimeout(() => (t.style.display = "none"), action ? 5500 : 2800);
}

export function savedTick() {                       // 自动保存可见(降低'刷新会不会丢'焦虑)
  let t = document.getElementById("saved-tick");
  if (!t) { t = document.createElement("div"); t.id = "saved-tick"; t.className = "saved-tick"; document.body.appendChild(t); }
  const d = new Date(), p = (n) => String(n).padStart(2, "0");
  t.textContent = `✓ 已自动保存 ${p(d.getHours())}:${p(d.getMinutes())}`;
  t.style.opacity = "1";
  clearTimeout(t._t); t._t = setTimeout(() => (t.style.opacity = "0"), 2000);
}

export const EXEMPT_REASONS = ["本料无第三方报告", "本料无MSDS(已附REACH)", "源缺待补", "客户豁免", "其他(填备注)"];
