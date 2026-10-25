// ノートの id を作る(仕様書「ノートの id」)。
// id = 時刻6文字 + 人の記号。時刻は 2026-01-01 00:00(日本時間)からの秒数を
// Crockford Base32(数字と大文字。I・L・O・U を除く)で表す。名前順 = 作成順になる。
// 人の記号は、各自が決めた6桁の数字を36進数(0〜9・A〜Z)にした4文字(229999 → 4XGV。Yu 2026-10-25)。
// 次の順に探す。
//   1. 個人 vault: _仕組み/個人設定.md の number(古い vault は _仕組み/記録/私.yaml の code)
//   2. 共有・機密 vault: 設定フォルダ名 .obsidian-<名前> の <名前> を、
//      _仕組み/tools/同期プログラム/メンバー.csv(機密は _仕組み/tools/メンバー.csv)で引く
//      (2列目が6桁の数字なら36進数に、古い3文字の記号ならそのまま)
// 同じ人が同じ秒に作るときは、ぶつからないように1秒ずつずらす。

const ABC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const EPOCH_MS = Date.UTC(2025, 11, 31, 15, 0, 0); // 2026-01-01 00:00 JST
const MEMBER_CSV = ["_仕組み/tools/同期プログラム/メンバー.csv", "_仕組み/tools/メンバー.csv"];
const MY_SETTINGS = "_仕組み/個人設定.md";
const OLD_MY_YAML = "_仕組み/記録/私.yaml";
const B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";

// 6桁の数字 → 36進数4文字。6桁でなければ null
function codeFromNumber(num) {
  if (!/^\d{6}$/.test(num)) return null;
  let n = parseInt(num, 10);
  let s = "";
  for (let i = 0; i < 4; i++) {
    s = B36[n % 36] + s;
    n = Math.floor(n / 36);
  }
  return s;
}

// メンバー.csv の値: 6桁の数字なら36進数に、古い3文字の記号はそのまま
function codeOf(value) {
  const v = String(value || "").trim();
  return codeFromNumber(v) || v.toUpperCase();
}

// 個人 vault か(個人設定.md か、古い 私.yaml があるか)
async function isPersonal(app) {
  const fs = app.vault.adapter;
  return (await fs.exists(MY_SETTINGS)) || (await fs.exists(OLD_MY_YAML));
}

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
  if (await fs.exists(MY_SETTINGS)) {
    const m = (await fs.read(MY_SETTINGS)).match(/^number:[ \t]*["']?([0-9]*)/m);
    const num = m ? m[1] : "";
    if (num) {
      const code = codeFromNumber(num);
      if (!code) throw new Error(`個人設定.md の number は6桁の数字にしてください(今は ${num})`);
      return code;
    }
  } else if (await fs.exists(OLD_MY_YAML)) {
    const m = (await fs.read(OLD_MY_YAML)).match(/^code:\s*["']?([0-9A-Za-z]+)/m);
    if (m) return m[1].toUpperCase();
  }
  const dir = app.vault.configDir; // 例: .obsidian-Yu
  const name = dir.startsWith(".obsidian-") ? dir.slice(".obsidian-".length) : "";
  if (name) {
    for (const path of MEMBER_CSV) {
      if (!(await fs.exists(path))) continue;
      for (const line of (await fs.read(path)).split(/\r?\n/).slice(1)) {
        const [n, code] = line.split(",").map((x) => (x || "").trim());
        if (n === name && code) return codeOf(code);
      }
    }
  }
  throw new Error(
    "人の記号が見つかりません。個人 vault は _仕組み/個人設定.md に number(6桁の数字)を、" +
    "共有・機密 vault は設定フォルダを .obsidian-<名前> にし、メンバー.csv に名前と記号を書いてください。"
  );
}

async function make_id(tp) {
  const app = (tp && tp.app) || window.app;
  const code = await memberCode(app);
  const used = new Set(app.vault.getFiles().map((f) => f.basename.split("_")[0].toUpperCase()));
  let sec = Math.floor((Date.now() - EPOCH_MS) / 1000);
  while (used.has(encodeTime(sec) + code)) sec++;
  const id = encodeTime(sec) + code;
  await logCreated(app, id, tp);
  return id;
}

// F-28: 個人 vault では、作ったノートを _仕組み/記録/作成履歴.csv に1行残す。
// 同期プログラムは、作って10分以内でテンプレートのままのノートを共有に集めない(取り消しを邪魔しないため)。
// 書けなくてもノートは作る。
const CREATED_LOG = "_仕組み/記録/作成履歴.csv";

async function logCreated(app, id, tp) {
  try {
    const fs = app.vault.adapter;
    if (!(await isPersonal(app))) return;
    const tpl = (tp && tp.config && tp.config.template_file && tp.config.template_file.name) || "";
    const row = `${new Date().toISOString()},${id},${tpl.replace(/[,\r\n]/g, " ")}\r\n`;
    if (await fs.exists(CREATED_LOG)) await fs.append(CREATED_LOG, row);
    else await fs.write(CREATED_LOG, "\ufeff日時,id,テンプレート\r\n" + row);
  } catch (e) {
    console.warn("作成履歴に書けませんでした", e);
  }
}

module.exports = make_id;
module.exports.isPersonal = isPersonal;
module.exports.codeFromNumber = codeFromNumber;
