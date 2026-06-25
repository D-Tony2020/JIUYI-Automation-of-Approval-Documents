// 前端规则校验 — extract 无置信度, 靠格式启发式抓可疑(零成本真护城河)。
// 与后端 app/rules.py 同规则(后端是权威兜底)。

export function checkVersion(v) {
  return /^[A-Za-z]\d{2}$/.test(String(v ?? "").trim());        // A01/B02 式
}

export function checkCode(v) {
  const s = String(v ?? "").trim();
  return s.length >= 6 && /[A-Za-z]/.test(s) && /\d/.test(s);   // 字母+数字, 长度≥6
}

export function checkName(v) {
  return String(v ?? "").trim().length > 0;
}

export function checkDim(dim) {
  const c = dim.中心, up = dim.上, lo = dim.下 ?? dim.上;
  if (![c, up].every((x) => typeof x === "number" && !Number.isNaN(x))) return false;
  if (up < 0 || lo < 0) return false;                           // 公差非负
  return true;
}
