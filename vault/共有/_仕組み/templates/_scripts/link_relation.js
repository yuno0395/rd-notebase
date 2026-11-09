// 関係としてつなぐ(friend)・反論としてつなぐ(challenger)。仕様書「全体像の把握(K-Plex)」。
// 右クリックのメニューから使う。
//
//   - [[ ]] の上で使う: そのリンク先を、今のノートの属性欄の friend / challenger に足す。
//     設計案で価値の仮説を「関係としてつなぐ」と、friend ではなく 価値仮説 に足す(K-Plex の左。)。
//   - 文字を選んで使う: 同じ名前か別名のノートがあれば、そのノートを足す。
// 本文のリンクはそのまま残す。属性欄の値は "[[id_名前|名前]]" の形で、引用符をつけて並べる。
// すでに入っているノートは二度足さない。まだファイルのないリンクは足さない(先に Ctrl+K などで作る)。
//
// このノートをリンク先の親にする(link_relation.asParent。): 向きが逆で、今のノートを
// リンク先のノートの parent に足す。価値の仮説の本文に書いた具体指標のノード [[ ]] の上で使うと、
// ノードの parent に仮説が入る。書き換えるのはリンク先なので、自分のノートのときだけ(他の人のノートは書き換えない)。

const T = "_仕組み/templates/";
const LABEL = { friend: "関係(friend)", challenger: "反論(challenger)", 価値仮説: "価値仮説" };

// 共通の関数(nameOf・resolve・setKey など)は make_note.js のものを使う。link_relation を呼ぶときに入れる
let M;

// カーソルの下の [[ ]] か、選んだ文字に当たるノート
function targetOf(app, ed, note) {
  const word = ed.getSelection().trim();
  const cur = ed.getCursor("from");
  if (!word) {
    const line = ed.getLine(cur.line);
    for (const m of line.matchAll(/\[\[([^\[\]\n]+?)\]\]/g)) {
      if (cur.ch < m.index || cur.ch > m.index + m[0].length) continue;
      const file = M.resolve(app, m[1], note.path);
      return file ? { file } : { error: "このリンクにはまだノートがありません。先に Ctrl+K などで作ってください" };
    }
    return { error: "[[ ]] の上で使うか、つなぐノートの名前を選んでください" };
  }
  const key = word.replace(/^\[\[|\]\]$/g, "").split("|")[0].trim();
  const direct = M.resolve(app, key, note.path);
  if (direct) return { file: direct };
  const low = key.toLowerCase();
  const same = app.vault.getMarkdownFiles().filter((f) => {
    if (f.path.startsWith(T)) return false;
    const fm = app.metadataCache.getFileCache(f)?.frontmatter;
    return M.nameOf(f).toLowerCase() === low || M.asList(fm?.aliases).some((a) => a.toLowerCase() === low);
  });
  if (same.length === 1) return { file: same[0] };
  if (same.length > 1) return { error: `「${key}」という名前のノートが ${same.length} つあります。[[ ]] の上で使ってください` };
  return { error: `「${key}」というノートがありません` };
}

// 開いているノートと、リンク先のノート。使えないときは知らせて null
function notes(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  M = tp.user.make_note;
  const view = app.workspace.activeEditor;
  if (!view?.editor || !view.file) {
    new Notice("ノートを開いてから使ってください");
    return null;
  }
  if (M.inProperties(Notice, view)) return null;
  const ed = view.editor;
  const note = view.file;
  // Templater はこのあと選んでいる文字を空の文字で置き換えるので、先に読んで選択を外しておく
  const found = targetOf(app, ed, note);
  ed.setCursor(ed.getCursor("to"));
  if (found.error) {
    new Notice(found.error, 6000);
    return null;
  }
  if (found.file.path === note.path) {
    new Notice("自分自身にはつなげません");
    return null;
  }
  return { note, file: found.file };
}

// owner の属性 key に target を足す。入っていた値はそのまま残し、後ろに足す。もう入っていれば足さない
async function add(tp, owner, key, target, label) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const values = M.asList(app.metadataCache.getFileCache(owner)?.frontmatter?.[key]);
  const already = values.some((v) => {
    const t = (v.match(/\[\[([^\]]+)\]\]/) || [])[1];
    return t && M.resolve(app, t, owner.path)?.path === target.path;
  });
  if (already) {
    new Notice(`「${M.nameOf(target)}」はもう${label}に入っています`);
    return;
  }
  await app.vault.process(owner, (text) => M.setKey(text, key, M.flow(values.concat([M.linkOf(target)]))));
  new Notice(`「${M.nameOf(target)}」を${label}につなぎました`);
}

async function link_relation(tp, role) {
  if (!LABEL[role]) throw new Error(`知らないつなぎ方です: ${role}`);
  const got = notes(tp);
  if (!got) return;
  const { note, file } = got;
  if (role === "friend" && M.typeOf(tp.app, note) === "設計案" && M.typeOf(tp.app, file) === "仮説") role = "価値仮説";
  await add(tp, note, role, file, LABEL[role]);
}

// このノートをリンク先の親にする: 今のノートを、リンク先のノートの parent に足す
async function asParent(tp) {
  const got = notes(tp);
  if (!got) return;
  const { note, file } = got;
  const O = tp.user.others_note;
  if (O && O.isTheirs(tp.app, file, await O.myName(tp.app))) {
    new tp.obsidian.Notice(`「${M.nameOf(file)}」は他の人のノートなので書き換えません。`
      + "書き足すときは、そのノートを開いて右クリック →「自分も作成者に入れて書く」のあとに使ってください", 8000);
    return;
  }
  await add(tp, file, "parent", note, `「${M.nameOf(file)}」の親(parent)`);
}

module.exports = Object.assign(link_relation, { asParent });
