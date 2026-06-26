// M2.4 确认环②文件树 纯逻辑(可 node 单测): 放置计划树 / 槽状态 / 缺项(镜像后端 validate_filetree)。
// 证据列 K=MSDS L=REACH·SVHC Y=RoHS, 与后端 OLE_COL/placement_plan.TYPE_COL 同口径。

export const COLS = [
  { key: "K", label: "MSDS", types: ["MSDS", "其他"] },
  { key: "L", label: "REACH/SVHC", types: ["REACH", "SVHC"] },
  { key: "Y", label: "RoHS", types: ["RoHS"] },
];

function asList(v) {
  return v == null ? [] : (Array.isArray(v) ? v : [v]);
}

export function materialMsds(m) {
  return asList((m.files || {}).MSDS).filter(Boolean)[0] || "";
}

export function filesOfCol(m, col) {
  // 该材质在某证据列承载的文件 [{文件,类型}]。
  const fz = m.files || {};
  const out = [];
  for (const t of col.types) for (const f of asList(fz[t])) if (f) out.push({ 文件: f, 类型: t });
  return out;
}

export function slotState(m, col) {
  // 槽状态色(=空槽图): 豁免→exempt; 有文件→ok; MSDS缺→todo(必补); 第三方缺→todo(软,gate不拦)。
  if (m.豁免) return "exempt";
  if (filesOfCol(m, col).length) return "ok";
  return "todo";
}

export function filetreeMissing(stage2_bom) {
  // 镜像后端 validate_filetree: 每材质 MSDS 必有(或豁免); 第三方缺软放不拦。
  const mats = (stage2_bom && stage2_bom.materials) || [];
  if (!mats.length) return ["无材质(先完成BOM脊柱)"];
  const out = [];
  mats.forEach((m, i) => {
    const 名 = (m.材质 || "").trim() || `材质${i + 1}`;
    if (!materialMsds(m) && !m.豁免) out.push(`${名}缺MSDS(可豁免)`);
  });
  return out;
}

export function planTree(stage2_bom) {
  // → {materials:[{idx,材质,零件,豁免,slots:{K:[],L:[],Y:[]}}], unlinked:[{文件,类型}], parts:{零件:[idx]}}
  const mats = (stage2_bom && stage2_bom.materials) || [];
  const parts = {}, order = [];
  const materials = mats.map((m, i) => {
    const p = (m.零件 || "").trim() || "(未归零件)";
    if (!parts[p]) { parts[p] = []; order.push(p); }
    parts[p].push(i);
    const slots = {};
    for (const col of COLS) slots[col.key] = filesOfCol(m, col);
    return { idx: i, 材质: m.材质 || `材质${i + 1}`, 零件: m.零件 || "", 豁免: !!m.豁免, slots };
  });
  return { materials, parts, order, unlinked: (stage2_bom && stage2_bom.unlinked_files) || [] };
}
