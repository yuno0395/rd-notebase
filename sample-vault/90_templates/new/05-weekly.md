<%*
// 週ノート：今週の週ノートを開く（無ければ 01_daily に作る。中身は periodic/weekly が当たる）。この一覧から選んだ時の仮のノートは消す
const tmp = tp.config.target_file;
tp.hooks.on_all_templates_executed(async () => {
  try { await app.vault.delete(tmp); } catch (e) {}
  app.commands.executeCommandById('periodic-notes:open-weekly-note');
});
-%>
