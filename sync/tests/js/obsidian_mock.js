// Obsidian と Templater のまね(テスト用)。テンプレートとスクリプト(_仕組み/templates/_scripts/*.js)を
// node で動かし、どのフォルダにどんなノートができるかを確かめる(作業の決まり R-10)。
// 本物と同じにするのは、スクリプトが使うところだけ。属性欄の読み方は簡単なもの(入れ子は読まない。R-03)。

"use strict";
const fs = require("fs");
const path = require("path");

// ---------- 属性欄 ----------

function stripComment(v) {
  // 引用符の外の「 #」から後ろは説明
  let q = null;
  for (let i = 0; i < v.length; i++) {
    const c = v[i];
    if (q) { if (c === q) q = null; continue; }
    if (c === '"' || c === "'") q = c;
    else if (c === "#" && (i === 0 || /\s/.test(v[i - 1]))) return v.slice(0, i).trim();
  }
  return v.trim();
}

function scalar(v) {
  v = v.trim();
  if (v === "") return null;
  if (v.startsWith('"')) { try { return JSON.parse(v); } catch (e) { return v; } } // テンプレートの <% %> の中など
  if (v.startsWith("'")) return v.slice(1, -1).replace(/''/g, "'");
  return v;
}

function splitFlow(inner) {
  const out = [];
  let cur = "", q = null, depth = 0;
  for (const c of inner) {
    if (q) { cur += c; if (c === q) q = null; continue; }
    if (c === '"' || c === "'") { q = c; cur += c; continue; }
    if (c === "[") depth++;
    if (c === "]") depth--;
    if (c === "," && depth === 0) { out.push(cur); cur = ""; continue; }
    cur += c;
  }
  if (cur.trim()) out.push(cur);
  return out.map(scalar).filter((x) => x !== null);
}

function parseFrontmatter(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return null;
  const fm = {};
  let last = null;
  for (const line of m[1].split(/\r?\n/)) {
    if (!line.trim()) continue;
    const item = line.match(/^\s+-\s+(.*)$/) || line.match(/^-\s+(.*)$/);
    if (item && last) {
      if (!Array.isArray(fm[last])) fm[last] = [];
      fm[last].push(scalar(stripComment(item[1])));
      continue;
    }
    const kv = line.match(/^([^\s:#][^:]*?)\s*:(.*)$/);
    if (!kv) continue;
    last = kv[1];
    const v = stripComment(kv[2]);
    fm[last] = v.startsWith("[") && v.endsWith("]") ? splitFlow(v.slice(1, -1)) : scalar(v);
  }
  return fm;
}

// ---------- vault ----------

class TFile {
  constructor(p) { this.setPath(p); }
  setPath(p) {
    this.path = p;
    this.name = p.split("/").pop();
    const dot = this.name.lastIndexOf(".");
    this.basename = dot > 0 ? this.name.slice(0, dot) : this.name;
    this.extension = dot > 0 ? this.name.slice(dot + 1) : "";
  }
  get parent() { return this._vault.folder(path.posix.dirname(this.path)); }
}

class TFolder {
  constructor(vault, p) { this._vault = vault; this.path = p; this.name = p.split("/").pop(); }
  get children() {
    const pre = this.path === "/" ? "" : this.path + "/";
    const direct = (p) => p.startsWith(pre) && !p.slice(pre.length).includes("/");
    return [
      ...[...this._vault.folders].filter(direct).map((p) => new TFolder(this._vault, p)),
      ...[...this._vault.files.values()].filter((f) => direct(f.path)),
    ];
  }
}

class Vault {
  constructor(app, configDir) {
    this.app = app;
    this.configDir = configDir;
    this.files = new Map(); // path → TFile
    this.data = new Map();  // path → 中身
    this.folders = new Set();
    this.adapter = {
      exists: async (p) => this.data.has(p) || this.folders.has(p),
      read: async (p) => { if (!this.data.has(p)) throw new Error(`ない: ${p}`); return this.data.get(p); },
      write: async (p, t) => this._write(p, t),
      append: async (p, t) => this._write(p, (this.data.get(p) || "") + t),
      getBasePath: () => "/vault",
    };
  }
  folder(p) { return p === "." || p === "" ? new TFolder(this, "/") : this.folders.has(p) ? new TFolder(this, p) : null; }
  _write(p, text) {
    const dir = path.posix.dirname(p);
    if (dir !== "." && !this.folders.has(dir)) throw new Error(`フォルダがありません: ${dir}(${p})`);
    if (!this.files.has(p)) { const f = new TFile(p); f._vault = this; this.files.set(p, f); }
    this.data.set(p, text);
    this.app.metadataCache._update(p);
    return this.files.get(p);
  }
  seed(p, text) {
    const parts = p.split("/");
    for (let i = 1; i < parts.length; i++) this.folders.add(parts.slice(0, i).join("/"));
    return this._write(p, text);
  }
  getFiles() { return [...this.files.values()]; }
  getMarkdownFiles() { return this.getFiles().filter((f) => f.extension === "md"); }
  getAbstractFileByPath(p) { return this.files.get(p) || (this.folders.has(p) ? new TFolder(this, p) : null); }
  async create(p, text) {
    if (this.files.has(p)) throw new Error(`もうあります: ${p}`);
    return this._write(p, text);
  }
  async createFolder(p) {
    if (this.folders.has(p)) throw new Error(`Folder already exists: ${p}`);
    this.folders.add(p);
    const parts = p.split("/");
    for (let i = 1; i < parts.length; i++) this.folders.add(parts.slice(0, i).join("/"));
  }
  async read(f) { return this.data.get(f.path); }
  async process(f, fn) { const t = fn(this.data.get(f.path)); this._write(f.path, t); return t; }
  async delete(f) {
    if (f instanceof TFolder) { this.folders.delete(f.path); return; }
    this.files.delete(f.path); this.data.delete(f.path);
  }
  async rename(f, to) {
    if (this.files.has(to)) throw new Error(`もうあります: ${to}`);
    const dir = path.posix.dirname(to);
    if (dir !== "." && !this.folders.has(dir)) throw new Error(`フォルダがありません: ${dir}`);
    const text = this.data.get(f.path);
    this.files.delete(f.path); this.data.delete(f.path);
    this.app.metadataCache.cache.delete(f.path);
    f.setPath(to);
    this.files.set(to, f); this.data.set(to, text);
    this.app.metadataCache._update(to);
  }
}

class MetadataCache {
  constructor(app) { this.app = app; this.cache = new Map(); }
  _update(p) {
    if (!p.endsWith(".md")) return;
    const fm = parseFrontmatter(this.app.vault.data.get(p) || "");
    this.cache.set(p, fm ? { frontmatter: fm } : {});
  }
  getFileCache(f) { return f ? this.cache.get(f.path) || null : null; }
  getFirstLinkpathDest(link, from) {
    const t = link.split("#")[0].trim();
    if (!t) return null;
    const files = this.app.vault.getFiles();
    return files.find((f) => f.path === t || f.path === t + ".md") ||
      files.find((f) => f.basename === t || f.name === t) || null;
  }
}

// ---------- エディタ(開いているノートの中身はファイルと同じ) ----------

class Editor {
  constructor(app, file) { this.app = app; this.file = file; this.anchor = { line: 0, ch: 0 }; this.head = { line: 0, ch: 0 }; }
  get lines() { return this.app.vault.data.get(this.file.path).split("\n"); }
  getValue() { return this.lines.join("\n"); }
  lineCount() { return this.lines.length; }
  getLine(n) { return this.lines[n] ?? ""; }
  off(pos) { const ls = this.lines; let o = 0; for (let i = 0; i < pos.line; i++) o += ls[i].length + 1; return o + pos.ch; }
  order() { return this.off(this.anchor) <= this.off(this.head) ? [this.anchor, this.head] : [this.head, this.anchor]; }
  getCursor(which) {
    const [a, b] = this.order();
    if (which === "from") return { ...a };
    if (which === "to") return { ...b };
    if (which === "anchor") return { ...this.anchor };
    return { ...this.head };
  }
  setCursor(pos) { this.anchor = { ...pos }; this.head = { ...pos }; }
  setSelection(a, b) { this.anchor = { ...a }; this.head = { ...(b || a) }; }
  somethingSelected() { return this.off(this.anchor) !== this.off(this.head); }
  getRange(a, b) { return this.getValue().slice(this.off(a), this.off(b)); }
  getSelection() { const [a, b] = this.order(); return this.getRange(a, b); }
  replaceRange(text, a, b) {
    const v = this.getValue();
    const s = this.off(a), e = this.off(b || a);
    this.app.vault._write(this.file.path, v.slice(0, s) + text + v.slice(e));
  }
  replaceSelection(text) { const [a, b] = this.order(); this.replaceRange(text, a, b); }
  focus() {}
}

// ---------- 画面(窓・知らせ) ----------

function makeObsidian(app) {
  class Notice {
    constructor(msg) { app.notices.push(String(msg)); }
    hide() {}
  }
  // 窓は app.answers の先頭の答えで閉じる(null は Esc)。選ぶ前に onChoose、そのあと onClose
  class Modal {
    constructor(a) { this.app = a; }
    setPlaceholder(t) { this.placeholder = t; }
    open() {
      app.prompts.push(this.placeholder || "");
      if (!app.answers.length) throw new Error(`答えを用意していない窓: ${this.placeholder}`);
      const ans = app.answers.shift();
      if (ans !== null) this.choose(ans);
      this.onClose();
    }
  }
  class FuzzySuggestModal extends Modal {
    choose(ans) {
      const items = this.getItems();
      if (!items.includes(ans)) throw new Error(`窓に ${ans} がない: ${items.join(",")}`);
      this.onChooseItem(ans);
    }
  }
  class SuggestModal extends Modal {
    // 打った文字で出る候補のうち、同じ名前のもの(なければ一番下の「新しく作る」)を選ぶ
    choose(ans) {
      const hits = this.getSuggestions(ans);
      this.onChooseSuggestion(hits.find((h) => h.shown === ans) || hits[hits.length - 1]);
    }
  }
  return { Notice, FuzzySuggestModal, SuggestModal };
}

// ---------- Templater ----------

function compile(src) {
  // <%* code %> はそのまま、<% expr %> は出力、-%> は後ろの改行を消す
  let body = "";
  let i = 0;
  const re = /<%([*_-]?)([\s\S]*?)(-?)%>/g;
  let m;
  let trimNext = false;
  while ((m = re.exec(src))) {
    let lit = src.slice(i, m.index);
    if (trimNext) lit = lit.replace(/^\r?\n/, "");
    body += `tR += ${JSON.stringify(lit)};\n`;
    if (m[1] === "*") body += m[2] + "\n";
    else body += `tR += String(await (${m[2].trim()}));\n`;
    trimNext = m[3] === "-";
    i = re.lastIndex;
  }
  let rest = src.slice(i);
  if (trimNext) rest = rest.replace(/^\r?\n/, "");
  body += `tR += ${JSON.stringify(rest)};\nreturn tR;`;
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  return new AsyncFunction("tp", "tR", body);
}

function pad(n) { return String(n).padStart(2, "0"); }
function dateNow(fmt, offset) {
  const d = new Date(Date.now() + (offset || 0) * 86400000);
  return fmt.replace("YYYY", d.getFullYear()).replace("MM", pad(d.getMonth() + 1)).replace("DD", pad(d.getDate()));
}

function loadScript(app, p) {
  const src = app.vault.data.get(p);
  const mod = { exports: {} };
  new Function("module", "exports", "window", "require", src)(mod, mod.exports, app.window, () => { throw new Error("require は使えない"); });
  return mod.exports;
}

class Templater {
  constructor(app, scriptsDir) { this.app = app; this.scriptsDir = scriptsDir; }
  user() {
    // 本物と同じく、呼ぶたびに読み込む
    const out = {};
    for (const p of this.app.vault.data.keys()) {
      if (p.startsWith(this.scriptsDir + "/") && p.endsWith(".js")) out[path.posix.basename(p, ".js")] = loadScript(this.app, p);
    }
    return out;
  }
  tp(target, template) {
    const app = this.app;
    const self = this;
    const tp = {
      app,
      obsidian: app.obsidian,
      user: this.user(),
      config: { target_file: target, template_file: template },
      date: { now: (fmt, offset) => dateNow(fmt, offset) },
      file: {
        get title() { return target.basename; },
        get path() { return target.path; },
        rename: async (name) => app.vault.rename(target, `${path.posix.dirname(target.path)}/${name}.md`.replace(/^\.\//, "")),
        move: async (p) => app.vault.rename(target, `${p}.md`),
        create_new: (tpl, name, open, folder) => self.createNew(tpl, folder, name, open),
      },
    };
    return tp;
  }
  async run(template, target) {
    const fn = compile(this.app.vault.data.get(template.path));
    return fn(this.tp(target, template), "");
  }
  // Templater の create_new_note_from_template と同じ順: 空のファイルを作り、テンプレートを当てて書く
  async createNew(template, folder, name, open) {
    const dir = folder ? folder.path : "";
    if (dir && dir !== "/" && !this.app.vault.folders.has(dir)) throw new Error(`フォルダがありません: ${dir}`);
    let p = `${dir && dir !== "/" ? dir + "/" : ""}${name || "無題"}.md`;
    const file = await this.app.vault.create(p, "");
    const text = await this.run(template, file);
    this.app.vault._write(file.path, text);
    this.app.created.push(file.path);
    return file;
  }
  // 開いているノートで _コマンド/ のテンプレートを当てる(キーを押したとき)
  async command(name) {
    const t = this.app.vault.getAbstractFileByPath(`_仕組み/templates/_コマンド/${name}.md`);
    if (!t) throw new Error(`コマンドがない: ${name}`);
    const ed = this.app.workspace.activeEditor.editor;
    const out = await this.run(t, this.app.workspace.activeEditor.file);
    // 本物の Templater は選んでいる文字を出力で置き換える
    ed.replaceSelection(out);
  }
}

// ---------- 組み立て ----------

function readTree(dir) {
  const out = {};
  const walk = (d, rel) => {
    for (const e of fs.readdirSync(d, { withFileTypes: true })) {
      const r = rel ? `${rel}/${e.name}` : e.name;
      if (e.isDirectory()) walk(path.join(d, e.name), r);
      else out[r] = fs.readFileSync(path.join(d, e.name), "utf8");
    }
  };
  walk(dir, "");
  return out;
}

function makeApp({ templatesDir, configDir = ".obsidian", files = {} }) {
  const app = { notices: [], prompts: [], answers: [], created: [] };
  app.window = { localStorage: { getItem: () => null, setItem() {} } };
  app.vault = new Vault(app, configDir);
  app.metadataCache = new MetadataCache(app);
  app.obsidian = makeObsidian(app);
  for (const [rel, text] of Object.entries(readTree(templatesDir))) app.vault.seed(`_仕組み/templates/${rel}`, text);
  for (const [p, text] of Object.entries(files)) {
    if (text === undefined) continue;
    if (p.endsWith("/")) app.vault.folders.add(p.slice(0, -1));
    else app.vault.seed(p, text);
  }
  app.fileManager = {
    renameFile: (f, to) => app.vault.rename(f, to),
  };
  app.workspace = {
    activeEditor: null,
    getActiveFile: () => app.workspace.activeEditor?.file || null,
    getLeaf: () => leaf(),
    getMostRecentLeaf: () => leaf(),
    getLeavesOfType: () => [],
    on: (name) => { app.watching = name; return name; },
    offref: () => {},
    setActiveLeaf: () => {},
    // 図を開く向き(Ctrl+D)。direction は "horizontal"(上下)か "vertical"(左右)
    createLeafBySplit: (from, direction, before) => { app.split = { direction, before }; return leaf(); },
  };
  function leaf() {
    return {
      setViewState: async (s) => { app.opened = s.state.file; },
      setDimension: (n) => { (app.dimensions ||= []).push(n); },
    };
  }
  app.templater = new Templater(app, "_仕組み/templates/_scripts");
  const templater = { create_new_note_from_template: (tpl, folder, name, open) => app.templater.createNew(tpl, folder, name, open) };
  app.plugins = {
    plugins: { "templater-obsidian": { templater } },
    getPlugin: (id) => app.plugins.plugins[id] || null,
  };
  // ノートを開き、cursor の文字を選ぶ(cursor は { line, ch, to? })
  app.open = (p, sel) => {
    const file = app.vault.getAbstractFileByPath(p);
    const ed = new Editor(app, file);
    app.workspace.activeEditor = { file, editor: ed };
    if (sel) ed.setSelection({ line: sel.line, ch: sel.ch }, { line: sel.line, ch: sel.to ?? sel.ch });
    return ed;
  };
  app.fm = (p) => app.metadataCache.getFileCache(app.vault.getAbstractFileByPath(p))?.frontmatter;
  app.text = (p) => app.vault.data.get(p);
  app.find = (re) => [...app.vault.files.keys()].filter((p) => re.test(p));
  // QuickAdd の「新しいノート」: folder に作り、テンプレートを当てる
  app.quickAdd = async (templateName, folder, name) => {
    const tpl = app.vault.getAbstractFileByPath(`_仕組み/templates/${templateName}.md`);
    if (!app.vault.folders.has(folder)) await app.vault.createFolder(folder);
    return app.templater.createNew(tpl, app.vault.folder(folder), name, false);
  };
  return app;
}

module.exports = { makeApp };
