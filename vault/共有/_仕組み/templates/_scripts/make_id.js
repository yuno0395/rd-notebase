// ノートの id を作る(仕様書「ノートの id」)。
// id = 時刻6文字 + 人の記号。時刻は 2026-01-01 00:00(日本時間)からの秒数を
// Crockford Base32(数字と大文字。I・L・O・U を除く)で表す。名前順 = 作成順になる。
// 人の記号は、各自が決めた6桁の数字を36進数(0〜9・A〜Z)にした4文字(229999 → 4XGV。Yu 2026-10-25)。
// 次の順に探す。
//   1. 個人 vault: _仕組み/個人設定.md の number
//   2. 共有・機密 vault: 設定フォルダ名 .obsidian-<番号>_<PCの記号>(例 .obsidian-229999_aa11234567)の
//      先頭の6桁の番号を36進数に(名前ではなく番号で見分ける。1人が複数の PC を使うので、
//      PC ごとに設定フォルダを分ける。Yu 2026-10-26)。_<PCの記号> のない .obsidian-229999 も読む
// 同じ人が同じ秒に作るときは、ぶつからないように1秒ずつずらす。

const ABC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
const EPOCH_MS = Date.UTC(2025, 11, 31, 15, 0, 0); // 2026-01-01 00:00 JST
const MY_SETTINGS = "_仕組み/個人設定.md";
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

// 個人 vault か(個人設定.md があるか)
async function isPersonal(app) {
  return await app.vault.adapter.exists(MY_SETTINGS);
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
  }
  const dir = app.vault.configDir; // 例: .obsidian-229999_aa11234567
  const name = dir.startsWith(".obsidian-") ? dir.slice(".obsidian-".length) : "";
  const num = name.match(/^(\d+)(?:_|$)/);
  if (num) {
    const code = codeFromNumber(num[1]);
    if (!code) throw new Error(`設定フォルダ ${dir} の番号は6桁の数字にしてください(例: .obsidian-229999_aa11234567)`);
    return code;
  }
  // 何が足りないかを言う(共有 vault には個人設定.md がないので、設定フォルダの名前で人を見分ける)
  throw new Error(
    `人の記号が見つかりません。いまの設定フォルダは ${dir} です。` +
    "共有・機密 vault は、設定 → ファイルとリンク →「設定フォルダを上書き」を .obsidian-<自分の6桁の番号>_<PCの記号>(例: .obsidian-229999_aa11234567)にして開き直してください。" +
    "個人 vault なら _仕組み/個人設定.md に number(6桁の数字)を書いてください。"
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
