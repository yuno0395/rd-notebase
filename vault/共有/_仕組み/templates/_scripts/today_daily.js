// Obsidian を開いたとき、今日のデイリーノートがなければテンプレートで作る(開かない。)。
// 個人 vault だけで働く。QuickAdd のマクロ「起動時」(_quickadd/起動時.js)から呼ぶ。
// 保存先・日付の形・テンプレートは Periodic Notes の設定を読む(読めなければ 00_PIP/デイリー・YYYY-MM-DD・デイリー)。
// Obsidian を開いたまま日付が変わったときは、Day Planner のタイムラインに予定を足すか、
// Periodic Notes の「今日のデイリーノートを開く」で作られる。
// Day Planner はデイリーの置き場所を Periodic Notes の設定(settings.daily)から読み、読めないとコアの
// 「デイリーノート」の設定で決める。いま配っている Periodic Notes は設定のしまい方が違うので読めず、
// コアはオフで設定が空なので、vault の一番上に作ってしまう。そこで起動時に、
// 画面の中だけで両方に同じ保存先・日付の形・テンプレートを入れておく。設定ファイルとコアのオン・オフは変えない。

const MY_SETTINGS = "_仕組み/個人設定.md";
const DEFAULT = { folder: "00_PIP/デイリー", format: "YYYY-MM-DD", template: "_仕組み/templates/デイリー" };

// Periodic Notes の設定ファイル。古い形(daily)と新しい形(calendarSets の day)の両方を読む
async function settingsOf(app) {
  try {
    const data = JSON.parse(await app.vault.adapter.read(`${app.vault.configDir}/plugins/periodic-notes/data.json`));
    const day = (data.calendarSets || []).map((c) => c.day).find((d) => d && d.folder);
    const d = data.daily && data.daily.folder ? data.daily : day ? { ...day, template: day.templatePath } : null;
    if (d) return { folder: d.folder, format: d.format || DEFAULT.format, template: d.template || DEFAULT.template };
  } catch (e) {}
  return DEFAULT;
}

// Day Planner が読む2か所(Periodic Notes の settings.daily とコアの設定)に、画面の中だけで入れる
function tellDayPlanner(app, conf) {
  try {
    const pn = app.plugins?.getPlugin?.("periodic-notes");
    if (pn && pn.settings && !(pn.settings.daily && pn.settings.daily.enabled)) {
      pn.settings.daily = { ...(pn.settings.daily || {}), enabled: true, folder: conf.folder, format: conf.format, template: conf.template };
    }
  } catch (e) {}
  try {
    const core = app.internalPlugins?.getPluginById?.("daily-notes")?.instance;
    if (core) core.options = { ...(core.options || {}), folder: conf.folder, format: conf.format, template: conf.template };
  } catch (e) {}
}

async function today_daily(tp) {
  const app = tp.app;
  const fs = app.vault.adapter;
  if (!(await fs.exists(MY_SETTINGS))) return; // 個人 vault だけ
  const conf = await settingsOf(app);
  tellDayPlanner(app, conf);
  const name = window.moment().format(conf.format || DEFAULT.format);
  const path = `${conf.folder}/${name}.md`;
  if (app.vault.getAbstractFileByPath(path)) return;
  const tplPath = conf.template.endsWith(".md") ? conf.template : `${conf.template}.md`;
  const tpl = app.vault.getAbstractFileByPath(tplPath);
  if (!tpl) return;
  await tp.user.make_note.ensureFolder(app, conf.folder);
  await tp.file.create_new(tpl, name, false, app.vault.getAbstractFileByPath(conf.folder));
}

Object.assign(today_daily, { settingsOf, tellDayPlanner });
module.exports = today_daily;
