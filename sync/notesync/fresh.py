"""F-28: 作ったばかりで、まだテンプレートのままのノートには触らない(取り消しを邪魔しないため)。

ノートを作るテンプレートは、id を作るときに個人 vault の `_仕組み/記録/作成履歴.csv` へ
「日時,id,テンプレート」を1行足す(_scripts/make_id.js)。同期プログラムはこれを読み、
作ってから 10 分以内で、本文がテンプレートの本文のままのノートを、
author の書き込み・自動入力・共有への集約の対象から外す。.trash の中は、もともと見ない。
"""

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from . import ids
from .vault import SYSTEM_DIR, iter_md, read

LOG = f"{SYSTEM_DIR}/記録/作成履歴.csv"
TEMPLATES = f"{SYSTEM_DIR}/templates"
WINDOW = 10 * 60
TAG = re.compile(r"<%.*?%>", re.S)


def body(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            text = text[end + 4:]
    return text


def squash(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.split("\n") if line.strip())


def matches_template(note_text: str, template_text: str) -> bool:
    """本文がテンプレートの本文のまま(Templater の <% %> の部分は何が入ってもよい)。"""
    parts = TAG.split(squash(body(template_text)))
    pattern = ".*?".join(re.escape(p) for p in parts)
    return re.fullmatch(pattern, squash(body(note_text)), re.S) is not None


def parse_time(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=ids.JST)
    return t.timestamp()


def find_template(personal: Path, shared: Path | None, name: str) -> Path | None:
    name = name.strip()
    if not name:
        return None
    if not name.endswith(".md"):
        name += ".md"
    for root in (personal, shared):
        if root:
            p = root / TEMPLATES / name
            if p.is_file():
                return p
    return None


def fresh_ids(personal: Path, shared: Path | None, now: float) -> set[str]:
    """作って10分以内で、テンプレートのままのノートの id。"""
    log = personal / LOG
    if not log.exists():
        return set()
    try:
        with log.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except (OSError, csv.Error, UnicodeDecodeError):
        return set()
    recent = {}
    for r in rows:
        t = parse_time(r.get("日時", ""))
        note_id = (r.get("id") or "").strip().upper()
        if t is not None and note_id and 0 <= now - t < WINDOW:
            recent[note_id] = r.get("テンプレート", "")
    if not recent:
        return set()
    out = set()
    for p, _rel in iter_md(personal):
        note_id = (ids.split_filename(p.stem)[0] or "").upper()
        if note_id not in recent:
            continue
        tpl = find_template(personal, shared, recent[note_id])
        if tpl and matches_template(read(p), read(tpl)):
            out.add(note_id)
    return out
