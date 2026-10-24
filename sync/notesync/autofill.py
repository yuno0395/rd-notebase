"""おまけの自動入力。壊れても核(id 付け・集約・再配布)は止めない(仕様書「核とおまけ」)。

- F-31: イシューの priority を impact と speed(と lead_weeks)から計算して書く。
- F-26: 設計記録・タスクの「残ったリスク」にあるイシューの previous が空なら、そのノートを入れる。
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

OWN_DIRS = ("01_目的", "02_ノード", "03_イシュー", "04_タスク", "05_ナレッジ")
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
RISK_SECTION = "残ったリスク"


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
        return str(self.fm.get("type") or "").strip()

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
                 now: float, idle_seconds: int):
        self.personal = personal
        self.report = report
        self.backup = backup
        self.dry_run = dry_run
        self.now = now
        self.idle_seconds = idle_seconds

    def busy(self, doc: Doc) -> bool:
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


def deadline(issue: Doc, projects: dict[str, Doc], today: date) -> tuple[date, str] | None:
    """lead_weeks の締め切り: イシューの milestone、なければプロジェクトの次のマイルストーンの見込み日。"""
    wanted = plain(str(issue.fm.get("milestone") or "")).strip()
    found: list[tuple[date, str]] = []
    for p in (plain(x).strip() for x in as_list(issue.fm.get("project"))):
        proj = projects.get(p)
        if not proj:
            continue
        stones = proj.fm.get("milestones") or []
        if not isinstance(stones, list):
            continue
        for s in stones:
            if not isinstance(s, dict):
                continue
            d = to_date(s.get("forecast") or s.get("plan"))
            if not d:
                continue
            name = str(s.get("name") or "").strip()
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

def section_links(text: str, heading: str) -> list[str]:
    _, body = frontmatter.split(text)
    out, inside = [], False
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m:
            inside = m.group(2) == heading
            continue
        if inside:
            out += [x.group(1).strip() for x in LINK.finditer(line)]
    return out


def fill_previous(docs: list[Doc], index: Index, w: Writer) -> None:
    for src in docs:
        if src.type not in ("設計記録", "タスク"):
            continue
        for t in section_links(src.text, RISK_SECTION):
            issue = index.resolve(t)
            if not issue or issue.type != "イシュー" or not issue.own or issue.id == src.id:
                continue
            if as_list(issue.fm.get("previous")):
                continue
            if w.set(issue, {"previous": json.dumps([src.link], ensure_ascii=False)},
                     f"previous に {src.name} を入れた"):
                w.report.todo(f"previous を補った: {issue.link} は {src.link} の「残ったリスク」にあったので、"
                              "previous に入れました。違っていたら直してください")


# ---------- F-27: generation ----------

def origin_issue(doc: Doc, index: Index) -> Doc | None:
    """previous の先にある元のイシュー。previous がイシューならそれ、対策(タスク・設計記録)なら、その parent のイシュー。"""
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


# ---------- まとめて ----------

def run_autofill(personal: Path, shared: Path | None, report: Report, backup: Backup,
                 dry_run: bool, now: float, idle_seconds: int) -> None:
    try:
        docs = load_docs(personal, own=True, tops=OWN_DIRS + ("99_archive",))
        docs += load_docs(personal / DIST, own=False)
        if shared and shared.exists():
            docs += load_docs(shared, own=False, skip={"00_inbox", "00_週報"})
        index = Index(docs)
        w = Writer(personal, report, backup, dry_run, now, idle_seconds)
        today = datetime.fromtimestamp(now, tz=ids.JST).date()
        fill_previous(docs, index, w)
        fill_generation(docs, index, w)
        fill_priority(docs, index, w, today)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"priority・previous・generation の自動入力で止まりました({type(e).__name__}: {e})。"
                    "id 付けと共有はそのまま行いました")
