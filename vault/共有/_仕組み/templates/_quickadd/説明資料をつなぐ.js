// 右クリック「説明資料をつなぐ」(仕様書「作った資料をつないで1つにする」、要件書 F-59b)。
// QuickAdd のマクロから呼ぶ(Excalidraw の図を開いているときも動くように)。
//
//   1. 開いている資料の図が1つ目。00_PIP/説明資料/ の資料から、つなぐものを順に選ぶ(「ここまで」で終わり)。
//   2. 機密区分がちがえば、どれにするかを選ぶ。社外向けの資料が入っていれば、社外向け・社内向けを選ぶ。
//   3. 合わせて 40 枚を超えるときは「PDF でつなぐ」かを聞く(図は重くなるので)。
//   4. 図でつなぐときは「今すぐ共有へ」と同じ合図(send_now.js)で同期プログラムに頼み、できた図を開く。
//      PDF でつなぐときは、それぞれの資料の枠を順に1ページずつにした PDF を1つ作る(図は作らない)。

const DECK_DIR = "00_PIP/説明資料";
const SCRIPTS = "_仕組み/templates/_scripts";
const QUICKADD = "_仕組み/templates/_quickadd";
const MANY = 40;

async function load(app, path) {
  const src = await app.vault.adapter.read(path);
  const mod = { exports: {} };
  new Function("module", "exports", "require", src)(mod, mod.exports, typeof require === "function" ? require : window.require);
  return mod.exports;
}

function frontOf(app, f) {
  return app.metadataCache.getFileCache(f)?.frontmatter || {};
}

function isDeck(app, f) {
  return f.path.startsWith(DECK_DIR + "/") && typeof frontOf(app, f).deck_common === "string";
}

async function waitView(app, file, ea) {
  for (let k = 0; k < 40; k++) {
    const v = app.workspace.activeLeaf?.view;
    if (v && v.file === file && typeof v.getViewType === "function" && v.getViewType() === "excalidraw") {
      ea.setView(v);
      if (ea.getViewElements().length > 0) return v;
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  return null;
}

module.exports = async function (params) {
  const { app, obsidian, quickAddApi: qa } = params;
  const { Notice } = obsidian;
  const first = app.workspace.getActiveFile();
  if (!first || !isDeck(app, first)) {
    new Notice("説明資料の図(00_PIP/説明資料/ のもの)を開いてから押してください", 8000);
    return;
  }
  const chosen = [first];
  for (;;) {
    const rest = app.vault.getMarkdownFiles()
      .filter((f) => isDeck(app, f) && !chosen.includes(f))
      .sort((a, b) => b.stat.mtime - a.stat.mtime);
    if (rest.length === 0) break;
    const names = rest.map((f) => f.basename.replace(/\.excalidraw$/, ""));
    const pick = await qa.suggester([`ここまで(${chosen.length} つをつなぐ)`, ...names], [null, ...rest]);
    if (!pick) break;
    chosen.push(pick);
  }
  const fms = chosen.map((f) => frontOf(app, f));
  const outside = fms.some((fm) => fm.deck_outside);
  if (chosen.length < 2 && !outside) {
    new Notice("つなぐ資料を選んでください(社外向けの資料なら1つだけで社内向けの写しが作れます)", 8000);
    return;
  }
  const labels = [...new Set(fms.map((fm) => String(fm.deck_label || "")).filter((x) => x))];
  let label = labels[0] || "";
  if (labels.length > 1) {
    label = await qa.suggester(labels.map((l) => `機密区分がちがいます。これにする: ${l}`), labels);
    if (!label) return;
  }
  let side = "社内";
  if (outside) {
    side = await qa.suggester(["社外向けにする(引用の id を伏せる)", "社内向けにする(引用に id を入れる)"], ["社外", "社内"]);
    if (!side) return;
  }
  const pages = fms.reduce((n, fm) => n + (Number(fm.deck_pages) || 0), 0);
  let how = "図";
  if (pages > MANY) {
    how = await qa.suggester(
      [`PDF でつなぐ(おすすめ。${pages} 枚あり、図にすると Excalidraw が重くなります)`, "図でつなぐ"], ["PDF", "図"]);
    if (!how) return;
  }
  if (how === "PDF") {
    const pdf = await load(app, `${QUICKADD}/説明資料をPDFにする.js`);
    const ea = pdf.getEA(obsidian);
    if (!ea) { new Notice("Excalidraw が入っていないか古いです。準備の bat でプラグインを入れ直してください", 10000); return; }
    const busy = new Notice("PDF でつないでいます…", 0);
    try {
      const all = [];
      for (const f of chosen) {
        await app.workspace.getLeaf(false).openFile(f);
        const v = await waitView(app, f, ea);
        if (!v) throw new Error(`${f.basename} を開けませんでした`);
        all.push(...(await pdf.framePages(ea, v)));
      }
      await app.workspace.getLeaf(false).openFile(first);
      const day = new Date().toISOString().slice(0, 10);
      await pdf.writePDF(ea, all, `つないだ資料_${String(fms[0].deck_title || first.basename)}_${day}.pdf`);
      new Notice(`PDF でつなぎました(${all.length} ページ)`, 8000);
    } catch (e) {
      console.error("説明資料をつなぐ", e);
      new Notice(`PDF でつなげませんでした: ${e.message}`, 10000);
    } finally {
      busy.hide();
    }
    return;
  }
  const send_now = await load(app, `${SCRIPTS}/send_now.js`);
  await send_now({ app, obsidian }, {
    つなぐ: { 資料: chosen.map((f) => f.path), 機密区分: label, 向け: side },
    waiting: "説明資料をつないでいます…",
    wait: 60,
  });
};
