// ノートの id を作る(仕様書「ノートの id」)。
// id = 時刻6文字 + 人の記号。時刻は 2026-01-01 00:00(日本時間)からの秒数を
// Crockford Base32(数字と大文字。I・L・O・U を除く)で表す。名前順 = 作成順になる。
// 人の記号は次の順に探す。
//   1. 個人 vault: _記録/私.yaml の code
//   2. 共有・機密 vault: 設定フォルダ名 .obsidian-<名前> の <名前> を、
//      _tools/同期プログラム/メンバー.csv(機密は _tools/メンバー.csv)で引く
// 同じ人が同じ秒に作るときは、ぶつからないように1秒ずつずらす。

const ABC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const EPOCH_MS = Date.UTC(2025, 11, 31, 15, 0, 0); // 2026-01-01 00:00 JST
const MEMBER_CSV = ["_tools/同期プログラム/メンバー.csv", "_tools/メンバー.csv"];

function encodeTime(sec) {
  let s = "";
  for (let i = 0; i < 6; i++) {
    s = ABC[sec % 32] + s;
    sec = Math.floor(sec / 32);
  }
  return s;
}

async function memberCode(app) {
  const fs = app.vault.adapter;
  if (await fs.exists("_記録/私.yaml")) {
    const m = (await fs.read("_記録/私.yaml")).match(/^code:\s*["']?([0-9A-Za-z]+)/m);
    if (m) return m[1].toUpperCase();
  }
  const dir = app.vault.configDir; // 例: .obsidian-Yu
  const name = dir.startsWith(".obsidian-") ? dir.slice(".obsidian-".length) : "";
  if (name) {
    for (const path of MEMBER_CSV) {
      if (!(await fs.exists(path))) continue;
      for (const line of (await fs.read(path)).split(/\r?\n/).slice(1)) {
        const [n, code] = line.split(",").map((x) => (x || "").trim());
        if (n === name && code) return code.toUpperCase();
      }
    }
  }
  throw new Error(
    "人の記号が見つかりません。個人 vault は _記録/私.yaml に code を、" +
    "共有・機密 vault は設定フォルダを .obsidian-<名前> にし、メンバー.csv に名前と記号を書いてください。"
  );
}

async function make_id(tp) {
  const app = (tp && tp.app) || window.app;
  const code = await memberCode(app);
  const used = new Set(app.vault.getFiles().map((f) => f.basename.split("_")[0].toUpperCase()));
  let sec = Math.floor((Date.now() - EPOCH_MS) / 1000);
  while (used.has(encodeTime(sec) + code)) sec++;
  return encodeTime(sec) + code;
}

module.exports = make_id;
