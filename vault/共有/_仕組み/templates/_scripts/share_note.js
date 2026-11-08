// 共有しないノート(00_PIP/ にあるもの・メモ)を共有する、またはその逆(仕様書「共有する範囲」v0.91)。
// 右クリックのメニューとノートの上の帯のボタン「共有する」「共有をやめる」から使う(新しいキーは作らない)。
// v0.90 までの「このメモを〜にする」はここに入った。
//
// 共有する:
//   1. メモ(type: メモ)なら種類を選ぶ(ノード・イシュー・タスク・仮説・目的・設計案・ナレッジ)。Esc なら何もしない。
//      ほかの種類のノート(PIP を選んで 00_PIP/メモ/ に置いたイシューなど)は種類はそのまま。
//   2. だれに見せるかを選ぶ(Internal use only / プロジェクト名 ＋ EXT_<相手>。PIP は出さない)。
//      窓に「次の同期で共有されます」と出す。これが確かめの1回。Esc なら何もしない。
//      visibility に PIP 以外がもう書いてあれば聞かずにそれを使う(属性欄で書き換えてから押した、の形)。
//   3. メモは、id・author・aliases をそのまま使って type をその種類にし、テンプレートの属性と見出しのうち
//      メモにないものを足す(メモのテンプレートの説明の行は消す)。ほかの種類は visibility と project だけ書く。
//   4. 置き場所: プロジェクトが1つなら <プロジェクト>/<種類のフォルダ>/、Internal・2つ以上は 共通/<種類のフォルダ>/、
//      週報は 00_週報/。ファイル名は <id>_<名前>.md。id は変わらないので、デイリーなどからのリンクは切れない。
//
// 共有をやめる: 自分のノートの visibility を [PIP] にして 00_PIP/メモ/ へ移す。もう共有に出した写しは残る
// (同期プログラムが同期レポートで知らせる)。

const T = "_仕組み/templates/";
const MEMO_TEMPLATE = T + "メモ.md";
const ID_PREFIX = /^[0-9A-Z]{6}[0-9A-Z]+_/i;
const OLD_DATE = /^\d{4}-\d{2}-\d{2}[ _]+/; // v0.84 までのメモの名前 <日付> <名前>
const WEEKLY_DIR = "00_週報";

const KINDS = [
  { kind: "ノード", type: "ノード", template: "ノード.md", folder: "02_ノード" },
  { kind: "イシュー", type: "イシュー", template: "イシュー.md", folder: "03_イシュー" },
  { kind: "タスク", type: "タスク", template: "タスク.md", folder: "04_タスク" },
  { kind: "仮説", type: "仮説", template: "価値の仮説.md", folder: "01_目的" },
  { kind: "目的", type: "目的", template: "目的.md", folder: "01_目的" },
  { kind: "設計案", type: "設計案", template: "設計案.md", folder: "01_設計案" },
  { kind: "ナレッジ", type: "ナレッジ", template: "ナレッジ.md", folder: "05_ナレッジ" },
];
// メモから選ぶ種類のほかに、共有できる種類と置くフォルダ
const FOLDERS = { 議事録: "04_タスク", "実験・試作記録": "04_タスク" };
const NOT_SHARED = ["デイリー", "プロジェクト", "窓口"];

// "---\n…\n---\n本文" を { head: 属性欄の行, body: 本文 } に
function split(text) {
  const t = text.replace(/\r\n/g, "\n");
  const m = t.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { head: [], body: t };
  return { head: m[1].split("\n"), body: t.slice(m[0].length) };
}

// 属性欄の行を、キーごとのかたまり(続く "  - …" の行も含む)に分ける。コメントだけの行は次のキーにつける
function blocks(head) {
  const out = [];
  let lead = [];
  for (const line of head) {
    const m = line.match(/^([^\s#:][^:]*?)\s*:/);
    if (m) { out.push({ key: m[1].trim(), lines: [...lead, line] }); lead = []; }
    else if (out.length && /^(\s+\S|-\s)/.test(line)) out[out.length - 1].lines.push(line);
    else lead.push(line);
  }
  return out;
}

function ymd(days) {
  const d = new Date(Date.now() + days * 86400000);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// テンプレートの属性欄の1行から Templater の <% %> を外し、値を入れる
function fill(line, key, v) {
  if (!/<%/.test(line)) return line;
  const comment = (line.replace(/<%[\s\S]*?%>/g, "").match(/\s+#\s.*$/) || [""])[0];
  let value;
  if (key === "id") value = v.id;
  else if (key === "author") value = v.author;
  else if (key === "aliases") value = v.aliases;
  else if (key === "project") value = v.project;
  else if (key === "due") value = ymd(7);
  else value = line.replace(/^[^:]*:\s*/, "").replace(/<%[\s\S]*?%>/g, "").replace(/\s+#\s.*$/, "").trim();
  const head = `${key}: ${value}`.trimEnd();
  return comment ? head.padEnd(Math.max(head.length + 1, 22)) + comment.trimStart() : head;
}

function headings(body) {
  return new Set(body.split("\n").filter((l) => /^#{1,6}\s/.test(l)).map((l) => l.replace(/^#+\s+/, "").trim()));
}

// テンプレートの本文を見出しごとに分ける(見出しと、その下の説明の行)
function sections(body) {
  const out = [];
  for (const line of body.split("\n")) {
    if (/^#{1,6}\s/.test(line)) out.push([line]);
    else if (out.length) out[out.length - 1].push(line);
  }
  return out.map((s) => ({ title: s[0].replace(/^#+\s+/, "").trim(), text: s.join("\n").replace(/\n+$/, "") }));
}

// 新しい中身。memo: メモの中身、tpl: テンプレートの中身
function convert(memo, tpl, k, v, memoTpl) {
  const m = split(memo);
  const t = split(tpl);
  const mine = blocks(m.head).filter((b) => !["type", "visibility", "id", "aliases", "author"].includes(b.key));
  const have = new Set(mine.map((b) => b.key));
  const head = [];
  for (const b of blocks(t.head)) {
    if (b.key === "visibility") { head.push(`visibility: ${v.visibility}`); continue; }   // 選んだ範囲(テンプレートの窓は使わない)
    if (b.key === "type") { head.push(...b.lines.slice(0, -1), `type: ${k.type}`); continue; }
    // メモにもあるキーはメモの値を使う(project はプロジェクトを選んだらそれ)
    if (have.has(b.key) && !(b.key === "project" && v.project !== "[]")) {
      head.push(...mine.find((x) => x.key === b.key).lines);
      continue;
    }
    head.push(...b.lines.map((l) => fill(l, b.key, v)));
  }
  // テンプレートにないメモの属性も残す
  const known = new Set(blocks(t.head).map((b) => b.key));
  for (const b of mine) if (!known.has(b.key)) head.push(...b.lines);

  // メモのテンプレートの説明の行は消す
  const drop = new Set(split(memoTpl || "").body.split("\n").map((l) => l.trim()).filter((l) => l));
  let body = m.body.split("\n").filter((l) => !drop.has(l.trim())).join("\n").replace(/^\n+/, "").trimEnd();
  const has = headings(body);
  const add = sections(t.body).filter((s) => !has.has(s.title));
  // 「背景」は同期プログラムが書く欄なので、テンプレートどおり一番上に置く(F-60)
  const top = add.filter((s) => s.title === "背景").map((s) => s.text);
  const rest = add.filter((s) => s.title !== "背景").map((s) => s.text);
  body = [...top, body, ...rest].filter((x) => x).join("\n");
  return `---\n${head.join("\n")}\n---\n${body}\n`;
}

function pick(app, obsidian, items, text, placeholder) {
  return new Promise((done) => {
    let picked = null;
    class Picker extends obsidian.FuzzySuggestModal {
      getItems() { return items; }
      getItemText(x) { return text(x); }
      onChooseItem(x) { picked = x; }
      onClose() { setTimeout(() => done(picked), 0); }
    }
    const m = new Picker(app);
    m.setPlaceholder(placeholder);
    m.open();
  });
}

function typeOf(app, file) {
  const fm = app.metadataCache.getFileCache(file)?.frontmatter || {};
  return String(fm.type || "").trim();
}

function inPip(file) {
  return file.path.startsWith(V_PIP_TOP + "/") || file.path.startsWith(OLD_PIP_TOP + "/");
}
const V_PIP_TOP = "00_PIP";
const OLD_PIP_TOP = "00_日誌";

async function moveTo(app, M, file, dest, name) {
  await M.ensureFolder(app, dest);
  const path = `${dest}/${name}.md`;
  if (path === file.path) return path;
  if (app.vault.getAbstractFileByPath(path)) throw new Error(`${path} がもうあります`);
  await app.fileManager.renameFile(file, path);
  return path;
}

async function share_note(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const M = tp.user.make_note;
  const V = tp.user.ask_visibility;
  const file = app.workspace.getActiveFile();
  if (!file || file.extension !== "md") {
    new Notice("共有したいノートを開いてから使ってください");
    return;
  }
  const fm = app.metadataCache.getFileCache(file)?.frontmatter || {};
  const type = typeOf(app, file);
  const now = V.read(fm.visibility);
  const memo = type === "メモ";
  if (!memo && !inPip(file) && !V.isPip(now)) {
    new Notice(`このノートはもう共有しています(visibility: ${V.text(now || [])})。見せる相手を変えるときは visibility を書き換えてください`, 8000);
    return;
  }
  if (NOT_SHARED.includes(type) || (!type && !memo)) {
    new Notice("デイリーなど、種類(type)のないノートは共有できません。残したい行は Ctrl+K / I / T でノートにしてください", 8000);
    return;
  }
  let k = null;
  if (memo) {
    const picked = await pick(app, tp.obsidian, KINDS.map((x) => x.kind), (x) => x,
      "どの種類にして共有しますか(このファイルのまま変えます。Esc でやめる)");
    k = KINDS.find((x) => x.kind === picked);
    if (!k) return;
  } else {
    k = KINDS.find((x) => x.type === type) || (type === "週報" ? { kind: "週報", type, folder: WEEKLY_DIR }
      : FOLDERS[type] ? { kind: type, type, folder: FOLDERS[type] } : null);
    if (!k) {
      new Notice(`「${type}」は共有するときの置き場所が決まっていません`);
      return;
    }
  }
  const name = file.basename.replace(ID_PREFIX, "").replace(OLD_DATE, "").trim() || file.basename;
  const list = now && !V.isPip(now) ? now
    : await V.pick(app, tp.obsidian, name, M.projectNames(app), false);
  if (!list) return;
  const ps = V.projectsOf(list);
  const dest = k.type === "週報" ? WEEKLY_DIR : V.placeOf(list, k.folder, M.COMMON);
  const project = k.type === "週報" ? null
    : k.type === "ノード" ? (ps.length === 1 ? M.flow(ps) : "[]")
      : M.flow(ps.length ? ps : [M.COMMON]);

  let id = String(fm.id || "").trim();
  if (memo) {
    const tplFile = app.vault.getAbstractFileByPath(T + k.template);
    if (!tplFile) throw new Error(`${T + k.template} がありません`);
    id = id || await tp.user.make_id(tp);
    const authors = M.asList(fm.author);
    const author = authors.length ? M.flow(authors) : `[${await tp.user.me(tp)}]`;
    const aliasList = M.asList(fm.aliases);
    const aliases = M.flow(aliasList.length ? aliasList : [name]);
    const memoTpl = app.vault.getAbstractFileByPath(MEMO_TEMPLATE);
    const memoTplText = memoTpl ? await app.vault.read(memoTpl) : "";
    const tplText = await app.vault.read(tplFile);
    await app.vault.process(file, (text) => convert(text, tplText, k,
      { id, author, aliases, project, visibility: V.text(list) }, memoTplText));
  } else {
    await app.vault.process(file, (text) => {
      let t = M.setKey(text, "visibility", V.text(list));
      if (project !== null && (project !== "[]" || "project" in fm)) t = M.setKey(t, "project", project);
      return t;
    });
  }
  const base = memo || (id && !ID_PREFIX.test(file.basename)) ? `${id}_${name}` : file.basename;
  await moveTo(app, M, file, dest, base);
  new Notice(`${k.kind}を共有するところに移しました(${dest}/)。次の同期で共有されます`, 6000);
}

// 共有をやめる: [PIP] にして 00_PIP/メモ/ へ
async function stop(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const M = tp.user.make_note;
  const V = tp.user.ask_visibility;
  const file = app.workspace.getActiveFile();
  if (!file || file.extension !== "md") {
    new Notice("共有をやめたいノートを開いてから使ってください");
    return;
  }
  const fm = app.metadataCache.getFileCache(file)?.frontmatter || {};
  if (inPip(file)) {
    new Notice("このノートはもう共有していません(00_PIP/ にあります)");
    return;
  }
  if (NOT_SHARED.includes(typeOf(app, file))) {
    new Notice("台帳と機密の窓口は、共有をやめられません");
    return;
  }
  const O = tp.user.others_note;
  if (O.isTheirs(app, file, await O.myName(app))) {
    new Notice("自分が作ったノートだけ共有をやめられます");
    return;
  }
  const ok = await pick(app, tp.obsidian, ["yes", "no"],
    (x) => (x === "yes" ? "共有をやめる(自分だけのノートにして 00_PIP/メモ/ へ移す)" : "やめない"),
    "もう共有に出した写しは消えずに残ります(同期レポートで知らせます)。共有をやめますか");
  if (ok !== "yes") return;
  await app.vault.process(file, (text) => M.setKey(text, "visibility", V.text([V.PIP])));
  await moveTo(app, M, file, V.PIP_DIR, file.basename);
  new Notice("共有をやめました(00_PIP/メモ/)。共有に出した写しは残っています。消すときは PL に頼んでください", 8000);
}

Object.assign(share_note, { convert, stop, KINDS });
module.exports = share_note;
