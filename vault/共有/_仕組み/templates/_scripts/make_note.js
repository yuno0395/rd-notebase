// イシュー・タスク・仮説・設計案・目的・ナレッジにする(仕様書「ショートカットキー」)。
// Ctrl+I(イシュー)・Ctrl+T(タスク)・Ctrl+H(仮説)・Ctrl+U(設計案)と、右クリックのメニューから使う。
//
//   - 文字を選んで使う: その文字を名前にする。
//   - [[ ]] の上で使う: そのリンクの名前で作る(まだファイルがないときだけ)。
//   - 何も選ばずに使う: カーソルのある行の文を名前にする(行頭の - や - [ ]、末尾の 📅 などは残す)。
// 同じ種類・同じ名前(か別名)のノートがあれば、作らずにそれにつなぐ。
// 質問はしない。作ったノートは開かない。parent には今のノートが入る。ただし、
//   - 仮説: 今のノートが仮説なら今のノート(下の仮説になる。仮説の木)。それ以外は parent をたどった先の目的。
//   - 設計案: parent は成果物の構成(Yu 2026-10-28)。目的で押せば成果物候補、設計案で押せば
//     その部分案。仮説で押したとき(たどった先が仮説のときも)は、parent にその目的、価値仮説にその仮説(この案が
//     実現する仮説)を入れる。ほかのノートでは parent をたどって最初に着く目的・仮説・設計案で同じように決める。
//   - イシュー: parent ではなく 脅かす に、今のノートから上流をたどって最初に着く設計案(その案が仮説を
//     実現できるかを脅かすリスク。Yu 2026-10-25。K-Plex で設計案の右に出す。2026-10-28)。設計案がなければ
//     価値の仮説(目的は越えない)。今のノートが
//     タスク・実験・試作記録なら、previous に今のノート、generation に元のイシュー＋1 を入れる。
//     今のノートがノードなら、friend に今のノートを入れる。どちらも見つからなければ 脅かす は空けて知らせる。

const T = "_仕組み/templates/";
const ID_PREFIX = /^[0-9A-Z]{6}[0-9A-Z]+_/i;
const BAD_CHARS = /[\\/:*?"<>|#^\[\]\r\n]/;
const MAX_NAME = 80;
// 行頭の印(- / - [ ] / 1. / # )と、Tasks の日付などの印
const LINE_HEAD = /^(\s*(?:[-*+]\s+(?:\[.\]\s+)?|\d+[.)]\s+|#{1,6}\s+)?)/;
const TASK_MARKS = /\s*(?:📅|⏳|🛫|✅|➕|🔁|⏫|🔼|🔽|❌|🆔|⛔).*$/u;

// イシューを生む対策(仕様書「対策から新しいイシューが生まれるとき」)
const COUNTERMEASURES = ["タスク", "実験・試作記録"];
// 設計案の上に来るもの
const SOLUTION_PARENTS = ["目的", "仮説", "設計案"];

// v0.37 までの設計記録と v0.54 までのソリューションは、設計案として扱う(Yu 2026-10-28)
function normType(t) {
  return t === "設計記録" || t === "ソリューション" ? "設計案" : t;
}

const KINDS = {
  イシュー: { type: "イシュー", template: T + "イシュー.md", folder: "03_イシュー" },
  タスク: { type: "タスク", template: T + "タスク.md", folder: "04_タスク" },
  仮説: { type: "仮説", template: T + "価値の仮説.md", folder: "01_目的" },
  設計案: { type: "設計案", template: T + "設計案.md", folder: "01_設計案" },
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
    if (!fm) return false;
    const t = String(fm.type || "").trim();
    if (normType(t) !== type) return false;
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

function typeOf(app, file) {
  const t = String(app.metadataCache.getFileCache(file)?.frontmatter?.type || "").trim();
  return normType(t);
}

// 今のノートか、その parent をたどった先にある目的(近いものから。5段まで)
function findPurpose(app, note) {
  let level = [note];
  const seen = new Set();
  for (let depth = 0; depth <= 5 && level.length; depth++) {
    const next = [];
    for (const f of level) {
      if (seen.has(f.path)) continue;
      seen.add(f.path);
      if (typeOf(app, f) === "目的") return f;
      next.push(...parentsOf(app, f));
    }
    level = next;
  }
  return null;
}

// 上流のノート。parent と、イシューの 脅かす(脅かす設計案か仮説。K-Plex では相手の右に出る。Yu 2026-10-28)
function parentsOf(app, f) {
  const fm = app.metadataCache.getFileCache(f)?.frontmatter || {};
  return [...asList(fm.parent), ...asList(fm["脅かす"])]
    .map((p) => (p.match(/\[\[([^\]]+)\]\]/) || [])[1])
    .filter((t) => t)
    .map((t) => resolve(app, t, f.path))
    .filter((d) => d);
}

// 今のノートから parent をたどって、いちばん近い段にある type のノートを全部返す。
// stop の種類のノートより上へはたどらない。5段まで。
function findNearest(app, note, type, stop = []) {
  let level = [note];
  const seen = new Set();
  for (let depth = 0; depth <= 5 && level.length; depth++) {
    const hit = [];
    const next = [];
    for (const f of level) {
      if (seen.has(f.path)) continue;
      seen.add(f.path);
      const t = typeOf(app, f);
      if (t === type) { hit.push(f); continue; }
      if (depth > 0 && stop.includes(t)) continue;
      next.push(...parentsOf(app, f));
    }
    if (hit.length) return hit;
    level = next;
  }
  return [];
}

// 今のノートから parent をたどって、最初に着く段にある、types のどれかのノート(5段まで。目的より上へはたどらない)
function findNearestOf(app, note, types) {
  let level = [note];
  const seen = new Set();
  for (let depth = 0; depth <= 5 && level.length; depth++) {
    const hit = [];
    const next = [];
    for (const f of level) {
      if (seen.has(f.path)) continue;
      seen.add(f.path);
      const t = typeOf(app, f);
      if (types.includes(t)) { hit.push(f); continue; }
      if (depth > 0 && t === "目的") continue;
      next.push(...parentsOf(app, f));
    }
    if (hit.length) return hit;
    level = next;
  }
  return [];
}

// 設計案の parent(成果物の構成)と 価値仮説(実現する価値の仮説。K-Plex の左に出る)。Yu 2026-10-28
function solutionLinks(app, note) {
  const ups = findNearestOf(app, note, SOLUTION_PARENTS);
  const hyps = ups.filter((f) => typeOf(app, f) === "仮説");
  const parents = ups.filter((f) => typeOf(app, f) !== "仮説");
  for (const h of hyps) {
    const p = findPurpose(app, h);
    if (p && !parents.some((x) => x.path === p.path)) parents.push(p);
  }
  return { parents, hyps };
}

// イシューの parent: いちばん近い設計案候補、なければ価値の仮説
function issueParents(app, note) {
  const sol = findNearest(app, note, "設計案", ["目的", "仮説"]);
  return sol.length ? sol : findNearest(app, note, "仮説", ["目的"]);
}

// イシューの世代。同期プログラム(F-27)と同じ数え方: previous がなければ 1、
// あれば previous の先の元のイシュー(対策ならその parent のイシュー)の世代＋1。循環していれば null
function generationOf(app, issue, path) {
  if (path.includes(issue.path)) return null;
  const fm = app.metadataCache.getFileCache(issue)?.frontmatter || {};
  const prev = asList(fm.previous)
    .map((p) => (p.match(/\[\[([^\]]+)\]\]/) || [])[1])
    .filter((t) => t)
    .map((t) => resolve(app, t, issue.path))
    .filter((d) => d);
  if (!prev.length) return 1;
  let best = 0;
  for (const p of prev) {
    const origin = typeOf(app, p) === "イシュー" ? p : findNearest(app, p, "イシュー", [])[0];
    if (!origin) continue;
    const g = generationOf(app, origin, path.concat([issue.path]));
    if (g === null) return null;
    best = Math.max(best, g);
  }
  return best + 1;
}

// イシューに入れる project: 今のノート、なければ元のイシュー、なければたどった先の目的のもの
function projectFor(app, note) {
  const own = asList(app.metadataCache.getFileCache(note)?.frontmatter?.project);
  if (own.length) return own;
  for (const f of [...findNearest(app, note, "イシュー", ["目的"]), findPurpose(app, note)]) {
    const p = f && asList(app.metadataCache.getFileCache(f)?.frontmatter?.project);
    if (p && p.length) return p;
  }
  return [];
}

// 作ったノートに最初から入れる値
function initialValues(app, kind, note) {
  const fm = app.metadataCache.getFileCache(note)?.frontmatter || {};
  const here = linkOf(note);
  const project = asList(fm.project);
  const out = {};
  if (kind === "設計案") {
    const { parents, hyps } = solutionLinks(app, note);
    if (parents.length) out.parent = flow(parents.map((f) => linkOf(f)));
    if (hyps.length) out["価値仮説"] = flow(hyps.map((f) => linkOf(f)));
  } else if (kind === "仮説") {
    // 仮説の parent は目的か上の仮説(仮説の木)。仮説で作ったら、その下の仮説にする。
    // それ以外は今のノートからたどった目的。見つからなければ空けておく
    if (typeOf(app, note) === "仮説") out.parent = flow([here]);
    else {
      const purpose = findPurpose(app, note);
      if (purpose) out.parent = flow([linkOf(purpose)]);
    }
  } else if (kind === "イシュー") {
    // イシューは 脅かす に脅かす設計案(なければ価値の仮説)。対策から生まれたものは previous と generation でたどれるようにする
    const here_type = typeOf(app, note);
    const ups = issueParents(app, note);
    if (ups.length) out["脅かす"] = flow(ups.map((f) => linkOf(f)));
    out.impact = "未判定";
    out.speed = "すぐ";
    const proj = projectFor(app, note);
    if (proj.length) out.project = `[${proj.join(", ")}]`;
    if (COUNTERMEASURES.includes(here_type)) {
      out.previous = flow([here]);
      const source = findNearest(app, note, "イシュー", ["目的"])[0];
      const g = source && generationOf(app, source, []);
      if (g) out.generation = String(g + 1);
    }
    if (here_type === "ノード") out.friend = flow([here]);
  } else if (kind !== "目的") out.parent = flow([here]);
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
  const fs = app.vault.adapter;
  if ((await fs.exists("_仕組み/個人設定.md")) || (await fs.exists("_仕組み/記録/私.yaml"))) return folder; // 個人 vault
  // 共有 vault で仮運用しているとき: 今のノートのプロジェクト、なければ 共通
  const project = (kind === "イシュー" ? projectFor(app, note) : asList(app.metadataCache.getFileCache(note)?.frontmatter?.project))[0];
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

// ノートを作っている間に、Obsidian がリンクを書き換えることがある
// (まだない [[名前]] が、作ったファイルの名前が id_名前 に変わったときに付け替えられる)。
// 置き換える前に、行の中をもう一度見て、正しい場所を探す。
function placeLink(app, ed, note, file, text, from, to, orig) {
  const line = ed.getLine(from.line);
  if (line.slice(from.ch, to.ch) !== orig) {
    let best = null;
    for (const m of line.matchAll(/\[\[([^\[\]\n]+?)\]\]/g)) {
      const dest = app.metadataCache.getFirstLinkpathDest(m[1].split("|")[0].trim(), note.path);
      if (dest?.path !== file.path) continue;
      if (!best || Math.abs(m.index - from.ch) < Math.abs(best.index - from.ch)) best = m;
    }
    if (best) {
      from = { line: from.line, ch: best.index };
      to = { line: from.line, ch: best.index + best[0].length };
    } else {
      to = from; // 見つからなければ、元の場所に足す
    }
  }
  ed.replaceRange(text, from, to);
  ed.setCursor({ line: from.line, ch: from.ch + text.length });
  ed.focus();
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

  const orig = ed.getRange(from, to);
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
    const noParent =
      (kind === "仮説" && typeOf(app, note) !== "仮説" && !findPurpose(app, note) && "目的") ||
      (kind === "イシュー" && !issueParents(app, note).length && "設計案か価値の仮説") ||
    (kind === "設計案" && !solutionLinks(app, note).parents.length && "目的か上の設計案");
    new Notice(`${kind}「${name}」を作りました` + (noParent ? `。${noParent}が見つからなかったので、${kind === "イシュー" ? "脅かす" : "parent"} に${noParent}を書いてください` : ""), noParent ? 8000 : undefined);
  }
  placeLink(app, ed, note, file, linkOf(file, name), from, to, orig);
}

// K-Plex の中心のノートから作る(仕様書「全体像の把握(K-Plex)」)。本文には触らない。
// QuickAdd の「K-Plex の中心から作る」が、Templater の tp の代わりに同じ形のものを渡して呼ぶ。
async function fromNote(tp, kind, note, rawName) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  if (!KINDS[kind]) throw new Error(`知らない種類です: ${kind}`);
  const name = String(rawName || "").trim();
  if (!name) return null;
  if (BAD_CHARS.test(name)) {
    new Notice("ファイル名に使えない文字(/ : * ? \" < > | # ^ [ ] や改行)が入っています");
    return null;
  }
  if (name.length > MAX_NAME) {
    new Notice(`名前が長すぎます(${MAX_NAME} 文字まで)`);
    return null;
  }
  const same = findSame(app, KINDS[kind].type, name);
  if (same.length) {
    new Notice(`同じ名前の${kind}がもうあります。つなぐときは本文で [[ ]] にしてください`, 6000);
    return null;
  }
  const file = await createNote(tp, kind, name, note);
  if (!file) return null;
  const noParent =
    (kind === "仮説" && typeOf(app, note) !== "仮説" && !findPurpose(app, note) && "目的") ||
    (kind === "イシュー" && !issueParents(app, note).length && "設計案か価値の仮説") ||
    (kind === "設計案" && !solutionLinks(app, note).parents.length && "目的か上の設計案");
  new Notice(`${kind}「${name}」を「${nameOf(note)}」から作りました` + (noParent ? `。${noParent}が見つからなかったので、${kind === "イシュー" ? "脅かす" : "parent"} に${noParent}を書いてください` : ""), noParent ? 8000 : undefined);
  return file;
}

make_note.fromNote = fromNote;
make_note.typeOf = typeOf;
module.exports = make_note;
