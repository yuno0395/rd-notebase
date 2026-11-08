// Ctrl+N(QuickAdd の「新しいノート」)で作ったノートを、プロジェクトのフォルダへ移す(仕様書「フォルダ構成」v0.72)。
// 目的・価値の仮説・設計案・イシュー・タスク・議事録・実験・試作記録・ナレッジのテンプレートの属性欄
// `project: [...]` の行から、置く種類のフォルダを渡して呼ぶ(例 place_note(tp, "03_イシュー"))。返した値がその行に入る。
//
// QuickAdd は 00_inbox/ に作る(一番上に種類のフォルダは置かない。)。そのときだけプロジェクトを選んでもらい、
// <プロジェクト>/03_イシュー/ へ移して、project に選んだものを入れる。
// 選ばずに閉じたら 00_inbox/ に残す(行き先が決まって project か parent を書けば、同期プログラムが移す。要件書 F-57)。
// Ctrl+I・T・H・U(make_note.js)で作ったノートは、もうプロジェクトのフォルダにあるので何もしない
// (project は make_note.js が入れる。親から決まるときは空のまま)。
// v0.71 までの QuickAdd の設定(一番上の 03_イシュー/ などに作る)で作られたときも同じように移す。
// folder を渡さない(部品のノード)ときは、QuickAdd が 共通/02_ノード/ に作る。どのプロジェクトのものか選んでもらい、
// 選んだら <プロジェクト>/02_ノード/ へ移す(プロジェクト固有のノード。v0.76)。
// 共通 を選ぶか Esc なら 共通/02_ノード/ のまま。あとで project を書き直せば同期プログラムが移す(要件書 F-57)。

const INBOX = "00_inbox";

async function place_note(tp, folder) {
  const app = tp.app;
  const file = tp.config.target_file;
  const M = tp.user.make_note;
  if (!folder) {
    if (file.path.startsWith("_仕組み/")) return "";   // テンプレートそのものを開いたとき
    const project = await M.chooseProject(app, tp.obsidian, "どのプロジェクトの部品ですか(Esc で空のまま、共通/02_ノード に置く)");
    const dest = project && project !== M.COMMON ? `${project}/02_ノード` : "";
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
  const project = await M.chooseProject(app, tp.obsidian, "どのプロジェクトのノートですか(Esc で 00_inbox に置いておく)");
  const dest = project ? `${project}/${type}` : INBOX;
  if (dest !== top) {
    await M.ensureFolder(app, dest);
    await tp.file.move(`${dest}/${file.basename}`);
  }
  // 古い設定で作られた一番上の種類のフォルダが空になったら片付ける
  const old = top !== INBOX && app.vault.getAbstractFileByPath(top);
  if (old && old.children && old.children.length === 0) {
    try { await app.vault.delete(old); } catch (e) { /* 残っても困らない */ }
  }
  return project ? JSON.stringify(project) : "";
}

module.exports = place_note;
