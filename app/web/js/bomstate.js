// BOM 编辑器纯逻辑(可 node 单测): 分组 / 判重 / 可疑判定 / 缺项(镜像后端 validate_bom)。
// 材质 m = {材质,供应商,供应商原文,成份:[{成份名称,CAS,重量%}],RoHS:{10项},报告编号,报告日期,源文件,
//          零件,材质类别,已核对,豁免,手补}

export function normName(s) {
  return String(s || "").replace(/\s+/g, "").toUpperCase();
}

export function groupByPart(materials) {
  // → {parts:{零件:[idx]}, order:[零件...], unclaimed:[idx]}。零件空=待认领。
  const parts = {}, order = [], unclaimed = [];
  materials.forEach((m, i) => {
    const p = (m.零件 || "").trim();
    if (!p) { unclaimed.push(i); return; }
    if (!parts[p]) { parts[p] = []; order.push(p); }
    parts[p].push(i);
  });
  return { parts, order, unclaimed };
}

export function syncPartSuppliers(materials) {
  // 供应商是【零件级】属性, 但反范式化存在每个材质上(m.供应商)。新增/拖入材质改了 m.零件 却没继承
  // 该零件已有的供应商 → 材质级 m.供应商 仍空 → materialMissing 误报"缺供应商", 而 UI 只有零件级
  // 供应商框、无法单材质修改 → 死结。此函数把每个零件的供应商(取该零件首个非空)同步到该零件全部材质,
  // 自愈维持"同零件共享一个供应商"的不变式。render/save/confirm 前都跑。返回是否有改动。
  const sup = {};
  for (const m of materials) {
    const p = (m.零件 || "").trim();
    if (p && (m.供应商 || "").trim() && !(p in sup)) sup[p] = m.供应商.trim();
  }
  let changed = false;
  for (const m of materials) {
    const p = (m.零件 || "").trim();
    if (p && sup[p] && (m.供应商 || "").trim() !== sup[p]) { m.供应商 = sup[p]; changed = true; }
  }
  return changed;
}

export function detectDups(materials) {
  // 同归一材质名 ≥2(未豁免) → [[idx,...]]。供联标, 不自动合并(CANEC色号料名会漏判, 另有手动合并兜底)。
  const by = {};
  materials.forEach((m, i) => {
    if (m.豁免) return;
    const k = normName(m.材质);
    if (k) (by[k] = by[k] || []).push(i);
  });
  return Object.values(by).filter((g) => g.length >= 2);
}

export function suspect(m) {
  // 可疑判据(镜像 spike/assemble normalize, 复核非重算)。命中→该卡标黄强制核。返回原因[]。
  const reasons = [];
  const comps = m.成份 || [];
  if (comps.some((c) => { const s = String(c.CAS || "").trim(); return !s || s === "/" || s === "-"; }))
    reasons.push("成分缺CAS");
  if (comps.some((c) => {
    const w = String(c["重量%"] || "").trim();
    return w && !w.includes("余量") && !/^[<≤>]/.test(w) && parseFloat(w) > 1;   // normalize_weight 已÷100, 正常≤1
  }))
    reasons.push("重量%未归一(>1)");
  const vals = Object.values(m.RoHS || {});
  if (vals.some((v) => v && !["ND", "NA", ""].includes(String(v).toUpperCase())))
    reasons.push("RoHS有数值需核");                                              // Pb=63/14 真信号
  if (vals.filter((v) => String(v).toUpperCase() === "NA").length >= 6)
    reasons.push("RoHS多项NA(可能漏测)");
  return reasons;
}

export function materialMissing(m, i) {
  // 单材质缺项(镜像后端 validate_bom)。
  const out = [];
  const 名 = (m.材质 || "").trim() || `材质${i + 1}`;
  for (const f of ["零件", "材质类别", "供应商"]) if (!(m[f] || "").trim()) out.push(`${名}缺${f}`);
  if (!m.已核对 && !m.豁免) out.push(`${名}未核对`);
  return out;
}

export function allMissing(materials) {
  if (!materials || !materials.length) return ["无材质(先拖材料让B提议)"];
  return materials.flatMap((m, i) => materialMissing(m, i));
}

export function cardState(m, i) {
  // 卡状态色(=示意空槽图): exempt豁免 / warn可疑或规则缺 / todo待补 / ok齐。
  if (m.豁免) return "exempt";
  if (suspect(m).length) return "warn";
  if (materialMissing(m, i).length) return "todo";
  return "ok";
}
