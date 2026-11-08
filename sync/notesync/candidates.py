"""F-58: 属性欄の入力候補。

Obsidian の属性欄は選択肢を固定できないが、vault にある値を候補に出す。そこで、使わないファイル
`_仕組み/templates/選択肢.md` に候補を箇条書きで持たせる。status の並びは仕組みの正本が書く(版で配る)。
author の並びは、共有 vault のプロジェクトの台帳の members を集めて、同期プログラムが書き直す
(中身が変わったときだけ)。共有 vault と個人 vault の両方の 選択肢.md を直す。ファイルがなければ何もしない。
"""

from __future__ import annotations

import re
from pathlib import Path

from .autofill import as_list, load_docs
from .report import Report
from .vault import plain_name, read, same_person, write

FILE = "_仕組み/templates/選択肢.md"
KEY = "author"


def team_members(shared: Path) -> list[str]:
    """プロジェクトの台帳の members を、書いてあるまま(番号_名前)で集める。同じ人は1回だけ。"""
    out: list[str] = []
    docs = load_docs(shared, own=False, skip={"00_inbox", "00_週報"})
    for d in sorted((d for d in docs if d.type == "プロジェクト" and not d.rel.startswith("99_archive/")),
                    key=lambda d: d.rel):
        for m in as_list(d.fm.get("members")):
            m = plain_name(m).strip()
            if m and not any(same_person(m, x) for x in out):
                out.append(m)
    return out


def with_list(text: str, key: str, values: list[str]) -> str:
    """属性欄の key を箇条書きの並びにする(ほかの行はそのまま)。属性欄がなければそのまま返す。"""
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.split(nl)
    if not lines or lines[0].strip() != "---":
        return text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return text
    block = [f"{key}:"] + [f"  - {v}" for v in values]
    pat = re.compile(rf"^{re.escape(key)}\s*:")
    for i in range(1, end):
        if pat.match(lines[i]):
            j = i + 1
            while j < end and re.match(r"^(\s+\S|-\s)", lines[j]):
                j += 1
            return nl.join(lines[:i] + block + lines[j:])
    return nl.join(lines[:end] + block + lines[end:])


def update_candidates(personal: Path, shared: Path | None, report: Report, dry_run: bool) -> None:
    """選択肢.md の author をプロジェクトのメンバーにそろえる。おまけなので、壊れても同期は止めない。"""
    if not shared or not shared.exists():
        return
    try:
        members = team_members(shared)
        for root in (shared, personal):
            path = root / FILE
            if not path.exists():
                continue
            old = read(path)
            new = with_list(old, KEY, members)
            if new != old:
                report.record(f"author の入力候補をプロジェクトのメンバーにそろえた: {root.name}")
                if not dry_run:
                    write(path, new)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"入力候補を直すところで止まりました({type(e).__name__}: {e})。同期はそのまま行いました")
