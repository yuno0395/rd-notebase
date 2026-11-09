// 右クリック「説明資料を PDF にする」(仕様書「発表と配布は PDF」、要件書 F-59b)。
// QuickAdd のマクロから呼ぶ(Excalidraw の図を開いているときも動くように。Templater は文書のときだけ)。
//
// Excalidraw のふつうの書き出しは図全体が1枚の PDF になるので使わない。
// Excalidraw の作者のスクリプト「Printable Layout Wizard」と同じ仕組みで、枠(フレーム)1つを1ページにし、
// 枠の名前の順(01 表紙・02 …)に並べる。枠の外と枠の名前は出ない。
// PDF は資料の図と同じ名前(.pdf)。00_PIP/説明資料/ に置くと、同期プログラムが報告フォルダに写す。

const MIN_VERSION = "2.15.0";

function excalidrawView(app) {
  const v = app.workspace.activeLeaf?.view;
  return v && typeof v.getViewType === "function" && v.getViewType() === "excalidraw" ? v : null;
}

function getEA(obsidian) {
  const EA = window.ExcalidrawAutomate;
  if (!EA) return null;
  const ea = typeof EA.getAPI === "function" ? EA.getAPI() : EA;
  if (!ea.verifyMinimumPluginVersion || !ea.verifyMinimumPluginVersion(MIN_VERSION)) return null;
  return ea;
}

// 開いている図の枠を、名前の順に1枚ずつの SVG にする(Printable Layout Wizard の printToPDF と同じやり方)
async function framePages(ea, view) {
  ea.setView(view);
  const frames = ea.getViewElements()
    .filter((el) => el.type === "frame")
    .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  if (frames.length === 0) return [];
  ea.clear();
  for (const f of frames) {
    // 枠の大きさの見えない四角を置き、全体の大きさが枠を含むようにする
    ea.style.opacity = 0;
    ea.style.roughness = 0;
    ea.style.fillStyle = "solid";
    ea.style.backgroundColor = "black";
    ea.style.strokeWidth = 0.01;
    ea.addRect(f.x, f.y, f.width, f.height);
  }
  const all = ea.getViewElements().concat(ea.getElements());
  const scene = await ea.createViewSVG({
    withBackground: true,
    theme: "light",
    padding: 0,
    selectedOnly: false,
    skipInliningFonts: false,
    embedScene: false,
    elementsOverride: all,
  });
  const box = ea.getBoundingBox(all);
  ea.clear();
  const pages = [];
  for (const f of frames) {
    const left = f.x - box.topX;
    const top = f.y - box.topY;
    const host = window.createDiv();
    host.innerHTML = scene.outerHTML;
    const svg = host.firstElementChild;
    svg.setAttribute("viewBox", `${left} ${top} ${f.width} ${f.height}`);
    svg.setAttribute("width", `${f.width}`);
    svg.setAttribute("height", `${f.height}`);
    pages.push(svg);
  }
  return pages;
}

async function writePDF(ea, pages, filename) {
  await ea.createPDF({
    SVG: pages,
    scale: { fitToPage: true },
    pageProps: {
      dimensions: {},
      backgroundColor: "#ffffff",
      margin: { left: 0, right: 0, top: 0, bottom: 0 },
      alignment: "center",
    },
    filename,
  });
}

function deckBase(file) {
  return file.basename.replace(/\.excalidraw$/, "");
}

module.exports = async function (params) {
  const { app, obsidian } = params;
  const { Notice } = obsidian;
  const ea = getEA(obsidian);
  if (!ea) {
    new Notice(`Excalidraw が入っていないか古いです(${MIN_VERSION} 以上が要ります)。準備の bat でプラグインを入れ直してください`, 10000);
    return;
  }
  const view = excalidrawView(app);
  const file = view?.file;
  const fm = file ? app.metadataCache.getFileCache(file)?.frontmatter || {} : {};
  if (!view || typeof fm.deck_common !== "string") {
    new Notice("説明資料の図(00_PIP/説明資料/ のもの)を開いてから押してください", 8000);
    return;
  }
  const busy = new Notice("PDF を作っています…", 0);
  try {
    const pages = await framePages(ea, view);
    if (pages.length === 0) {
      new Notice("ページ(枠)がありません", 6000);
      return;
    }
    await writePDF(ea, pages, `${deckBase(file)}.pdf`);
    new Notice(`PDF を作りました(${pages.length} ページ)。00_PIP/説明資料/ に置けば、共有に出ているノートの資料は報告フォルダにも写ります`, 8000);
  } catch (e) {
    console.error("説明資料を PDF にする", e);
    new Notice(`PDF を作れませんでした: ${e.message}`, 10000);
  } finally {
    busy.hide();
  }
};

module.exports.framePages = framePages;
module.exports.writePDF = writePDF;
module.exports.getEA = getEA;
module.exports.excalidrawView = excalidrawView;
