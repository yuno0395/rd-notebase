"""F-01〜04: id のないノートに id をつけ、名前とリンクを直す。同じ名前のノートを知らせる。"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import frontmatter, ids
from .report import Report
from .safety import Backup
from .vault import GUIDE_DIRS, NO_ID_DIRS, Note, is_root_doc, iter_md, needs_id, notes, read, write

LINK = re.compile(r"\[\[([^\[\]|#^\n]+)(\|[^\[\]\n]*)?\]\]")
NO_LINK_FIX_DIRS = {"90_共有"} | GUIDE_DIRS  # 他の人のノートの写しと、配布物の案内は書き換えない


@dataclass
class Vault:
    label: str   # レポートでの呼び名(個人・共有・機密)
    root: Path
    assign: bool  # id をつけるか(個人と機密だけ。共有は各自の PC からは触らない)


def created_time(path: Path) -> datetime:
    st = path.stat()
    t = getattr(st, "st_birthtime", None)
    if t is None:
        t = st.st_ctime if os.name == "nt" else st.st_mtime
    return datetime.fromtimestamp(t, tz=ids.JST)


def collect_used(vaults: list[Vault]) -> set[str]:
    used = set()
    for v in vaults:
        for n in notes(v.root):
            for x in (n.file_id, n.fm_id):
                if x:
                    used.add(x)
    return used


def valid_id(text: str | None) -> bool:
    return bool(text) and ids.ID_FILENAME.match(f"{text}_x") is not None


def assign_ids(v: Vault, member: str, code: str, used: set[str], report: Report,
               backup: Backup, dry_run: bool, now: float, idle_seconds: int,
               fresh: set[str] = frozenset()) -> dict[str, str]:
    """id のないノートに id をつける。戻り値は {古いファイル名: 新しいファイル名}。
    fresh(F-28: 作ったばかりでテンプレートのままのノートの id)には author も書かない。"""
    renamed: dict[str, str] = {}
    for n in notes(v.root):
        if not needs_id(n):
            if has_id_without_author(n) and (n.file_id or "").upper() not in fresh:
                fill_author(v, n, member, report, backup, dry_run, now, idle_seconds)
            continue
        if idle_seconds > 0 and now - n.path.stat().st_mtime < idle_seconds:
            report.record(f"{v.label}: {n.rel} は書いている途中なので、次の同期で id をつけます")
            continue
        new_id = n.fm_id if valid_id(n.fm_id) else ids.make_id(created_time(n.path), code, used)
        used.add(new_id)
        new_stem = f"{new_id}_{n.name}"
        new_path = n.path.with_name(new_stem + ".md")
        if new_path.exists():
            report.warn(f"{v.label}: {n.rel} を {new_stem}.md にできません(同じ名前のファイルがあります)")
            continue
        text = read(n.path)
        values = {}
        if n.fm_id != new_id:
            values["id"] = new_id
        if "author" not in frontmatter.load(text):
            values["author"] = member
        if not dry_run:
            backup.save(v.root, n.path)
            if values:
                write(n.path, frontmatter.set_values(text, values))
            n.path.rename(new_path)
        renamed[n.stem] = new_stem
        when = ids.decode_time(new_id).strftime("%Y-%m-%d %H:%M:%S")
        report.record(f"{v.label}: id をつけた {n.rel} → {new_stem}.md({when} 作成)")
    return renamed


def has_id_without_author(n: Note) -> bool:
    """テンプレートで作ったノートは id だけを持ち、author がない。"""
    return bool(n.file_id) and n.top not in NO_ID_DIRS and not is_root_doc(n)


def fill_author(v: Vault, n: Note, member: str, report: Report, backup: Backup,
                dry_run: bool, now: float, idle_seconds: int) -> None:
    """F-03: id はテンプレートが入れるので、author は同期プログラムが書く。"""
    text = read(n.path)
    if "author" in frontmatter.load(text):
        return
    if idle_seconds > 0 and now - n.path.stat().st_mtime < idle_seconds:
        return
    if not dry_run:
        backup.save(v.root, n.path)
        write(n.path, frontmatter.set_values(text, {"author": member}))
    report.record(f"{v.label}: author を書いた {n.rel}")


def name_index(vaults: list[Vault]) -> tuple[dict[str, set[str]], set[str]]:
    """{名前または別名(小文字): {ファイル名}} と、すべてのファイル名(小文字)。"""
    index: dict[str, set[str]] = defaultdict(set)
    stems: set[str] = set()
    for v in vaults:
        for n in notes(v.root):
            stems.add(n.stem.lower())
            if n.file_id:
                for name in [n.name, *n.aliases]:
                    index[name.strip().lower()].add(n.stem)
    return index, stems


def report_same_names(vaults: list[Vault], report: Report) -> None:
    """F-04: 同じ名前か別名を持つ、id の違うノートを知らせる(統合は人が行う)。"""
    by_name: dict[str, set[str]] = defaultdict(set)
    for v in vaults:
        for n in notes(v.root):
            if not n.file_id or v.label == "機密":
                continue
            for name in {n.name, *n.aliases}:
                by_name[name.strip().lower()].add(n.file_id)
    stems = {}
    for v in vaults:
        for n in notes(v.root):
            if n.file_id:
                stems[n.file_id] = n.stem
    for name, found in sorted(by_name.items()):
        if len(found) > 1:
            listed = "、".join(f"[[{stems[i]}]]" for i in sorted(found))
            report.todo(f"同じ名前: 「{name}」のノートが {len(found)} つあります({listed})。同じものなら統合してください")


def fix_links(v: Vault, index: dict[str, set[str]], stems: set[str], report: Report,
              backup: Backup, dry_run: bool) -> int:
    """名前だけのリンク [[水]] を、id つきの [[0RAYFN001_水|水]] に直す。

    直すのは、そのファイル名のノートがなく、名前か別名で1つのノートに決まるときだけ。
    """
    changed_files = 0
    for path, rel in iter_md(v.root):
        if rel.parts[0] in NO_LINK_FIX_DIRS:
            continue
        if len(rel.parts) == 1 and rel.name.startswith("00_"):
            continue  # 直下の案内ファイルと同期レポート
        text = read(path)

        def repl(m: re.Match) -> str:
            target = m.group(1).strip()
            alias = m.group(2)
            key = target.lower()
            if "/" in target or key in stems:
                return m.group(0)
            found = index.get(key, set())
            if len(found) != 1:
                if len(found) > 1:
                    report.todo(f"リンク `[[{target}]]`({v.label}: {rel.as_posix()})の行き先が {len(found)} つあり、直していません")
                return m.group(0)
            stem = next(iter(found))
            shown = alias[1:] if alias else target
            return f"[[{stem}|{shown}]]"

        new = LINK.sub(repl, text)
        if new != text:
            changed_files += 1
            report.record(f"{v.label}: リンクを id つきに直した {rel.as_posix()}")
            if not dry_run:
                backup.save(v.root, path)
                write(path, new)
    return changed_files
