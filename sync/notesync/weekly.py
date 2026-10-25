"""F-29・F-30: 管理者向けの週報(仕様書「管理者向けの週報」)。

共有 vault のノートの属性と、ノート履歴(history.py)から、プロジェクトごとに作る。
置き場所は個人設定の report(例: Box\\開発ノート_報告)の `<プロジェクト名>/<年-週>.md`。
週報を作るのはチーム設定の report_runner の1台だけ。毎週月曜の最初の同期で作る。

機密フォルダの中身は読まない。secret_refs の件数だけを出す。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from . import ids
from .autofill import Doc, Index, as_list, load_docs, plain, targets, to_date
from .history import HISTORY_DIR, done_date, extensions, read_rows
from .report import Report

BIG = {"方針", "絞込", "出荷", "大"}
STAGES = ["未把握", "現象", "設計空間", "原理"]
OPEN_TASK = {"未着手", "進行中", "待ち", "確認待ち"}
DONE = {"完了", "中止"}
WORK_TYPES = {"タスク", "イシュー", "実験・試作記録"}
STALE_DAYS = 14
CANDIDATE_CSV = "候補の数.csv"


def stage(doc: Doc) -> int:
    r = str(doc.fm.get("resolution") or "").strip() or "未把握"
    return STAGES.index(r) if r in STAGES else 0


def impact(doc: Doc) -> str:
    return str(doc.fm.get("impact") or "").strip()


def status(doc: Doc) -> str:
    return str(doc.fm.get("status") or "").strip()


def is_dr(doc: Doc) -> bool:
    """DR の議事録: kind: DR(DR 議事録のテンプレート)。前からのものは名前に DR を含むもの。"""
    return str(doc.fm.get("kind") or "").strip().upper() == "DR" or "DR" in doc.name.upper()


def owner(doc: Doc) -> str:
    o = as_list(doc.fm.get("owner")) or as_list(doc.fm.get("author"))
    return plain(o[0]) if o else "(不明)"


@dataclass
class Week:
    year: int
    week: int

    @classmethod
    def of(cls, d: date) -> "Week":
        y, w, _ = d.isocalendar()
        return cls(y, w)

    @property
    def label(self) -> str:
        return f"{self.year}-W{self.week:02d}"


@dataclass
class ProjectReport:
    name: str
    lines: list[str] = field(default_factory=list)
    rows: dict[str, list[list[str]]] = field(default_factory=dict)  # Excel の表(シート名 → 行)

    def table(self, sheet: str, header: list[str], body: list[list[str]], empty: str = "なし") -> None:
        self.rows[sheet] = [header] + body
        if not body:
            self.lines += [empty, ""]
            return
        self.lines.append("| " + " | ".join(header) + " |")
        self.lines.append("| " + " | ".join("---" for _ in header) + " |")
        for r in body:
            self.lines.append("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |")
        self.lines.append("")


class Builder:
    def __init__(self, shared: Path, today: date, history: list[dict]):
        self.shared = shared
        self.today = today
        self.history = history
        self.docs = [d for d in load_docs(shared, own=False, skip={"00_inbox", "00_週報"})
                     if not d.rel.startswith("99_archive/")]
        self.index = Index(self.docs)

    # ---------- つながり ----------

    def parents(self, d: Doc) -> list[Doc]:
        return [p for p in (self.index.resolve(t) for t in targets(d.fm.get("parent"))) if p]

    def reach(self, d: Doc, want: str, seen: set[str] | None = None) -> list[Doc]:
        """parent をたどって着く、type が want のノート。"""
        seen = seen if seen is not None else set()
        if d.id in seen:
            return []
        seen.add(d.id)
        if d.type == want:
            return [d]
        out = []
        for p in self.parents(d):
            out += self.reach(p, want, seen)
        return out

    def project_of(self, d: Doc) -> set[str]:
        top = d.rel.split("/")[0]
        if d.type == "イシュー":
            return {plain(p) for p in as_list(d.fm.get("project"))} or {top}
        return {top}

    def in_project(self, pj: str) -> list[Doc]:
        return [d for d in self.docs if pj in self.project_of(d) or d.rel.startswith(pj + "/")]

    # ---------- 1枚目 ----------

    def outlook_age(self, proj: Doc) -> int | None:
        days = [r["日時"][:10] for r in self.history if r.get("id") == proj.id and r.get("項目") == "outlook"]
        if not days:
            return None
        return (self.today - date.fromisoformat(max(days))).days

    def readiness(self, issues: list[Doc]) -> list[list[str]]:
        rows = []
        purposes: dict[str, tuple[Doc, list[Doc]]] = {}
        for i in issues:
            if impact(i) not in BIG:
                continue
            for p in self.reach(i, "目的"):
                purposes.setdefault(p.id, (p, []))[1].append(i)
        for p, items in sorted(purposes.values(), key=lambda x: x[0].name):
            ok = [i for i in items if stage(i) >= 2]
            counts = [sum(1 for i in items if stage(i) == s) for s in range(4)]
            ratio = f"{len(ok) * 100 // len(items)}%({len(ok)}/{len(items)})"
            rows.append([p.name, ratio] + [str(c) for c in counts])
        return rows

    def candidates(self, docs: list[Doc]) -> dict[str, int]:
        """一組の候補(同じ parent の設計記録、ノードの parts)のうち、不採用・中止でないものの数。"""
        out: dict[str, int] = {}
        groups: dict[str, list[Doc]] = {}
        for d in docs:
            if d.type == "設計記録":
                for p in self.parents(d):
                    groups.setdefault(p.name, []).append(d)
        for name, items in groups.items():
            if len(items) >= 2:
                out[name] = sum(1 for d in items if status(d) not in ("不採用", "中止"))
        for d in docs:
            if d.type == "ノード" and len(as_list(d.fm.get("parts"))) >= 2 and d.name not in out:
                parts = [self.index.resolve(t) for t in targets(d.fm.get("parts"))]
                cands = [p for p in parts if p and p.type == "設計記録"]
                if len(cands) >= 2:
                    out[d.name] = sum(1 for p in cands if status(p) not in ("不採用", "中止"))
        return out

    # ---------- 2枚目から ----------

    def off_purpose(self, docs: list[Doc]) -> list[list[str]]:
        rows = []
        for d in docs:
            if d.type not in WORK_TYPES or status(d) in DONE | {"解消"}:
                continue
            hyps = self.reach(d, "仮説")
            if not hyps:
                rows.append([d.type, d.name, owner(d), "仮説につながっていない"])
                continue
            # 仮説は木になる(仮説の parent に仮説)。どの道でも、上のどこかに外れた仮説があれば外れたとみなす
            gone = [self.gone_hypothesis(h) for h in hyps]
            if all(gone):
                rows.append([d.type, d.name, owner(d), f"外れた仮説につながっている({gone[0].name})"])
        return rows

    def gone_hypothesis(self, h: Doc, seen: set[str] | None = None) -> Doc | None:
        """h から parent をたどった仮説(h を含む)のうち、外れたもの。目的より上へはたどらない。"""
        seen = seen if seen is not None else set()
        if h.id in seen or h.type != "仮説":
            return None
        seen.add(h.id)
        if status(h) == "外れた":
            return h
        for p in self.parents(h):
            g = self.gone_hypothesis(p, seen)
            if g:
                return g
        return None

    def challenged(self, docs: list[Doc]) -> list[list[str]]:
        """反論(challenger)がついたまま検証中の仮説。下につながる仮説・イシューの数も出す。"""
        rows = []
        for h in docs:
            if h.type != "仮説" or status(h) != "検証中":
                continue
            refs = [self.index.resolve(t) for t in targets(h.fm.get("challenger"))]
            names = [r.name for r in refs if r] or [plain(x) for x in as_list(h.fm.get("challenger"))]
            if not names:
                continue
            below = sum(1 for d in docs if d.type in ("仮説", "イシュー") and any(p.id == h.id for p in self.parents(d)))
            rows.append([h.name, "、".join(names), str(below)])
        return rows

    def same_nodes(self, pj: str, docs: list[Doc]) -> list[list[str]]:
        rows = []
        mine = [d for d in docs if d.type in ("イシュー", "タスク")]
        others = [d for d in self.docs if d.type in ("イシュー", "タスク") and pj not in self.project_of(d)
                  and not d.rel.startswith(pj + "/")]
        for d in mine:
            nodes = {n.id for n in (self.index.resolve(t) for t in targets(d.fm.get("friend"))) if n}
            for o in others:
                shared = nodes & {n.id for n in (self.index.resolve(t) for t in targets(o.fm.get("friend"))) if n}
                if shared:
                    names = "、".join(sorted(self.index.by_id[x].name for x in shared))
                    rows.append([d.name, "・".join(sorted(self.project_of(o))), o.name, names])
        return rows

    def last_dr(self, pj: str) -> date | None:
        days = [to_date(d.fm.get("date")) for d in self.in_project(pj)
                if d.type == "議事録" and is_dr(d)]
        days = [x for x in days if x and x <= self.today]
        return max(days) if days else None

    def changed_since(self, note_id: str, item: str, since: date) -> bool:
        return any(r.get("id") == note_id and r.get("項目") == item and r["日時"][:10] > since.isoformat()
                   for r in self.history)

    def stuck(self, pj: str, docs: list[Doc]) -> list[list[str]]:
        rows = []
        dr = self.last_dr(pj)
        tasks = [d for d in self.docs if d.type == "タスク"]
        for i in docs:
            if i.type != "イシュー" or impact(i) not in BIG or status(i) in {"解消", "中止"}:
                continue
            mine = [t for t in tasks if i in self.parents(t)]
            done = [t for t in mine if done_date(self.history, t.id)]
            if dr:
                after = [t for t in done if done_date(self.history, t.id) > dr.isoformat()]
                if len(after) >= 2 and not self.changed_since(i.id, "resolution", dr):
                    rows.append([i.name, owner(i), f"DR({dr.isoformat()})のあと対策 {len(after)} 件完了、"
                                 f"resolution は {STAGES[stage(i)]} のまま"])
            if len(done) >= 2 and self.assembled_leaf(i):
                rows.append([i.name, owner(i), f"対策 {len(done)} 件完了、原因が組み立て値のまま"
                             f"({self.assembled_leaf(i)})"])
        for t in tasks:
            if pj not in self.project_of(t) and not any(pj in self.project_of(p) for p in self.reach(t, "イシュー")):
                continue
            n = extensions(self.history, t.id)
            if n >= 2:
                rows.append([t.name, owner(t), f"期限を {n} 回延ばした"])
        return rows

    def assembled_leaf(self, issue: Doc) -> str:
        """friend からノードの parts を下へたどり、parts のない組み立て値の末端の名前。"""
        seen, out = set(), []
        level = [n for n in (self.index.resolve(t) for t in targets(issue.fm.get("friend"))) if n]
        while level:
            nxt = []
            for n in level:
                if n.id in seen:
                    continue
                seen.add(n.id)
                parts = [p for p in (self.index.resolve(t) for t in targets(n.fm.get("parts"))) if p]
                kind = str(n.fm.get("value_kind") or "").strip()
                if not parts and kind.startswith("組み立て"):
                    out.append(n.name)
                nxt += parts
            level = nxt
        return "、".join(out)

    def people(self, docs: list[Doc]) -> list[list[str]]:
        # 確認を頼まれた: 確認待ちのタスクの review_request に名前があるもの(仕様書「確認待ち」)
        counts: dict[str, list[int]] = {}
        for t in docs:
            if t.type != "タスク" or status(t) not in OPEN_TASK:
                continue
            c = counts.setdefault(owner(t), [0, 0, 0, 0, 0])
            s = status(t)
            if s == "進行中":
                c[0] += 1
            elif s == "待ち":
                c[1] += 1
            elif s == "確認待ち":
                c[3] += 1
                for who in {plain(r) for r in as_list(t.fm.get("review_request"))}:
                    counts.setdefault(who, [0, 0, 0, 0, 0])[4] += 1
            due = to_date(t.fm.get("due"))
            if due and due < self.today:
                c[2] += 1
        return [[k, *map(str, v)] for k, v in sorted(counts.items())]

    def milestones(self, proj: Doc) -> list[list[str]]:
        rows = []
        for m in proj.fm.get("milestones") or []:
            if not isinstance(m, dict):
                continue
            plan, fc = to_date(m.get("plan")), to_date(m.get("forecast"))
            diff = f"{(fc - plan).days:+d} 日" if plan and fc else ""
            rows.append([str(m.get("name") or ""), plan.isoformat() if plan else "",
                         fc.isoformat() if fc else "", diff])
        return rows

    # ---------- まとめ ----------

    def build(self, proj: Doc, trend: dict[str, list[int]]) -> ProjectReport:
        pj = proj.name
        docs = self.in_project(pj)
        r = ProjectReport(pj)
        L = r.lines
        L += [f"# 週報 {pj}({Week.of(self.today).label}、{self.today.isoformat()} 作成)", ""]
        outlook = str(proj.fm.get("outlook") or "").strip() or "(未記入)"
        L += ["## 見込み", "", f"- 見込み: **{outlook}**",
              f"- 理由: {str(proj.fm.get('outlook_reason') or '').strip() or '(未記入)'}",
              f"- 管理者に判断してほしいこと: {str(proj.fm.get('request_to_manager') or '').strip() or 'なし'}"]
        age = self.outlook_age(proj)
        if age is None or age > STALE_DAYS:
            L.append("- **見込み未更新**(2週間以上更新されていません)")
        L.append("")
        L += ["## 出荷準備度(目的ごと)", ""]
        r.table("出荷準備度", ["目的", "出荷準備度", "段階0 未把握", "段階1 現象", "段階2 設計空間", "段階3 原理"],
                self.readiness([d for d in docs if d.type == "イシュー"]))
        L += ["## 残っている候補の数", ""]
        r.table("候補の数", ["候補の組", "推移"],
                [[k, "→".join(str(x) for x in v)] for k, v in sorted(trend.items())])
        L += ["## マイルストーン", ""]
        r.table("マイルストーン", ["名前", "計画日", "見込み日", "ずれ"], self.milestones(proj))
        L += ["## 目的に沿っていない仕事", ""]
        r.table("目的に沿わない", ["種類", "名前", "担当", "理由"], self.off_purpose(docs))
        L += ["## 反論のついた仮説(検証中のまま)", ""]
        r.table("反論のついた仮説", ["仮説", "反論", "すぐ下の仮説・イシュー"], self.challenged(docs))
        L += ["## 他のプロジェクトと同じノードを使うもの", ""]
        r.table("同じノード", ["このプロジェクト", "相手のプロジェクト", "相手", "同じノード"], self.same_nodes(pj, docs))
        L += ["## 行き詰まりの候補", ""]
        r.table("行き詰まり", ["名前", "担当", "様子"], self.stuck(pj, docs))
        L += ["## 担当者ごとのタスク", ""]
        r.table("担当者", ["担当", "進行中", "待ち", "期限切れ", "確認待ち", "確認を頼まれた"], self.people(docs))
        refs = sum(len(as_list(d.fm.get("secret_refs"))) for d in docs)
        L += ["## 機密", "", f"機密の事実への参照: {refs} 件(中身は載せません)", ""]
        return r


def read_trend(path: Path) -> dict[str, list[tuple[str, int]]]:
    out: dict[str, list[tuple[str, int]]] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["候補の組"], []).append((row["週"], int(row["数"])))
    return out


def write_trend(path: Path, week: str, now: dict[str, int]) -> dict[str, list[int]]:
    old = read_trend(path)
    for k, v in now.items():
        seq = [x for x in old.get(k, []) if x[0] != week]
        old[k] = seq + [(week, v)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\r\n")
        w.writerow(["週", "候補の組", "数"])
        for k, seq in sorted(old.items()):
            for wk, n in seq:
                w.writerow([wk, k, n])
    return {k: [n for _, n in seq][-6:] for k, seq in old.items() if k in now}


def all_history(shared: Path) -> list[dict]:
    rows = []
    d = shared / HISTORY_DIR
    if d.exists():
        for p in sorted(d.glob("*.csv")):
            rows += read_rows(p)
    rows.sort(key=lambda r: r.get("日時", ""))
    return rows


def runner_of(shared: Path) -> str:
    p = shared / "_仕組み" / "同期設定.yaml"
    if not p.exists():
        return ""
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ""
    return str(data.get("report_runner") or "").strip()


def make_weekly(shared: Path, out_dir: Path, today: date, report: Report, dry_run: bool = False,
                force: bool = False) -> list[Path]:
    """全プロジェクトの週報を作る。今週の分がもうあれば作らない(force なら作り直す)。"""
    week = Week.of(today).label
    b = Builder(shared, today, all_history(shared))
    made = []
    for proj in sorted(b.index.projects().values(), key=lambda d: d.name):
        if status(proj) in ("完了", "中断"):
            continue
        path = out_dir / proj.name / f"{week}.md"
        if path.exists() and not force:
            continue
        trend_path = out_dir / proj.name / CANDIDATE_CSV
        now = b.candidates(b.in_project(proj.name))
        trend = ({k: [n for _, n in seq][-5:] + [now[k]] for k, seq in read_trend(trend_path).items() if k in now}
                 | {k: [v] for k, v in now.items() if k not in read_trend(trend_path)}) if dry_run \
            else write_trend(trend_path, week, now)
        r = b.build(proj, trend)
        report.record(f"週報を作った: {proj.name}/{week}.md")
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(r.lines), encoding="utf-8")
            try:
                from .weekly_xlsx import write_xlsx
                write_xlsx(path.with_suffix(".xlsx"), r)
            except ImportError:
                pass  # Excel の部品(openpyxl)がない PC では Markdown だけ
        made.append(path)
    return made


def maybe_weekly(member: str, shared: Path | None, out_dir: Path | None, now: float, report: Report,
                 dry_run: bool) -> None:
    """月曜の同期で、report_runner の PC だけが作る(F-29)。"""
    if not shared or not out_dir:
        return
    today = datetime.fromtimestamp(now, tz=ids.JST).date()
    if today.weekday() != 0 or runner_of(shared).lower() != member.lower():
        return
    try:
        make_weekly(shared, out_dir, today, report, dry_run)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"週報を作るところで止まりました({type(e).__name__}: {e})。同期はそのまま行いました")
