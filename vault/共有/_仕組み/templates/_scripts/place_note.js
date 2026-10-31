// Ctrl+N(QuickAdd の「新しいノート」)で作ったノートを、プロジェクトのフォルダへ移す(仕様書「フォルダ構成」v0.67)。
// 目的・価値の仮説・設計案・イシュー・タスク・議事録・実験・試作記録・ナレッジのテンプレートの属性欄
// `project: [...]` の行から呼ぶ。返した値がその行に入る。
//
// QuickAdd は一番上の種類のフォルダ(03_イシュー/ など)に作るので、そのときだけプロジェクトを選んでもらい、
// <プロジェクト>/03_イシュー/ へ移して、project に選んだものを入れる。
// Ctrl+I・T・H・U(make_note.js)で作ったノートは、もうプロジェクトのフォルダにあるので何もしない
// (project は make_note.js が入れる。親から決まるときは空のまま)。
// 選ばずに閉じたら 00_inbox/ へ移す(行き先のわからないもの)。

async function place_note(tp) {
  const app = tp.app;
  const file = tp.config.target_file;
  const M = tp.user.make_note;
  const parts = file.path.split("/");
  if (parts.length !== 2 || !M.TYPE_FOLDERS.includes(parts[0])) return "";
  const project = await M.chooseProject(app, tp.obsidian, "どのプロジェクトのノートですか(Esc で 00_inbox へ)");
  const dest = project ? `${project}/${parts[0]}` : "00_inbox";
  await M.ensureFolder(app, dest);
  await tp.file.move(`${dest}/${file.basename}`);
  // 空になった一番上の種類のフォルダは片付ける(一番上は毎日開くものだけにする)
  const old = app.vault.getAbstractFileByPath(parts[0]);
  if (old && old.children && old.children.length === 0) {
    try { await app.vault.delete(old); } catch (e) { /* 残っても困らない */ }
  }
  return project ? JSON.stringify(project) : "";
}

module.exports = place_note;
