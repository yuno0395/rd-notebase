// 他の人のノートの扱い(仕様書「他の人のノートを読む・書き足す」v0.67)。個人 vault だけで働く。
//
// 個人 vault には、自分のノートと、同期プログラムが配った他の人のノートが同じフォルダに並ぶ。
// author に自分がいないノートが、他の人のノート。
// 人は「番号_名前」(例 229999_Yu)で書く(仕様書 v0.68)。同姓同名がいても番号で見分ける。
// 名前だけの古い書き方(Yu)も読む(そのときは名前で比べる)。
//
//   others_note(tp, "watch"): Obsidian を開いたときに1回呼ぶ(Templater の起動時テンプレート)。
//     他の人のノートを開くと読む画面にし、右上に「〇〇さんのノート(読むだけ)」と出す。うっかり書き換え防止。
//     Ctrl+E で編集の画面に切り替えれば書けるが、書き換えた中身は次の同期で共有の中身に戻る(backup に残る)。
//   others_note(tp, "join"): 右クリックの「自分も作成者に入れて書く」。author に自分を足して、編集の画面にする。
//     以後は自分のノートとして扱われ、直した中身は共有へ出て、元の作成者にも届く。

const MY_SETTINGS = "_仕組み/個人設定.md";
const ID_PREFIX = /^[0-9A-Z]{6}[0-9A-Z]+_/i;

function plainName(v) {
  const t = (String(v).match(/\[\[([^\]|]+)/) || [null, String(v)])[1].trim();
  return t.replace(ID_PREFIX, "");
}

// "229999_Yu" → { number: "229999", name: "Yu" }、"Yu" → { number: "", name: "Yu" }、"229999" → 番号だけ
function person(v) {
  const t = plainName(v);
  const m = t.match(/^(\d{6})(?:_(.*))?$/);
  return m ? { number: m[1], name: (m[2] || "").trim() } : { number: "", name: t.trim() };
}

// 画面に出す名前
function personName(v) {
  const p = person(v);
  return p.name || p.number;
}

// 同じ人か。両方に番号があれば番号で、どちらかが名前だけなら名前で比べる
function samePerson(a, b) {
  const x = person(a);
  const y = person(b);
  if (x.number && y.number) return x.number === y.number;
  return !!x.name && x.name === y.name;
}

function hasPerson(list, who) {
  return (list || []).some((x) => samePerson(x, who));
}

function authorsOf(app, file) {
  const a = app.metadataCache.getFileCache(file)?.frontmatter?.author;
  const list = a === undefined || a === null || a === "" ? [] : Array.isArray(a) ? a : [a];
  return list.map((x) => plainName(x)).filter((x) => x);
}

// 自分(ノートに書く形)。個人 vault は個人設定.md の number と name から「229999_Yu」。
// 共有・機密 vault は設定フォルダ名 .obsidian-<番号>_<PCの記号> の番号だけ(名前はわからないので番号で比べる)
async function myName(app) {
  const fs = app.vault.adapter;
  if (await fs.exists(MY_SETTINGS)) {
    const text = await fs.read(MY_SETTINGS);
    const name = (text.match(/^name:[ \t]*["']?([^"'#\r\n]*)/m) || [null, ""])[1].trim();
    const number = (text.match(/^number:[ \t]*["']?(\d{6})\b/m) || [null, ""])[1];
    if (!name) return number;
    return number ? `${number}_${name}` : name;
  }
  const dir = app.vault.configDir;
  const m = dir.match(/^\.obsidian-(\d{6})(?:_|$)/);
  return m ? m[1] : "";
}

function isTheirs(app, file, me) {
  if (!file || file.extension !== "md" || !me) return false;
  const a = authorsOf(app, file);
  return a.length > 0 && !hasPerson(a, me);
}

async function watch(tp) {
  const app = tp.app;
  const { Notice, MarkdownView } = tp.obsidian;
  if (!(await app.vault.adapter.exists(MY_SETTINGS))) return; // 個人 vault だけ
  const me = await myName(app);
  if (!me) return;
  if (window.__notebaseOthersRef) app.workspace.offref(window.__notebaseOthersRef); // 2回呼ばれても1つだけ
  window.__notebaseOthersRef = app.workspace.on("file-open", async (file) => {
    if (!isTheirs(app, file, me)) return;
    const leaf = app.workspace.getLeavesOfType("markdown").find((l) => l.view instanceof MarkdownView && l.view.file === file);
    if (leaf && leaf.view.getMode() === "source") {
      const st = leaf.getViewState();
      await leaf.setViewState({ ...st, state: { ...st.state, mode: "preview" } });
    }
    new Notice(`${authorsOf(app, file).map(personName).join("・")}さんのノートです(読むだけ)。書き足すときは右クリックの「自分も作成者に入れて書く」`, 5000);
  });
}

async function join(tp) {
  const app = tp.app;
  const { Notice, MarkdownView } = tp.obsidian;
  const file = app.workspace.getActiveFile();
  const me = await myName(app);
  if (!file || !me || !(await app.vault.adapter.exists(MY_SETTINGS))) {
    new Notice("個人 vault でノートを開いてから使ってください");
    return;
  }
  if (!isTheirs(app, file, me)) {
    new Notice("自分のノートなので、そのまま書けます");
    return;
  }
  await app.fileManager.processFrontMatter(file, (fm) => {
    const list = fm.author === undefined || fm.author === null || fm.author === "" ? [] : Array.isArray(fm.author) ? fm.author : [fm.author];
    fm.author = [...list, me];
  });
  const leaf = app.workspace.getLeavesOfType("markdown").find((l) => l.view instanceof MarkdownView && l.view.file === file);
  if (leaf && leaf.view.getMode() === "preview") {
    const st = leaf.getViewState();
    await leaf.setViewState({ ...st, state: { ...st.state, mode: "source" } });
  }
  new Notice("作成者に自分を足しました。書き足した中身は、次の同期で共有へ出て元の作成者にも届きます", 6000);
}

async function others_note(tp, what) {
  if (what === "join") return join(tp);
  return watch(tp);
}

Object.assign(others_note, { isTheirs, myName, authorsOf, person, personName, samePerson, hasPerson });
module.exports = others_note;
