// ノートを作るときに、だれに見せるか(visibility)を選んでもらう(仕様書「共有する範囲」v0.91)。
// テンプレートの属性欄から呼ぶ: visibility: <%* tR += await tp.user.ask_visibility(tp) %>
//
// 書けるのは決まった言葉だけ:
//   PIP(自分だけ。ほかと組み合わせない)/ Internal use only(社内全般)/ 台帳のプロジェクト名(所属者だけ。2つ以上も可)
//   と、PIP 以外に足せる EXT_<相手>(特定の社外。共有の _仕組み/EXT_一覧.csv に登録した相手)。
// 選ぶ窓: 1. PIP / Internal use only / プロジェクト名(Esc なら PIP)
//         2. プロジェクトを選んだら「ほかのプロジェクトも足す」(「これで決める」か Esc で終わり)
//         3. PIP 以外なら EXT を足すか(登録した相手がいなければ聞かない)
// PIP を選んだノートは、種類にかかわらず 00_PIP/メモ/ へ移す(同期プログラムは 00_PIP/ を読まない)。
// Ctrl+I・T・H・U・「ナレッジにする」・K-Plex の中心から作るときは、押したノートの範囲を聞かずに引き継ぐ
// (make_note.js が window.__notebaseVisibility に入れる。デイリー・メモ・週報から作るときは聞く)。
// 共有 vault で作るときは聞かずに Internal use only。

const PIP = "PIP";
const INTERNAL = "Internal use only";
const EXT_PREFIX = "EXT_";
const PIP_DIR = "00_PIP/メモ";
const EXT_LIST = "_仕組み/EXT_一覧.csv";
const OLD = { 個人: PIP, 社内: INTERNAL };
const DONE = "__done__";
const NO_EXT = "__no_ext__";

// 属性欄の値 → 配列。v0.89 までの 個人・社内 は読み替える。チーム・空は null(範囲を決めていない)
function read(value) {
  const list = (Array.isArray(value) ? value : value == null ? [] : [value])
    .map((v) => String(v).trim()).filter((v) => v);
  if (!list.length || list.every((v) => v === "チーム")) return null;
  return [...new Set(list.filter((v) => v !== "チーム").map((v) => OLD[v] || v))];
}

function isPip(list) {
  return !!list && list.includes(PIP);
}

function projectsOf(list) {
  return (list || []).filter((v) => v !== PIP && v !== INTERNAL && !v.startsWith(EXT_PREFIX));
}

// 属性欄に書く形
function text(list) {
  return "[" + (list || []).map((v) => JSON.stringify(v)).join(", ") + "]";
}

// 置く場所。PIP は 00_PIP/メモ、プロジェクトが1つならそのフォルダ、ほか(Internal・2つ以上)は 共通。範囲がなければ null
function placeOf(list, folder, common = "共通") {
  if (!list) return null;
  if (isPip(list)) return PIP_DIR;
  const ps = projectsOf(list);
  return ps.length === 1 ? `${ps[0]}/${folder}` : `${common}/${folder}`;
}

async function extNames(app) {
  try {
    const t = await app.vault.adapter.read(EXT_LIST);
    return t.split(/\r?\n/).slice(1).map((l) => l.split(",")[0].trim()).filter((n) => n && !n.startsWith("#"))
      .map((n) => (n.startsWith(EXT_PREFIX) ? n : EXT_PREFIX + n));
  } catch (e) {
    return [];
  }
}

function choose(app, obsidian, items, label, placeholder) {
  return new Promise((done) => {
    let value = null;
    class Picker extends obsidian.FuzzySuggestModal {
      getItems() { return items; }
      getItemText(x) { return label(x); }
      onChooseItem(x) { value = x; }
      onClose() { setTimeout(() => done(value), 0); } // 選んだときは onChooseItem が閉じたあとに呼ばれる
    }
    const m = new Picker(app);
    m.setPlaceholder(placeholder);
    m.open();
  });
}

// 窓で選ぶ。projects は台帳のプロジェクト名(最近選んだ順)。allowPip: false なら PIP を出さず、Esc は null(やめる)
async function pick(app, obsidian, name, projects, allowPip = true) {
  const shown = String(name).replace(/^[0-9A-Z]{6}[0-9A-Z]+_/, "");
  const first = [...(allowPip ? [PIP] : []), INTERNAL, ...projects];
  const label = (x) => (x === PIP ? "PIP(自分だけ。共有しない)" : x === INTERNAL ? "Internal use only(社内全般)"
    : x === DONE ? "これで決める" : x === NO_EXT ? "社外には見せない" : x.startsWith(EXT_PREFIX) ? `${x}(この社外にも見せる)`
      : `${x}(このプロジェクトの所属者だけ)`);
  const top = await choose(app, obsidian, first, label,
    `「${shown}」をだれに見せますか(${allowPip ? "Esc で PIP" : "次の同期で共有されます。Esc でやめる"})`);
  if (!top) return allowPip ? [PIP] : null;
  if (top === PIP) return [PIP];
  const out = [top];
  if (top !== INTERNAL) {
    for (;;) {
      const rest = projects.filter((p) => !out.includes(p));
      if (!rest.length) break;
      const more = await choose(app, obsidian, [DONE, ...rest], label, "ほかのプロジェクトにも見せますか(Esc で決める)");
      if (!more || more === DONE) break;
      out.push(more);
    }
  }
  const ext = await extNames(app);
  for (;;) {
    const rest = ext.filter((e) => !out.includes(e));
    if (!rest.length) break;
    const more = await choose(app, obsidian, [NO_EXT, ...rest], label, "社外にも見せますか(Esc で見せない)");
    if (!more || more === NO_EXT || more === DONE) break;
    out.push(more);
  }
  return out;
}

async function ask_visibility(tp) {
  const app = tp.app;
  const file = tp.config.target_file;
  if (file.path.startsWith("_仕組み/")) return "";   // テンプレートそのものを開いたとき
  const inherited = typeof window !== "undefined" ? window.__notebaseVisibility : null;
  if (inherited) return text(inherited);
  if (!(await tp.user.make_id.isPersonal(app))) return text([INTERNAL]);
  const M = tp.user.make_note;
  const picked = await pick(app, tp.obsidian, file.basename, M.projectNames(app));
  // place_note.js が、選んだ範囲から置き場所を決める(プロジェクトをもう一度聞かない)
  if (typeof window !== "undefined") window.__notebaseChosen = { file, value: picked };
  if (isPip(picked) && !file.path.startsWith(PIP_DIR + "/")) {
    await M.ensureFolder(app, PIP_DIR);
    await tp.file.move(`${PIP_DIR}/${file.basename}`);
  }
  return text(picked);
}

module.exports = Object.assign(ask_visibility, { pick, read, text, isPip, projectsOf, placeOf, extNames,
  PIP, INTERNAL, PIP_DIR });
