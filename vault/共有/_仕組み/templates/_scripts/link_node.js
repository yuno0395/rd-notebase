// Ctrl+K: 語を [[ ]] でつなぎ、ノードがなければその場で作る(仕様書「ショートカットキー」)。
//
//   - 文字を選んで押す: 同じ名前か別名(aliases)のノードが1つならつなぐ。2つ以上なら選ぶ。
//     なければノードのテンプレートで作ってつなぐ。
//   - [[ ]] の中で押す: まだファイルのないリンクなら、上と同じようにつなぐか作る。
//   - 何も選ばずに押す: 検索窓を出す。名前と別名で探し、候補にない名前ならそのまま作る。
// 表示名は選んだ文字(別名で選んだときはその別名)のままにして、文章の見た目を変えない。
// 新しいノートは開かない(書き続けられるように)。

const NODE_TEMPLATE = "_仕組み/templates/ノード.md";
const BAD_CHARS = /[\\/:*?"<>|#^\[\]\r\n]/;

// 共通の関数(nameOf・asList・placeLink)は make_note.js のものを使う。link_node を呼ぶときに入れる
let M;

// vault の中のノード(type: ノード)を、名前と別名で引ける形にする。配られた他の人のノードも含む(同じ 共通/02_ノード/ にある)。
function nodeIndex(app) {
  const out = [];
  for (const file of app.vault.getMarkdownFiles()) {
    if (file.path.startsWith("_仕組み/templates/")) continue;
    const fm = app.metadataCache.getFileCache(file)?.frontmatter;
    if (!fm || String(fm.type || "").trim() !== "ノード") continue;
    out.push({ file, name: M.nameOf(file), aliases: M.asList(fm.aliases) });
  }
  return out;
}

function exactMatches(index, word) {
  const key = word.trim().toLowerCase();
  return index.filter((n) => n.name.toLowerCase() === key || n.aliases.some((a) => a.toLowerCase() === key));
}

// 検索窓の候補: 名前1つ・別名1つを1行にする。
function rows(index) {
  const out = [];
  for (const n of index) {
    const others = n.aliases.filter((a) => a !== n.name);
    out.push({ node: n, shown: n.name, label: others.length ? `${n.name}(別名: ${others.join("、")})` : n.name });
    for (const a of others) out.push({ node: n, shown: a, label: `${a} → ${n.name}` });
  }
  return out;
}

function pick(tp, items, initial) {
  const { SuggestModal } = tp.obsidian;
  return new Promise((resolve) => {
    let chosen = null;
    class NodeSuggest extends SuggestModal {
      getSuggestions(query) {
        const q = query.trim().toLowerCase();
        const hits = items.filter((r) => r.label.toLowerCase().includes(q));
        const exact = items.some((r) => r.shown.toLowerCase() === q);
        if (query.trim() && !exact) hits.push({ create: query.trim(), label: `新しいノードを作る: ${query.trim()}` });
        return hits;
      }
      renderSuggestion(r, el) {
        el.setText(r.label);
      }
      onChooseSuggestion(r) {
        chosen = r;
      }
      onClose() {
        // onChooseSuggestion は onClose のあとに呼ばれることがあるので、少し待つ
        setTimeout(() => resolve(chosen), 0);
      }
    }
    const modal = new NodeSuggest(tp.app);
    modal.setPlaceholder("ノードの名前か別名(なければ新しく作る)");
    modal.open();
    if (initial) {
      modal.inputEl.value = initial;
      modal.inputEl.dispatchEvent(new Event("input"));
    }
  });
}

async function createNode(tp, name) {
  const app = tp.app;
  // 共有 vault で仮運用しているときは 共通/02_ノード、個人 vault では 02_ノード
  const personal = await app.vault.adapter.exists("_仕組み/個人設定.md");
  const folder = !personal && app.vault.getAbstractFileByPath("共通/02_ノード") ? "共通/02_ノード" : "02_ノード";
  if (!app.vault.getAbstractFileByPath(folder)) await app.vault.createFolder(folder);
  const template = app.vault.getAbstractFileByPath(NODE_TEMPLATE);
  if (!template) throw new Error(`${NODE_TEMPLATE} がありません`);
  // テンプレートの中で id がつき、ファイル名が id_名前 に変わる
  return await tp.file.create_new(template, name, false, app.vault.getAbstractFileByPath(folder));
}

async function link_node(tp) {
  const app = tp.app;
  M = tp.user.make_note;
  const { Notice } = tp.obsidian;
  const view = app.workspace.activeEditor;
  if (!view?.editor || !view.file) {
    new Notice("ノートを開いてから Ctrl+K を押してください");
    return;
  }
  const ed = view.editor;
  const note = view.file;
  let from = ed.getCursor("from");
  let to = ed.getCursor("to");
  let word = ed.getSelection();
  let linkTarget = null; // [[ ]] の中で押したときの、リンクの行き先
  // Templater はこのあと選んでいる文字を空の文字で置き換えるので、先に選択を外しておく
  ed.setCursor(to);

  if (!word) {
    // [[ ]] の中にカーソルがあれば、そのリンクを対象にする
    const line = ed.getLine(from.line);
    for (const m of line.matchAll(/\[\[([^\[\]\n]+?)\]\]/g)) {
      const start = m.index, end = m.index + m[0].length;
      if (from.ch < start || from.ch > end) continue;
      const [target, alias] = m[1].split("|");
      if (app.metadataCache.getFirstLinkpathDest(target.trim(), note.path)) {
        new Notice("このリンクはもうノードにつながっています");
        return;
      }
      word = alias ? alias.trim() : target.trim();
      from = { line: from.line, ch: start };
      to = { line: from.line, ch: end };
      linkTarget = target.trim();
      break;
    }
  }

  const index = nodeIndex(app);
  let node = null;
  let shown = word ? word.trim() : "";
  let newName = null;

  if (word) {
    if (BAD_CHARS.test(word.trim()) || !word.trim()) {
      new Notice("ファイル名に使えない文字(/ : * ? \" < > | # ^ [ ] や改行)が入っています");
      return;
    }
    const lookup = linkTarget ?? word;
    const found = exactMatches(index, lookup);
    if (found.length === 1) {
      node = found[0];
    } else if (found.length > 1) {
      const r = await pick(tp, rows(found), "");
      if (!r) return;
      if (r.create) newName = r.create;
      else node = r.node;
    } else {
      newName = (linkTarget ?? word).trim();
    }
  } else {
    const r = await pick(tp, rows(index), "");
    if (!r) return;
    if (r.create) {
      if (BAD_CHARS.test(r.create)) {
        new Notice("ファイル名に使えない文字が入っています");
        return;
      }
      newName = r.create;
      shown = r.create;
    } else {
      node = r.node;
      shown = r.shown;
    }
  }

  const orig = ed.getRange(from, to);
  let file;
  if (newName) {
    file = await createNode(tp, newName);
    if (!file) return;
    new Notice(`ノード「${newName}」を作りました`);
  } else {
    file = node.file;
  }
  M.placeLink(app, ed, note, file, `[[${file.basename}|${shown}]]`, from, to, orig);
}

module.exports = link_node;
