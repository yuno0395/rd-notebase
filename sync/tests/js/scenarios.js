// キーを押したとき、ノートが決まった場所に、正しい属性欄でできるか(作業の決まり R-10・R-03・R-05)。
// node sync/tests/js/scenarios.js <テンプレートのフォルダ> <結果の JSON>
// 結果の JSON には、作ったノートの中身を入れる。属性欄が YAML として読めるかは pytest が確かめる。

"use strict";
const assert = require("assert/strict");
const fs = require("fs");
const { makeApp } = require("./obsidian_mock");

const TEMPLATES = process.argv[2];
const OUT = process.argv[3];

const SETTINGS = `---\nname: "yu"\nnumber: "229999"\n---\n`;
const PJ = "0RB0004XGV_試しPJ";

// 個人 vault: 個人設定・プロジェクトの台帳・目的・仮説・設計案・イシューが1つずつ
function personal(extra = {}) {
  return makeApp({
    templatesDir: TEMPLATES,
    files: {
      "_仕組み/個人設定.md": SETTINGS,
      "_仕組み/記録/": "",
      "00_inbox/": "",
      "共通/02_ノード/": "",
      "00_PIP/デイリー/2026-11-07.md": "# 2026-11-07\n\n## メモ\n- 型の温度を上げる\n",
      [`試しPJ/${PJ}.md`]: `---\nid: 0RB0004XGV\ntype: プロジェクト\nauthor: ["229999_yu"]\n---\n`,
      "試しPJ/01_目的/0RB0014XGV_軽くする.md": `---\nid: 0RB0014XGV\ntype: 目的\nauthor: ["229999_yu"]\nproject: ["試しPJ"]\n---\n- 持ち運べる\n`,
      "試しPJ/01_目的/0RB0024XGV_持ち運べる.md": `---\nid: 0RB0024XGV\ntype: 仮説\nauthor: ["229999_yu"]\nparent: ["[[0RB0014XGV_軽くする|軽くする]]"]\n---\n- 片手で持てる\n`,
      "試しPJ/01_設計案/0RB0034XGV_樹脂化.md": `---\nid: 0RB0034XGV\ntype: 設計案\nauthor: ["229999_yu"]\nparent: ["[[0RB0014XGV_軽くする|軽くする]]"]\n価値仮説: ["[[0RB0024XGV_持ち運べる|持ち運べる]]"]\n---\n- 割れる\n`,
      "試しPJ/03_イシュー/0RB0044XGV_割れる.md": `---\nid: 0RB0044XGV\ntype: イシュー\nauthor: ["229999_yu"]\nproject: ["試しPJ"]\n脅かす: ["[[0RB0034XGV_樹脂化|樹脂化]]"]\n---\n- 落下試験をする\n`,
      ...extra,
    },
  });
}

const results = {};
const tests = [];
function test(name, fn) { tests.push([name, fn]); }

// 作ったノートの中身を残す(pytest が属性欄を読む)
function keep(app, name) {
  for (const p of app.created) results[`${name}: ${p}`] = app.text(p);
}

function only(list, what) {
  assert.equal(list.length, 1, `${what} が ${list.length} 個: ${list.join(", ")}`);
  return list[0];
}

function noTopFolders(app) {
  const top = [...app.vault.folders].filter((f) => !f.includes("/"));
  for (const bad of ["01_目的", "01_設計案", "02_ノード", "03_イシュー", "04_タスク", "05_ナレッジ"]) {
    assert.ok(!top.includes(bad), `一番上に ${bad}/ ができた`);
  }
}

// ---------- Ctrl+K ----------

test("Ctrl+K: 選んだ語のノードを 共通/02_ノード に作ってつなぐ", async () => {
  const app = personal();
  const daily = "00_PIP/デイリー/2026-11-07.md";
  app.open(daily, { line: 3, ch: 4, to: 6 }); // 「温度」
  app.answers.push("Internal use only");       // だれに見せるか
  await app.templater.command("ノードにする");
  const p = only(app.find(/^共通\/02_ノード\/[0-9A-Z]{10}_温度\.md$/), "温度のノード");
  const fm = app.fm(p);
  assert.equal(fm.type, "ノード");
  assert.deepEqual(fm.aliases, ["温度"]);
  assert.deepEqual(fm.author, ["229999_yu"]);
  assert.deepEqual(fm.visibility, ["Internal use only"]);
  assert.equal(app.prompts.length, 1);
  assert.match(app.text(daily), /\[\[[0-9A-Z]{10}_温度\|温度\]\]/);
  noTopFolders(app);
  keep(app, "Ctrl+K");
});

test("Ctrl+K: 何も選ばずに押すと検索窓。あるノードはつなぎ、ない名前は作る", async () => {
  const app = personal({ "共通/02_ノード/0RB0074XGV_樹脂.md": `---\nid: 0RB0074XGV\ntype: ノード\naliases: ["樹脂", "プラ"]\n---\n` });
  const daily = "00_PIP/デイリー/2026-11-07.md";
  app.open(daily, { line: 4, ch: 0 });
  app.answers.push("プラ");
  await app.templater.command("ノードにする");
  assert.match(app.text(daily), /\[\[0RB0074XGV_樹脂\|プラ\]\]/);
  app.open(daily, { line: 3, ch: 10 }); // 行の終わり(リンクの上ではない)
  app.answers.push("金型", null);               // 名前、だれに見せるかは Esc で PIP
  await app.templater.command("ノードにする");
  const p = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_金型\.md$/), "金型のノード(PIP)");
  assert.deepEqual(app.fm(p).visibility, ["PIP"]);
  assert.equal(app.prompts.length, 3);
});

// ---------- Ctrl+I ----------

test("Ctrl+I: 同じ名前のイシューがあれば、作らずにつなぐ", async () => {
  const app = personal();
  const src = "試しPJ/01_設計案/0RB0034XGV_樹脂化.md";
  app.open(src, { line: 7, ch: 2 });
  await app.templater.command("イシューにする");
  assert.equal(app.created.length, 0);
  assert.match(app.text(src), /- \[\[0RB0044XGV_割れる\|割れる\]\]/);
});

test("Ctrl+I・Ctrl+K: 属性欄に入力中なら何もしない(本文の見出しをノートにしない。PC 試験 2026-11-08)", async () => {
  const app = personal();
  const src = "試しPJ/01_目的/0RB0024XGV_持ち運べる.md";
  app.open(src, { line: 6, ch: 2 });
  const before = app.text(src);
  global.document = { activeElement: { closest: (sel) => (sel === ".metadata-container" ? {} : null) } };
  try {
    await app.templater.command("イシューにする");
  } finally {
    delete global.document;
  }
  // 属性欄の行を選んだだけ(属性欄の外側の要素にいる)でも、本文の文字の欄の外なら止める
  const view = app.workspace.activeEditor;
  const text = { contains: () => false };
  view.editor.cm = { contentDOM: text };
  view.containerEl = { contains: () => true };
  global.document = { activeElement: { closest: () => null } };
  try {
    await app.templater.command("イシューにする");
    await app.templater.command("ノードにする");
    await app.templater.command("関係としてつなぐ");
  } finally {
    delete global.document;
  }
  assert.equal(app.created.length, 0);
  assert.equal(app.text(src), before);
  assert.equal(app.notices.filter((n) => n.includes("属性欄では使えません")).length, 4);
});

test("Ctrl+I: 本文の文字の欄にいれば、属性欄の止めは働かない", async () => {
  const app = personal();
  const src = "試しPJ/01_目的/0RB0024XGV_持ち運べる.md";
  app.open(src, { line: 6, ch: 2 });
  const view = app.workspace.activeEditor;
  const inside = { closest: () => null };
  view.editor.cm = { contentDOM: { contains: (el) => el === inside } };
  view.containerEl = { contains: () => true };
  global.document = { activeElement: inside };
  try {
    await app.templater.command("イシューにする");
  } finally {
    delete global.document;
  }
  assert.equal(app.created.length, 1);
});

test("Ctrl+I: 仮説の行で押すと 脅かす に仮説、project を引用符つきで入れる", async () => {
  const app = personal();
  const src = "試しPJ/01_目的/0RB0024XGV_持ち運べる.md";
  app.open(src, { line: 6, ch: 2 });
  await app.templater.command("イシューにする");
  const p = only(app.find(/^試しPJ\/03_イシュー\/[0-9A-Z]{10}_片手で持てる\.md$/), "イシュー");
  const fm = app.fm(p);
  assert.deepEqual(fm["脅かす"], ["[[0RB0024XGV_持ち運べる|持ち運べる]]"]);
  assert.equal(fm.impact, "未判定");
  assert.match(app.text(p), /^project: \["試しPJ"\]/m);
  assert.match(app.text(src), /- \[\[[0-9A-Z]{10}_片手で持てる\|片手で持てる\]\]/);
  keep(app, "Ctrl+I 仮説");
});

test("Ctrl+I: デイリーで押すと、だれに見せるかを1回だけ聞く。プロジェクトを選べばそのフォルダ", async () => {
  const app = personal();
  app.open("00_PIP/デイリー/2026-11-07.md", { line: 3, ch: 2 });
  app.answers.push("試しPJ");                     // だれに見せるか(デイリーからは引き継がない)。プロジェクトはもう聞かない
  await app.templater.command("イシューにする");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  const p = only(app.find(/^試しPJ\/03_イシュー\/[0-9A-Z]{10}_型の温度を上げる\.md$/), "イシュー");
  assert.deepEqual(app.fm(p).project, ["試しPJ"]);
  assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);
});

test("Internal use only を選ぶと 共通 に置く(Ctrl+I をデイリーで・Ctrl+N)", async () => {
  let app = personal();
  app.open("00_PIP/デイリー/2026-11-07.md", { line: 3, ch: 2 });
  app.answers.push("Internal use only");
  await app.templater.command("イシューにする");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  let p = only(app.find(/^共通\/03_イシュー\/[0-9A-Z]{10}_型の温度を上げる\.md$/), "Internal のイシュー");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  assert.deepEqual(app.fm(p).project, ["共通"]);
  app = personal();
  app.answers.push("Internal use only");
  await app.quickAdd("タスク", "00_inbox", "見込みを出す");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  p = only(app.find(/^共通\/04_タスク\/[0-9A-Z]{10}_見込みを出す\.md$/), "Internal のタスク");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  assert.deepEqual(app.fm(p).project, ["共通"]);
  keep(app, "Ctrl+I デイリー");
});

test("Esc なら PIP にして 00_PIP/メモ に置く(Ctrl+I をデイリーで・Ctrl+N)", async () => {
  let app = personal();
  app.open("00_PIP/デイリー/2026-11-07.md", { line: 3, ch: 2 });
  app.answers.push(null);                        // だれに見せるか(Esc で PIP)。プロジェクトは聞かない
  await app.templater.command("イシューにする");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  let p = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_型の温度を上げる\.md$/), "PIP のイシュー");
  assert.deepEqual(app.fm(p).visibility, ["PIP"]);
  assert.equal(app.fm(p).type, "イシュー");
  app = personal();
  app.answers.push(null);
  await app.quickAdd("タスク", "00_inbox", "見込みを出す");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  p = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_見込みを出す\.md$/), "PIP のタスク");
  assert.deepEqual(app.fm(p).visibility, ["PIP"]);
  noTopFolders(app);
  keep(app, "Esc で PIP");
});

test("プロジェクト2つと社外(EXT)を選べる。2つなら 共通 に置く", async () => {
  const app = personal({
    "試し2/0RB00A4XGV_試し2.md": `---\nid: 0RB00A4XGV\ntype: プロジェクト\nauthor: ["229999_yu"]\n---\n`,
    "_仕組み/EXT_一覧.csv": "名前,説明\nA社,試作の外注先\n",
  });
  app.answers.push("試しPJ", "試し2", "EXT_A社");   // だれに見せるか、ほかのプロジェクト(残りがなくなれば聞かない)、社外
  await app.quickAdd("イシュー", "00_inbox", "二つにまたがる");
  assert.equal(app.prompts.length, 3, `窓が ${app.prompts.length} 回出た`);
  const p = only(app.find(/^共通\/03_イシュー\/[0-9A-Z]{10}_二つにまたがる\.md$/), "2つのプロジェクトのイシュー");
  assert.deepEqual(app.fm(p).visibility, ["試しPJ", "試し2", "EXT_A社"]);
  assert.deepEqual(app.fm(p).project, ["試しPJ", "試し2"]);
  keep(app, "プロジェクト2つと EXT");
});

test("Internal use only のプロジェクト: 選べば Internal use only、置き場所はそのプロジェクトのまま", async () => {
  const pj = { [`試しPJ/${PJ}.md`]: `---\nid: 0RB0004XGV\ntype: プロジェクト\nauthor: ["229999_yu"]\nvisibility: [Internal use only]\n---\n` };
  let app = personal(pj);
  app.open("00_PIP/デイリー/2026-11-07.md", { line: 3, ch: 2 });
  app.answers.push("試しPJ");
  await app.templater.command("イシューにする");
  let p = only(app.find(/^試しPJ\/03_イシュー\/[0-9A-Z]{10}_型の温度を上げる\.md$/), "イシュー");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  assert.deepEqual(app.fm(p).project, ["試しPJ"]);
  app = personal(pj);
  app.answers.push("試しPJ");
  await app.quickAdd("タスク", "00_inbox", "見込みを出す");
  p = only(app.find(/^試しPJ\/04_タスク\/[0-9A-Z]{10}_見込みを出す\.md$/), "タスク");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  // 範囲を書いていないイシューから Ctrl+T でも、置いたプロジェクトの範囲になる
  app = personal(pj);
  app.open("試しPJ/03_イシュー/0RB0044XGV_割れる.md", { line: 7, ch: 2 });
  await app.templater.command("タスクにする");
  p = only(app.find(/^試しPJ\/04_タスク\/[0-9A-Z]{10}_落下試験をする\.md$/), "タスク");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  keep(app, "Internal のプロジェクト");
});


// ---------- Ctrl+T・H・U ----------

test("Ctrl+T: イシューの行で押すと parent にイシュー、<PJ>/04_タスク に作る", async () => {
  const app = personal();
  app.open("試しPJ/03_イシュー/0RB0044XGV_割れる.md", { line: 7, ch: 2 });
  await app.templater.command("タスクにする");
  const p = only(app.find(/^試しPJ\/04_タスク\/[0-9A-Z]{10}_落下試験をする\.md$/), "タスク");
  assert.deepEqual(app.fm(p).parent, ["[[0RB0044XGV_割れる|割れる]]"]);
  assert.equal(app.prompts.length, 0);
  assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);   // 押したイシューの範囲(書いていなければ置き場所のプロジェクト)を聞かずに引き継ぐ
  keep(app, "Ctrl+T");
});

test("Ctrl+T: 共有しない(PIP)ノートで押すと、聞かずに PIP を引き継ぎ 00_PIP/メモ に置く", async () => {
  const issue = "00_PIP/メモ/0RB0054XGV_売上が届かない.md";
  const app = personal({
    [issue]: `---\nid: 0RB0054XGV\ntype: イシュー\nauthor: ["229999_yu"]\nvisibility: [PIP]\nproject: ["試しPJ"]\n---\n- 見込みを出し直す\n- 単価が下がる\n`,
  });
  app.open(issue, { line: 7, ch: 2 });
  await app.templater.command("タスクにする");
  const t = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_見込みを出し直す\.md$/), "タスク");
  assert.deepEqual(app.fm(t).visibility, ["PIP"]);
  assert.equal(app.prompts.length, 0, `窓が ${app.prompts.length} 回出た`);
});

test("Ctrl+H: 目的の行で押すと parent に目的、<PJ>/01_目的 に作る", async () => {
  const app = personal();
  app.open("試しPJ/01_目的/0RB0014XGV_軽くする.md", { line: 6, ch: 2 });
  await app.templater.command("仮説にする");
  // 「持ち運べる」はもうあるのでつなぐだけ
  assert.equal(app.created.length, 0);
  assert.match(app.text("試しPJ/01_目的/0RB0014XGV_軽くする.md"), /\[\[0RB0024XGV_持ち運べる\|持ち運べる\]\]/);
});

test("Ctrl+U: 仮説の行で押すと parent に目的・価値仮説に仮説、<PJ>/01_設計案 に作る", async () => {
  const app = personal();
  const src = "試しPJ/01_目的/0RB0024XGV_持ち運べる.md";
  app.open(src, { line: 6, ch: 2 });
  await app.templater.command("設計案にする");
  const p = only(app.find(/^試しPJ\/01_設計案\/[0-9A-Z]{10}_片手で持てる\.md$/), "設計案");
  const fm = app.fm(p);
  assert.deepEqual(fm.parent, ["[[0RB0014XGV_軽くする|軽くする]]"]);
  assert.deepEqual(fm["価値仮説"], ["[[0RB0024XGV_持ち運べる|持ち運べる]]"]);
  keep(app, "Ctrl+U");
});

test("Ctrl+U: イシューで押すと、脅かされた案と並ぶ候補(parent と価値仮説を写し、previous にイシュー)", async () => {
  const app = personal();
  const src = "試しPJ/03_イシュー/0RB0044XGV_割れる.md";
  app.open(src, { line: 7, ch: 2, to: 4 }); // 「落下」
  await app.templater.command("設計案にする");
  const p = only(app.find(/^試しPJ\/01_設計案\/[0-9A-Z]{10}_落下\.md$/), "設計案");
  const fm = app.fm(p);
  assert.deepEqual(fm.parent, ["[[0RB0014XGV_軽くする|軽くする]]"]);
  assert.deepEqual(fm["価値仮説"], ["[[0RB0024XGV_持ち運べる|持ち運べる]]"]);
  assert.deepEqual(fm.previous, ["[[0RB0044XGV_割れる|割れる]]"]);
});

const TASK = {
  "試しPJ/04_タスク/0RB0054XGV_落下試験.md": `---\nid: 0RB0054XGV\ntype: タスク\nauthor: ["229999_yu"]\nparent: ["[[0RB0044XGV_割れる|割れる]]"]\n---\n- 角が欠ける\n`,
};

test("Ctrl+I: タスクで押すと previous にタスク、generation に元のイシュー＋1", async () => {
  const app = personal(TASK);
  app.open("試しPJ/04_タスク/0RB0054XGV_落下試験.md", { line: 6, ch: 2 });
  await app.templater.command("イシューにする");
  const p = only(app.find(/^試しPJ\/03_イシュー\/[0-9A-Z]{10}_角が欠ける\.md$/), "イシュー");
  const fm = app.fm(p);
  assert.deepEqual(fm.previous, ["[[0RB0054XGV_落下試験|落下試験]]"]);
  assert.equal(fm.generation, "2");
  assert.deepEqual(fm["脅かす"], ["[[0RB0034XGV_樹脂化|樹脂化]]"]);
  keep(app, "Ctrl+I タスク");
});

test("ナレッジにする: タスクで押すと parent にタスク、risk_reduction にイシュー", async () => {
  const app = personal(TASK);
  app.open("試しPJ/04_タスク/0RB0054XGV_落下試験.md", { line: 6, ch: 2 });
  await app.templater.command("ナレッジにする");
  const p = only(app.find(/^試しPJ\/05_ナレッジ\/[0-9A-Z]{10}_角が欠ける\.md$/), "ナレッジ");
  assert.deepEqual(app.fm(p).parent, ["[[0RB0054XGV_落下試験|落下試験]]"]);
  assert.match(app.text(p), /risk_reduction:\n {2}- "\[\[0RB0044XGV_割れる\|割れる\]\] \?→\?"/);
  keep(app, "ナレッジにする");
});

test("関係としてつなぐ: 設計案で仮説のリンクの上なら 価値仮説 に足す、ほかは friend", async () => {
  const app = personal({
    "試しPJ/01_設計案/0RB0064XGV_金属.md": `---\nid: 0RB0064XGV\ntype: 設計案\nauthor: ["229999_yu"]\naliases: ["金属"]\n価値仮説: []\n---\n[[0RB0024XGV_持ち運べる|持ち運べる]] [[0RB0034XGV_樹脂化|樹脂化]]\n`,
  });
  const p = "試しPJ/01_設計案/0RB0064XGV_金属.md";
  app.open(p, { line: 7, ch: 3 });
  await app.templater.command("関係としてつなぐ");
  app.open(p, { line: 7, ch: 40 });
  await app.templater.command("関係としてつなぐ");
  assert.deepEqual(app.fm(p)["価値仮説"], ["[[0RB0024XGV_持ち運べる|持ち運べる]]"]);
  assert.deepEqual(app.fm(p).friend, ["[[0RB0034XGV_樹脂化|樹脂化]]"]);
  results["関係としてつなぐ"] = app.text(p);
});

test("このノートをリンク先の親にする: 仮説の本文の [[指標]] の上で使うと、指標のノードの parent に仮説を足す", async () => {
  const node = "共通/02_ノード/0RB0084XGV_片手で持てる.md";
  const theirs = "共通/02_ノード/0RB0094XGV_落としても割れない.md";
  const app = personal({
    "試しPJ/01_目的/0RB0024XGV_持ち運べる.md": `---\nid: 0RB0024XGV\ntype: 仮説\nauthor: ["229999_yu"]\nparent: ["[[0RB0014XGV_軽くする|軽くする]]"]\n---\n- [[0RB0084XGV_片手で持てる|片手で持てる]]\n- [[0RB0094XGV_落としても割れない|落としても割れない]]\n`,
    [node]: `---\nid: 0RB0084XGV\ntype: ノード\nauthor: ["229999_yu"]\naliases: ["片手で持てる"]\nparent: ["[[0RB0014XGV_軽くする|軽くする]]"]\n---\n`,
    [theirs]: `---\nid: 0RB0094XGV\ntype: ノード\nauthor: ["111111_kato"]\naliases: ["落としても割れない"]\n---\n`,
  });
  const src = "試しPJ/01_目的/0RB0024XGV_持ち運べる.md";
  const before = app.text(src);
  app.open(src, { line: 6, ch: 5 });
  await app.templater.command("このノートをリンク先の親にする");
  assert.deepEqual(app.fm(node).parent, ["[[0RB0014XGV_軽くする|軽くする]]", "[[0RB0024XGV_持ち運べる|持ち運べる]]"]);
  app.open(src, { line: 6, ch: 5 });
  await app.templater.command("このノートをリンク先の親にする");   // 2回押しても1つだけ
  assert.equal(app.fm(node).parent.length, 2);
  assert.ok(app.notices.some((n) => n.includes("もう")), app.notices.join(" / "));
  app.open(src, { line: 7, ch: 5 });
  const theirsBefore = app.text(theirs);
  await app.templater.command("このノートをリンク先の親にする");   // 他の人のノートは書き換えない(R-14)
  assert.equal(app.text(theirs), theirsBefore);
  assert.ok(app.notices.some((n) => n.includes("他の人のノート")), app.notices.join(" / "));
  assert.equal(app.text(src), before);   // 今のノートは変えない
  assert.equal(app.prompts.length, 0);
  results["このノートをリンク先の親にする"] = app.text(node);
});

test("Ctrl+K: 押したノートの visibility を聞かずに引き継ぐ", async () => {
  const hyp = (v) => `---\nid: 0RB0024XGV\ntype: 仮説\nauthor: ["229999_yu"]\nvisibility: [${v}]\nparent: ["[[0RB0014XGV_軽くする|軽くする]]"]\n---\n- 片手で持てる\n`;
  const src = "試しPJ/01_目的/0RB0024XGV_持ち運べる.md";
  let app = personal({ [src]: hyp("Internal use only") });
  app.open(src, { line: 7, ch: 2, to: 8 });
  await app.templater.command("ノードにする");
  let p = only(app.find(/^共通\/02_ノード\/[0-9A-Z]{10}_片手で持てる\.md$/), "Internal のノード");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  assert.equal(app.prompts.length, 0, `窓が ${app.prompts.length} 回出た`);
  keep(app, "Ctrl+K 引き継ぐ");
  app = personal({ [src]: hyp("試しPJ") });
  app.open(src, { line: 7, ch: 2, to: 8 });
  await app.templater.command("ノードにする");
  p = only(app.find(/^試しPJ\/02_ノード\/[0-9A-Z]{10}_片手で持てる\.md$/), "プロジェクトのノード");
  assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);
  assert.equal(app.prompts.length, 0);
  app = personal({ "00_PIP/メモ/0RB0024XGV_持ち運べる.md": hyp("PIP") });
  app.open("00_PIP/メモ/0RB0024XGV_持ち運べる.md", { line: 7, ch: 2, to: 8 });
  await app.templater.command("ノードにする");
  p = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_片手で持てる\.md$/), "PIP のノード");
  assert.deepEqual(app.fm(p).visibility, ["PIP"]);
  assert.equal(app.prompts.length, 0);
});

// ---------- Ctrl+N(QuickAdd は 00_inbox に作り、テンプレートが移す) ----------

for (const [tpl, folder] of [["イシュー", "03_イシュー"], ["タスク", "04_タスク"], ["目的", "01_目的"],
  ["価値の仮説", "01_目的"], ["設計案", "01_設計案"], ["ナレッジ", "05_ナレッジ"], ["議事録", "04_タスク"],
  ["実験・試作記録", "04_タスク"]]) {
  test(`Ctrl+N「${tpl}」: プロジェクトを選ぶと <PJ>/${folder} へ移す`, async () => {
    const app = personal();
    app.answers.push("試しPJ");                   // だれに見せるか(親がないので聞く)。プロジェクトはもう聞かない
    await app.quickAdd(tpl, "00_inbox", "新しいもの");
    const p = only(app.find(new RegExp(`^試しPJ/${folder}/[0-9A-Z]{10}_新しいもの\\.md$`)), tpl);
    assert.deepEqual(app.fm(p).project, ["試しPJ"]);
    assert.deepEqual(app.fm(p).author, ["229999_yu"]);
    assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);
    assert.equal(app.prompts.length, 1);
    noTopFolders(app);
    keep(app, `Ctrl+N ${tpl}`);
  });
}

test("共有 vault の Ctrl+N「イシュー」: だれに見せるかは聞かずに Internal、プロジェクトを Esc なら 00_inbox に残す", async () => {
  const app = makeApp({ templatesDir: TEMPLATES, configDir: ".obsidian-229999_aa11234567", files: { "00_inbox/": "" } });
  app.answers.push(null);                        // プロジェクト
  await app.quickAdd("イシュー", "00_inbox", "あとで決める");
  const p = only(app.find(/^00_inbox\/[0-9A-Z]{10}_あとで決める\.md$/), "inbox のイシュー");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
});

test("Ctrl+K: 見せる範囲をプロジェクト1つにしたノードは <PJ>/02_ノード に作ってつなぐ", async () => {
  const app = personal();
  const daily = "00_PIP/デイリー/2026-11-07.md";
  app.open(daily, { line: 3, ch: 4, to: 6 }); // 「温度」
  app.answers.push("試しPJ", "__done__");     // だれに見せるか → ほかのプロジェクトは足さない
  await app.templater.command("ノードにする");
  const p = only(app.find(/^試しPJ\/02_ノード\/[0-9A-Z]{10}_温度\.md$/), "温度のノード");
  assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);
  assert.equal(app.find(/^共通\/02_ノード\/.*温度/).length, 0);
  assert.match(app.text(daily), /\[\[[0-9A-Z]{10}_温度\|温度\]\]/);
});

test("Ctrl+N「ノード」: 見せる範囲がプロジェクト1つなら <PJ>/02_ノード、2つなら 共通/02_ノード", async () => {
  let app = personal({ "別PJ/0RB0094XGV_別PJ.md": `---\nid: 0RB0094XGV\ntype: プロジェクト\n---\n` });
  app.answers.push("試しPJ", "__done__");
  await app.quickAdd("ノード", "共通/02_ノード", "樹脂");
  only(app.find(/^試しPJ\/02_ノード\/[0-9A-Z]{10}_樹脂\.md$/), "PJ のノード");
  app = personal({ "別PJ/0RB0094XGV_別PJ.md": `---\nid: 0RB0094XGV\ntype: プロジェクト\n---\n` });
  app.answers.push("試しPJ", "別PJ");
  await app.quickAdd("ノード", "共通/02_ノード", "樹脂");
  const p = only(app.find(/^共通\/02_ノード\/[0-9A-Z]{10}_樹脂\.md$/), "2つの PJ のノード");
  assert.deepEqual(app.fm(p).visibility, ["試しPJ", "別PJ"]);
});

test("Ctrl+N「ノード」: 共通/02_ノード に作り、だれに見せるかを聞く", async () => {
  const app = personal();
  app.answers.push("Internal use only");
  await app.quickAdd("ノード", "共通/02_ノード", "樹脂");
  const p = only(app.find(/^共通\/02_ノード\/[0-9A-Z]{10}_樹脂\.md$/), "ノード");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  assert.equal(app.prompts.length, 1);
  keep(app, "Ctrl+N ノード");
});

test("共有 vault の Ctrl+N「ノード」: だれに見せるかは聞かずに Internal use only", async () => {
  const app = makeApp({ templatesDir: TEMPLATES, configDir: ".obsidian-229999_aa11234567", files: { "共通/02_ノード/": "" } });
  await app.quickAdd("ノード", "共通/02_ノード", "樹脂");
  const p = only(app.find(/^共通\/02_ノード\/[0-9A-Z]{10}_樹脂\.md$/), "ノード");
  assert.deepEqual(app.fm(p).visibility, ["Internal use only"]);
  assert.equal(app.prompts.length, 0);
});

test("Ctrl+N「部品」: プロジェクトを選ぶと <PJ>/02_ノード、Internal なら 共通/02_ノード、Esc なら 00_PIP/メモ", async () => {
  let app = personal();
  app.answers.push("試しPJ");                    // だれに見せるか。プロジェクトはもう聞かない
  await app.quickAdd("部品", "共通/02_ノード", "ねじ");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  const p = only(app.find(/^試しPJ\/02_ノード\/[0-9A-Z]{10}_ねじ\.md$/), "部品");
  assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);
  keep(app, "Ctrl+N 部品");
  app = personal();
  app.answers.push("Internal use only");
  await app.quickAdd("部品", "共通/02_ノード", "ねじ");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  only(app.find(/^共通\/02_ノード\/[0-9A-Z]{10}_ねじ\.md$/), "Internal の部品");
  app = personal();
  app.answers.push(null);
  await app.quickAdd("部品", "共通/02_ノード", "ねじ");
  const q = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_ねじ\.md$/), "PIP の部品");
  assert.deepEqual(app.fm(q).visibility, ["PIP"]);
});

test("Ctrl+N「機密の窓口」「メモ」: 決まった場所にできる", async () => {
  const app = personal({ "共通/機密の窓口/": "", "00_PIP/メモ/": "" });
  await app.quickAdd("機密の窓口", "共通/機密の窓口", "案件A");
  only(app.find(/^共通\/機密の窓口\/[0-9A-Z]{10}_案件A\.md$/), "窓口");
  await app.quickAdd("メモ", "00_PIP/メモ", "思いつき");
  const m = only(app.find(/^00_PIP\/メモ\/[0-9A-Z]{10}_思いつき\.md$/), "メモ");   // メモにも id(v0.85)
  assert.equal(app.fm(m).type, "メモ");
  assert.deepEqual(app.fm(m).visibility, ["PIP"]);
  assert.deepEqual(app.fm(m).aliases, ["思いつき"]);
  keep(app, "Ctrl+N 窓口とメモ");
});

// ---------- 共有する・共有をやめる ----------

test("共有する: メモを同じ id のまま選んだ種類にし、選んだプロジェクトへ移す", async () => {
  const memo = "00_PIP/メモ/0RB0094XGV_吸水を測る.md";
  const app = personal({
    [memo]: `---\nid: 0RB0094XGV\ntype: メモ\nauthor: ["229999_yu"]\naliases: ["吸水を測る"]\nvisibility: [PIP]\n---\n` +
      "共有されないメモ(PIP)。自分の 00_PIP/メモ/ に残るだけで、同期プログラムは読まない。\nPA66 は吸水で寸法が変わる\n",
  });
  app.open(memo, { line: 8, ch: 0 });
  app.answers.push("タスク", "試しPJ");             // 種類、だれに見せるか
  await app.templater.command("共有する");
  assert.ok(app.prompts.some((x) => x.includes("次の同期で共有されます")), "共有されると知らせていない");
  const p = "試しPJ/04_タスク/0RB0094XGV_吸水を測る.md";
  assert.ok(app.text(p), "移った先にない");
  assert.ok(!app.text(memo), "メモが残っている");
  const fm = app.fm(p);
  assert.equal(fm.id, "0RB0094XGV");
  assert.equal(fm.type, "タスク");
  assert.deepEqual(fm.author, ["229999_yu"]);
  assert.deepEqual(fm.project, ["試しPJ"]);
  assert.deepEqual(fm.visibility, ["試しPJ"]);
  assert.match(app.text(p), /PA66 は吸水で寸法が変わる\n## やること/);
  assert.match(app.text(p), /\n---\n## 背景\n同期プログラムが書く/);   // 背景はメモの本文より上(F-60)
  assert.ok(!app.text(p).includes("共有されないメモ"));
  results["共有する: " + p] = app.text(p);
  // id のない前のメモ(00_日誌/メモ/)は、ここで id がつき、日付が外れる
  const old = "00_日誌/メモ/2026-10-29 樹脂の選び方.md";
  const app2 = personal({ [old]: "---\ntype: メモ\nvisibility: 個人\n---\n考え中\n" });
  app2.open(old, { line: 4, ch: 0 });
  app2.answers.push("ノード", "Internal use only");
  await app2.templater.command("共有する");
  const n = only(app2.find(/^共通\/02_ノード\/[0-9A-Z]{10}_樹脂の選び方\.md$/), "ノード");
  assert.deepEqual(app2.fm(n).aliases, ["樹脂の選び方"]);
  assert.deepEqual(app2.fm(n).visibility, ["Internal use only"]);
  results["共有する: " + n] = app2.text(n);
});

test("共有する: PIP のイシューは種類はそのまま、範囲だけ選んで移す。Esc なら何もしない", async () => {
  const note = "00_PIP/メモ/0RB00B4XGV_割れが心配.md";
  const src = `---\nid: 0RB00B4XGV\ntype: イシュー\nauthor: ["229999_yu"]\nvisibility: [PIP]  # だれに見せるか\nproject: []\n---\n本文\n`;
  let app = personal({ [note]: src });
  app.open(note);
  app.answers.push(null);
  await app.templater.command("共有する");
  assert.equal(app.text(note), src);
  app = personal({ [note]: src });
  app.open(note);
  app.answers.push("試しPJ");
  await app.templater.command("共有する");
  assert.equal(app.prompts.length, 1, `窓が ${app.prompts.length} 回出た`);
  const p = "試しPJ/03_イシュー/0RB00B4XGV_割れが心配.md";
  assert.deepEqual(app.fm(p).visibility, ["試しPJ"]);
  assert.deepEqual(app.fm(p).project, ["試しPJ"]);
  assert.match(app.text(p), /# だれに見せるか/);   // 行の後ろのコメントは残す
  // もう共有しているノートでは何もしない
  app.open(p);
  await app.templater.command("共有する");
  assert.ok(app.notices.some((x) => x.includes("もう共有しています")));
});

test("共有をやめる: 自分のノートを PIP にして 00_PIP/メモ へ。写しが残ることを知らせる", async () => {
  const issue = "試しPJ/03_イシュー/0RB0044XGV_割れる.md";
  let app = personal();
  app.open(issue);
  app.answers.push("no");
  await app.templater.command("共有をやめる");
  assert.ok(app.text(issue), "やめないのに移った");
  app.answers.push("yes");
  await app.templater.command("共有をやめる");
  assert.ok(app.prompts.some((x) => x.includes("写しは消えずに残ります")), "写しが残ると知らせていない: " + app.notices.join(" / "));
  const p = "00_PIP/メモ/0RB0044XGV_割れる.md";
  assert.deepEqual(app.fm(p).visibility, ["PIP"]);
  // 他の人のノートではやめられない
  const other = "試しPJ/03_イシュー/0RB00C4ABC_他の人の.md";
  app = personal({ [other]: `---\nid: 0RB00C4ABC\ntype: イシュー\nauthor: ["111111_kato"]\n---\n` });
  app.open(other);
  await app.templater.command("共有をやめる");
  assert.ok(app.text(other));
  assert.ok(app.notices.some((x) => x.includes("自分が作ったノートだけ")));
});

// ---------- Ctrl+D ----------

test("Ctrl+D: 図を _仕組み/attachments/<id>/fig_<ノート>.excalidraw.md に作り、Summary を引用する", async () => {
  const app = personal();
  const note = "試しPJ/01_設計案/0RB0034XGV_樹脂化.md";
  app.open(note, { line: 7, ch: 0 });
  await app.templater.command("図を開く");
  assert.ok(app.text("_仕組み/attachments/0RB0034XGV/fig_0RB0034XGV_樹脂化.excalidraw.md"), "図がない");
  assert.match(app.text(note), /!\[\[_仕組み\/attachments\/0RB0034XGV\/fig_0RB0034XGV_樹脂化\.excalidraw#\^clippedframe=/);
  assert.match(app.text(note), /^image: "\[\[_仕組み\/attachments\/0RB0034XGV\/fig_0RB0034XGV_樹脂化\.excalidraw\.svg\]\]"/m);
  // 引用は本文の先頭(属性欄のすぐ後)。カーソルの位置(7行目)ではない
  const t = app.text(note);
  assert.match(t, /\n---\n!\[\[_仕組み\/attachments\/0RB0034XGV\/fig_/, "引用が属性欄のすぐ後にない");
  // まだ書き出していない図の代わりの白い SVG
  assert.ok(app.text("_仕組み/attachments/0RB0034XGV/fig_0RB0034XGV_樹脂化.excalidraw.svg"), "白い SVG がない");
  // 既定では図をノートの下に 70% で開く
  assert.deepEqual(app.split, { direction: "horizontal", before: false });
  assert.deepEqual(app.dimensions, [70, 30]);
});

// ---------- 起動時 ----------

// QuickAdd のマクロ「起動時」(Run on startup)。Templater の起動時テンプレートは PC ごとにオフなので使わない
async function startup(app) {
  const src = app.vault.data.get("_仕組み/templates/_quickadd/起動時.js");
  const mod = { exports: {} };
  global.window = app.window;
  new Function("module", "exports", src)(mod, mod.exports);
  await mod.exports({ app, obsidian: app.obsidian, quickAddApi: {} });
}

test("起動時: 今日のデイリーを 00_PIP/デイリー に作り、Day Planner が読む置き場所を合わせる", async () => {
  const app = personal({ "00_PIP/デイリー/": "" });
  app.window.moment = () => ({ format: () => "2099-01-01" });
  // いま配っている Periodic Notes は settings.daily を持たない(設定はストアの中)。コアのデイリーノートはオフで空
  const periodic = { settings: { subscribe() {} } };
  const core = { options: {} };
  app.plugins.plugins["periodic-notes"] = periodic;
  app.internalPlugins = { getPluginById: (id) => (id === "daily-notes" ? { instance: core } : null) };
  await startup(app);
  only(app.find(/^00_PIP\/デイリー\/2099-01-01\.md$/), "デイリー");
  assert.deepEqual(app.find(/^2099-01-01\.md$/), [], "一番上にできた");
  assert.equal(periodic.settings.daily.enabled, true);
  assert.equal(periodic.settings.daily.folder, "00_PIP/デイリー");
  assert.equal(core.options.folder, "00_PIP/デイリー");
  assert.equal(core.options.template, "_仕組み/templates/デイリー");
  assert.ok(app.watching, "他の人のノートを見張っていない");
});

test("起動時: 共有 vault(個人設定がない)では何もしない", async () => {
  const app = makeApp({ templatesDir: TEMPLATES, files: { "00_PIP/デイリー/": "" } });
  app.window.moment = () => ({ format: () => "2099-01-01" });
  await startup(app);
  assert.deepEqual(app.find(/2099-01-01/), []);
});

// ---------- 説明資料を作る ----------

// 合図を置く send_now と、1行を聞く窓はまねに置き換え、渡したものを見る
async function deck(app, notePath, answers, ask) {
  app.open(notePath);
  const tp = app.templater.tp(app.vault.getAbstractFileByPath(notePath), null);
  const all = tp.user.make_deck.order("", "");   // 窓の項目は同じ読み込みのものを渡す
  app.answers.push(...answers.map((n) => (n === null ? null : all.find((s) => s.name === n))));
  tp.system = { prompt: async (label) => { app.prompts.push(label); return ask; } };
  tp.user.send_now = async (_tp, opts) => { app.sent = opts; };
  await tp.user.make_deck(tp);
}

test("説明資料: 設計案では「意見をもらう」が一番上、聞きたいことを合図に入れる", async () => {
  const app = personal();
  const order = app.templater.user().make_deck.order("設計案", "").map((s) => s.name);
  assert.equal(order[0], "意見をもらう");
  assert.equal(order.length, 5);
  assert.equal(app.templater.user().make_deck.order("ノード", "部品")[0].name, "社外へ仕様を伝える");
  assert.equal(app.templater.user().make_deck.order("プロジェクト", "")[0].name, "予定を確かめる");
  const design = "試しPJ/01_設計案/0RB0034XGV_樹脂化.md";
  await deck(app, design, [order[0]], "もっと軽い案は");
  assert.deepEqual(app.sent.資料, { note: design, 筋書き: "意見をもらう", ひとこと: "もっと軽い案は" });
  assert.equal(app.sent.wait, 60);
});

test("説明資料: Esc なら何も送らない。知ってもらうは1行を聞かない", async () => {
  const app = personal();
  const goal = "試しPJ/01_目的/0RB0014XGV_軽くする.md";
  await deck(app, goal, [null], "x");
  assert.equal(app.sent, undefined);
  assert.equal(app.templater.user().make_deck.order("目的", "")[0].name, "知ってもらう");
  const before = app.prompts.length;
  await deck(app, goal, ["知ってもらう"], "x");
  assert.equal(app.prompts.length, before + 1);   // 筋書きの窓だけ
  assert.equal(app.sent.資料.ひとこと, "");
});

test("説明資料: id のないノート(デイリー)では作らない", async () => {
  const app = personal();
  await deck(app, "00_PIP/デイリー/2026-11-07.md", [], "");
  assert.equal(app.sent, undefined);
  assert.ok(app.notices.some((n) => n.includes("id のないノート")));
});

// ---------- 走らせる ----------

(async () => {
  let failed = 0;
  for (const [name, fn] of tests) {
    try {
      await fn();
      console.log(`ok   ${name}`);
    } catch (e) {
      failed++;
      console.log(`FAIL ${name}\n     ${e && e.stack ? e.stack.split("\n").slice(0, 3).join("\n     ") : e}`);
    }
  }
  if (OUT) fs.writeFileSync(OUT, JSON.stringify(results, null, 1), "utf8");
  console.log(`${tests.length - failed} / ${tests.length} 件 通った`);
  process.exit(failed ? 1 : 0);
})();
