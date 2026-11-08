// 自分を「番号_名前」(例 229999_山田)で返す。テンプレートの属性 author に入れる。
//   author: [<%* tR += await tp.user.me(tp) %>]
// 個人 vault は _仕組み/個人設定.md の number と name から。
// 共有・機密 vault は設定フォルダ名 .obsidian-<番号>_<PCの記号> の番号と、メンバー.csv(名前,番号)の名前から。
// わからなければ空(author は同期プログラムが書く)。YAML で数字だけにならないよう、引用符つきで返す。

const MEMBER_CSV = ["_仕組み/tools/同期プログラム/メンバー.csv", "_仕組み/tools/メンバー.csv"];

async function me(tp) {
  const app = tp.app;
  let who = "";
  try {
    who = await tp.user.others_note.myName(app);
  } catch (e) {
    return "";
  }
  if (/^\d{6}$/.test(who)) who = (await nameFromCsv(app, who)) || who;
  return who ? JSON.stringify(who) : "";
}

async function nameFromCsv(app, number) {
  const fs = app.vault.adapter;
  for (const path of MEMBER_CSV) {
    if (!(await fs.exists(path))) continue;
    for (const line of (await fs.read(path)).split(/\r?\n/).slice(1)) {
      const [name, num] = line.split(",").map((x) => (x || "").trim());
      if (name && num === number) return `${number}_${name}`;
    }
  }
  return "";
}

module.exports = me;
