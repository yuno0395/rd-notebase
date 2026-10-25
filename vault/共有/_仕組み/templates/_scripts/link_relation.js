// 関係としてつなぐ(friend)・反論としてつなぐ(challenger)。仕様書「全体像の把握(K-Plex)」。
// 右クリックのメニューから使う。
//
//   - [[ ]] の上で使う: そのリンク先を、今のノートの属性欄の friend / challenger に足す。
//   - 文字を選んで使う: 同じ名前か別名のノートがあれば、そのノートを足す。
// 本文のリンクはそのまま残す。属性欄の値は "[[id_名前|名前]]" の形で、引用符をつけて並べる。
// すでに入っているノートは二度足さない。まだファイルのないリンクは足さない(先に Ctrl+K などで作る)。

const T = "_仕組み/templates/";
const ID_PREFIX = /^[0-9A-Z]{6}[0-9A-Z]+_/i;
const LABEL = { friend: "関係(friend)", challenger: "反論(challenger)" };

function nameOf(file) {
  return file.basename.replace(ID_PREFIX, "");
}

function linkOf(file, shown) {
  return `[[${file.basename}|${shown ?? nameOf(file)}]]`;
}

function asList(v) {
  if (v === undefined || v === null || v === "") return [];
  return (Array.isArray(v) ? v : [v]).map((x) => String(x).trim()).filter((x) => x);
}

function resolve(app, target, from) {
  return app.metadataCache.getFirstLinkpathDest(target.split("|")[0].trim(), from);
}

function flow(values) {
  return "[" + values.map((v) => JSON.stringify(v)).join(", ") + "]";
}

// 属性欄の key の行を value にする。行末の説明(# …)は残す。続く `  - …` の行も置き換える。なければ最後に足す。
function setKey(text, key, value) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return `---\n${key}: ${value}\n---\n` + text;
  const lines = m[1].split(/\r?\n/);
  const at = lines.findIndex((l) => new RegExp(`^${key}\\s*:`).test(l));
  if (at >= 0) {
    const comment = (lines[at].match(/\s+#\s.*$/) || [""])[0];
    let end = at + 1;
    while (end < lines.length && /^(\s+\S|-\s)/.test(lines[end])) end++;
    const head = `${key}: ${value}`;
    lines.splice(at, end - at, comment ? head.padEnd(Math.max(head.length + 1, 22)) + comment.trimStart() : head);
  } else {
    lines.push(`${key}: ${value}`);
  }
  return text.replace(m[1], () => lines.join("\n"));
}

// カーソルの下の [[ ]] か、選んだ文字に当たるノート
function targetOf(app, ed, note) {
  const word = ed.getSelection().trim();
  const cur = ed.getCursor("from");
  if (!word) {
    const line = ed.getLine(cur.line);
    for (const m of line.matchAll(/\[\[([^\[\]\n]+?)\]\]/g)) {
      if (cur.ch < m.index || cur.ch > m.index + m[0].length) continue;
      const file = resolve(app, m[1], note.path);
      return file ? { file } : { error: "このリンクにはまだノートがありません。先に Ctrl+K などで作ってください" };
    }
    return { error: "[[ ]] の上で使うか、つなぐノートの名前を選んでください" };
  }
  const key = word.replace(/^\[\[|\]\]$/g, "").split("|")[0].trim();
  const direct = resolve(app, key, note.path);
  if (direct) return { file: direct };
  const low = key.toLowerCase();
  const same = app.vault.getMarkdownFiles().filter((f) => {
    if (f.path.startsWith(T)) return false;
    const fm = app.metadataCache.getFileCache(f)?.frontmatter;
    return nameOf(f).toLowerCase() === low || asList(fm?.aliases).some((a) => a.toLowerCase() === low);
  });
  if (same.length === 1) return { file: same[0] };
  if (same.length > 1) return { error: `「${key}」という名前のノートが ${same.length} つあります。[[ ]] の上で使ってください` };
  return { error: `「${key}」というノートがありません` };
}

async function link_relation(tp, role) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  if (!LABEL[role]) throw new Error(`知らないつなぎ方です: ${role}`);
  const view = app.workspace.activeEditor;
  if (!view?.editor || !view.file) {
    new Notice("ノートを開いてから使ってください");
    return;
  }
  const ed = view.editor;
  const note = view.file;
  // Templater はこのあと選んでいる文字を空の文字で置き換えるので、先に読んで選択を外しておく
  const found = targetOf(app, ed, note);
  ed.setCursor(ed.getCursor("to"));
  if (found.error) {
    new Notice(found.error, 6000);
    return;
  }
  const file = found.file;
  if (file.path === note.path) {
    new Notice("自分自身にはつなげません");
    return;
  }
  const fm = app.metadataCache.getFileCache(note)?.frontmatter || {};
  const values = asList(fm[role]);
  const already = values.some((v) => {
    const t = (v.match(/\[\[([^\]]+)\]\]/) || [])[1];
    return t && resolve(app, t, note.path)?.path === file.path;
  });
  if (already) {
    new Notice(`「${nameOf(file)}」はもう${LABEL[role]}に入っています`);
    return;
  }
  // 入っていた値はそのまま残し、後ろに足す
  const next = values.concat([linkOf(file)]);
  await app.vault.process(note, (text) => setKey(text, role, flow(next)));
  new Notice(`「${nameOf(file)}」を${LABEL[role]}につなぎました`);
}

module.exports = link_relation;
