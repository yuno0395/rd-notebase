// Ctrl+D: 開いているノートの図を開く。なければ作る(仕様書「図とパワーポイント」)。
// 図はノートの下に大きめに開く(figure_place・figure_size で変えられる)。
// 図は _仕組み/attachments/<id>/fig_<ノートのファイル名>.excalidraw.md(タブで何の図か分かるように。)。
// 例 0RDGPG4XGV_保圧を変えて試作する.md → fig_0RDGPG4XGV_保圧を変えて試作する.excalidraw.md
// 図は初めて押したときに作り、枠「Summary」の引用のウィキリンクを本文の先頭(属性欄のすぐ後)に入れる。2回目からは図を開くだけ
// (ノートを作るときに自動で作る案は採らなかった。)。
// 図を作るとき、まだ書き出していない SVG の代わりに白い 16:9 の SVG を置く(image のリンク先がないと、
// Ctrl+S やグラフに「まだないファイル」と出るため)。Excalidraw が図を保存すると上書きする。
// ノートの名前を変える前の fig_ の図は、開くときにいまの名前へ変える
// (Obsidian の名前の変更なので、ノートの引用も直る。書き出した SVG・PNG も同じ名前にする)。
// 同期のあとでも、同期プログラムが共有の古い名前の図を消すので二重にならない(要件書 F-51)。
// ひな形は種類にかかわらず 図.excalidraw.md(16:9 の枠「Summary」1つ。)。
// 2枚目を自分で足したときは、Excalidraw でフレームを選び「フレームへのリンクをコピー」で貼る。
// どの種類のノートでも、image が空か古い名前の図を指していれば、図の書き出し fig_<ノートのファイル名>.excalidraw.svg
// へのリンクを入れる(Excalidraw は fig_….excalidraw.md の .md を .svg に変えた名前で書き出す)。
// 一覧のカードの図になる(Bases のカードは Excalidraw の枠を描けないので、Excalidraw が保存のたびに書き出す SVG を使う。
// 「タスクなど、あらゆるノートを部品のように画像で視認できるようにしたい」)。

const FIG_TEMPLATE = "_仕組み/templates/図.excalidraw.md";
// 図の開き方。
// 個人 vault の _仕組み/個人設定.md の属性で変えられる(書いていなければこの値)。開いたあとは境目をドラッグして変えてもよい。
//   figure_place: 下 / 上 / 右 / 左  … 図をノートのどちら側に開くか
//   figure_size:  図の大きさ(画面のうち図が占める割合、10〜90 の %)
const MY_SETTINGS = "_仕組み/個人設定.md";
const PLACE = "下";
const SIZE = 70;
const SUMMARY = "Summary";
const BLANK_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">' +
  '<rect x="0.5" y="0.5" width="1599" height="899" fill="#ffffff" stroke="#d0d0d0"/></svg>\n';

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
  if (!theirs && fig.path === path) await blankSvg(app, `${dir}/${name}.excalidraw.svg`);
  if (!theirs) await fillImage(app, note, `${dir}/${name}.excalidraw.svg`, dir);
  // もう開いていれば、その図に移るだけ(図が何枚も並ばないように)
  const open = app.workspace.getLeavesOfType("excalidraw").find((l) => l.view?.file?.path === fig.path);
  if (open) {
    app.workspace.setActiveLeaf(open, { focus: true });
    return;
  }
  const { place, size } = await layout(app);
  const here = app.workspace.getMostRecentLeaf() || app.workspace.getLeaf(false);
  const dirOf = { 下: "horizontal", 上: "horizontal", 右: "vertical", 左: "vertical" };
  const leaf = app.workspace.createLeafBySplit(here, dirOf[place], place === "上" || place === "左");
  await leaf.setViewState({ type: "excalidraw", state: { file: fig.path }, active: true });
  // 割合を変える(Obsidian の中の仕組みを使うので、変わらなくても図は開く)
  try {
    leaf.setDimension(size);
    here.setDimension(100 - size);
  } catch (e) {}
}

// 個人設定.md の figure_place・figure_size。なければ既定の値
async function layout(app) {
  let place = PLACE, size = SIZE;
  try {
    if (await app.vault.adapter.exists(MY_SETTINGS)) {
      const t = await app.vault.adapter.read(MY_SETTINGS);
      const p = t.match(/^figure_place:[ \t]*["']?(上|下|右|左)/m);
      const n = t.match(/^figure_size:[ \t]*["']?(\d+)/m);
      if (p) place = p[1];
      if (n) size = Math.min(90, Math.max(10, parseInt(n[1], 10)));
    }
  } catch (e) {}
  return { place, size };
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
// このノートの図のフォルダ(dir)の fig_ の SVG を指していて、いまの名前と違うとき(ノートの名前を変える前の図、
// 前の版が入れていた間違った名前 fig_….svg)も、いまの名前に直す。それ以外の値が書いてあれば変えない。
// 種類は問わない。前からあるノートで image の行がなければ足す。
async function fillImage(app, note, svg, dir) {
  const fm = app.metadataCache.getFileCache(note)?.frontmatter || {};
  const now = String(fm.image ?? "").trim();
  if (now === `[[${svg}]]`) return;
  if (now && !now.startsWith(`[[${dir}/fig_`)) return;
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

// まだ書き出していない図の SVG の代わりに、白い 16:9 の SVG を置く。あれば何もしない
async function blankSvg(app, svg) {
  if (app.vault.getAbstractFileByPath(svg)) return;
  try { await app.vault.create(svg, BLANK_SVG); } catch (e) {}
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

// 引用は本文の先頭(属性欄のすぐ後)に入れる(「カーソルの位置でなく md の先頭(frontmatter 直後)固定にしたい」)。
// Summary はそのノートの要点なので、どこで Ctrl+D を押しても同じ場所に入る。
// エディタで開いていればエディタに入れる(ファイルを直接書き換えると、開いている古い中身で上書きされるため)。
async function addEmbed(app, note, line) {
  const view = app.workspace.activeEditor;
  const ed = view?.file === note ? view.editor : null;
  if (ed) {
    let at = 0;
    if (ed.getLine(0).trim() === "---") {
      for (let i = 1; i < ed.lineCount(); i++) if (ed.getLine(i).trim() === "---") { at = i + 1; break; }
    }
    if (at >= ed.lineCount()) ed.replaceRange("\n" + line + "\n", { line: at - 1, ch: ed.getLine(at - 1).length });
    else ed.replaceRange(line + "\n", { line: at, ch: 0 });
    return;
  }
  await app.vault.process(note, (t) => {
    const m = t.match(/^---\r?\n[\s\S]*?\r?\n---[ \t]*(\r?\n|$)/);
    const head = m ? m[0] + (m[1] ? "" : "\n") : "";
    return head + line + "\n" + t.slice(m ? m[0].length : 0);
  });
}

module.exports = open_figure;
