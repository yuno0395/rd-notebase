"""F-31 後半・F-32: ノートの外の履歴(共有の `_仕組み/記録/ノート履歴/<名前>.csv`)。

タスクの due と status、イシューの status と resolution が変わったら、1行足す。
ノートには書かない(仕様書「ノートの外へ」)。読むのは週報(F-29)。

- 最初の due: その id の due の行のうち一番古いもの。due を変えても残る
- 完了日: status が「完了」になった行の日
- 期限を延ばした回数: 前の値がある due の行のうち、後の日の方が遅いものの数

Box の競合を避けるため、ファイルは人ごとに分け、自分のノートの行だけを書く。
前回の値は、このファイルの最後の行から読む(同期の記録が消えても作り直さなくてよい)。
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path

from . import ids
from .autofill import OWN_DIRS, load_docs
from .report import Report

HISTORY_DIR = "_仕組み/記録/ノート履歴"
COLUMNS = ["日時", "id", "名前", "種類", "項目", "前", "後"]
WATCH = {"タスク": ("due", "status"), "イシュー": ("status", "resolution")}


def history_path(shared: Path, member: str) -> Path:
    return shared / HISTORY_DIR / f"{member}.csv"


def value_of(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (date, datetime)):
        return v.isoformat()[:10]
    return str(v).strip()


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f)]


def last_values(rows: list[dict]) -> dict[tuple[str, str], str]:
    out = {}
    for r in rows:
        out[(r.get("id", ""), r.get("項目", ""))] = r.get("後", "")
    return out


def record_history(personal: Path, shared: Path, member: str, report: Report,
                   dry_run: bool, now: float, started: dict | None = None) -> None:
    """started: F-54 で 進行中 にしたタスクの id と着手の日。その status の行は着手の日で書く。"""
    started = started or {}
    try:
        path = history_path(shared, member)
        rows = read_rows(path)
        last = last_values(rows)
        stamp = datetime.fromtimestamp(now, tz=ids.JST).strftime("%Y-%m-%d %H:%M")
        new = []
        for d in load_docs(personal, own=True, tops=OWN_DIRS + ("99_archive",)):
            for key in WATCH.get(d.type, ()):
                now_v = value_of(d.fm.get(key))
                before = last.get((d.id, key))
                if before is None and not now_v:
                    continue  # まだ書いていない値は記録しない
                if before == now_v:
                    continue
                when = stamp
                if key == "status" and now_v == "進行中" and d.id in started:
                    when = f"{started[d.id].isoformat()} 00:00"
                new.append({"日時": when, "id": d.id, "名前": d.name, "種類": d.type,
                            "項目": key, "前": before or "", "後": now_v})
        if not new:
            return
        report.record(f"ノート履歴に {len(new)} 行足した({HISTORY_DIR}/{member}.csv)")
        if dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\r\n")
        if not path.exists():
            w.writeheader()
        w.writerows(new)
        # Excel でそのまま開けるよう、最初だけ BOM をつける
        with path.open("a", encoding="utf-8-sig" if not path.exists() else "utf-8", newline="") as f:
            f.write(buf.getvalue())
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"ノート履歴の記録で止まりました({type(e).__name__}: {e})。id 付けと共有はそのまま行いました")


# ---------- 週報(F-29)で使う読み方 ----------

def first_due(rows: list[dict], note_id: str) -> str:
    for r in rows:
        if r["id"] == note_id and r["項目"] == "due" and r["後"]:
            return r["後"]
    return ""


def done_date(rows: list[dict], note_id: str) -> str:
    out = ""
    for r in rows:
        if r["id"] == note_id and r["項目"] == "status":
            out = r["日時"][:10] if r["後"] == "完了" else ""
    return out


def extensions(rows: list[dict], note_id: str) -> int:
    return sum(1 for r in rows if r["id"] == note_id and r["項目"] == "due" and r["前"] and r["後"] > r["前"])
