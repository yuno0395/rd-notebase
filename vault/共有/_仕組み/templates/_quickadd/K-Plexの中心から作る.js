// K-Plex の中心のノートから、イシュー・タスク・仮説を作る(仕様書「全体像の把握(K-Plex)」)。
// QuickAdd のマクロ「K-Plex の中心から作る」(Ctrl+Shift+N)から呼ぶ。
//
//   1. 開いている K-Plex の中心のノートを読む(K-Plex がなければ、開いているノート)。
//   2. 作る種類を選ぶ(中心の種類に合うものを上に出す)。
//   3. 名前を打つ。Ctrl+I / T / H と同じ決まり(make_note.js)で作る。中心の本文には触らない。
// K-Plex 自身の作成(Ctrl+矢印)や、中心の編集欄は使わない(つながりを書く向きが決まりと逆になるため)。

const MAKE_NOTE = "_仕組み/templates/_scripts/make_note.js";
const KPLEX_TYPES = ["k-plex-react-view", "k-plex-sidepanel-view"];
const ID_PREFIX = /^[0-9A-Z]{6}[0-9A-Z]+_/i;

// 中心の種類ごとに、上に出す種類
const ORDER = {
  目的: ["仮説", "イシュー", "タスク"],
  仮説: ["イシュー", "仮説", "タスク"],
  イシュー: ["タスク", "イシュー", "仮説"],
  タスク: ["イシュー", "タスク", "仮説"],
  設計記録: ["イシュー", "タスク", "仮説"],
  "実験・試作記録": ["イシュー", "タスク", "仮説"],
};
const LABEL = {
  イシュー: "イシュー(心配なこと)",
  タスク: "タスク(リスクを下げる仕事)",
  仮説: "仮説(価値の仮説。仮説の下なら下の仮説)",
};

function kplexCenter(app) {
  const leaves = KPLEX_TYPES.flatMap((t) => app.workspace.getLeavesOfType(t));
  const active = app.workspace.getMostRecentLeaf?.() || app.workspace.activeLeaf;
  const ordered = leaves.sort((a, b) => (b === active) - (a === active));
  for (const leaf of ordered) {
    const session = leaf.view?.documentSession;
    const path = session?.centerPath || leaf.view?.getState?.()?.plexSession?.centerPath;
    const file = path && app.vault.getAbstractFileByPath(path);
    if (file && file.extension === "md") return file;
  }
  return null;
}

async function loadMakeNote(app) {
  const src = await app.vault.adapter.read(MAKE_NOTE);
  const mod = { exports: {} };
  new Function("module", "exports", src)(mod, mod.exports);
  return mod.exports;
}

module.exports = async function (params) {
  const { app, quickAddApi, obsidian } = params;
  const center = kplexCenter(app) || app.workspace.getActiveFile();
  if (!center) {
    new obsidian.Notice("K-Plex でノートを中心に置いてから使ってください");
    return;
  }
  const templater = app.plugins.plugins["templater-obsidian"]?.templater;
  if (!templater) {
    new obsidian.Notice("Templater が有効になっていません");
    return;
  }
  const makeNote = await loadMakeNote(app);
  const shown = center.basename.replace(ID_PREFIX, "");
  const order = ORDER[makeNote.typeOf(app, center)] || ["イシュー", "タスク", "仮説"];
  const kind = await quickAddApi.suggester(order.map((k) => `${LABEL[k]} ← ${shown}`), order);
  if (!kind) return;
  const name = await quickAddApi.inputPrompt(`${kind}の名前(「${shown}」から作る)`);
  if (!name) return;
  // make_note.js が使う Templater の tp と同じ形
  const tp = {
    app,
    obsidian,
    file: {
      create_new: (template, filename, open, folder) =>
        templater.create_new_note_from_template(template, folder, filename, open),
    },
  };
  await makeNote.fromNote(tp, kind, center, name);
};
