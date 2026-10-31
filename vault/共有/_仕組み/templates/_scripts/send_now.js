// Ctrl+Shift+S「今すぐ共有へ」: このノートを保存し、同期プログラムに「今すぐ同期して」と合図する
// (仕様書「ショートカットキー」、要件書 F-48)。
//
// 合図は この PC の %APPDATA%\知見同期\今すぐ\<時刻>.json に置く。共有クラウドフォルダの外なので、
// 同じ人の別の PC には届かず、二重に動かない。中身は この vault の場所だけ。
// 同期プログラム(watch)が拾ってすぐ1回同期し、<時刻>.done.json に結果を書く。
// それを読んで右上に出す。30秒たっても結果がなければ、同期プログラムが動いていないと知らせる。
// スマホなど、ファイルを外に書けない端末では何もせずに知らせる。

const WAIT_SECONDS = 30;

function signalDir(path, os) {
  // 同期プログラムの config.default_config_path() と同じ場所
  const base = process.env.APPDATA || path.join(os.homedir(), ".config");
  return path.join(base, "知見同期", "今すぐ");
}

async function send_now(tp) {
  const app = tp.app;
  const { Notice, MarkdownView, Platform } = tp.obsidian;
  const req = typeof require === "function" ? require : window.require;
  const adapter = app.vault.adapter;
  if (!Platform.isDesktopApp || !req || typeof adapter.getBasePath !== "function") {
    new Notice("この端末では「今すぐ共有へ」は使えません。PC の Obsidian で押してください", 6000);
    return;
  }
  const fs = req("fs");
  const path = req("path");
  const os = req("os");

  // Templater はこのあと選んでいる文字を空の文字で置き換えるので、選択をいったん外し、あとで戻す
  const ed = app.workspace.activeEditor?.editor;
  if (ed && ed.somethingSelected()) {
    const anchor = ed.getCursor("anchor");
    const head = ed.getCursor("head");
    ed.setCursor(head);
    setTimeout(() => ed.setSelection(anchor, head), 0);
  }

  // まず保存する(書いたばかりの内容を送るため)
  const view = app.workspace.getActiveViewOfType(MarkdownView);
  try {
    if (view && typeof view.save === "function") await view.save();
    else app.commands.executeCommandById("editor:save-file");
  } catch (e) {
    app.commands.executeCommandById("editor:save-file");
  }

  const dir = signalDir(path, os);
  const name = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const signal = path.join(dir, `${name}.json`);
  const done = path.join(dir, `${name}.done.json`);
  try {
    fs.mkdirSync(dir, { recursive: true });
    const tmp = signal + ".tmp";
    fs.writeFileSync(tmp, JSON.stringify({ vault: adapter.getBasePath() }), "utf8");
    fs.renameSync(tmp, signal);
  } catch (e) {
    new Notice(`合図を置けませんでした: ${e.message}`, 8000);
    return;
  }
  const waiting = new Notice("共有へ送っています…", 0);

  // 結果を待つ。Templater を待たせないよう、待つのは裏で行う
  (async () => {
    const until = Date.now() + WAIT_SECONDS * 1000;
    while (Date.now() < until) {
      await new Promise((r) => setTimeout(r, 1000));
      if (!fs.existsSync(done)) continue;
      waiting.hide();
      try {
        const res = JSON.parse(fs.readFileSync(done, "utf8"));
        new Notice(res.message || "共有へ送りました", res.ok ? 5000 : 10000);
      } catch (e) {
        new Notice("同期しました。同期レポートを見てください", 5000);
      }
      try { fs.unlinkSync(done); } catch (e) { /* 同期プログラムが後で消す */ }
      return;
    }
    waiting.hide();
    // 拾われなかった合図は残すと、あとで同期プログラムが動き出したときにすぐ同期する。
    // それでよいので消さない
    new Notice(
      "同期プログラムから返事がありません。動いていないか、前の同期の途中です。" +
        "動いていれば、終わりしだい送ります",
      10000
    );
  })();
}

module.exports = send_now;
