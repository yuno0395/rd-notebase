// Ctrl+S: ふつうに保存して、まだファイルのない [[ ]] があれば名前を右上に出す(仕様書「ショートカットキー」)。
//
// ファイルは作らない。[[ ]] はノードとは限らず、イシュー・タスク・メモのこともあるので、
// 作るかどうかと種類は人が決める([[ ]] の中で Ctrl+K / I / T / H)。
// Linter の「保存のときに整える」は保存のコマンドについているので、これまでどおり動く。

const MAX_NAMES = 5;

// 本文から [[ ]] を拾う。コードの欄(``` で囲んだところ と `…`)の中は数えない。
function linksIn(text) {
  const out = [];
  let inFence = false;
  for (const line of text.split("\n")) {
    if (/^\s*(```|~~~)/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    const plain = line.replace(/`[^`]*`/g, "");
    for (const m of plain.matchAll(/\[\[([^\[\]\n]+?)\]\]/g)) {
      const [target, alias] = m[1].split("|");
      const path = target.split("#")[0].trim();
      if (!path) continue; // 同じノートの見出しへのリンク
      out.push({ path, shown: (alias || path).trim() });
    }
  }
  return out;
}

async function save_check(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const view = app.workspace.activeEditor;
  const ed = view?.editor;
  const file = view?.file;

  // Templater はこのあと選んでいる文字を空の文字で置き換えるので、選択をいったん外し、あとで戻す
  let restore = null;
  if (ed && ed.somethingSelected()) {
    const anchor = ed.getCursor("anchor");
    const head = ed.getCursor("head");
    ed.setCursor(head);
    restore = () => ed.setSelection(anchor, head);
  }

  app.commands.executeCommandById("editor:save-file");
  if (restore) setTimeout(restore, 0);
  if (!ed || !file) return;

  const missing = [];
  const seen = new Set();
  for (const link of linksIn(ed.getValue())) {
    const key = link.path.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    if (!app.metadataCache.getFirstLinkpathDest(link.path, file.path)) missing.push(link.shown);
  }
  if (!missing.length) return;

  const names = missing.slice(0, MAX_NAMES).join("、");
  const more = missing.length > MAX_NAMES ? ` ほか ${missing.length - MAX_NAMES} 件` : "";
  new Notice(
    `ファイルのないリンク: ${names}${more}\n作るときは [[ ]] の中で Ctrl+K(ノード)などを押します`,
    8000
  );
}

module.exports = save_check;
