"""F-33: 今日のデイリーノートの先頭に、同期プログラムからの短い知らせを出す。

- 共有されなかったノートと理由(同期レポートの「対応が必要」のうち、集めなかったもの)
- F-30 の「見込みを更新してください」は、週報から見込みを外したのでやめた(Yu 2026-10-29)

見出しのすぐ下に、次の形の囲みを置き、同期のたびに丸ごと書き換える。知らせがなくなれば消す。
デイリーノートがまだなければ作らない。書いている途中なら触らない。

> [!note] 同期プログラムから(自動で書き換えます)
> - 共有されていない: …
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from . import ids
from .report import Report
from .safety import Backup
from .vault import read, write

DAILY_DIR = "00_日誌/デイリー"
TITLE = "> [!note] 同期プログラムから(自動で書き換えます)"
UNSHARED = ("未入力:", "確認待ち:", "機密へのリンク:", "project 不明:")
MAX_LINES = 8


def strip_block(text: str) -> str:
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        if lines[i].rstrip() == TITLE:
            i += 1
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            if i < len(lines) and not lines[i].strip():
                i += 1  # 囲みのあとの空行
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def put_block(text: str, items: list[str]) -> str:
    nl = "\r\n" if "\r\n" in text else "\n"
    body = strip_block(text.replace("\r\n", "\n"))
    if not items:
        return body.replace("\n", nl)
    shown = items[:MAX_LINES]
    if len(items) > MAX_LINES:
        shown.append(f"ほか {len(items) - MAX_LINES} 件は [[同期レポート]] に")
    block = [TITLE] + [f"> - {x}" for x in shown] + [""]
    lines = body.split("\n")
    # 属性欄と最初の見出しのあとに置く
    at = 0
    if lines and lines[0] == "---":
        end = next((k for k in range(1, len(lines)) if lines[k] == "---"), 0)
        at = end + 1
    if at < len(lines) and lines[at].startswith("# "):
        at += 1
        if at < len(lines) and not lines[at].strip():
            at += 1
    lines[at:at] = block
    return "\n".join(lines).replace("\n", nl)


def update_daily(personal: Path, shared: Path | None, member: str, report: Report, backup: Backup,
                 dry_run: bool, now: float, idle_seconds: int) -> None:
    try:
        today = datetime.fromtimestamp(now, tz=ids.JST).date()
        path = personal / DAILY_DIR / f"{today.isoformat()}.md"
        if not path.exists():
            return
        items = [t for t in report.todos if t.startswith(UNSHARED)]
        items = [t.replace("(共有していません)", "").strip() for t in items]
        items = [f"共有されていない: {t}" for t in items]
        text = read(path)
        new = put_block(text, items)
        if new == text:
            return
        if idle_seconds > 0 and now - path.stat().st_mtime < idle_seconds:
            return  # 書いている途中。次の同期で入れる
        if not dry_run:
            backup.save(personal, path)
            write(path, new)
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"デイリーノートへの知らせで止まりました({type(e).__name__}: {e})")
