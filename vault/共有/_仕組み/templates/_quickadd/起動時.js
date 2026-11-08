// Obsidian を開いたときに1回動く(個人 vault だけ)。QuickAdd のマクロ「起動時」(Run on startup)から呼ぶ。
//   1. 今日のデイリーノートがなければ作る。Day Planner がデイリーの置き場所を読めるようにする(today_daily.js)
//   2. 他の人のノートを開いたら読む画面にする(others_note.js の watch)
// Templater の「起動時テンプレート」は使わない。Templater 2.x から PC ごとの設定(最初はオフ)になり、
// 配る設定ファイルではオンにできないため。

const SCRIPTS = "_仕組み/templates/_scripts";

async function load(app, name) {
  const src = await app.vault.adapter.read(`${SCRIPTS}/${name}.js`);
  const mod = { exports: {} };
  new Function("module", "exports", src)(mod, mod.exports);
  return mod.exports;
}

module.exports = async function (params) {
  const { app, obsidian } = params;
  if (!(await app.vault.adapter.exists("_仕組み/個人設定.md"))) return; // 個人 vault だけ
  const templater = app.plugins.plugins["templater-obsidian"]?.templater;
  // today_daily.js・others_note.js が使う Templater の tp と同じ形
  const tp = {
    app,
    obsidian,
    user: { make_note: await load(app, "make_note") },
    file: {
      create_new: (template, filename, open, folder) =>
        templater.create_new_note_from_template(template, folder, filename, open),
    },
  };
  for (const [name, args] of [["today_daily", []], ["others_note", ["watch"]]]) {
    try {
      await (await load(app, name))(tp, ...args);
    } catch (e) {
      console.error(`起動時: ${name}`, e);
    }
  }
};
