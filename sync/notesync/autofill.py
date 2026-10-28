"""おまけの自動入力。壊れても核(id 付け・集約・再配布)は止めない(仕様書「核とおまけ」)。

- F-31: イシューの priority を impact と speed(と lead_weeks)から計算して書く。
- F-26: タスク・実験・試作記録の「リスクはどう変わったか」(古いノートは「残ったリスク」)にあるイシューの
  previous が空なら、そのノートを入れる。
- F-27: イシューの generation を previous をたどって計算し、空なら入れ、食い違えば知らせる。

書き換えるのは自分のノート(個人 vault の 01〜05)だけ。他の人のノートは読むだけにする。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import frontmatter, ids
from .assign import LINK
from .report import Report
from .safety import Backup
from .vault import SKIP_DIRS, box_copy_of, is_hidden, read, write

OWN_DIRS = ("01_目的", "01_設計案", "02_ノード", "03_イシュー", "04_タスク", "05_ナレッジ")
DIST = "90_共有"

# 仕様書「priority の決め方」
PRIORITY = {
    ("方針", "すぐ"): 1, ("絞込", "すぐ"): 1,
    ("方針", "時間がかかる"): 2, ("絞込", "時間がかかる"): 2, ("出荷", "すぐ"): 2,
    ("出荷", "時間がかかる"): 3, ("中", "すぐ"): 3,
    ("中", "時間がかかる"): 4, ("小", "すぐ"): 4, ("小", "時間がかかる"): 4,
}
IMPACTS = {"方針", "絞込", "出荷", "中", "小", "未判定"}
SPEEDS = {"すぐ", "時間がかかる"}
RISK_SECTIONS = ("リスクはどう変わったか", "残ったリスク", "判定")


@dataclass
class Doc:
    path: Path
    rel: str        # vault の一番上からの相対パス(/ 区切り)
    id: str
    name: str
    fm: dict
    text: str
    own: bool       # 自分のノート(書き換えてよい)

    @property
    def type(self) -> str:
        t = str(self.fm.get("type") or "").strip()
        # v0.37 までの設計記録と v0.54 までのソリューションは設計案(Yu 2026-10-25、2026-10-28)
        return "設計案" if t in ("設計記録", "ソリューション") else t

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def link(self) -> str:
        return f"[[{self.stem}|{self.name}]]"


def as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x is not None and str(x).strip()]
    return [str(value)]


def targets(value) -> list[str]:
    """属性の値から [[ ]] の行き先(| の左)を取り出す。リンクでなければ値そのもの。"""
    out = []
    for v in as_list(value):
        found = [m.group(1).strip() for m in LINK.finditer(v)]
        out += found or [v.strip()]
    return out


def plain(value: str) -> str:
    t = targets(value)
    t = t[0] if t else value
    file_id, name = ids.split_filename(t.split("/")[-1])
    return name if file_id else t


def load_docs(root: Path, own: bool, tops: tuple[str, ...] | None = None,
              skip: set[str] = frozenset()) -> list[Doc]:
    out = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        parts = rel.parts
        if any(is_hidden(x) for x in parts) or parts[0] in SKIP_DIRS or parts[0] in skip:
            continue
        if tops is not None and parts[0] not in tops:
            continue
        if p.name.endswith(".excalidraw.md") or box_copy_of(p)[0]:
            continue
        file_id, name = ids.split_filename(p.stem)
        if not file_id:
            continue
        text = read(p)
        out.append(Doc(p, rel.as_posix(), file_id.upper(), name, frontmatter.load(text), text, own))
    return out


class Index:
    def __init__(self, docs: list[Doc]):
        self.by_id: dict[str, Doc] = {}
        self.by_name: dict[str, set[str]] = {}
        # 自分のノートを先に入れ、配られた写しや共有の同じ id より優先する
        for d in sorted(docs, key=lambda d: not d.own):
            self.by_id.setdefault(d.id, d)
            for n in [d.name, *as_list(d.fm.get("aliases"))]:
                self.by_name.setdefault(n.strip().lower(), set()).add(d.id)

    def resolve(self, target: str) -> Doc | None:
        file_id, _ = ids.split_filename(target.split("/")[-1])
        if file_id and file_id.upper() in self.by_id:
            return self.by_id[file_id.upper()]
        found = self.by_name.get(target.strip().lower(), set())
        if len(found) == 1:
            return self.by_id.get(next(iter(found)))
        return None

    def projects(self) -> dict[str, Doc]:
        out: dict[str, Doc] = {}
        for d in self.by_id.values():
            if d.type == "プロジェクト":
                out.setdefault(d.name, d)
        return out


class Writer:
    """自分のノートの属性を書き換える。試し運転では書かず、記録だけ残す。"""

    def __init__(self, personal: Path, report: Report, backup: Backup, dry_run: bool,
                 now: float, idle_seconds: int, fresh: set[str] = frozenset()):
        self.personal = personal
        self.fresh = fresh  # F-28: 作ったばかりでテンプレートのままのノートは触らない
        self.report = report
        self.backup = backup
        self.dry_run = dry_run
        self.now = now
        self.idle_seconds = idle_seconds

    def busy(self, doc: Doc) -> bool:
        if doc.id in self.fresh:
            return True
        return self.idle_seconds > 0 and self.now - doc.path.stat().st_mtime < self.idle_seconds

    def set(self, doc: Doc, values: dict[str, str], what: str) -> bool:
        if self.busy(doc):
            self.report.record(f"{doc.rel} は書いている途中なので、{what}は次の同期で入れます")
            return False
        new = frontmatter.set_values(doc.text, values)
        if new == doc.text:
            return False
        self.report.record(f"{what}: {doc.rel}")
        if not self.dry_run:
            self.backup.save(self.personal, doc.path)
            write(doc.path, new)
        doc.text = new
        doc.fm = frontmatter.load(new)
        return True


    def set_text(self, doc: Doc, new: str, what: str) -> bool:
        if new == doc.text:
            return False
        if self.busy(doc):
            self.report.record(f"{doc.rel} は書いている途中なので、{what}は次の同期で入れます")
            return False
        self.report.record(f"{what}: {doc.rel}")
        if not self.dry_run:
            self.backup.save(self.personal, doc.path)
            write(doc.path, new)
        doc.text = new
        doc.fm = frontmatter.load(new)
        return True


# ---------- F-31: priority ----------

def to_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


MILESTONE_SECTION = "期間・主な節目"


def milestones(proj: Doc) -> list[tuple[str, date | None, date | None]]:
    """プロジェクトの節目 (名前, 計画日, 見込み日)。

    本文「## 期間・主な節目」の表(| 節目 | 計画日 | 見込み日 |)を読む。
    v0.48 までの属性 milestones: [{name, plan, forecast}] も読み続ける
    (Obsidian のプロパティ欄が入れ子を扱えず赤くなるため本文の表に移した。Yu 2026-10-26)。
    """
    out: list[tuple[str, date | None, date | None]] = []
    _, body = frontmatter.split(proj.text)
    inside = False
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m:
            inside = m.group(2) == MILESTONE_SECTION
            continue
        if not inside or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not cells[0] or set(cells[0]) <= set("-: ") or cells[0] == "節目":
            continue
        cells += [""] * 3
        out.append((plain(cells[0]), to_date(cells[1]), to_date(cells[2])))
    if out:
        return out
    stones = proj.fm.get("milestones") or []
    if isinstance(stones, list):
        for s in stones:
            if isinstance(s, dict):
                out.append((str(s.get("name") or "").strip(), to_date(s.get("plan")),
                            to_date(s.get("forecast"))))
    return out


def deadline(issue: Doc, projects: dict[str, Doc], today: date) -> tuple[date, str] | None:
    """lead_weeks の締め切り: イシューの milestone、なければプロジェクトの次のマイルストーンの見込み日。"""
    wanted = plain(str(issue.fm.get("milestone") or "")).strip()
    found: list[tuple[date, str]] = []
    for p in (plain(x).strip() for x in as_list(issue.fm.get("project"))):
        proj = projects.get(p)
        if not proj:
            continue
        for name, plan, forecast in milestones(proj):
            d = forecast or plan
            if not d:
                continue
            if wanted:
                if name == wanted:
                    found.append((d, f"{p} の {name}"))
            elif d >= today:
                found.append((d, f"{p} の {name}"))
    return min(found) if found else None


def priority_of(issue: Doc, projects: dict[str, Doc], today: date, report: Report) -> int | None:
    impact = str(issue.fm.get("impact") or "").strip() or "未判定"
    speed = str(issue.fm.get("speed") or "").strip() or "すぐ"
    if impact == "大":
        impact = "出荷"
        report.todo(f"impact の書き直し: {issue.link} の impact「大」は v0.22 までの書き方です。"
                    "出荷として priority を計算しました。方針・絞込・出荷から選び直してください")
    if impact not in IMPACTS or speed not in SPEEDS:
        report.todo(f"impact か speed が読めません: {issue.link}(impact: {impact}、speed: {speed})。priority を入れていません")
        return None
    p = 2 if impact == "未判定" else PRIORITY[(impact, speed)]
    lead = issue.fm.get("lead_weeks")
    if lead not in (None, "") and p > 1:
        try:
            weeks = float(lead)
        except (TypeError, ValueError):
            report.todo(f"lead_weeks が数ではありません: {issue.link}({lead})")
            return p
        due = deadline(issue, projects, today)
        if due and (due[0] - today).days / 7 <= weeks:
            report.record(f"期限から逆算して priority 1 にした: {issue.rel}"
                          f"({due[1]} {due[0].isoformat()} まで {lead} 週かかる)")
            return 1
    return p


def fill_priority(docs: list[Doc], index: Index, w: Writer, today: date) -> None:
    projects = index.projects()
    for d in docs:
        if not d.own or d.type != "イシュー" or d.rel.startswith("99_"):
            continue
        p = priority_of(d, projects, today, w.report)
        if p is None:
            continue
        if str(d.fm.get("priority") or "").strip() != str(p):
            w.set(d, {"priority": str(p)}, f"priority を {p} にした")


# ---------- F-26: previous ----------

def section_links(text: str, heading) -> list[str]:
    headings = {heading} if isinstance(heading, str) else set(heading)
    _, body = frontmatter.split(text)
    out, inside = [], False
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m:
            inside = m.group(2) in headings
            continue
        if inside:
            out += [x.group(1).strip() for x in LINK.finditer(line)]
    return out


def fill_previous(docs: list[Doc], index: Index, w: Writer) -> None:
    for src in docs:
        if src.type not in ("タスク", "実験・試作記録"):
            continue
        for t in section_links(src.text, RISK_SECTIONS):
            issue = index.resolve(t)
            if not issue or issue.type != "イシュー" or not issue.own or issue.id == src.id:
                continue
            if as_list(issue.fm.get("previous")):
                continue
            if w.set(issue, {"previous": json.dumps([src.link], ensure_ascii=False)},
                     f"previous に {src.name} を入れた"):
                w.report.todo(f"previous を補った: {issue.link} は {src.link} のリスクの欄にあったので、"
                              "previous に入れました。違っていたら直してください")


# ---------- F-27: generation ----------

def origin_issue(doc: Doc, index: Index) -> Doc | None:
    """previous の先にある元のイシュー。previous がイシューならそれ、対策(タスク)なら、その parent のイシュー。"""
    if doc.type == "イシュー":
        return doc
    seen = set()
    level = [doc]
    while level:
        nxt = []
        for d in level:
            if d.id in seen:
                continue
            seen.add(d.id)
            for t in targets(d.fm.get("parent")):
                p = index.resolve(t)
                if not p:
                    continue
                if p.type == "イシュー":
                    return p
                nxt.append(p)
        level = nxt
    return None


def generation_of(issue: Doc, index: Index, memo: dict[str, int | None], path: list[str]) -> int | None:
    """None は循環(警告は呼ぶ側で出す)。"""
    if issue.id in memo:
        return memo[issue.id]
    if issue.id in path:
        return None
    prev = [index.resolve(t) for t in targets(issue.fm.get("previous"))]
    prev = [p for p in prev if p]
    if not prev:
        memo[issue.id] = 1
        return 1
    best = 0
    for p in prev:
        o = origin_issue(p, index)
        if not o:
            continue
        g = generation_of(o, index, memo, path + [issue.id])
        if g is None:
            memo[issue.id] = None
            return None
        best = max(best, g)
    memo[issue.id] = best + 1
    return best + 1


def fill_generation(docs: list[Doc], index: Index, w: Writer) -> None:
    memo: dict[str, int | None] = {}
    for d in docs:
        if not d.own or d.type != "イシュー" or d.rel.startswith("99_"):
            continue
        g = generation_of(d, index, memo, [])
        if g is None:
            w.report.warn(f"previous が輪になっています: {d.link} から previous をたどると元に戻ります。"
                          "generation を入れていません")
            continue
        now = str(d.fm.get("generation") or "").strip()
        if not now:
            if g > 1 or as_list(d.fm.get("previous")):
                w.set(d, {"generation": str(g)}, f"generation を {g} にした")
        elif now != str(g):
            w.report.todo(f"generation の食い違い: {d.link} は {now} ですが、previous をたどると {g} です。"
                          "どちらかを直してください")


# ---------- F-36: 類似・参考ナレッジ ----------

REF_SECTION = "類似・参考ナレッジ"
REF_DAYS = 7      # 作ってからこの日数のあいだだけ足す(消したリンクを何度も戻さないため)
REF_MAX = 5


def nodes_of(d: Doc, index: Index) -> set[str]:
    out = {n.id for n in (index.resolve(t) for t in targets(d.fm.get("friend"))) if n and n.type == "ノード"}
    if d.type != "イシュー":
        for p in (index.resolve(t) for t in targets(d.fm.get("parent"))):
            if p and p.type == "イシュー":
                out |= nodes_of(p, index)
    return out


def projects_of(d: Doc, index: Index) -> set[str]:
    if d.type == "イシュー":
        return {plain(p) for p in as_list(d.fm.get("project"))}
    out = set()
    for p in (index.resolve(t) for t in targets(d.fm.get("parent"))):
        if p and p.type == "イシュー":
            out |= projects_of(p, index)
    return out


def knowledge_issues(k: Doc, index: Index) -> list[Doc]:
    found = [index.resolve(m.group(1).strip()) for v in as_list(k.fm.get("risk_reduction")) for m in LINK.finditer(v)]
    level = [index.resolve(t) for t in targets(k.fm.get("parent"))]
    seen = set()
    while level:
        nxt = []
        for p in level:
            if not p or p.id in seen:
                continue
            seen.add(p.id)
            if p.type == "イシュー":
                found.append(p)
            else:
                nxt += [index.resolve(t) for t in targets(p.fm.get("parent"))]
        level = nxt
    return [f for f in found if f]


def insert_refs(text: str, lines: list[str]) -> str | None:
    nl = "\r\n" if "\r\n" in text else "\n"
    rows = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, r in enumerate(rows) if re.match(rf"^#{{1,6}}\s+{REF_SECTION}\s*$", r)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(rows)) if re.match(r"^#{1,6}\s", rows[i])), len(rows))
    while end > start + 1 and not rows[end - 1].strip():
        end -= 1
    rows[end:end] = lines
    return nl.join(rows)


def fill_references(docs: list[Doc], index: Index, w: Writer) -> None:
    for d in docs:
        if not d.own or d.type not in ("イシュー", "タスク") or d.rel.startswith("99_"):
            continue
        made = ids.decode_time(d.id).timestamp()
        if w.now - made > REF_DAYS * 86400:
            continue
        nodes = nodes_of(d, index)
        if not nodes:
            continue
        mine = projects_of(d, index)
        have = {index.resolve(m.group(1).strip()).id for m in LINK.finditer(d.text)
                if index.resolve(m.group(1).strip())}
        issues, knowledge = [], []
        for o in index.by_id.values():
            if o.id == d.id or o.id in have or o.rel.startswith("99_"):
                continue
            if o.type == "イシュー" and nodes_of(o, index) & nodes and not (projects_of(o, index) & mine):
                issues.append(o)
            elif o.type == "ナレッジ" and str(o.fm.get("usefulness") or "").strip().upper() in ("A", "B"):
                related = set()
                for i in knowledge_issues(o, index):
                    related |= nodes_of(i, index)
                related |= {x.id for x in (index.resolve(m.group(1).strip()) for m in LINK.finditer(o.text)) if x}
                if related & nodes:
                    knowledge.append(o)
        lines = [f"- {k.link}(ナレッジ、有用性 {str(k.fm.get('usefulness')).strip().upper()})"
                 for k in sorted(knowledge, key=lambda k: str(k.fm.get("usefulness")))[:REF_MAX]]
        lines += [f"- {i.link}({'・'.join(sorted(projects_of(i, index))) or '別のプロジェクト'} のイシュー)"
                  for i in sorted(issues, key=lambda i: i.name)[:REF_MAX]]
        if not lines:
            continue
        new = insert_refs(d.text, lines)
        if new:
            w.set_text(d, new, f"類似・参考ナレッジを {len(lines)} 件足した")


# ---------- まとめて ----------

def run_autofill(personal: Path, shared: Path | None, report: Report, backup: Backup,
                 dry_run: bool, now: float, idle_seconds: int, fresh: set[str] = frozenset()) -> None:
    try:
        docs = load_docs(personal, own=True, tops=OWN_DIRS + ("99_archive",))
        docs += load_docs(personal / DIST, own=False)
        if shared and shared.exists():
            docs += load_docs(shared, own=False, skip={"00_inbox", "00_週報"})
        index = Index(docs)
        w = Writer(personal, report, backup, dry_run, now, idle_seconds, fresh)
        today = datetime.fromtimestamp(now, tz=ids.JST).date()
        fill_previous(docs, index, w)
        fill_generation(docs, index, w)
        fill_priority(docs, index, w, today)
        fill_references(docs, index, w)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"priority・previous・generation の自動入力で止まりました({type(e).__name__}: {e})。"
                    "id 付けと共有はそのまま行いました")
