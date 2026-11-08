// 右クリック「説明資料を作る」(仕様書「説明資料(ノートから組み立てる)」、要件書 F-59)。
//
//   1. 筋書きを5つから選ぶ。開いているノートの種類に合うものが一番上(Enter だけでよい)。Esc なら何もしない。
//   2. 「意見をもらう」「決めてもらう」のときだけ、聞きたいこと・決めてほしいことを1行書く(空でよい)。
//      この1行は資料にだけ出て、ノートには書かない。
//   3. 「今すぐ共有へ」と同じ合図(send_now.js)に、ノートの場所と筋書きを足して置く。
//      同期プログラムが1回同期してから、共有 vault のノートで HTML の資料を作り、ブラウザで開く。

const STORIES = [
  { name: "知ってもらう", hint: "開発の概要・結果の報告・引き継ぎ" },
  { name: "意見をもらう", hint: "考え方の相談・より良い設計案の問い合わせ", ask: "聞きたいこと(なくてもよい)" },
  { name: "決めてもらう", hint: "DR での絞り込み・採用・判断のお願い", ask: "決めてほしいこと(なくてもよい)" },
  { name: "予定を確かめる", hint: "節目に間に合うか・どこが遅れているか" },
  { name: "社外へ仕様を伝える", hint: "試験先・協力会社・仕入れ先に実験や部品の仕様を伝える" },
];

// 種類に合う筋書き(同期プログラムの deck.default_story と同じ決まり)
function first(type, kind) {
  if (type === "イシュー" || type === "設計案") return "意見をもらう";
  if (type === "議事録") return "決めてもらう";
  if (type === "プロジェクト") return "予定を確かめる";
  if (type === "実験・試作記録" || type === "タスク" || kind === "部品") return "社外へ仕様を伝える";
  return "知ってもらう";
}

// 種類に合うものを一番上にした並び
function order(type, kind) {
  const top = first(type, kind);
  return [...STORIES.filter((s) => s.name === top), ...STORIES.filter((s) => s.name !== top)];
}

function pick(tp, items, placeholder) {
  const { FuzzySuggestModal } = tp.obsidian;
  return new Promise((resolve) => {
    let chosen = null;
    const m = new (class extends FuzzySuggestModal {
      getItems() { return items; }
      getItemText(s) { return `${s.name}(${s.hint})`; }
      onChooseItem(s) { chosen = s; }
      onClose() { setTimeout(() => resolve(chosen), 0); }
    })(tp.app);
    m.setPlaceholder(placeholder);
    m.open();
  });
}

async function make_deck(tp) {
  const app = tp.app;
  const { Notice } = tp.obsidian;
  const file = app.workspace.getActiveFile();
  if (!file) { new Notice("説明したいノートを開いてから押してください", 6000); return; }
  const fm = app.metadataCache.getFileCache(file)?.frontmatter || {};
  if (!fm.id) { new Notice("id のないノート(デイリー・メモなど)からは作れません", 6000); return; }
  const story = await pick(tp, order(String(fm.type || ""), String(fm.kind || "")),
    "聞く人に何をしてほしいですか(一番上はこのノートに合うもの)");
  if (!story) return;
  let ask = "";
  if (story.ask) ask = (await tp.system.prompt(story.ask, "")) || "";
  await tp.user.send_now(tp, {
    資料: { note: file.path, 筋書き: story.name, ひとこと: ask },
    waiting: "説明資料を作っています…",
    wait: 60,
  });
}

make_deck.order = order;
module.exports = make_deck;
