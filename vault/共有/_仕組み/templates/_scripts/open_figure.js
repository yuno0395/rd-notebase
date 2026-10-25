// Ctrl+D: 開いているノートの図を開く。なければ作る(仕様書「図とパワーポイント」)。
// 図は _仕組み/attachments/<id>/図.excalidraw.md。ひな形はノートの種類で選ぶ(なければ 図.excalidraw.md の 16:9 の枠1つ)。
//   ナレッジ       → ナレッジ図.excalidraw.md(1枚目 実施前・やったこと・実施後、2枚目 トレードオフ曲線)
//   ソリューション → トレードオフ曲線.excalidraw.md
// 初めて作ったとき、ひな形の枠ごとに引用のウィキリンクを入れる。枠の名前と同じ見出し(下の表)があれば
// その見出しの説明の行の下に入れる。見出しがなければ、1枚目だけカーソルの位置に入れる。2回目からは図を開くだけ。
// 2枚目を自分で足したときは、Excalidraw でフレームを選び「フレームへのリンクをコピー」で貼る。

const FIG_TEMPLATE = "_仕組み/templates/図.excalidraw.md";
const TEMPLATES = {
  "ナレッジ": "_仕組み/templates/ナレッジ図.excalidraw.md",
  "ソリューション": "_仕組み/templates/トレードオフ曲線.excalidraw.md",
  "設計記録": "_仕組み/templates/トレードオフ曲線.excalidraw.md",
};
// 枠の名前 → 引用を入れる見出し(左から探す)
const HEADINGS = {
  "ナレッジ図": ["ナレッジ図"],
  "トレードオフ曲線": ["トレードオフ曲線", "どの条件ならこの案が勝つか"],
};

async function open_figure(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const note = app.workspace.getActiveFile();
  if (!note || note.extension !== "md") {
    new Notice("ノートを開いてから Ctrl+D を押してください");
    return;
  }
  if (note.path.endsWith(".excalidraw.md")) {
    new Notice("図の中では使えません");
    return;
  }
  const fm = app.metadataCache.getFileCache(note)?.frontmatter;
  const id = fm?.id;
  if (!id) {
    new Notice("このノートには id がありません。Ctrl+N で作ったノートで使ってください");
    return;
  }
  const dir = `_仕組み/attachments/${id}`;
  const path = `${dir}/図.excalidraw.md`;
  let fig = app.vault.getAbstractFileByPath(path);
  if (!fig) {
    let tpl = TEMPLATES[fm?.type];
    if (!tpl || !app.vault.getAbstractFileByPath(tpl)) tpl = FIG_TEMPLATE; // 機密 vault などひな形がないとき
    const src = await app.vault.adapter.read(tpl);
    if (!app.vault.getAbstractFileByPath(dir)) await app.vault.createFolder(dir);
    fig = await app.vault.create(path, src);
    await addEmbeds(app, note, `${dir}/図.excalidraw`, frames(src));
  }
  const leaf = app.workspace.getLeaf("split", "vertical");
  await leaf.setViewState({ type: "excalidraw", state: { file: fig.path }, active: true });
}

// ひな形の枠(id と名前)を並び順に返す。読めなければ1枚目だけ。
function frames(src) {
  try {
    const json = JSON.parse(src.match(/```json\n([\s\S]*?)\n```/)[1]);
    const list = json.elements.filter((e) => e.type === "frame" && !e.isDeleted).map((e) => ({ id: e.id, name: e.name || "" }));
    if (list.length) return list;
  } catch (e) {}
  return [{ id: "frame1", name: "" }];
}

// 枠ごとに引用を入れる。見出しが合えばその下、合わなければカーソルの位置(図は説明の途中につける)。
async function addEmbeds(app, note, figLink, list) {
  const atCursor = [];
  const underHeading = [];
  const view = app.workspace.activeEditor;
  const ed = view?.file === note ? view.editor : null;
  const text = ed ? ed.getValue() : await app.vault.read(note);
  list.forEach((f, i) => {
    const line = `![[${figLink}#^clippedframe=${f.id}]]`;
    const h = (HEADINGS[f.name] || []).find((name) => findHeading(text, name) >= 0);
    if (h) underHeading.push({ heading: h, line });
    else if (i === 0) atCursor.push(line); // 2枚目からは見出しがなければ入れない(見出しを消した人には要らない)
  });
  // 開いているノートはエディタ経由で直す(保存前の内容と食い違わないよう)
  for (const { heading, line } of underHeading) {
    if (ed) {
      const lines = ed.getValue().split("\n");
      const at = insertLine(lines, heading);
      ed.replaceRange(line + "\n", { line: at, ch: 0 });
    } else {
      await app.vault.process(note, (t) => {
        const lines = t.split("\n");
        lines.splice(insertLine(lines, heading), 0, line);
        return lines.join("\n");
      });
    }
  }
  if (!atCursor.length) return;
  const block = atCursor.join("\n");
  if (ed) {
    const from = ed.getCursor("from");
    const to = ed.getCursor("to");
    const before = ed.getLine(from.line).slice(0, from.ch);
    const after = ed.getLine(to.line).slice(to.ch);
    ed.replaceSelection((before.trim() ? "\n" : "") + block + (after.trim() ? "\n" : ""));
    return;
  }
  await app.vault.process(note, (t) => t.replace(/\s*$/, "\n\n" + block + "\n"));
}

function findHeading(text, name) {
  return text.split("\n").findIndex((l) => l.trim() === `## ${name}`);
}

// 見出しの次の行が説明(見出しでも引用でもない1行)なら、その下。なければ見出しのすぐ下。
function insertLine(lines, name) {
  const i = lines.findIndex((l) => l.trim() === `## ${name}`);
  const next = lines[i + 1];
  if (next !== undefined && next.trim() && !next.startsWith("#") && !next.startsWith("![[")) return i + 2;
  return i + 1;
}

module.exports = open_figure;
