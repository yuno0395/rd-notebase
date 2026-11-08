// Ctrl+D: 開いているノートの図を開く。なければ作る(仕様書「図とパワーポイント」)。
// 図は _仕組み/attachments/<id>/fig_<ノートのファイル名>.excalidraw.md(タブで何の図か分かるように。)。
// 例 0RDGPG4XGV_保圧を変えて試作する.md → fig_0RDGPG4XGV_保圧を変えて試作する.excalidraw.md
// ノートの名前を変える前の fig_ の図は、開くときにいまの名前へ変える
// (Obsidian の名前の変更なので、ノートの引用も直る。書き出した SVG・PNG も同じ名前にする)。
// 同期のあとでも、同期プログラムが共有の古い名前の図を消すので二重にならない(要件書 F-51)。
// ひな形は種類にかかわらず 図.excalidraw.md(16:9 の枠「Summary」1つ。)。
// 初めて作ったとき、枠「Summary」の引用のウィキリンクをカーソルの位置に入れる。2回目からは図を開くだけ。
// 2枚目を自分で足したときは、Excalidraw でフレームを選び「フレームへのリンクをコピー」で貼る。
// 部品のノート(kind: 部品)・設計案・ナレッジか、属性欄に image の行があるノートで、image が空なら、図の書き出し fig_<ノートのファイル名>.excalidraw.svg へのリンクを入れる
// (Excalidraw は fig_….excalidraw.md の .md を .svg に変えた名前で書き出す)。
// 部品一覧のカードの概略図になる(Bases のカードは Excalidraw の枠を描けないので、Excalidraw が保存のたびに書き出す SVG を使う。)。

const FIG_TEMPLATE = "_仕組み/templates/図.excalidraw.md";
const SUMMARY = "Summary";

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
  const name = `fig_${note.basename}`;
  const path = `${dir}/${name}.excalidraw.md`;
  let fig = findFigure(app, dir, path, id);
  // 他の人のノート(author に自分がいない)の図は、名前を変えずに開くだけ(書いた人の側で変わって届く)。
  // 図がなければ作らない(作っても共有へは出ないため)
  const O = tp.user.others_note;
  const theirs = O && O.isTheirs(app, note, await O.myName(app));
  if (fig && fig.path !== path && !theirs) fig = await renameFigure(app, fig, dir, name);
  if (!fig && theirs) {
    new Notice("他の人のノートなので、図は作りません。書き足すときは「自分も作成者に入れて書く」を押してから Ctrl+D");
    return;
  }
  if (!fig) {
    const src = await app.vault.adapter.read(FIG_TEMPLATE);
    if (!app.vault.getAbstractFileByPath(dir)) await app.vault.createFolder(dir);
    fig = await app.vault.create(path, src);
    await addEmbed(app, note, `![[${dir}/${name}.excalidraw#^clippedframe=${summaryFrame(src)}]]`);
  }
  if (!theirs) await fillImage(app, note, `${dir}/${name}.excalidraw.svg`, `${dir}/${name}.svg`);
  const leaf = app.workspace.getLeaf("split", "vertical");
  await leaf.setViewState({ type: "excalidraw", state: { file: fig.path }, active: true });
}

// いまの名前 → 同じ id の fig_ の図(ノートの名前を変えた後)の順に探す。
function findFigure(app, dir, path, id) {
  const exact = app.vault.getAbstractFileByPath(path);
  if (exact) return exact;
  const folder = app.vault.getAbstractFileByPath(dir);
  const figs = (folder?.children || [])
    .filter((f) => f.name.startsWith("fig_") && f.name.endsWith(".excalidraw.md"))
    .sort((a, b) => (b.name.startsWith(`fig_${id}`) - a.name.startsWith(`fig_${id}`)) || a.name.localeCompare(b.name));
  return figs[0] || null;
}

// 古い名前の図をいまの名前にする。先に SVG・PNG を変える(Excalidraw が名前をそろえる設定でも重ならない)。
async function renameFigure(app, fig, dir, name) {
  const oldBase = fig.path.slice(0, -".md".length);   // fig_….excalidraw(書き出しは fig_….excalidraw.svg など)
  try {
    for (const ext of [".svg", ".png", ".dark.svg", ".light.svg", ".dark.png", ".light.png"]) {
      const f = app.vault.getAbstractFileByPath(oldBase + ext);
      const to = `${dir}/${name}.excalidraw${ext}`;
      if (f && !app.vault.getAbstractFileByPath(to)) await app.fileManager.renameFile(f, to);
    }
    await app.fileManager.renameFile(fig, `${dir}/${name}.excalidraw.md`);
    return app.vault.getAbstractFileByPath(`${dir}/${name}.excalidraw.md`) || fig;
  } catch (e) {
    return app.vault.getAbstractFileByPath(fig.path) || fig; // 変えられなくても開く
  }
}

// image が空なら、図の SVG へのリンクを入れる。ほかの値が書いてあれば変えない。
// エディタで開いているときはエディタの行を直す(ファイルを直接書き換えると、Ctrl+D のテンプレートの挿入が
// 開いている古い中身で上書きし、書いた image が消えるため)。
// wrong は前の版が入れていた間違った名前(fig_….svg)。それが入っていたら正しい名前に直す。
async function fillImage(app, note, svg, wrong) {
  const fm = app.metadataCache.getFileCache(note)?.frontmatter || {};
  const has = Object.prototype.hasOwnProperty.call(fm, "image");
  const card = String(fm.kind || "").trim() === "部品" || ["設計案", "ナレッジ"].includes(String(fm.type || "").trim());
  if (!has && !card) return;   // 一覧をカードで見る種類だけ(前からあるノートで image の行がなくても足す)
  const now = String(fm.image ?? "").trim();
  if (now && now !== `[[${wrong}]]`) return;
  const value = `image: "[[${svg}]]"`;
  const view = app.workspace.activeEditor;
  const ed = view?.file === note ? view.editor : null;
  if (ed && ed.getLine(0).trim() === "---") {
    let end = -1;
    for (let i = 1; i < ed.lineCount(); i++) if (ed.getLine(i).trim() === "---") { end = i; break; }
    if (end > 0) {
      for (let i = 1; i < end; i++) {
        const line = ed.getLine(i);
        if (/^image\s*:/.test(line)) {
          ed.replaceRange(value, { line: i, ch: 0 }, { line: i, ch: line.length });
          return;
        }
      }
      ed.replaceRange(value + "\n", { line: end, ch: 0 });
      return;
    }
  }
  await app.fileManager.processFrontMatter(note, (f) => { f.image = `[[${svg}]]`; });
}

// ひな形の枠「Summary」の id。なければ最初の枠、読めなければ frame1。
function summaryFrame(src) {
  try {
    const json = JSON.parse(src.match(/```json\n([\s\S]*?)\n```/)[1]);
    const list = json.elements.filter((e) => e.type === "frame" && !e.isDeleted);
    const f = list.find((e) => e.name === SUMMARY) || list[0];
    if (f) return f.id;
  } catch (e) {}
  return "frame1";
}

// 引用をカーソルの位置に入れる(図は説明の途中につける)。エディタで開いていなければ末尾に足す。
async function addEmbed(app, note, line) {
  const view = app.workspace.activeEditor;
  const ed = view?.file === note ? view.editor : null;
  if (ed) {
    const from = ed.getCursor("from");
    const to = ed.getCursor("to");
    const before = ed.getLine(from.line).slice(0, from.ch);
    const after = ed.getLine(to.line).slice(to.ch);
    ed.replaceSelection((before.trim() ? "\n" : "") + line + (after.trim() ? "\n" : ""));
    return;
  }
  await app.vault.process(note, (t) => t.replace(/\s*$/, "\n\n" + line + "\n"));
}

module.exports = open_figure;
