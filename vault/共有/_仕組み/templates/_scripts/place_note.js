// Ctrl+N(QuickAdd の「新しいノート」)で作ったノートを、プロジェクトのフォルダへ移す(仕様書「フォルダ構成」v0.72)。
// 目的・価値の仮説・設計案・イシュー・タスク・議事録・実験・試作記録・ナレッジのテンプレートの属性欄
// `project: [...]` の行から、置く種類のフォルダを渡して呼ぶ(例 place_note(tp, "03_イシュー"))。返した値がその行に入る。
//
// QuickAdd は 00_inbox/ に作る(一番上に種類のフォルダは置かない。)。
// 置き場所は、その前の visibility の行で選んだ範囲から決める(v0.91。プロジェクトをもう一度聞かない):
//   PIP → 00_PIP/メモ/(ask_visibility.js が移す)、プロジェクト1つ → <プロジェクト>/<種類>/、
//   Internal use only・プロジェクト2つ以上 → 共通/<種類>/。project には選んだプロジェクト(Internal なら 共通)を入れる。
// 範囲を選んでいないとき(共有 vault)はプロジェクトを選んでもらい、Esc なら 00_inbox/ に残す
// (行き先が決まって project か parent を書けば、同期プログラムが移す。要件書 F-57)。
// Ctrl+I・T・H・U(make_note.js)で作ったノートは、make_note.js が置き場所を決めたので何もしない。
// v0.71 までの QuickAdd の設定(一番上の 03_イシュー/ などに作る)で作られたときも同じように移す。
// folder を渡さない(部品のノード)ときは、QuickAdd が 共通/02_ノード/ に作る。プロジェクトが1つなら
// <プロジェクト>/02_ノード/ へ移す(プロジェクト固有のノード。v0.76)。ほかは 共通/02_ノード/ のまま。

const INBOX = "00_inbox";

async function place_note(tp, folder) {
  const app = tp.app;
  const file = tp.config.target_file;
  const M = tp.user.make_note;
  const V = tp.user.ask_visibility;
  if (window[M.PLACING]) return "";   // Ctrl+I・T・H・U が置き場所を決めて作っている(もう聞いた)
  if (file.path.startsWith("_仕組み/")) return "";   // テンプレートそのものを開いたとき
  const chosen = window.__notebaseChosen;
  const list = chosen && chosen.file === file ? chosen.value : null;
  window.__notebaseChosen = null;
  if (list && V.isPip(list)) return "";   // 00_PIP/メモ/ に移してある
  const ps = list ? V.projectsOf(list) : null;
  if (!folder) {
    let project = ps ? (ps.length === 1 ? ps[0] : null)
      : await M.chooseProject(app, tp.obsidian, "どのプロジェクトの部品ですか(Esc で空のまま、共通/02_ノード に置く)");
    if (project === M.COMMON) project = null;
    const dest = project ? `${project}/02_ノード` : "";
    if (dest && file.parent?.path !== dest) {
      await M.ensureFolder(app, dest);
      await tp.file.move(`${dest}/${file.basename}`);
    }
    return project ? JSON.stringify(project) : "";
  }
  const parts = file.path.split("/");
  if (parts.length !== 2) return "";
  const top = parts[0];
  const type = M.TYPE_FOLDERS.includes(top) ? top : folder;
  if (!(top === INBOX || M.TYPE_FOLDERS.includes(top)) || !M.TYPE_FOLDERS.includes(type)) return "";
  let projects;
  if (ps) projects = ps.length ? ps : [M.COMMON];
  else {
    const p = await M.chooseProject(app, tp.obsidian, "どのプロジェクトのノートですか(Esc で 00_inbox に置いておく)");
    projects = p ? [p] : [];
  }
  const dest = !projects.length ? INBOX : projects.length === 1 ? `${projects[0]}/${type}` : `${M.COMMON}/${type}`;
  if (dest !== top) {
    await M.ensureFolder(app, dest);
    await tp.file.move(`${dest}/${file.basename}`);
  }
  // 古い設定で作られた一番上の種類のフォルダが空になったら片付ける
  const old = top !== INBOX && app.vault.getAbstractFileByPath(top);
  if (old && old.children && old.children.length === 0) {
    try { await app.vault.delete(old); } catch (e) { /* 残っても困らない */ }
  }
  return projects.map((p) => JSON.stringify(p)).join(", ");
}

module.exports = place_note;
