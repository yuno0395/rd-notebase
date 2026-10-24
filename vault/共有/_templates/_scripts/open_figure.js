// Alt+D: 開いているノートの図を開く。なければ作る(仕様書「図とパワーポイント」)。
// 図は _attachments/<id>/図.excalidraw.md。ひな形は _templates/図.excalidraw.md(16:9 の枠1つ)。
// 初めて作ったとき、カーソルの位置に1枚目のフレームを引用するウィキリンクを入れる。
// 2回目からは図を開くだけ。2枚目からは、Excalidraw でフレームを選び「フレームへのリンクをコピー」で貼る。

const FIG_TEMPLATE = "_templates/図.excalidraw.md";
const FIRST_FRAME = "frame1"; // ひな形のフレームの id

async function open_figure(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const note = app.workspace.getActiveFile();
  if (!note || note.extension !== "md") {
    new Notice("ノートを開いてから Alt+D を押してください");
    return;
  }
  if (note.path.endsWith(".excalidraw.md")) {
    new Notice("図の中では使えません");
    return;
  }
  const id = app.metadataCache.getFileCache(note)?.frontmatter?.id;
  if (!id) {
    new Notice("このノートには id がありません。Ctrl+N で作ったノートで使ってください");
    return;
  }
  const dir = `_attachments/${id}`;
  const path = `${dir}/図.excalidraw.md`;
  let fig = app.vault.getAbstractFileByPath(path);
  if (!fig) {
    if (!app.vault.getAbstractFileByPath(dir)) await app.vault.createFolder(dir);
    fig = await app.vault.create(path, await app.vault.adapter.read(FIG_TEMPLATE));
    addEmbed(app, note, `![[${dir}/図.excalidraw#^frame=${FIRST_FRAME}]]`);
  }
  const leaf = app.workspace.getLeaf("split", "vertical");
  await leaf.setViewState({ type: "excalidraw", state: { file: fig.path }, active: true });
}

// カーソルの位置に引用を入れる(図は説明の途中につける)。
// 引用は独立した1行にする。同じ行に文字や見出しがあると、改行をはさむ。
function addEmbed(app, note, line) {
  const view = app.workspace.activeEditor;
  if (view?.file === note && view.editor) {
    const ed = view.editor;
    const from = ed.getCursor("from");
    const to = ed.getCursor("to");
    const before = ed.getLine(from.line).slice(0, from.ch);
    const after = ed.getLine(to.line).slice(to.ch);
    ed.replaceSelection((before.trim() ? "\n" : "") + line + (after.trim() ? "\n" : ""));
    return;
  }
  return app.vault.process(note, (text) => text.replace(/\s*$/, "\n\n" + line + "\n"));
}

module.exports = open_figure;
