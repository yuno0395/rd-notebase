"""F-17b: 添付の置き場所とリンクの形をそろえる(個人 vault だけ)。

- id のないノートに貼った添付は、Custom Attachment Location が `_仕組み/attachments/` の直下に入れる
  (id がまだないので、フォルダ名が空になる)。id を振ったあと、そのノートだけが指している添付を
  `_仕組み/attachments/<id>/` へ移し、リンクを直す。ほかのノートも指していれば動かさず知らせる。
- `_仕組み/attachments/<id>/` の添付へのリンクが vault の一番上からのパスでなければ
  (`![[成形品.jpg]]` など)、`_仕組み/attachments/<id>/成形品.jpg` の形に直す。
- 日誌(00_日誌/ のデイリー・週報)には id がないので、ファイル名(日付)のフォルダ
  `_仕組み/attachments/日誌/<ファイル名>/` を使う(例 `日誌/2026-10-26/`、`日誌/2026-W43/`)。
- 書いている途中のノートは触らない。inbox など、id も日誌のフォルダもないノートの添付は動かさない。
"""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

from . import ids
from .heavy import ATTACH, MDLINK, WIKI, free_name
from .report import Report
from .safety import Backup
from .state import digest
from .vault import box_copy_of, iter_md, read, write

SKIP_TOPS = {"90_共有"}  # 他の人のノートの写しは書き換えない
DIARY_TOP = "00_日誌"
DIARY_DIR = "日誌"  # _仕組み/attachments/日誌/<ファイル名>/


def clean(target: str) -> str:
    t = target.strip()
    if t.startswith("<") and t.endswith(">"):
        t = t[1:-1]
    return unquote(t).replace("\\", "/")


def is_external(t: str) -> bool:
    return "://" in t or t.startswith(("mailto:", "#"))


def resolve(root: Path, note_id: str | None, t: str) -> Path | None:
    """リンク先の添付ファイル。添付でなければ None。"""
    if is_external(t) or t.lower().endswith(".md") or "." not in t.rsplit("/", 1)[-1]:
        return None
    base = root / ATTACH
    p = root / t
    if p.is_file() and base in p.parents:
        return p
    if "/" in t:
        return None
    # 最短パスのリンク(ファイル名だけ)。自分のフォルダ、直下の順に探す
    for cand in ([base / note_id / t] if note_id else []) + [base / t]:
        if cand.is_file():
            return cand
    return None


def form(path: str, md: bool) -> str:
    return f"<{path}>" if md and " " in path else path


class Fixer:
    def __init__(self, root: Path, renamed: dict[str, str], report: Report, backup: Backup,
                 dry_run: bool, now: float, idle_seconds: int):
        self.root = root
        self.renamed = renamed
        self.report = report
        self.backup = backup
        self.dry_run = dry_run
        self.now = now
        self.idle_seconds = idle_seconds
        self.base = root / ATTACH

    def busy(self, p: Path) -> bool:
        return self.idle_seconds > 0 and self.now - p.stat().st_mtime < self.idle_seconds

    def notes(self) -> list[tuple[Path, str, str | None]]:
        """(パス, 相対パス, 添付のフォルダ名)。フォルダ名は id、日誌なら 日誌/<ファイル名>、どちらもなければ None。
        試し運転では振るはずの id を使う。"""
        out = []
        for p, rel in iter_md(self.root):
            if rel.parts[0] in SKIP_TOPS:
                continue
            stem = self.renamed.get(p.stem, p.stem)
            folder = ids.split_filename(stem)[0]
            if not folder and rel.parts[0] == DIARY_TOP:
                folder = f"{DIARY_DIR}/{p.stem}"
            out.append((p, rel.as_posix(), folder))
        return out

    def links(self, text: str):
        for m in WIKI.finditer(text):
            yield m.group(1)
        for m in MDLINK.finditer(text):
            yield m.group(2)

    def loose_users(self, notes) -> dict[Path, set[str]]:
        """直下の添付 → それを指すノート(相対パス)。"""
        users: dict[Path, set[str]] = defaultdict(set)
        for p, rel, note_id in notes:
            for t in self.links(read(p)):
                f = resolve(self.root, note_id, clean(t))
                if f and f.parent == self.base:
                    users[f].add(rel)
        return users

    def rewrite(self, text: str, note_id: str, moved: dict[Path, Path]) -> str:
        old_rel = {k.relative_to(self.root).as_posix(): v for k, v in moved.items()}

        def target_of(raw: str) -> str | None:
            t = clean(raw)
            f = old_rel.get(t) or resolve(self.root, note_id, t)
            if not f:
                return None
            f = moved.get(f, f)
            if f.parent == self.base:
                return None  # 直下に残したもの(ほかのノートも指している)
            want = f.relative_to(self.root).as_posix()
            if not want.startswith(f"{ATTACH}/{note_id}/"):
                return None  # ほかのノートの添付は、そのノートのものとして残す
            return None if t == want else want

        def wiki(m):
            new = target_of(m.group(1))
            if not new:
                return m.group(0)
            return m.group(0).replace(m.group(1), new, 1)

        def md(m):
            new = target_of(m.group(2))
            if not new:
                return m.group(0)
            return m.group(0).replace(f"]({m.group(2)})", f"]({form(new, True)})")

        return MDLINK.sub(md, WIKI.sub(wiki, text))

    def run(self) -> None:
        if not self.base.exists():
            return
        notes = self.notes()
        users = self.loose_users(notes)
        owner = {rel: (p, note_id) for p, rel, note_id in notes}
        moved: dict[Path, Path] = {}
        for f, rels in sorted(users.items()):
            if box_copy_of(f)[0]:
                continue
            with_id = [r for r in rels if owner[r][1]]
            if len(rels) > 1:
                self.report.todo(f"添付 {ATTACH}/{f.name} を {len(rels)} つのノートが指しているので、動かしていません"
                                 f"({'、'.join(sorted(rels))})。どのノートのものか決めて移してください")
                continue
            if not with_id:
                continue  # inbox など、置き場の決まらないノートの添付
            p, note_id = owner[with_id[0]]
            if self.busy(p) or self.busy(f):
                continue
            dest = self.base / note_id / f.name
            same = dest.exists() and digest(dest) == digest(f)
            final = dest if same else free_name(dest)
            moved[f] = final
            self.report.record(f"添付を移した: {ATTACH}/{f.name} → {final.relative_to(self.root).as_posix()}")
            if not self.dry_run:
                final.parent.mkdir(parents=True, exist_ok=True)
                if same:
                    f.unlink()
                else:
                    shutil.move(str(f), str(final))
        for p, rel, note_id in notes:
            if not note_id:
                continue
            text = read(p)
            new = self.rewrite(text, note_id, moved)
            if new == text or self.busy(p):
                continue
            self.report.record(f"添付へのリンクを一番上からのパスに直した: {rel}")
            if not self.dry_run:
                self.backup.save(self.root, p)
                write(p, new)


def fix_attachments(root: Path, renamed: dict[str, str], report: Report, backup: Backup,
                    dry_run: bool, now: float, idle_seconds: int) -> None:
    try:
        Fixer(root, renamed, report, backup, dry_run, now, idle_seconds).run()
    except Exception as e:  # おまけが壊れても、核の同期は続ける
        report.warn(f"添付の置き場所の直しで止まりました({type(e).__name__}: {e})")
