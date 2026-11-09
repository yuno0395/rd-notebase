"""F-59: 説明資料(仕様書「説明資料(ノートから組み立てる)」)。

Obsidian の右クリック「説明資料を作る」で、押したノートと筋書き(聞く人にしてほしいこと)が
「今すぐ共有へ」と同じ合図で届く(now.py)。1回同期したあと、共有 vault のノートだけで組み立てる
(押したノートが PIP なら個人 vault のノートで。v0.100)。機密 vault は読まない。
中身はノートで直して作り直し、体裁は Excalidraw の図の上で直す。

筋書きは5つ。どれも 表紙 → 要点 → (筋書きごとの章) → 足りないところ の順。1ノート1枚で、
見出しはノートの名前、絵は図の SVG、文は筋書きか種類ごとに決まった欄。
載せるのは押したノートの範囲(visibility)で見せてよいノートだけで、機密区分も押したノートから決める。
Excalidraw の図にするのは deck_draw.py。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import frontmatter, ids
from .autofill import LINK, Doc, as_list, plain, targets, to_date
from . import visibility as vis
from .vault import COMMON, person_name
from .weekly import (DROPPED, OPEN_TASK, SOLVED, Builder, all_history, impact, is_policy_risk, owner, prio,
                     status)

STORIES = ["知ってもらう", "意見をもらう", "決めてもらう", "予定を確かめる", "社外へ仕様を伝える"]
OUTSIDE = "社外へ仕様を伝える"
MAX_NOTES = 20     # 1ノート1枚にするのはここまで。残りは章ごとに表1枚
CUT = 200          # 欄の文字はこの長さで切る(社外向けは切らない)
OUT_DIR = "説明資料"

# 種類ごとに1枚に出す欄(筋書きの章で決めていないとき。仕様書の表)
FIELDS = {
    "目的": ["誰に何を届けるか", "達成の判定基準"],
    "仮説": ["この仮説", "確かめ方", "わかったこと"],
    "設計案": ["この案の中身", "価値の仮説を実現できるか", "どの条件ならこの案が勝つか", "採用・不採用の理由"],
    "イシュー": ["リスク", "減らす方法"],
    "タスク": ["完了の条件", "リスクはどう変わったか"],
    "ナレッジ": ["結論", "次に気をつけること"],
    "実験・試作記録": ["判定", "測定結果"],
    "ノード": ["これは何か", "わかっていること"],
    "議事録": ["決まったこと", "出た指摘・懸念"],
    "プロジェクト": ["このプロジェクトで届けるもの", "期間・主な節目"],
}
# 種類 → テンプレート(欄の説明の行を外すため)
TEMPLATE = {"仮説": "価値の仮説", "部品": "部品"}
# 社外向けに出さない部品表の列
SECRET_COLS = ("単価", "金額", "価格", "見積", "発注先", "仕入", "原価")


class DeckError(Exception):
    """作れないとき。文は Obsidian の右上に出る。"""


@dataclass
class Slide:
    kind: str                 # cover / summary / note / table / figure / text / gaps
    title: str
    chapter: str = ""
    sections: list[tuple[str, str]] = field(default_factory=list)   # (見出し, Markdown の文)
    image: str = ""           # 図の SVG の中身
    foot: str = ""
    faded: bool = False
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    svg: str = ""             # 全体の形・工程表の図
    big: str = ""             # 大きく出す1行(聞きたいこと・決めてほしいこと)
    refs: list[tuple[str, str]] = field(default_factory=list)   # 引用: もとのノートの (id, 名前)
    image_path: Path | None = None   # 図の SVG のファイル(資料に絵として貼る)


@dataclass
class Deck:
    title: str
    story: str
    project: str
    made_on: date
    maker: str
    slides: list[Slide] = field(default_factory=list)
    gaps: list[list[str]] = field(default_factory=list)   # [ノートの名前, 足りないもの]
    label: str = ""           # 機密区分(押したノートの visibility から)
    hide_ids: bool = False    # 社外のもの: 引用に id を出さない
    source: str = ""          # 押したノートの id
    pip: bool = False         # 押したノートが PIP(個人 vault で作った)
    affiliation: str = ""     # 作った人の所属(個人設定.md の affiliation)
    company: str = ""         # チーム設定の 会社名

    @property
    def count(self) -> int:
        return len(self.slides)


def default_story(doc_type: str, kind: str = "") -> str:
    """種類に合う筋書き(Obsidian の窓で一番上に出すもの。make_deck.js と同じ決まり)。"""
    if doc_type in ("イシュー", "設計案"):
        return "意見をもらう"
    if doc_type == "議事録":
        return "決めてもらう"
    if doc_type == "プロジェクト":
        return "予定を確かめる"
    if doc_type in ("実験・試作記録", "タスク") or kind == "部品":
        return OUTSIDE
    return "知ってもらう"


# ---------- ノートの本文 ----------

HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


def sections_of(text: str) -> dict[str, list[str]]:
    """本文を見出し(## など)ごとの行に分ける。"""
    _, body = frontmatter.split(text)
    out: dict[str, list[str]] = {}
    cur = ""
    for line in body.splitlines():
        m = HEAD.match(line)
        if m:
            cur = m.group(2)
            out.setdefault(cur, [])
            continue
        out.setdefault(cur, []).append(line)
    return out


def plain_links(text: str) -> str:
    """[[id_名前|名前]] を 名前 に。id は見せない。"""
    def one(m):
        if m.group(2):
            return m.group(2)[1:]
        return plain(m.group(0))
    return LINK.sub(one, text)


class Notes:
    """共有 vault のノートを、資料に載せる形で読む。"""

    def __init__(self, shared: Path, today: date, project: str | None = None, history: list[dict] | None = None):
        self.shared = shared
        self.b = Builder(shared, today, all_history(shared) if history is None else history)
        self.today = today
        self.project = project  # 資料のもとのノートのプロジェクト
        self.scope: vis.Scope | None = None   # 押したノートの範囲。None なら PIP 以外は全部載せる
        self.allow_all = False                 # 押したノートが PIP(個人 vault で作る)なら全部
        self.hidden: dict[str, str] = {}       # 範囲が狭いので載せなかったノート id → 名前
        self._tpl: dict[str, dict[str, set[str]]] = {}

    # --- 載せてよいか ---

    def ok(self, d: Doc) -> bool:
        """押したノートの範囲で見せてよいか(仕様書「機密区分の決め方」)。だめなら hidden に覚える。"""
        if self.allow_all:
            return True
        s = vis.parse(d.fm)
        good = not s.pip and (self.scope is None or covers(effective(d), self.scope))
        if not good and not s.pip:
            self.hidden.setdefault(d.id, self.title(d))
        return good

    # --- つながり ---

    def docs(self) -> list[Doc]:
        return [d for d in self.b.docs if self.ok(d)]

    def get(self, note_id: str) -> Doc | None:
        d = self.b.index.by_id.get(note_id.upper())
        return d if d and self.ok(d) else None

    def resolve(self, target: str) -> Doc | None:
        d = self.b.index.resolve(target)
        return d if d and self.ok(d) else None

    def parents(self, d: Doc) -> list[Doc]:
        return [p for p in self.b.parents(d) if self.ok(p)]

    def kids(self, d: Doc, *types: str) -> list[Doc]:
        return [k for k in self.b.children.get(d.id, []) if (not types or k.type in types) and self.ok(k)]

    def threats(self, *ds: Doc) -> list[Doc]:
        """ds を 脅かす(か parent の)イシュー。中止を除き、閉じていないもの・impact の大きい順。"""
        want = {d.id for d in ds}
        out = [i for i in self.docs() if i.type == "イシュー" and status(i) != "中止"
               and any(p.id in want for p in self.parents(i))]
        return sorted(out, key=lambda i: (status(i) in SOLVED, not is_policy_risk(i), prio(i) or 9, i.name))

    def ups(self, d: Doc) -> list[Doc]:
        """目的までの親(近い順)。"""
        out, seen, cur = [], {d.id}, [d]
        while cur:
            nxt = []
            for c in cur:
                for p in self.parents(c):
                    if p.id not in seen:
                        seen.add(p.id)
                        out.append(p)
                        if p.type != "目的":
                            nxt.append(p)
            cur = nxt
        return out

    def values(self, d: Doc) -> list[Doc]:
        return [h for h in self.b.values(d) if self.ok(h)]

    def knowledge_for(self, *ds: Doc) -> list[Doc]:
        """ds を risk_reduction に書いたか、parent にしたナレッジ。"""
        want = {d.id for d in ds}
        out = []
        for k in self.docs():
            if k.type != "ナレッジ":
                continue
            refs = [self.b.index.resolve(t) for t in targets(k.fm.get("risk_reduction"))]
            if any(r and r.id in want for r in refs) or any(p.id in want for p in self.parents(k)):
                out.append(k)
        return sorted(out, key=lambda k: k.name)

    def project_of(self, d: Doc) -> str:
        names = sorted(self.b.project_of(d))
        return names[0] if names else ""

    def ledger(self, d: Doc) -> Doc | None:
        if d.type == "プロジェクト":
            return d
        return self.b.index.projects().get(self.project_of(d))

    # --- 1枚の中身 ---

    def title(self, d: Doc) -> str:
        a = as_list(d.fm.get("aliases"))
        return (a[0] if a else d.name).strip() or d.name

    def template_lines(self, d: Doc) -> dict[str, set[str]]:
        name = TEMPLATE.get("部品" if str(d.fm.get("kind") or "").strip() == "部品" else d.type, d.type)
        if name not in self._tpl:
            p = self.shared / "_仕組み" / "templates" / f"{name}.md"
            try:
                secs = sections_of(p.read_text(encoding="utf-8"))
            except OSError:
                secs = {}
            self._tpl[name] = {k: {x.strip() for x in v if x.strip()} for k, v in secs.items()}
        return self._tpl[name]

    def field(self, d: Doc, heading: str) -> str:
        """欄の中身。テンプレートの説明の行・図の引用・Templater の行は外す。"""
        skip = self.template_lines(d).get(heading, set())
        lines = []
        for line in sections_of(d.text).get(heading, []):
            t = line.strip()
            if t in skip or t.startswith("![[") or "<%" in t or t.startswith("%%"):
                continue
            lines.append(line.rstrip())
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        return plain_links("\n".join(lines))

    def image(self, d: Doc) -> str:
        """図の SVG の中身。"""
        p = self.image_path(d)
        if not p:
            return ""
        try:
            return p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""

    def image_path(self, d: Doc) -> Path | None:
        """図の SVG(属性 image。なければ添付の fig_*.svg)。"""
        cands = []
        for t in targets(d.fm.get("image")):
            cands.append(self.shared / t.lstrip("/"))
        folder = self.shared / "_仕組み" / "attachments" / d.id
        if folder.is_dir():
            cands += sorted(folder.glob("fig_*.svg"))
        for p in cands:
            if p.suffix.lower() == ".svg" and p.is_file():
                return p
        return None

    def foot(self, d: Doc) -> str:
        bits = [d.type]
        if status(d):
            bits.append(status(d))
        if d.type == "イシュー" and impact(d):
            bits.append(f"impact {impact(d)}")
        who = [person_name(a) for a in as_list(d.fm.get("author"))]
        if who:
            bits.append("作成 " + "・".join(who))
        rev = [person_name(a) for a in as_list(d.fm.get("reviewed_by"))]
        if rev:
            bits.append("確認 " + "・".join(rev))
        secret = [plain(t) for t in as_list(d.fm.get("secret_refs"))]
        if secret:
            bits.append("機密の参照 " + "・".join(secret))
        day = to_date(d.fm.get("updated")) or date.fromtimestamp(d.path.stat().st_mtime)
        bits.append(f"更新 {day.isoformat()}")
        return " ・ ".join(bits)


class Composer:
    """筋書きに沿って Deck を組み立てる。"""

    def __init__(self, notes: Notes, story: str, start: Doc, ask: str, maker: str):
        self.n = notes
        self.story = story
        self.start = start
        self.ask = ask.strip()
        self.used = 0
        self.seen: set[str] = set()
        self.deck = Deck(notes.title(start), story, notes.project_of(start), notes.today, maker)

    # --- 部品 ---

    def add(self, s: Slide) -> None:
        self.deck.slides.append(s)

    def note(self, d: Doc, chapter: str, fields: list[str] | None = None, faded: bool = False) -> bool:
        """1ノート1枚。20枚を超えたら False(呼んだ側が表にまとめる)。"""
        if d.id in self.seen or not self.n.ok(d):
            return True
        if self.used >= MAX_NOTES:
            return False
        self.seen.add(d.id)
        self.used += 1
        names = fields or FIELDS.get(d.type, ["これは何か"])
        secs = []
        for h in names:
            v = self.n.field(d, h)
            if self.story == OUTSIDE:
                v = outside_text(v)
            elif len(v) > CUT:
                v = cut(v)
            secs.append((h, v))
            if not v.strip() and self.story != OUTSIDE:
                self.deck.gaps.append([self.n.title(d), f"「{h}」が空"])
        img_path = self.n.image_path(d)
        img = self.n.image(d)
        if self.story != OUTSIDE:
            if not img:
                self.deck.gaps.append([self.n.title(d), "図がない(Ctrl+D で枠 Summary に描く)"])
            if d.type == "ナレッジ" and not as_list(d.fm.get("reviewed_by")):
                self.deck.gaps.append([self.n.title(d), "確認者(reviewed_by)がいない"])
            if d.type == "ナレッジ":
                rr = [plain(t) for t in as_list(d.fm.get("risk_reduction"))]
                if rr:
                    secs.append(("下がったリスク", "\n".join(f"- {plain_links(r)}" for r in rr)))
        foot = "" if self.story == OUTSIDE else self.n.foot(d)
        self.add(Slide("note", self.n.title(d), chapter, secs, img, foot, faded,
                       refs=[(d.id, self.n.title(d))], image_path=img_path if img else None))
        return True

    def notes(self, ds: list[Doc], chapter: str, fields: list[str] | None = None) -> None:
        rest = []
        for d in ds:
            if not self.note(d, chapter, fields):
                rest.append(d)
        if rest:
            self.add(Slide("table", f"{chapter}: ほかに {len(rest)} 件", chapter, headers=["名前", "種類", "status"],
                           rows=[[self.n.title(d), d.type, status(d)] for d in rest],
                           refs=[(d.id, self.n.title(d)) for d in rest]))

    def table(self, title: str, chapter: str, headers: list[str], rows: list[list[str]], faded=False) -> None:
        self.add(Slide("table", title, chapter, headers=headers, rows=rows or [], faded=faded))

    def text(self, title: str, chapter: str, body: str, big: str = "") -> None:
        self.add(Slide("text", title, chapter, [("", body)] if body else [], big=big))

    def summary(self, lines: list[tuple[str, str]]) -> None:
        self.add(Slide("summary", "要点", "", [(k, v) for k, v in lines if v]))

    # --- 全体 ---

    def build(self) -> Deck:
        cover = Slide("cover", self.deck.title, "", [("筋書き", self.story)])
        if self.story != OUTSIDE and self.deck.project:
            cover.sections.append(("プロジェクト", self.deck.project))
        cover.sections += [("作った日", self.n.today.isoformat()), ("作った人", self.deck.maker)]
        self.add(cover)
        {"知ってもらう": self.inform, "意見をもらう": self.opinion, "決めてもらう": self.decide,
         "予定を確かめる": self.schedule, OUTSIDE: self.outside}[self.story]()
        if self.story != OUTSIDE:
            for name in self.n.hidden.values():
                self.deck.gaps.append([name, "範囲が狭いので載せていません"])
            gaps = self.deck.gaps
            self.add(Slide("gaps", "足りないところ", "", headers=["ノート", "足りないもの"], rows=gaps))
        return self.deck

    # --- 1 知ってもらう ---

    def inform(self) -> None:
        c, n = self.start, self.n
        if c.type == "ナレッジ":
            return self.result(c)
        ups = n.ups(c)
        designs = [u for u in ups if u.type == "設計案"]
        anchor = [c] if c.type in ("設計案", "仮説", "目的") else designs[:1] or [c]
        hyps = []
        for a in anchor:
            hyps += [h for h in n.values(a) if h.id not in {x.id for x in hyps}]
        right = n.threats(c, *designs[:1]) if c.type != "イシュー" else []
        downs: list[Doc] = []
        if c.type == "設計案":
            downs += [k for k in n.kids(c, "設計案") if status(k) not in DROPPED]
        if c.type in ("目的", "プロジェクト"):
            goals = [c] if c.type == "目的" else [g for g in n.docs() if g.type == "目的" and n.project_of(g) == c.name]
            for g in goals:
                downs += n.kids(g, "仮説", "設計案")
        tasks = []
        for x in [c, *right]:
            tasks += [t for t in n.kids(x, "タスク", "実験・試作記録") if status(t) != "中止"]
        know = n.knowledge_for(c, *right, *tasks)
        closed = sum(1 for i in right if status(i) in SOLVED)
        goal_names = "、".join(n.title(g) for g in ups if g.type == "目的")
        req = str((n.ledger(c).fm.get("request_to_manager") if n.ledger(c) else "") or "").strip()
        self.summary([("何のため", goal_names or "(目的につながっていません)"),
                      ("目論見", "、".join(n.title(h) for h in hyps)),
                      ("考えていること", n.title(c)),
                      ("不安材料", f"{len(right)} 件(閉じた {closed}・閉じていない {len(right) - closed}、"
                                  f"うち方針リスク {sum(1 for i in right if is_policy_risk(i))})" if right else ""),
                      ("わかったこと", f"{len(know)} 件" if know else ""),
                      ("判断してほしいこと", req)])
        self.add(Slide("figure", "全体の形", "", svg=self.kplex(c, n.ups(c), hyps, right, downs)))
        why = [u for u in reversed(ups) if u.type in ("目的", "仮説")] + [h for h in hyps if h not in ups]
        if c.type in ("目的", "仮説"):
            why = [w for w in why if w.id != c.id] + [c]
        self.notes(why, "なんのため")
        how = designs[:1] + ([c] if c.type not in ("目的", "仮説", "イシュー", "タスク", "実験・試作記録") else [])
        self.notes(how + [d for d in downs if d.type == "設計案"], "どう実現するか")
        self.notes(([c] if c.type == "イシュー" else []) + right, "何が不安か")
        done = [t for t in tasks if status(t) == "完了"]
        self.notes(([c] if c.type in ("タスク", "実験・試作記録") else []) + know + done, "何がわかったか")
        opened = [i for i in ([c] if c.type == "イシュー" else []) + right if status(i) not in SOLVED]
        moving = [t for t in tasks if status(t) in OPEN_TASK]
        self.table("これから", "これから", ["名前", "種類", "status", "担当", "期限"],
                   [[n.title(d), d.type, status(d), owner(d), str(d.fm.get("due") or "")] for d in opened + moving])
        gone = [d for d in n.kids(designs[0] if designs else c, "設計案") if status(d) in DROPPED] + \
               [h for h in hyps if status(h) == "仮説が誤っていた"]
        if gone:
            self.table("外したもの", "これから", ["名前", "種類", "status"],
                       [[n.title(d), d.type, status(d)] for d in gone], faded=True)

    def result(self, k: Doc) -> None:
        """ナレッジで押したとき: 結果の報告(結論 → 下がったリスク → 確かめたこと → 次に気をつけること)。"""
        n = self.n
        issues = [i for i in (n.resolve(t) for t in targets(k.fm.get("risk_reduction"))) if i]
        tasks = [p for p in n.parents(k) if p.type in ("タスク", "実験・試作記録")]
        self.summary([("結論", cut(n.field(k, "結論"), 120)),
                      ("下がったリスク", "、".join(n.title(i) for i in issues)),
                      ("確かめたこと", "、".join(n.title(t) for t in tasks))])
        self.note(k, "結論", ["結論", "わかったこと"])
        self.notes(issues, "下がったリスク")
        self.notes(tasks, "確かめたこと")
        self.text("次に気をつけること", "次に気をつけること", n.field(k, "次に気をつけること"))

    # --- 2 意見をもらう ---

    def opinion(self) -> None:
        c, n = self.start, self.n
        if c.type in ("タスク", "実験・試作記録"):
            c = next((p for p in n.parents(c) if p.type == "イシュー"), None) or c
        if c.type == "イシュー":
            return self.consult(c)
        if c.type == "設計案":
            return self.inquire(c)
        raise DeckError("「意見をもらう」は、イシューか設計案(タスク・実験・試作記録でもよい)で押してください")

    def consult(self, i: Doc) -> None:
        n = self.n
        back = [p for p in n.parents(i) if p.type in ("設計案", "仮説")][:2]
        tried = [t for t in n.kids(i, "タスク", "実験・試作記録") if status(t) != "中止"]
        know = n.knowledge_for(i, *tried)
        nodes = []
        for m in LINK.finditer(frontmatter.split(i.text)[1]):
            d = n.resolve(m.group(1).strip())
            if d and d.type == "ノード" and d not in nodes:
                nodes.append(d)
        self.summary([("聞きたいこと", self.ask or "(書いていません)"),
                      ("何のための話か", "、".join(n.title(b) for b in back)),
                      ("問題", f"{n.title(i)}: {cut(n.field(i, 'リスク'), 80)}"),
                      ("これまでに試したこと", f"{len(tried)} 件")])
        self.big("聞きたいこと")
        self.notes(back, "背景")
        self.note(i, "問題", ["リスク", "設計空間"])
        self.notes(tried, "これまでに試したこと")
        self.notes(know + nodes, "わかっていること")
        self.text("いまの考え方", "いまの考え方", n.field(i, "減らす方法"))
        self.big("聞きたいこと")

    def inquire(self, d: Doc) -> None:
        n = self.n
        goals = [u for u in n.ups(d) if u.type == "目的"]
        hyps = n.values(d)
        sibs = self.siblings(d)
        self.summary([("聞きたいこと", self.ask or "(書いていません)"),
                      ("何を実現したいか", "、".join(n.title(h) for h in hyps) or "、".join(n.title(g) for g in goals)),
                      ("並ぶ候補", f"{len([s for s in sibs if status(s) not in DROPPED])} 件")])
        self.big("聞きたいこと")
        self.notes(goals, "何を実現したいか")
        self.notes(hyps, "何を実現したいか", ["この仮説", "具体的にすると"])
        self.text("要求・制約", "要求・制約", n.field(d, "要求・制約"))
        self.note(d, "今の案", ["この案の中身", "どの条件ならこの案が勝つか"])
        self.compare(sibs, "並ぶ候補")
        other = n.field(d, "他の候補との比較")
        if other:
            self.text("他の候補との比較", "並ぶ候補", cut(other))
        self.notes(n.threats(d), "今の案の弱いところ")
        gone = [s for s in sibs if status(s) in DROPPED]
        if gone:
            self.table("外した案とその理由", "外した案", ["案", "status", "採用・不採用の理由"],
                       [[n.title(s), status(s), cut(n.field(s, "採用・不採用の理由"), 80)] for s in gone], faded=True)
        self.big("聞きたいこと")

    def big(self, title: str) -> None:
        self.add(Slide("text", title, title, big=self.ask or "(聞きたいことを書いていません)"))

    def siblings(self, d: Doc) -> list[Doc]:
        ps = self.n.parents(d)
        out = [d]
        for p in ps:
            out += [k for k in self.n.kids(p, "設計案") if k.id not in {x.id for x in out}]
        return out

    def compare(self, ds: list[Doc], chapter: str) -> None:
        n = self.n
        rows = []
        for s in ds:
            if status(s) in DROPPED:
                continue
            risks = [i for i in n.threats(s) if is_policy_risk(i)]
            solved = sum(1 for i in risks if status(i) in SOLVED)
            rows.append([n.title(s), status(s) or "進行中", "、".join(n.title(h) for h in n.values(s)),
                         str(len(risks) - solved), str(solved), cut(n.field(s, "どの条件ならこの案が勝つか"), 60)])
        self.table("候補の比較", chapter, ["候補", "status", "実現する仮説", "方針リスク 未解決", "解決", "どの条件なら勝つか"],
                   rows)

    # --- 3 決めてもらう ---

    def decide(self) -> None:
        c, n = self.start, self.n
        ask = self.ask
        if c.type == "設計案":
            cands = self.siblings(c)
        elif c.type == "目的":
            cands = n.kids(c, "設計案")
        elif c.type == "プロジェクト":
            cands = [k for g in n.docs() if g.type == "目的" and n.project_of(g) == c.name for k in n.kids(g, "設計案")]
            ask = ask or str(c.fm.get("request_to_manager") or "").strip()
        elif c.type == "議事録":
            cands = []
            for m in LINK.finditer(sections_text(c, "議題")):
                d = n.resolve(m.group(1).strip())
                if d and d.type == "設計案" and d not in cands:
                    cands.append(d)
            ask = ask or cut(n.field(c, "議題"), 120)
        else:
            raise DeckError("「決めてもらう」は、設計案・目的・台帳・議事録で押してください")
        if not cands:
            raise DeckError("選ぶ候補(設計案)が見つかりません。議事録なら「議題」に設計案のリンクを書いてください")
        self.ask = ask
        alive = [s for s in cands if status(s) not in DROPPED]
        pick = next((s for s in alive if status(s) == "採用"), None)
        if pick:
            rec = f"{n.title(pick)}(採用)"
        elif alive:
            least = min(alive, key=lambda s: sum(1 for i in n.threats(s) if is_policy_risk(i) and status(i) not in SOLVED))
            rec = f"いちばん方針リスクが少ない: {n.title(least)}"
        else:
            rec = ""
        goals = []
        for s in cands:
            goals += [g for g in n.ups(s) if g.type == "目的" and g not in goals]
        hyps = []
        for s in alive:
            hyps += [h for h in n.values(s) if h not in hyps]
        self.summary([("決めてほしいこと", ask or "(書いていません)"), ("候補", f"{len(alive)} 件"), ("参考", rec)])
        self.add(Slide("text", "決めてほしいこと", "決めてほしいこと", big=ask or "(決めてほしいことを書いていません)"))
        self.notes(goals, "何を実現したいか")
        self.notes(hyps, "何を実現したいか", ["この仮説", "具体的にすると"])
        self.compare(cands, "候補の比較")
        self.notes(alive, "候補", ["この案の中身", "どの条件ならこの案が勝つか"])
        risks = []
        for s in alive:
            for i in n.threats(s):
                if impact(i) in ("方針", "絞込") and status(i) not in SOLVED:
                    risks.append([n.title(s), n.title(i), impact(i), status(i)])
        curves = [k for s in alive for k in n.knowledge_for(*n.threats(s)) if n.field(k, "トレードオフ曲線")]
        self.notes(list(dict.fromkeys(curves)), "トレードオフ曲線", ["結論", "トレードオフ曲線"])
        self.table("候補ごとの残りのリスク", "残りのリスク", ["候補", "イシュー", "impact", "status"], risks)
        if c.type == "議事録" and n.field(c, "解像度の判定"):
            self.text("解像度", "解像度", n.field(c, "解像度の判定"))
        self.add(Slide("text", "決めてほしいこと", "決めてほしいこと", big=ask or "(決めてほしいことを書いていません)"))

    # --- 4 予定を確かめる ---

    def schedule(self) -> None:
        n = self.n
        proj = n.ledger(self.start)
        if not proj:
            raise DeckError("このノートのプロジェクトの台帳が見つかりません")
        self.deck.title = n.title(proj)
        self.deck.project = proj.name
        today = n.today
        stones = n.b.milestones(proj)
        late = [r for r in stones if r[3].startswith("+") and r[3] != "+0 日"]
        nxt = next((r for r in stones if (to_date(r[2]) or to_date(r[1]) or date.max) >= today), None)
        docs = [d for d in n.b.in_project(proj.name) if n.ok(d)]
        tasks = [t for t in docs if t.type == "タスク" and status(t) in OPEN_TASK]
        overdue = [t for t in tasks if (to_date(t.fm.get("due")) or date.max) < today]
        req = str(proj.fm.get("request_to_manager") or "").strip()
        self.summary([("次の節目", f"{nxt[0]}(計画 {nxt[1] or '-'}・見込み {nxt[2] or '-'}・ずれ {nxt[3] or '-'})" if nxt else ""),
                      ("遅れている節目", f"{len(late)} 件"), ("期限切れのタスク", f"{len(overdue)} 件"),
                      ("判断してほしいこと", req)])
        self.table("節目", "節目", ["節目", "計画日", "見込み日", "ずれ"], stones)
        from .schedule import build_plan
        from .weekly_html import gantt_svg
        plan = build_plan(proj, [d for d in docs if d.rel.startswith(proj.name + "/")], n.b.index, n.b.history, today)
        if plan.bars or plan.stones:
            self.add(Slide("figure", "工程表", "工程表", svg=gantt_svg(plan, today)))

        def parent_name(t):
            p = next((p for p in n.parents(t)), None)
            return n.title(p) if p else ""
        self.table("遅れ・期限切れのタスク", "遅れ", ["タスク", "担当", "期限", "status", "減らすイシュー"],
                   [[n.title(t), owner(t), str(t.fm.get("due") or ""), status(t), parent_name(t)] for t in overdue])
        self.table("待ちのタスク", "待ち", ["タスク", "担当", "期限", "減らすイシュー"],
                   [[n.title(t), owner(t), str(t.fm.get("due") or ""), parent_name(t)] for t in tasks if status(t) == "待ち"])
        self.table("節目の前に閉じる方針リスク", "方針リスク", ["イシュー", "status", "担当"],
                   [[n.title(i), status(i), owner(i)] for i in docs
                    if i.type == "イシュー" and is_policy_risk(i) and status(i) not in SOLVED | {"中止"}])
        until = (to_date(nxt[2]) or to_date(nxt[1])) if nxt else None
        soon = [t for t in tasks if t not in overdue and (not until or (to_date(t.fm.get("due")) or date.max) <= until)]
        self.table("これから(次の節目まで)", "これから", ["タスク", "担当", "期限", "status"],
                   [[n.title(t), owner(t), str(t.fm.get("due") or ""), status(t)]
                    for t in sorted(soon, key=lambda t: str(t.fm.get("due") or "9999"))])

    # --- 5 社外へ仕様を伝える ---

    def outside(self) -> None:
        d, n = self.start, self.n
        is_part = str(d.fm.get("kind") or "").strip() == "部品"
        if d.type not in ("実験・試作記録", "タスク") and not is_part:
            raise DeckError("「社外へ仕様を伝える」は、実験・試作記録・タスク・部品で押してください")
        if as_list(d.fm.get("secret_refs")):
            raise DeckError("機密につながるノートからは社外向けを作れません")
        self.deck.project = ""
        if is_part:
            fields = ["これは何か", "PartsList"]
            lead = n.field(d, "これは何か")
        elif d.type == "タスク":
            fields = ["やること", "完了の条件"]
            lead = n.field(d, "やること")
        else:
            fields = ["目的と仮説", "条件"]
            lead = n.field(d, "目的と仮説")
        self.summary([("頼みたいこと", f"{n.title(d)}: {cut(outside_text(lead), 120)}")])
        self.note(d, "仕様", fields)
        who = "・".join(person_name(a) for a in as_list(d.fm.get("author")))
        self.text("問い合わせ先", "問い合わせ先", who)

    # --- 図 ---

    def kplex(self, c: Doc, ups: list[Doc], hyps: list[Doc], right: list[Doc], downs: list[Doc]) -> str:
        from .weekly_html import kplex_svg
        n = self.n
        goal = next((u for u in ups if u.type == "目的"), None)
        return kplex_svg({
            "goal": n.title(goal) if goal else "",
            "name": n.title(c), "status": status(c) or "",
            "hyps": [(n.title(h), status(h) == "仮説が誤っていた") for h in hyps],
            "parts": [n.title(x) for x in downs],
            "issues": [(n.title(i), prio(i), status(i) in SOLVED, is_policy_risk(i)) for i in right],
        })


def sections_text(d: Doc, heading: str) -> str:
    return "\n".join(sections_of(d.text).get(heading, []))


def cut(text: str, n: int = CUT) -> str:
    t = text.strip()
    if len(t) <= n:
        return t
    return t[:n].rstrip() + "…(続きはノートに)"


def outside_text(text: str) -> str:
    """社外向けの文: 部品表の値段・発注先の列を外す。"""
    out, drop = [], []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not drop and not set("".join(cells)) <= set("-: "):
                if not out or not out[-1].strip().startswith("|"):
                    drop = [i for i, c in enumerate(cells) if any(k in c for k in SECRET_COLS)]
            cells = [c for i, c in enumerate(cells) if i not in drop]
            line = "| " + " | ".join(cells) + " |"
        else:
            drop = []
        out.append(line)
    return "\n".join(out)


# ---------- 範囲と機密区分 ----------

def top_of(d: Doc) -> str:
    return d.rel.split("/", 1)[0]


def effective(d: Doc) -> vis.Scope:
    """visibility を書いていない古いノートは、置き場所のプロジェクト(共通なら Internal use only)とみなす。"""
    s = vis.parse(d.fm)
    if s.open:
        top = top_of(d)
        if top in (COMMON, "99_archive") or "/" not in d.rel:
            s.internal = True
        else:
            s.projects = [top]
    return s


def covers(doc: vis.Scope, want: vis.Scope) -> bool:
    """doc のノートを、want の範囲の人に見せてよいか。"""
    if want.ext:
        return set(want.ext) <= set(doc.ext)
    if want.internal:
        return doc.internal
    if want.projects:
        return doc.internal or set(want.projects) <= set(doc.projects)
    return True


def label_of(scope: vis.Scope, company: str, pip: bool) -> str:
    """機密区分。"""
    if pip or scope.pip:
        return "Confidential"
    if scope.ext:
        names = [e[len(vis.EXT_PREFIX):] for e in scope.ext] + ([company] if company else [])
        return "+".join(names) + "/Confidential"
    if scope.internal:
        return vis.INTERNAL
    if scope.projects:
        return "+".join(scope.projects) + "/Confidential"
    return vis.INTERNAL


def settings_value(personal: Path | None, key: str) -> str:
    """個人設定.md の属性(affiliation など)。"""
    if not personal:
        return ""
    try:
        fm = frontmatter.load((personal / "_仕組み" / "個人設定.md").read_text(encoding="utf-8"))
    except OSError:
        return ""
    return str(fm.get(key) or "").strip()


AFFILIATION_LINE = 'affiliation: "" # 自分の所属。例: 開発部 第2グループ(説明資料の {所属} に入る)'


def add_affiliation(personal: Path | None) -> bool:
    """個人設定.md の属性欄に affiliation がなければ空の行を足す(前の版で作った vault のため)。"""
    if not personal:
        return False
    f = personal / "_仕組み" / "個人設定.md"
    try:
        text = f.read_text(encoding="utf-8")
    except OSError:
        return False
    m = re.match(r"\A---\r?\n(.*?)(\r?\n)---", text, re.S)
    if not m or re.search(r"^affiliation\s*:", m.group(1), re.M):
        return False
    nl = m.group(2)
    f.write_text(text[: m.end(1)] + nl + AFFILIATION_LINE + text[m.end(1):], encoding="utf-8")
    return True


def company_name(shared: Path | None) -> str:
    """チーム設定(_仕組み/同期設定.yaml)の 会社名。"""
    if not shared:
        return ""
    import yaml
    try:
        data = yaml.safe_load((shared / "_仕組み" / "同期設定.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ""
    return str(data.get("会社名") or "").strip() if isinstance(data, dict) else ""


# ---------- 入口 ----------

def note_id(personal_note: Path) -> str:
    fid, _ = ids.split_filename(personal_note.stem)
    if not fid:
        raise DeckError("id のないノート(デイリー・メモなど)からは作れません")
    return fid.upper()


def build(shared: Path, personal_note: Path, story: str, ask: str, maker: str, today: date,
          personal: Path | None = None) -> Deck:
    """personal(個人 vault)を渡すと、押したノートが PIP のときに個人 vault のノートで作る。"""
    if story not in STORIES:
        raise DeckError(f"知らない筋書きです: {story}")
    try:
        fm = frontmatter.load(personal_note.read_text(encoding="utf-8"))
    except OSError:
        fm = {}
    pip = vis.is_pip(fm)
    fid = note_id(personal_note)
    if pip:
        if not personal:
            raise DeckError("共有していないノート(PIP)からは作れません")
        n = Notes(personal, today, history=all_history(shared) if shared else [])
        n.allow_all = True
        start = n.get(fid)
        if not start:
            raise DeckError("このノートを読めませんでした。保存してからもう一度押してください")
        scope = vis.Scope(pip=True)
    else:
        n = Notes(shared, today)
        start = n.get(fid)
        if not start:
            raise DeckError("共有していないノートからは作れません(まだ共有に出ていないか、visibility が PIP)")
        top = top_of(start)
        n.project = top if top not in (COMMON, "99_archive") else None
        scope = effective(start)
        n.scope = scope
    company = company_name(shared)
    d = Composer(n, story, start, ask, maker).build()
    d.source = start.id
    d.pip = pip
    d.label = label_of(scope, company, pip)
    if story == OUTSIDE and not scope.ext and not pip:
        # 社外へ仕様を伝える資料はプロジェクト名を出さない(相手を EXT_ で決めていなければ会社名だけ)
        d.label = f"{company}/Confidential" if company else "Confidential"
    d.hide_ids = story == OUTSIDE or bool(scope.ext)
    d.company = company
    d.affiliation = settings_value(personal, "affiliation")
    return d


SAFE = re.compile(r'[\\/:*?"<>|\r\n\t#^\[\]]+')
DECK_DIR = Path(vis.PIP_TOP) / OUT_DIR    # 個人 vault の 00_PIP/説明資料/


def free_name(folder: Path, base: str) -> str:
    """同じ名前の資料があれば _2・_3 を付ける(手直しを消さないよう、上書きしない)。"""
    name, k = base, 1
    while (folder / f"{name}.excalidraw.md").exists() or (folder / f"{name}_共通.excalidraw.md").exists():
        k += 1
        name = f"{base}_{k}"
    return name


def base_name(deck: Deck) -> str:
    return SAFE.sub("_", f"{deck.story}_{deck.title}_{deck.made_on.isoformat()}")


def make(shared: Path, personal: Path, rel_or_path: str, story: str, ask: str, maker: str, today: date) -> tuple[Path, Deck]:
    """資料の図を個人 vault の 00_PIP/説明資料/ に作る。戻り値は資料の図のファイル。"""
    from . import deck_draw
    p = Path(rel_or_path)
    if not p.is_absolute():
        p = personal / p
    add_affiliation(personal)
    deck = build(shared, p, story, ask, maker, today, personal)
    folder = personal / DECK_DIR
    name = free_name(folder, base_name(deck))
    path = deck_draw.write_deck(deck, folder, name, shared, personal)
    return path, deck


def deck_of_pdf(pdf: Path) -> Path | None:
    """PDF の名前から資料の図を探す(<資料>.pdf・<資料>.excalidraw.pdf・<資料>.excalidraw-pages.pdf)。"""
    stem = pdf.stem
    for tail in ("-pages", ".excalidraw"):
        if stem.endswith(tail):
            stem = stem[: -len(tail)]
    if stem.endswith(".excalidraw"):
        stem = stem[: -len(".excalidraw")]
    p = pdf.with_name(f"{stem}.excalidraw.md")
    return p if p.is_file() else None


def copy_pdfs(personal: Path | None, report_dir: Path | None, dry: bool = False) -> list[Path]:
    """00_PIP/説明資料/ の PDF のうち、共有に出ているノートの社内向けの資料のものを、
    報告フォルダの <プロジェクト>/説明資料/ に写す(要件書 F-59b)。新しいか更新されたものだけ。"""
    if not personal or not report_dir:
        return []
    folder = personal / DECK_DIR
    if not folder.is_dir():
        return []
    out = []
    for pdf in sorted(folder.glob("*.pdf")):
        src = deck_of_pdf(pdf)
        if not src:
            continue
        try:
            fm = frontmatter.load(src.read_text(encoding="utf-8"))
        except OSError:
            continue
        pj = str(fm.get("deck_report") or "").strip()
        if not pj or fm.get("deck_outside") or fm.get("deck_pip"):
            continue
        dest = report_dir / SAFE.sub("_", pj) / OUT_DIR / pdf.name
        if dest.exists() and dest.stat().st_mtime >= pdf.stat().st_mtime:
            continue
        out.append(dest)
        if not dry:
            import shutil
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pdf, dest)
    return out
