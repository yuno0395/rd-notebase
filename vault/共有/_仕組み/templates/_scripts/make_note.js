// イシュー・タスク・仮説・設計案・目的・ナレッジにする(仕様書「ショートカットキー」)。
// Ctrl+I(イシュー)・Ctrl+T(タスク)・Ctrl+H(仮説)・Ctrl+U(設計案)と、右クリックのメニューから使う。
//
//   - 文字を選んで使う: その文字を名前にする。
//   - [[ ]] の上で使う: そのリンクの名前で作る(まだファイルがないときだけ)。
//   - 何も選ばずに使う: カーソルのある行の文を名前にする(行頭の - や - [ ]、末尾の 📅 などは残す)。
// 同じ種類・同じ名前(か別名)のノートがあれば、作らずにそれにつなぐ。
// 質問はしない。作ったノートは開かない。parent には今のノートが入る。ただし、
//   - 仮説: 今のノートが仮説なら今のノート(下の仮説になる。仮説の木)。それ以外は parent をたどった先の目的。
//   - 設計案: parent は成果物の構成。目的で押せば成果物候補、設計案で押せば
//     その部分案。仮説で押したとき(たどった先が仮説のときも)は、parent にその目的、価値仮説にその仮説(この案が
//     実現する仮説)を入れる。ほかのノートでは parent をたどって最初に着く目的・仮説・設計案で同じように決める。
//     イシューで押したとき(イシューの対策で考え方の違う案を出す。)は、脅かされている設計案と
//     並ぶ候補にする: parent はその案の parent、価値仮説はその案の値を写し、previous にそのイシューを入れる。
//     脅かされているのが仮説なら、上と同じく parent に目的、価値仮説にその仮説。どちらも previous はそのイシュー。
//   - イシュー: parent ではなく 脅かす に、今のノートから上流をたどって最初に着く設計案(その案が仮説を
//     実現できるかを脅かすリスク。。K-Plex で設計案の右に出す。2026-10-28)。設計案がなければ
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


const KINDS = {
  イシュー: { type: "イシュー", template: T + "イシュー.md", folder: "03_イシュー" },
  タスク: { type: "タスク", template: T + "タスク.md", folder: "04_タスク" },
  仮説: { type: "仮説", template: T + "価値の仮説.md", folder: "01_目的" },
  設計案: { type: "設計案", template: T + "設計案.md", folder: "01_設計案" },
  目的: { type: "目的", template: T + "目的.md", folder: "01_目的" },
  ナレッジ: { type: "ナレッジ", template: T + "ナレッジ.md", folder: "05_ナレッジ" },
};

// ファイル名にできる名前か。だめなら知らせる
function nameOk(Notice, name) {
  if (!name || BAD_CHARS.test(name)) {
    new Notice("ファイル名に使えない文字(/ : * ? \" < > | # ^ [ ] や改行)が入っています");
    return false;
  }
  if (name.length > MAX_NAME) {
    new Notice(`名前が長すぎます(${MAX_NAME} 文字まで)。短くしてください`);
    return false;
  }
  return true;
}

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
    if (String(fm.type || "").trim() !== type) return false;
    return nameOf(f).toLowerCase() === key || asList(fm.aliases).some((a) => a.toLowerCase() === key);
  });
}

// [[ ]] の中の行き先から、ノートを探す
function resolve(app, target, from) {
  return app.metadataCache.getFirstLinkpathDest(target.split("|")[0].trim(), from);
}

// 属性欄の key の行を value にする。行末の説明(# …)は残す。続く `  - …` の行も置き換える。なければ type の下に足す
// (属性欄がなければ作る)。link_relation.js も使う。
function setKey(text, key, value) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return `---\n${value.startsWith("\n") ? `${key}:${value}` : `${key}: ${value}`}\n---\n` + text;
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
  return String(app.metadataCache.getFileCache(file)?.frontmatter?.type || "").trim();
}

// 属性 key に書いたリンクの先のノート
function linked(app, f, key) {
  return asList(app.metadataCache.getFileCache(f)?.frontmatter?.[key])
    .map((p) => (p.match(/\[\[([^\]]+)\]\]/) || [])[1])
    .filter((t) => t)
    .map((t) => resolve(app, t, f.path))
    .filter((d) => d);
}

// 上流のノート。parent と、イシューの 脅かす(脅かす設計案か仮説。K-Plex では相手の右に出る。)
function parentsOf(app, f) {
  return [...linked(app, f, "parent"), ...linked(app, f, "脅かす")];
}

// 今のノートから上流をたどって、いちばん近い段にある types のどれかのノートを全部返す(今のノートも含む)。
// stop の種類のノートより上へはたどらない。5段まで。
function findNearest(app, note, types, stop = []) {
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
      if (depth > 0 && stop.includes(t)) continue;
      next.push(...parentsOf(app, f));
    }
    if (hit.length) return hit;
    level = next;
  }
  return [];
}

// 今のノートか、上流をたどった先にある目的(近いもの)
function findPurpose(app, note) {
  return findNearest(app, note, ["目的"])[0] || null;
}

// 設計案の parent(成果物の構成)と 価値仮説(実現する価値の仮説。K-Plex の左に出る)。
function solutionLinks(app, note) {
  const ups = findNearest(app, note, SOLUTION_PARENTS, ["目的"]);
  const hyps = ups.filter((f) => typeOf(app, f) === "仮説");
  const parents = ups.filter((f) => typeOf(app, f) !== "仮説");
  for (const h of hyps) {
    const p = findPurpose(app, h);
    if (p && !parents.some((x) => x.path === p.path)) parents.push(p);
  }
  return { parents, hyps };
}

// イシューで Ctrl+U: 脅かされている設計案と並ぶ候補。脅かされているのが仮説なら solutionLinks と同じ
function changeLinks(app, issue) {
  const parents = [];
  const hyps = [];
  const add = (list, f) => { if (f && !list.some((x) => x.path === f.path)) list.push(f); };
  for (const t of linked(app, issue, "脅かす")) {
    const ty = typeOf(app, t);
    if (ty === "設計案") {
      linked(app, t, "parent").forEach((f) => add(parents, f));
      linked(app, t, "価値仮説")
        .filter((f) => typeOf(app, f) === "仮説").forEach((f) => add(hyps, f));
    } else if (ty === "仮説") {
      add(hyps, t);
      add(parents, findPurpose(app, t));
    }
  }
  return { parents, hyps };
}

function designParents(app, note) {
  return (typeOf(app, note) === "イシュー" ? changeLinks(app, note) : solutionLinks(app, note)).parents;
}

// イシューの parent: いちばん近い設計案候補、なければ価値の仮説
function issueParents(app, note) {
  const sol = findNearest(app, note, ["設計案"], ["目的", "仮説"]);
  return sol.length ? sol : findNearest(app, note, ["仮説"], ["目的"]);
}

// イシューの世代。同期プログラム(F-27)と同じ数え方: previous がなければ 1、
// あれば previous の先の元のイシュー(対策ならその parent のイシュー)の世代＋1。循環していれば null
function generationOf(app, issue, path) {
  if (path.includes(issue.path)) return null;
  const prev = linked(app, issue, "previous");
  if (!prev.length) return 1;
  let best = 0;
  for (const p of prev) {
    const origin = typeOf(app, p) === "イシュー" ? p : findNearest(app, p, ["イシュー"])[0];
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
  for (const f of [...findNearest(app, note, ["イシュー"], ["目的"]), findPurpose(app, note)]) {
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
    const fromIssue = typeOf(app, note) === "イシュー";
    const { parents, hyps } = fromIssue ? changeLinks(app, note) : solutionLinks(app, note);
    if (parents.length) out.parent = flow(parents.map((f) => linkOf(f)));
    if (hyps.length) out["価値仮説"] = flow(hyps.map((f) => linkOf(f)));
    if (fromIssue) out.previous = flow([here]);
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
    if (proj.length) out.project = flow(proj);
    if (COUNTERMEASURES.includes(here_type)) {
      out.previous = flow([here]);
      const source = findNearest(app, note, ["イシュー"], ["目的"])[0];
      const g = source && generationOf(app, source, []);
      if (g) out.generation = String(g + 1);
    }
    if (here_type === "ノード") out.friend = flow([here]);
  } else if (kind !== "目的") out.parent = flow([here]);
  if (kind === "目的" && project.length) out.project = flow(project);
  if (kind === "ナレッジ") {
    // 今のノート(タスク)の parent のイシュー。変化は「出荷→?」のように空けておく
    const issues = linked(app, note, "parent").filter((f) => typeOf(app, f) === "イシュー");
    if (issues.length) {
      const items = issues.map((f) => {
        const impact = String(app.metadataCache.getFileCache(f)?.frontmatter?.impact || "").trim() || "?";
        return `\n  - ${JSON.stringify(`${linkOf(f)} ${impact}→?`)}`;
      });
      out.risk_reduction = items.join("");
    }
  }
  // 共有しないメモ(type: メモ)から作ったときは、メモへのリンクを入れない。作ったノートは共有されるので、
  // メモの名前が共有に出ないようにする
  if (typeOf(app, note) === "メモ") for (const k of ["parent", "previous", "friend"]) delete out[k];
  return out;
}

// ---------- 置き場所(個人 vault も共有 vault と同じ並び。仕様書「フォルダ構成」v0.67) ----------
// <プロジェクト>/01_目的/ などに置く。ノードは 共通/02_ノード/(project を書いた部品と、見せる範囲がプロジェクト1つのノードは <プロジェクト>/02_ノード/)。決め方は同期プログラムと同じ
// (要件書 F-06): project が書いてあればそれ(2つ以上か 共通 なら 共通)、なければ parent をたどる。

const COMMON = "共通";
const TYPE_FOLDERS = ["01_目的", "01_設計案", "02_ノード", "03_イシュー", "04_タスク", "05_ナレッジ"];
const RECENT_KEY = "notebase-recent-projects";

// [[0RB001001_試しPJ|試しPJ]] や 試しPJ を、名前 試しPJ にする
function plainName(v) {
  const t = (String(v).match(/\[\[([^\]|]+)/) || [null, String(v)])[1].trim();
  return t.replace(ID_PREFIX, "");
}

function projectOfList(list) {
  const ps = asList(list).map(plainName).filter((x) => x);
  if (ps.length > 1 || ps.includes(COMMON)) return COMMON;
  return ps[0] || null;
}

// 部品でないノードの置き場所。visibility がプロジェクト名1つだけ(Internal・PIP なし)ならそれ、ほかは 共通
function nodeProject(value) {
  const list = (Array.isArray(value) ? value : value == null ? [] : [value]).map((v) => String(v).trim()).filter((v) => v);
  if (list.some((v) => v === "PIP" || v === "個人" || v === "Internal use only" || v === "社内")) return COMMON;
  const ps = [...new Set(list.filter((v) => v !== "チーム" && !v.startsWith("EXT_")))];
  return ps.length === 1 ? ps[0] : COMMON;
}

// ノートの振り分け先のプロジェクト。決まらなければ null
function projectOf(app, file, seen = new Set()) {
  if (!file || seen.has(file.path)) return null;
  seen.add(file.path);
  const fm = app.metadataCache.getFileCache(file)?.frontmatter || {};
  const t = String(fm.type || "").trim();
  // 部品(kind: 部品)だけは project のプロジェクトに置く。ほかのノードと project のない部品は 共通(v0.76)
  const part = t === "ノード" && String(fm.kind || "").trim() === "部品";
  if (t === "窓口") return COMMON;
  // 部品でないノードは、見せる範囲がプロジェクト1つだけならそのプロジェクト、ほかは 共通(v0.94)
  if (t === "ノード" && !part) return nodeProject(fm.visibility);
  if (t === "プロジェクト") return nameOf(file);
  const own = projectOfList(fm.project);
  if (own) return own;
  if (part) return COMMON;
  if (t === "イシュー" || t === "目的") return null;
  for (const p of asList(fm.parent)) {
    const target = (p.match(/\[\[([^\]]+)\]\]/) || [])[1];
    const found = target && projectOf(app, resolve(app, target, file.path), seen);
    if (found) return found;
  }
  return null;
}

// 作るノートのプロジェクト。属性に入れる値(values)から決める
function projectOfNew(app, kind, note, values) {
  if (kind === "イシュー") return projectOfList(projectFor(app, note));
  if (kind === "目的") return projectOfList(app.metadataCache.getFileCache(note)?.frontmatter?.project);
  for (const m of String(values.parent || "").matchAll(/\[\[([^\]|]+)/g)) {
    const found = projectOf(app, resolve(app, m[1], note.path));
    if (found) return found;
  }
  return null;
}

// vault にあるプロジェクトの台帳の名前(最近選んだものを先に)
function projectNames(app) {
  const names = app.vault.getMarkdownFiles()
    .filter((f) => !f.path.startsWith("99_archive/") && !f.path.startsWith("_仕組み/") && typeOf(app, f) === "プロジェクト")
    .map((f) => nameOf(f));
  let recent = [];
  try { recent = JSON.parse(window.localStorage.getItem(RECENT_KEY) || "[]"); } catch (e) { recent = []; }
  const rank = (n) => { const i = recent.indexOf(n); return i < 0 ? 999 : i; };
  return [...new Set(names)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b, "ja"));
}

// プロジェクトを選ぶ窓。Esc で閉じたら null
function chooseProject(app, obsidian, placeholder) {
  const names = projectNames(app);
  return new Promise((done) => {
    let picked = null;
    class Picker extends obsidian.FuzzySuggestModal {
      getItems() { return [...names, COMMON]; }
      getItemText(x) { return x === COMMON ? "共通(プロジェクトをまたぐもの)" : x; }
      onChooseItem(x) { picked = x; }
      onClose() { setTimeout(() => done(picked), 0); } // 選んだときは onChooseItem が閉じたあとに呼ばれる
    }
    const m = new Picker(app);
    m.setPlaceholder(placeholder);
    m.open();
  }).then((picked) => {
    if (picked && picked !== COMMON) {
      try {
        const recent = JSON.parse(window.localStorage.getItem(RECENT_KEY) || "[]").filter((x) => x !== picked);
        window.localStorage.setItem(RECENT_KEY, JSON.stringify([picked, ...recent].slice(0, 20)));
      } catch (e) { /* 覚えられなくても選んだものは使う */ }
    }
    return picked;
  });
}

// 置くフォルダ。PIP は 00_PIP/メモ。親から決まればそこ。決まらなければ選んだ範囲のプロジェクト
// (1つならそのフォルダ、Internal・2つ以上なら 共通)。範囲もなければプロジェクトを選んでもらい、Esc なら 00_inbox
async function placeFor(app, obsidian, kind, note, values, visibility, V) {
  const folder = KINDS[kind].folder;
  if (V && V.isPip(visibility)) return V.PIP_DIR;
  let project = projectOfNew(app, kind, note, values);
  if (!project && V && visibility) {
    const ps = V.projectsOf(visibility);
    values.project = flow(ps.length ? ps : [COMMON]);
    return ps.length === 1 ? `${ps[0]}/${folder}` : `${COMMON}/${folder}`;
  }
  if (!project) {
    project = await chooseProject(app, obsidian, `${kind}をどのプロジェクトに置きますか(Esc で 00_inbox へ)`);
    if (!project) return "00_inbox";
    values.project = flow([project]);
  }
  return `${project}/${folder}`;
}

// フォルダを上から順に作る(共通/02_ノード のように2段でも)
async function ensureFolder(app, path) {
  let dir = "";
  for (const part of path.split("/")) {
    dir = dir ? `${dir}/${part}` : part;
    if (!app.vault.getAbstractFileByPath(dir)) await app.vault.createFolder(dir);
  }
}

// make_note.js が置き場所を決めて作っている間の印。テンプレートの place_note.js は、この印があれば
// プロジェクトをもう一度聞かない(Esc で 00_inbox に作ったときに2回聞いていた)。
// K-Plex の QuickAdd は make_note.js を別に読み込むので、印は window に置く
const PLACING = "__notebasePlacing";
// 共有する範囲(visibility)は、押したノートから引き継ぐ。
// テンプレートの ask_visibility.js がこれを見て、あれば聞かずに使う
const INHERIT = "__notebaseVisibility";
// 種類のないノート(デイリーなど)・メモ・週報から作るときは引き継がない(窓で聞く)
const NO_INHERIT = ["", "メモ", "週報"];
const OPEN = "open";   // 押したノートに範囲が書いていない(v0.89 までのチーム・空)

function visibilityFrom(app, note, V) {
  if (NO_INHERIT.includes(typeOf(app, note))) return null;
  const list = V ? V.read(app.metadataCache.getFileCache(note)?.frontmatter?.visibility) : null;
  return list || OPEN;
}

async function createNote(tp, kind, name, note) {
  const app = tp.app;
  const k = KINDS[kind];
  const values = initialValues(app, kind, note);
  // だれに見せるか: 押したノートから引き継ぐ。デイリー・メモ・週報から作るときは、プロジェクトより先に聞き、
  // 選んだ範囲で置き場所を決める(プロジェクトは聞かない)。共有 vault では聞かない(テンプレートが Internal にする)
  const V = tp.user && tp.user.ask_visibility && tp.user.ask_visibility.pick ? tp.user.ask_visibility : null;
  let visibility = visibilityFrom(app, note, V);
  if (!visibility && V && tp.user.make_id && (await tp.user.make_id.isPersonal(app))) {
    visibility = await V.pick(app, tp.obsidian, name, projectNames(app));
  }
  const open = visibility === OPEN;
  if (open) visibility = null;
  const folderPath = await placeFor(app, tp.obsidian, kind, note, values, visibility, V);
  // 押したノートに範囲が書いていなければ、置いたプロジェクト(共通なら Internal use only)にする
  if (open && V) {
    const top = folderPath.split("/")[0];
    visibility = top === COMMON || top === "00_inbox" ? [V.INTERNAL] : [top];
  }
  // Internal use only のプロジェクトに置いたら Internal use only にする(置き場所はそのプロジェクトのまま)
  if (V && V.toScope) visibility = V.toScope(app, visibility);
  await ensureFolder(app, folderPath);
  const template = app.vault.getAbstractFileByPath(k.template);
  if (!template) throw new Error(`${k.template} がありません`);
  // テンプレートの中で id がつき、ファイル名が id_名前 に変わる
  let file;
  window[PLACING] = true;
  window[INHERIT] = visibility || null;
  try {
    file = await tp.file.create_new(template, name, false, app.vault.getAbstractFileByPath(folderPath));
  } finally {
    window[PLACING] = false;
    window[INHERIT] = null;
  }
  if (!file) return null;
  await app.vault.process(file, (text) => {
    for (const [key, value] of Object.entries(values)) text = setKey(text, key, value);
    return text;
  });
  return file;
}

// 作ったと知らせる。親が見つからなかったときは、何を書けばよいかも言う
function notifyCreated(app, Notice, kind, note, message) {
  const noParent =
    (kind === "仮説" && typeOf(app, note) !== "仮説" && !findPurpose(app, note) && "目的") ||
    (kind === "イシュー" && !issueParents(app, note).length && "設計案か価値の仮説") ||
    (kind === "設計案" && !designParents(app, note).length && "目的か上の設計案");
  if (!noParent) return new Notice(message);
  new Notice(`${message}。${noParent}が見つからなかったので、${kind === "イシュー" ? "脅かす" : "parent"} に${noParent}を書いてください`, 8000);
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

// 属性欄(プロパティ)を選んでいる・入力しているときは、本文のカーソルが別の行(見出しなど)にあり、
// そこをノートにしてしまう。そのときは何もしないで知らせる(PC 試験 2026-11-08)。
// 属性欄の中にいるか、このノートの画面の中で本文の文字の欄の外(属性欄・題名・埋め込みの一覧)にいれば止める。
// Ctrl+K・I・T・H・U・関係/反論としてつなぐで使う
function inProperties(Notice, view) {
  const el = typeof document !== "undefined" ? document.activeElement : null;
  if (!el) return false;
  const meta = el.closest && el.closest(".metadata-container");
  const text = view && view.editor && view.editor.cm && view.editor.cm.contentDOM;
  const inNote = view && view.containerEl && view.containerEl.contains && view.containerEl.contains(el);
  const outsideText = inNote && text && !text.contains(el);
  if (!meta && !outsideText) return false;
  new Notice("属性欄では使えません。本文の行で押してください");
  return true;
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
  if (inProperties(Notice, view)) return;
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
  if (!nameOk(Notice, name)) return;

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
    notifyCreated(app, Notice, kind, note, `${kind}「${name}」を作りました`);
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
  if (!name || !nameOk(Notice, name)) return null;
  const same = findSame(app, KINDS[kind].type, name);
  if (same.length) {
    new Notice(`同じ名前の${kind}がもうあります。つなぐときは本文で [[ ]] にしてください`, 6000);
    return null;
  }
  const file = await createNote(tp, kind, name, note);
  if (!file) return null;
  notifyCreated(app, Notice, kind, note, `${kind}「${name}」を「${nameOf(note)}」から作りました`);
  return file;
}

// ほかのスクリプト(link_node.js・link_relation.js・K-Plex の QuickAdd)も、tp.user.make_note から使う
Object.assign(make_note, { fromNote, inProperties, typeOf, nameOf, linkOf, asList, resolve, flow, placeLink, setKey,
  chooseProject, projectNames, ensureFolder, nameOk, TYPE_FOLDERS, COMMON, PLACING, INHERIT });
module.exports = make_note;
