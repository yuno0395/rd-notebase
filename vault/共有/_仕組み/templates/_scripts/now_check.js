// Ctrl+J「今の仕事を確かめる」(仕様書「今の仕事を確かめる」、Yu 2026-10-29 OK)。
//
// 今のタスクについて、3つの問いに ○ か × で答える。属性欄を読むだけで、ノートは書き換えない。
//   1. 目的への貢献が一番大きいか: つながるイシューの priority が、自分が手をつけられるイシューの中で一番上か
//   2. 自分で実行できるか: owner が自分(空なら author)、イシューの speed が「すぐ」、
//      タスクの status が「待ち」「確認待ち」でない
//   3. 少しチャレンジングか: つながるイシューの resolution が「未把握」か「現象」
// 今のタスク = 今日のデイリーノートのタイムラインで今の時刻の行にあるタスクへのリンク。
// なければ、開いているノート(タスクのとき)。
// × があれば、代わりに取りかかれる上位の候補を3つ出す(リンクを押すと開く)。
// チェックボックスの雑務は判定しない。判定するのはタスクのノートだけ。

const DAILY_DIR = "00_日誌/デイリー";
const CLOSED_ISSUE = ["低減済み", "解消", "中止"];
const CLOSED_TASK = ["完了", "中止"];
const BLOCKED = ["待ち", "確認待ち"];
const CHALLENGING = ["未把握", "現象"];
const NO_PRIORITY = 99;

function asList(v) {
  if (v === undefined || v === null || v === "") return [];
  return (Array.isArray(v) ? v : [v]).map((x) => String(x));
}

function plain(v) {
  // "[[0RAYFN001_Yu|Yu]]" や "Yu" を "Yu" にする
  const m = String(v).match(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/);
  const s = m ? (m[2] || m[1]) : String(v);
  return s.replace(/^[0-9A-Z]{6}[0-9A-Z]+_/, "").trim();
}

function linkTargets(v) {
  const out = [];
  for (const x of asList(v)) {
    const found = [...x.matchAll(/\[\[([^\]|#]+)/g)].map((m) => m[1].trim());
    out.push(...(found.length ? found : [x.trim()]));
  }
  return out;
}

async function myName(app) {
  const fs = app.vault.adapter;
  if (await fs.exists("_仕組み/記録/私.yaml")) {
    const m = (await fs.read("_仕組み/記録/私.yaml")).match(/^name:\s*["']?([^"'\r\n#]+)/m);
    if (m) return m[1].trim();
  }
  const dir = app.vault.configDir; // 共有・機密 vault: .obsidian-<名前>
  return dir.startsWith(".obsidian-") ? dir.slice(".obsidian-".length) : "";
}

function fmOf(app, file) {
  return app.metadataCache.getFileCache(file)?.frontmatter || {};
}

function priorityOf(fm) {
  const n = parseInt(String(fm.priority ?? "").trim(), 10);
  return Number.isFinite(n) ? n : NO_PRIORITY;
}

function people(fm, key) {
  return asList(fm[key]).map(plain).filter(Boolean);
}

function ownerOf(fm) {
  const owner = people(fm, "owner");
  return owner.length ? owner : people(fm, "author");
}

function pad(n) {
  return String(n).padStart(2, "0");
}

// 今日のデイリーノートのタイムラインで、今の時刻の行にあるタスク
async function taskFromTimeline(app) {
  const now = new Date();
  const name = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  const daily = app.vault.getAbstractFileByPath(`${DAILY_DIR}/${name}.md`);
  if (!daily) return { task: null, line: null };
  const minutes = now.getHours() * 60 + now.getMinutes();
  const text = await app.vault.cachedRead(daily);
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*[-*]\s*(?:\[.\]\s*)?(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*(.*)$/);
    if (!m) continue;
    const from = +m[1] * 60 + +m[2];
    const to = +m[3] * 60 + +m[4];
    if (minutes < from || minutes >= to) continue;
    for (const t of linkTargets(m[5])) {
      const f = app.metadataCache.getFirstLinkpathDest(t, daily.path);
      if (f && fmOf(app, f).type === "タスク") return { task: f, line: m[5].trim() };
    }
    return { task: null, line: m[5].trim() || `${m[1]}:${m[2]} - ${m[3]}:${m[4]}` };
  }
  return { task: null, line: null };
}

function issuesOf(app, task) {
  const out = [];
  for (const t of linkTargets(fmOf(app, task).parent)) {
    const f = app.metadataCache.getFirstLinkpathDest(t, task.path);
    if (f && fmOf(app, f).type === "イシュー") out.push(f);
  }
  return out;
}

function judge(app, task, issues, me, myBest) {
  const tfm = fmOf(app, task);
  const ifms = issues.map((f) => fmOf(app, f));
  const best = Math.min(NO_PRIORITY, ...ifms.map(priorityOf));
  const status = String(tfm.status || "").trim();
  const owners = ownerOf(tfm);
  const quick = ifms.some((fm) => String(fm.speed || "").trim() === "すぐ");
  const challenging = ifms.some((fm) => CHALLENGING.includes(String(fm.resolution || "").trim()));
  const q1 = issues.length > 0 && best <= myBest;
  const q2 = owners.includes(me) && quick && !BLOCKED.includes(status);
  return { best, q1, q2, q3: challenging, owners, quick, status, ifms };
}

function linkTo(app, f, from) {
  return app.fileManager.generateMarkdownLink(f, from || "");
}

async function now_check(tp) {
  const app = tp.app;
  const { Notice, Modal, MarkdownRenderer } = tp.obsidian;

  // Templater は選んでいる文字を空の文字で置き換えるので、選択をいったん外し、あとで戻す
  const ed = app.workspace.activeEditor?.editor;
  if (ed && ed.somethingSelected()) {
    const anchor = ed.getCursor("anchor");
    const head = ed.getCursor("head");
    ed.setCursor(head);
    setTimeout(() => ed.setSelection(anchor, head), 0);
  }

  const me = await myName(app);
  if (!me) {
    new Notice("自分の名前が見つかりません。_仕組み/記録/私.yaml に name を書いてください", 8000);
    return;
  }

  // 今のタスク
  const tl = await taskFromTimeline(app);
  let task = tl.task;
  let where = "タイムラインの今の時刻の行";
  if (!task) {
    const open = app.workspace.getActiveFile();
    if (open && fmOf(app, open).type === "タスク") {
      task = open;
      where = "開いているノート";
    }
  }
  if (!task) {
    const why = tl.line
      ? `今の時刻のタイムライン(${tl.line})にタスクのノートへのリンクがありません`
      : "今日のデイリーノートのタイムラインに今の時刻の行がありません";
    new Notice(`${why}。タスクのノートを開いて Ctrl+J を押してください(チェックボックスの雑務は判定しません)`, 10000);
    return;
  }

  // 自分の未完了のタスクと、自分が手をつけられるイシュー
  const files = app.vault.getMarkdownFiles();
  const myTasks = [];
  const reachable = new Set();
  for (const f of files) {
    const fm = fmOf(app, f);
    if (fm.type === "タスク" && !CLOSED_TASK.includes(String(fm.status || "").trim()) && ownerOf(fm).includes(me)) {
      const issues = issuesOf(app, f).filter((i) => !CLOSED_ISSUE.includes(String(fmOf(app, i).status || "").trim()));
      myTasks.push({ f, issues });
      issues.forEach((i) => reachable.add(i.path));
    }
    if (fm.type === "イシュー" && !CLOSED_ISSUE.includes(String(fm.status || "").trim()) && ownerOf(fm).includes(me)) {
      reachable.add(f.path);
    }
  }
  const myBest = Math.min(NO_PRIORITY, ...[...reachable].map((p) => priorityOf(fmOf(app, app.vault.getAbstractFileByPath(p)))));

  const issues = issuesOf(app, task);
  const r = judge(app, task, issues, me, myBest);
  const mark = (ok) => (ok ? "○" : "×");
  const pri = r.best === NO_PRIORITY ? "priority まだなし" : `priority ${r.best}`;
  const lines = [];
  lines.push(`今のタスク: ${linkTo(app, task)}(${where})`);
  lines.push("");
  if (!issues.length) {
    lines.push(`- × 目的への貢献: parent にイシューがありません`);
  } else {
    const top = myBest === NO_PRIORITY ? "" : `。自分が手をつけられる中の一番上は priority ${myBest}`;
    lines.push(`- ${mark(r.q1)} 目的への貢献が一番大きいか: ${issues.map((i) => linkTo(app, i, task.path)).join("、")} は ${pri}${top}`);
  }
  const why2 = [];
  if (!r.owners.includes(me)) why2.push(`担当は ${r.owners.join("・") || "空"}`);
  if (!r.quick) why2.push("イシューの speed が「すぐ」でない");
  if (BLOCKED.includes(r.status)) why2.push(`status が「${r.status}」`);
  lines.push(`- ${mark(r.q2)} 自分で実行できるか${why2.length ? ": " + why2.join("、") : ""}`);
  const res = [...new Set(r.ifms.map((fm) => String(fm.resolution || "").trim() || "空"))].join("・") || "空";
  lines.push(`- ${mark(r.q3)} 少しチャレンジングか: resolution は ${res}`);

  if (!(r.q1 && r.q2 && r.q3)) {
    const cands = myTasks
      .filter((t) => t.f.path !== task.path && t.issues.length)
      .map((t) => ({ t, j: judge(app, t.f, t.issues, me, myBest) }))
      .filter((c) => c.j.q2)
      .sort((a, b) => a.j.best - b.j.best || (b.j.q3 ? 1 : 0) - (a.j.q3 ? 1 : 0) || a.t.f.basename.localeCompare(b.t.f.basename))
      .slice(0, 3);
    lines.push("");
    if (cands.length) {
      lines.push("代わりに取りかかれる候補:");
      for (const c of cands) {
        const p = c.j.best === NO_PRIORITY ? "priority まだなし" : `priority ${c.j.best}`;
        lines.push(`1. ${linkTo(app, c.t.f)}(${p}${c.j.q3 ? "、答えがまだわかっていない" : ""})`);
      }
    } else {
      lines.push("代わりに取りかかれる自分のタスクは見つかりませんでした。上のイシューのタスクを作るか、担当を見直してください。");
    }
  }

  const md = lines.join("\n");
  class Result extends Modal {
    onOpen() {
      this.titleEl.setText("今の仕事を確かめる");
      MarkdownRenderer.render(app, md, this.contentEl, task.path, this);
      this.contentEl.addEventListener("click", (ev) => {
        const a = ev.target.closest("a.internal-link");
        if (!a) return;
        ev.preventDefault();
        app.workspace.openLinkText(a.getAttribute("data-href") || a.textContent, task.path, false);
        this.close();
      });
    }
    onClose() {
      this.contentEl.empty();
    }
  }
  new Result(app).open();
}

module.exports = now_check;
