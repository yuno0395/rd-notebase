"""F-53: プロジェクトの工程表(マイルストーンとタスクのガントチャート。Yu 2026-10-29)。

台帳の「期間・主な節目」の表(計画日・見込み日)と、ノート履歴(history.py)のタスクの status の
変わった日から作る。タスクの始まりは 進行中(待ち・確認待ち・完了も)になった最初の日、終わりは
完了・中止になった日。まだ終わっていないタスクは今日まで伸ばす。

出すところは2つ(Yu 2026-10-29「週報の HTML と共有 vault の両方」):
- 共有 vault の `<プロジェクト>/00_工程表_<プロジェクト>.md`。Mermaid のガント(Obsidian でも GitHub でも
  図になる、ただの文字)と、同じ中身の表。各自の個人 vault の同じ場所にも置く(台帳の埋め込みが切れないように)
- 週報の HTML の「工程表」の節(weekly_html.py が SVG にする)

台帳の「期間・主な節目」の表の下に `![[00_工程表_<プロジェクト>]]` が1つもなければ、1回だけ足す。
同期プログラムが作るファイルなので、id はつけず、人は書き換えない(次の同期で作り直す)。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import frontmatter, ids
from .autofill import MILESTONE_SECTION, Doc, Index, as_list, load_docs, milestones, targets
from .report import Report
from .vault import has_person, read, write

PREFIX = "00_工程表_"
STARTED = {"進行中", "待ち", "確認待ち", "完了", "中止"}
ENDED = {"完了", "中止"}
NO_PARENT = "(イシューなし)"


def file_name(project: str) -> str:
    return f"{PREFIX}{project}.md"


def embed_line(project: str) -> str:
    return f"![[{PREFIX}{project}]]"


@dataclass
class Bar:
    name: str
    group: str        # 減らすイシューの名前
    start: date
    end: date
    state: str        # 完了 / 中止 / 進行中(まだ終わっていない)
    guessed: bool     # 始まりか終わりが記録になく、推定した
    due: date | None


@dataclass
class Plan:
    project: str
    stones: list[tuple[str, date | None, date | None]]
    bars: list[Bar]


def _day(text: str) -> date | None:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def _status(d: Doc) -> str:
    return str(d.fm.get("status") or "").strip()


def _created(d: Doc) -> date:
    try:
        return ids.decode_time(d.id).date()
    except ValueError:
        return datetime.fromtimestamp(d.path.stat().st_mtime, tz=ids.JST).date()


def task_bar(task: Doc, rows: list[dict], group: str, today: date) -> Bar | None:
    """1つのタスクの棒。まだ着手していない(未着手で記録もない)ものは出さない。"""
    st = _status(task)
    ups = [r for r in rows if r.get("項目") == "status"]
    start = next((_day(r["日時"]) for r in ups if r.get("後") in STARTED), None)
    guessed = False
    if start is None:
        if st not in STARTED:
            return None
        start, guessed = _created(task), True   # 記録の前に着手していた
    end = None
    if st in ENDED:
        end = next((_day(r["日時"]) for r in reversed(ups) if r.get("後") in ENDED), None)
        if end is None:
            end, guessed = datetime.fromtimestamp(task.path.stat().st_mtime, tz=ids.JST).date(), True
    state = st if st in ENDED else "進行中"
    end = max(end or today, start)
    due = _day(str(task.fm.get("due") or ""))
    return Bar(task.name, group, start, end, state, guessed, due)


def build_plan(project: Doc, docs: list[Doc], index: Index, history: list[dict], today: date) -> Plan:
    by_id: dict[str, list[dict]] = {}
    for r in history:
        by_id.setdefault(r.get("id", ""), []).append(r)
    bars = []
    for d in docs:
        if d.type != "タスク":
            continue
        parent = next((index.resolve(t) for t in targets(d.fm.get("parent")) if index.resolve(t)), None)
        group = parent.name if parent else NO_PARENT
        b = task_bar(d, sorted(by_id.get(d.id, []), key=lambda r: r.get("日時", "")), group, today)
        if b:
            bars.append(b)
    first: dict[str, date] = {}
    for b in bars:
        first[b.group] = min(first.get(b.group, b.start), b.start)
    bars.sort(key=lambda b: (b.group == NO_PARENT, first[b.group], b.group, b.start))
    return Plan(project.name, milestones(project), bars)


# ---------- 共有 vault の Markdown(Mermaid) ----------

def _safe(s: str) -> str:
    """Mermaid の名前に使えない : # ; を置き換える。"""
    return re.sub(r"[:#;]", "・", s).strip() or "(名前なし)"


def mermaid(plan: Plan) -> str:
    out = ["```mermaid", "gantt", "  dateFormat YYYY-MM-DD", "  axisFormat %m/%d"]
    if plan.stones:
        out.append("  section マイルストーン")
        for name, plan_day, fc in plan.stones:
            if plan_day:
                out.append(f"  {_safe(name)} 計画 :milestone, {plan_day.isoformat()}, 0d")
            if fc and fc != plan_day:
                tag = "crit, milestone" if plan_day and fc > plan_day else "milestone"
                out.append(f"  {_safe(name)} 見込み :{tag}, {fc.isoformat()}, 0d")
    group = None
    for b in plan.bars:
        if b.group != group:
            group = b.group
            out.append(f"  section {_safe(group)}")
        tag = {"完了": "done, ", "中止": "done, ", "進行中": "active, "}.get(b.state, "")
        # Mermaid の終わりの日は含まないので、1日足して終わりの日まで塗る
        days = (b.end - b.start).days + 1
        out.append(f"  {_safe(b.name)} :{tag}{b.start.isoformat()}, {days}d")
    out.append("```")
    return "\n".join(out)


def markdown(plan: Plan, project: Doc, today: date) -> str:
    lines = [
        f"# 工程表 {plan.project}",
        "",
        f"> 同期プログラムが台帳の「期間・主な節目」の表とタスクの status の記録から作りました({today.isoformat()})。"
        "ここは書き換えないでください(次の同期で作り直します)。",
        f"> 台帳: {project.link}",
        "",
    ]
    if not plan.stones and not plan.bars:
        lines.append("まだ節目も着手したタスクもありません。")
        return "\n".join(lines) + "\n"
    lines += [mermaid(plan), ""]
    if plan.bars:
        lines += ["| タスク | イシュー | 始まり | 終わり | 状態 |", "| --- | --- | --- | --- | --- |"]
        for b in plan.bars:
            end = b.end.isoformat() if b.state in ENDED else f"({b.end.isoformat()} 時点で続いている)"
            mark = "(推定)" if b.guessed else ""
            lines.append(f"| {b.name} | {b.group} | {b.start.isoformat()}{mark} | {end} | {b.state} |")
        lines.append("")
        if any(b.guessed for b in plan.bars):
            lines.append("(推定): 記録より前に始めた・終えたタスク。作った日かファイルを変えた日で代わりにした")
            lines.append("")
    return "\n".join(lines)


def _put(path: Path, text: str, report: Report, dry_run: bool, what: str) -> None:
    if path.exists() and read(path) == text:
        return
    report.record(f"{what}: {path.name}")
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, text)


def add_embed(project: Doc, report: Report, backup, dry_run: bool, now: float, idle_seconds: int,
              vault: Path) -> None:
    """台帳の「期間・主な節目」の表の下に、工程表の埋め込みを1回だけ足す。"""
    line = embed_line(project.name)
    if line in project.text:
        return
    if idle_seconds > 0 and now - project.path.stat().st_mtime < idle_seconds:
        report.record(f"{project.rel} は書いている途中なので、工程表の埋め込みは次の同期で足します")
        return
    lines = project.text.split("\n")
    at = None
    inside = False
    for k, ln in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", ln)
        if m:
            if inside:
                break
            inside = m.group(2) == MILESTONE_SECTION
            if inside:
                at = k + 1
            continue
        if inside and ln.strip():
            at = k + 1      # 節の中の最後の文字のある行の下
    if at is None:
        return               # 節がない台帳には足さない
    new = "\n".join(lines[:at] + ["", line] + lines[at:])
    report.record(f"台帳に工程表を埋め込んだ: {project.rel}")
    if not dry_run:
        backup.save(vault, project.path)
        write(project.path, new)
    project.text = new
    project.fm = frontmatter.load(new)


def update_schedules(personal: Path, shared: Path, member: str, report: Report, backup,
                     dry_run: bool, now: float, idle_seconds: int, history: list[dict] | None = None) -> None:
    """全プロジェクトの工程表を作り直す(中身が変わったときだけ書く)。おまけなので、壊れても同期は止めない。
    member は自分(番号_名前 か 名前)。members に入っているプロジェクトの工程表を個人 vault にも置く。"""
    try:
        from .weekly import all_history
        today = datetime.fromtimestamp(now, tz=ids.JST).date()
        docs = [d for d in load_docs(shared, own=False, skip={"00_inbox", "00_週報"})
                if not d.rel.startswith("99_archive/")]
        index = Index(docs)
        history = all_history(shared) if history is None else history
        for name, proj in sorted(index.projects().items()):
            if _status(proj) in ("完了", "中断"):
                continue
            mine = [d for d in docs if d.rel.startswith(name + "/")]
            plan = build_plan(proj, mine, index, history, today)
            text = markdown(plan, proj, today)
            folder = Path(proj.rel).parent.as_posix()
            _put(shared / folder / file_name(name), text, report, dry_run, "工程表を作り直した")
            if has_person(as_list(proj.fm.get("members")), member) and personal.exists():  # 共有と同じ場所に置く(配られた台帳の埋め込みが切れない)
                _put(personal / folder / file_name(name), text, report, dry_run, "工程表を配った")
            add_embed(proj, report, backup, dry_run, now, idle_seconds, shared)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"工程表を作るところで止まりました({type(e).__name__}: {e})。同期はそのまま行いました")
