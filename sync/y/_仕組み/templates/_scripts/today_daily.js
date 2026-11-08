// Obsidian を開いたとき、今日のデイリーノートがなければテンプレートで作る(開かない。)。
// 個人 vault だけで働く(Templater の起動時テンプレート「起動時(今日の日誌を作る)」から呼ぶ)。
// 保存先・日付の形・テンプレートは Periodic Notes の設定を読む(読めなければ 00_日誌/デイリー・YYYY-MM-DD・デイリー)。
// Obsidian を開いたまま日付が変わったときは、Day Planner のタイムラインに予定を足すか、
// Periodic Notes の「今日のデイリーノートを開く」で作られる。
// Day Planner は Periodic Notes の設定を読めないと、コアの「デイリーノート」の設定で場所を決め、
// コアがオフだと vault の一番上に作ってしまう。そこで起動時に、コアの設定(画面の中だけ)にも
// 同じ保存先・日付の形・テンプレートを入れておく。コアのプラグインはオフのまま。

const MY_SETTINGS = "_仕組み/個人設定.md";
const DEFAULT = { folder: "00_日誌/デイリー", format: "YYYY-MM-DD", template: "_仕組み/templates/デイリー" };

async function today_daily(tp) {
  const app = tp.app;
  const fs = app.vault.adapter;
  if (!(await fs.exists(MY_SETTINGS))) return; // 個人 vault だけ
  let conf = DEFAULT;
  try {
    const d = JSON.parse(await fs.read(`${app.vault.configDir}/plugins/periodic-notes/data.json`)).daily;
    if (d && d.folder) conf = { ...DEFAULT, ...d };
  } catch (e) {}
  try {
    const core = app.internalPlugins?.getPluginById?.("daily-notes")?.instance;
    if (core) core.options = { ...(core.options || {}), folder: conf.folder, format: conf.format, template: conf.template };
  } catch (e) {}
  const name = window.moment().format(conf.format || DEFAULT.format);
  const path = `${conf.folder}/${name}.md`;
  if (app.vault.getAbstractFileByPath(path)) return;
  const tplPath = conf.template.endsWith(".md") ? conf.template : `${conf.template}.md`;
  const tpl = app.vault.getAbstractFileByPath(tplPath);
  if (!tpl) return;
  let folder = "";
  for (const part of conf.folder.split("/")) {
    folder = folder ? `${folder}/${part}` : part;
    if (!app.vault.getAbstractFileByPath(folder)) await app.vault.createFolder(folder);
  }
  await tp.file.create_new(tpl, name, false, app.vault.getAbstractFileByPath(conf.folder));
}

module.exports = today_daily;
