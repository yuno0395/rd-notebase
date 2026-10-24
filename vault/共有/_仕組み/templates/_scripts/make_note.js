// イシュー・タスク・仮説・目的・ナレッジにする(仕様書「ショートカットキー」)。
// Ctrl+I(イシュー)・Ctrl+T(タスク)・Ctrl+H(仮説)と、右クリックのメニューから使う。
//
//   - 文字を選んで使う: その文字を名前にする。
//   - [[ ]] の上で使う: そのリンクの名前で作る(まだファイルがないときだけ)。
//   - 何も選ばずに使う: カーソルのある行の文を名前にする(行頭の - や - [ ]、末尾の 📅 などは残す)。
// 同じ種類・同じ名前(か別名)のノートがあれば、作らずにそれにつなぐ。
// 質問はしない。parent には今のノートが入る。作ったノートは開かない。

const T = "_仕組み/templates/";
const ID_PREFIX = /^[0-9A-Z]{6}[0-9A-Z]+_/i;
const BAD_CHARS = /[\\/:*?"<>|#^\[\]\r\n]/;
const MAX_NAME = 80;
// 行頭の印(- / - [ ] / 1. / # )と、Tasks の日付などの印
const LINE_HEAD = /^(\s*(?:[-*+]\s+(?:\[.\]\s+)?|\d+[.)]\s+|#{1,6}\s+)?)/;
const TASK_MARKS = /\s*(?:📅|⏳|🛫|✅|➕|🔁|⏫|🔼|🔽|❌|🆔|⛔).*$/u;

const KINDS = {
  イシュー: { type: "イシュー", template: T + "イシュー.md", folder: "03_イシュー" },
  タスク: { type: "タスク", template: T + "タスク.md", folder: "04_タスク" },
  仮説: { type: "仮説", template: T + "価値の仮説.md", folder: "01_目的" },
  目的: { type: "目的", template: T + "目的.md", folder: "01_目的" },
  ナレッジ: { type: "ナレッジ", template: T + "ナレッジ.md", folder: "05_ナレッジ" },
};

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

function findSame(app, type, name) {
  const key = name.trim().toLowerCase();
  return app.vault.getMarkdownFiles().filter((f) => {
    if (f.path.startsWith(T)) return false;
    const fm = app.metadataCache.getFileCache(f)?.frontmatter;
    if (!fm || String(fm.type || "").trim() !== type) return false;
    return nameOf(f).toLowerCase() === key || asList(fm.aliases).some((a) => a.toLowerCase() === key);
  });
}

// [[ ]] の中の行き先から、ノートを探す
function resolve(app, target, from) {
  return app.metadataCache.getFirstLinkpathDest(target.split("|")[0].trim(), from);
}

// 属性欄の key の行を value にする。行末の説明(# …)は残す。続く `  - …` の行も置き換える。なければ type の下に足す。
function setKey(text, key, value) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return text;
  const lines = m[1].split(/\r?\n/);
  const at = lines.findIndex((l) => new RegExp(`^${key}\\s*:`).test(l));
  if (at >= 0) {
    const comment = (lines[at].match(/\s+#\s.*$/) || [""])[0];
    let end = at + 1;
    while (end < lines.length && /^(\s+\S|-\s)/.test(lines[end])) end++;
    const head = value.startsWith("\n") ? `${key}:${value}` : `${key}: ${value}`;
    const pad = comment ? head.padEnd(Math.max(head.length + 1, 22)) : head;
    lines.splice(at, end - at, comment ? pad + comment.trimStart() : head);
  } else {
    const t = lines.findIndex((l) => /^type\s*:/.test(l));
    lines.splice(t >= 0 ? t + 1 : lines.length, 0, value.startsWith("\n") ? `${key}:${value}` : `${key}: ${value}`);
  }
  return text.replace(m[1], () => lines.join("\n"));
}

function flow(values) {
  return "[" + values.map((v) => JSON.stringify(v)).join(", ") + "]";
}

// 作ったノートに最初から入れる値
function initialValues(app, kind, note) {
  const fm = app.metadataCache.getFileCache(note)?.frontmatter || {};
  const here = linkOf(note);
  const project = asList(fm.project);
  const out = {};
  if (kind !== "目的") out.parent = flow([here]);
  if (kind === "イシュー") {
    out.impact = "未判定";
    out.speed = "すぐ";
    if (project.length) out.project = `[${project.join(", ")}]`;
  }
  if (kind === "目的" && project.length) out.project = `[${project.join(", ")}]`;
  if (kind === "ナレッジ") {
    // 今のノート(タスク)の parent のイシュー。変化は「出荷→?」のように空けておく
    const issues = asList(fm.parent)
      .map((p) => (p.match(/\[\[([^\]]+)\]\]/) || [])[1])
      .filter((t) => t)
      .map((t) => resolve(app, t, note.path))
      .filter((f) => f && app.metadataCache.getFileCache(f)?.frontmatter?.type === "イシュー");
    if (issues.length) {
      const items = issues.map((f) => {
        const impact = String(app.metadataCache.getFileCache(f)?.frontmatter?.impact || "").trim() || "?";
        return `\n  - ${JSON.stringify(`${linkOf(f)} ${impact}→?`)}`;
      });
      out.risk_reduction = items.join("");
    }
  }
  return out;
}

async function placeFor(app, kind, note) {
  const folder = KINDS[kind].folder;
  if (await app.vault.adapter.exists("_仕組み/記録/私.yaml")) return folder; // 個人 vault
  // 共有 vault で仮運用しているとき: 今のノートのプロジェクト、なければ 共通
  const fm = app.metadataCache.getFileCache(note)?.frontmatter || {};
  const project = asList(fm.project)[0];
  const top = note.path.split("/")[0];
  for (const p of [project, top, "共通"]) {
    if (p && app.vault.getAbstractFileByPath(`${p}/${folder}`)) return `${p}/${folder}`;
  }
  return folder;
}

async function createNote(tp, kind, name, note) {
  const app = tp.app;
  const k = KINDS[kind];
  const folderPath = await placeFor(app, kind, note);
  if (!app.vault.getAbstractFileByPath(folderPath)) await app.vault.createFolder(folderPath);
  const template = app.vault.getAbstractFileByPath(k.template);
  if (!template) throw new Error(`${k.template} がありません`);
  const values = initialValues(app, kind, note);
  // テンプレートの中で id がつき、ファイル名が id_名前 に変わる
  const file = await tp.file.create_new(template, name, false, app.vault.getAbstractFileByPath(folderPath));
  if (!file) return null;
  await app.vault.process(file, (text) => {
    for (const [key, value] of Object.entries(values)) text = setKey(text, key, value);
    return text;
  });
  return file;
}

async function make_note(tp, kind) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const k = KINDS[kind];
  const view = app.workspace.activeEditor;
  if (!k) throw new Error(`知らない種類です: ${kind}`);
  if (!view?.editor || !view.file) {
    new Notice(`ノートを開いてから「${kind}にする」を使ってください`);
    return;
  }
  const ed = view.editor;
  const note = view.file;
  const noteType = String(app.metadataCache.getFileCache(note)?.frontmatter?.type || "").trim();
  if (kind === "仮説" && noteType !== "目的") {
    new Notice("仮説は、目的のノートの中で作ります(parent に目的が入るため)");
    return;
  }

  let from = ed.getCursor("from");
  let to = ed.getCursor("to");
  let word = ed.getSelection();
  // Templater はこのあと選んでいる文字を空の文字で置き換えるので、先に選択を外しておく
  ed.setCursor(to);

  const line = ed.getLine(from.line);
  if (!word) {
    // [[ ]] の上なら、そのリンク
    for (const m of line.matchAll(/\[\[([^\[\]\n]+?)\]\]/g)) {
      const start = m.index, end = m.index + m[0].length;
      if (from.ch < start || from.ch > end) continue;
      const [target, alias] = m[1].split("|");
      if (resolve(app, target, note.path)) {
        new Notice("このリンクはもうノートにつながっています");
        return;
      }
      word = (alias || target).trim();
      from = { line: from.line, ch: start };
      to = { line: from.line, ch: end };
      break;
    }
  }
  if (!word) {
    // 行の文。行頭の印と末尾の日付などは残す
    const head = line.match(LINE_HEAD)[1].length;
    let body = line.slice(head);
    const tail = body.match(TASK_MARKS);
    if (tail) body = body.slice(0, tail.index);
    const trimmed = body.trim();
    if (!trimmed) {
      new Notice("名前にする文字を選ぶか、文のある行で使ってください");
      return;
    }
    const lead = body.indexOf(trimmed);
    from = { line: from.line, ch: head + lead };
    to = { line: from.line, ch: head + lead + trimmed.length };
    word = trimmed;
  }

  const name = word.trim();
  if (!name || BAD_CHARS.test(name)) {
    new Notice("ファイル名に使えない文字(/ : * ? \" < > | # ^ [ ] や改行)が入っています");
    return;
  }
  if (name.length > MAX_NAME) {
    new Notice(`名前が長すぎます(${MAX_NAME} 文字まで)。短く選び直してください`);
    return;
  }

  let file;
  const same = findSame(app, k.type, name);
  if (same.length === 1) {
    file = same[0];
  } else if (same.length > 1) {
    new Notice(`同じ名前の${kind}が ${same.length} つあります。Ctrl+K の検索窓か手でつないでください`);
    return;
  } else {
    file = await createNote(tp, kind, name, note);
    if (!file) return;
    new Notice(`${kind}「${name}」を作りました`);
  }
  const text = linkOf(file, name);
  ed.replaceRange(text, from, to);
  ed.setCursor({ line: from.line, ch: from.ch + text.length });
  ed.focus();
}

module.exports = make_note;
