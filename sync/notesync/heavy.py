"""F-17〜20: 重い添付を vault の外の 開発データ/ へ移し、リンクを書き換える(仕様書「重い添付ファイルの置き場所」)。

- vault に残すもの: 画像・PDF・ノート(.md)・20MB 未満の動画。それ以外は重い添付。
- 置き場所: ノートを共有していれば 開発データ/<共有でのフォルダ>/<id>/(プロジェクト名か 共通)、
  まだなら 開発データ/_個人/<名前>/<id>/。共有されたら _個人/ からプロジェクトへ移す(F-20)。
- 個人 vault のリンクは、その PC の `file:///` に書き換える(F-18)。共有 vault では
  `開発データ/...` の相対パスにし、配るときにその人の `file:///` に直す(F-19、share.py の Context.copy)。
- 機密フォルダの添付は動かさない(F-40)。消すことはしない。移す前と後はレポートに残す。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import quote, unquote

import yaml

from . import ids
from .report import Report
from .safety import Backup
from .state import digest
from .vault import SYSTEM_DIR, box_copy_of, is_hidden, iter_md, read, write

ATTACH = f"{SYSTEM_DIR}/attachments"
DATA_PREFIX = "開発データ/"
PERSONAL_DIR = "_個人"
DIST = "90_共有"

DEFAULT_KEEP = {
    "images": ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"],
    "pdf": True,
    "video": ["mp4", "webm", "mov"],
    "video_max_mb": 20,
}

WIKI = re.compile(r"!?\[\[([^\[\]|#\n]+)(#[^\[\]|\n]*)?(\|[^\[\]\n]*)?\]\]")
MDLINK = re.compile(r"!?\[([^\[\]\n]*)\]\((<[^>\n]+>|[^)\s]+)\)")


def keep_rules(shared: Path | None) -> dict:
    rules = dict(DEFAULT_KEEP)
    if shared:
        p = shared / SYSTEM_DIR / "同期設定.yaml"
        if p.exists():
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                rules.update(data.get("keep_in_vault") or {})
            except yaml.YAMLError:
                pass
    return rules


def is_heavy(path: Path, rules: dict) -> bool:
    name = path.name.lower()
    if name.endswith(".md"):
        return False
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext in [str(x).lower() for x in rules.get("images", [])]:
        return False
    if ext == "pdf" and rules.get("pdf", True):
        return False
    if ext in [str(x).lower() for x in rules.get("video", [])]:
        return path.stat().st_size >= float(rules.get("video_max_mb", 20)) * 1024 * 1024
    return True


# ---------- リンクの形(F-18・F-19) ----------

def file_url(path: Path) -> str:
    return "file:///" + quote(path.as_posix().lstrip("/"), safe="/:")


def url_prefix(data_root: Path) -> str:
    return file_url(data_root).rstrip("/") + "/"


def to_shared(text: str, data_root: Path | None) -> str:
    """個人の `file:///<自分の開発データ>/...` を `開発データ/...` にする。"""
    if not data_root:
        return text
    pre = url_prefix(data_root)

    def repl(m: re.Match) -> str:
        dest = m.group(2)
        inner = dest[1:-1] if dest.startswith("<") else dest
        if inner.startswith(pre):
            rest = unquote(inner[len(pre):])
            new = DATA_PREFIX + rest
            new = f"<{new}>" if " " in new else new
            return m.group(0).replace(f"]({dest})", f"]({new})")
        return m.group(0)

    return MDLINK.sub(repl, text)


def to_personal(text: str, data_root: Path | None) -> str:
    """共有の `開発データ/...` を、自分の PC の `file:///` にする。"""
    if not data_root:
        return text

    def repl(m: re.Match) -> str:
        dest = m.group(2)
        inner = dest[1:-1] if dest.startswith("<") else dest
        if inner.startswith(DATA_PREFIX):
            new = file_url(data_root / inner[len(DATA_PREFIX):])
            return m.group(0).replace(f"]({dest})", f"]({new})")
        return m.group(0)

    return MDLINK.sub(repl, text)


# ---------- ノートのリンクを書き換える ----------

def relink(text: str, note_id: str, rel_name: str, new_url: str, own_note: bool,
           old_url: str | None = None) -> str:
    """添付 `_仕組み/attachments/<id>/<rel_name>` を指すリンクを `[名前](new_url)` にする。
    own_note(その id のノート)なら、ファイル名だけのリンクも対象にする。old_url を指すリンクも直す。"""
    tail = f"attachments/{note_id}/{rel_name}"
    shown = rel_name.split("/")[-1]

    def hits(target: str) -> bool:
        t = unquote(target.strip()).replace("\\", "/")
        return t.endswith(tail) or (own_note and t == rel_name)

    def wiki(m: re.Match) -> str:
        if not hits(m.group(1)):
            return m.group(0)
        alias = m.group(3)[1:] if m.group(3) else shown
        return f"[{alias}]({new_url})"

    def md(m: re.Match) -> str:
        dest = m.group(2)
        inner = dest[1:-1] if dest.startswith("<") else dest
        if hits(inner) or (old_url and inner == old_url):
            return f"[{m.group(1) or shown}]({new_url})"
        return m.group(0)

    return MDLINK.sub(md, WIKI.sub(wiki, text))


def free_name(dest: Path) -> Path:
    """同じ名前があれば _2、_3 … をつける。"""
    if not dest.exists():
        return dest
    stem, dot, ext = dest.name.rpartition(".")
    if not dot:
        stem, ext = dest.name, ""
    n = 2
    while True:
        cand = dest.with_name(f"{stem}_{n}.{ext}" if ext else f"{stem}_{n}")
        if not cand.exists():
            return cand
        n += 1


def shared_folder_of(shared: Path | None, note_id: str) -> str | None:
    """共有 vault でのノートの一番上のフォルダ(プロジェクト名か 共通)。共有していなければ None。"""
    if not shared or not shared.exists():
        return None
    for p, rel in iter_md(shared):
        if ids.split_filename(p.stem)[0] == note_id and len(rel.parts) > 1:
            top = rel.parts[0]
            if top not in ("99_archive", "00_inbox", "00_週報"):
                return top
    return None


class Mover:
    def __init__(self, personal: Path, shared: Path | None, data_root: Path, member: str,
                 report: Report, backup: Backup, dry_run: bool, now: float, idle_seconds: int):
        self.personal = personal
        self.shared = shared
        self.data_root = data_root
        self.member = member
        self.report = report
        self.backup = backup
        self.dry_run = dry_run
        self.now = now
        self.idle_seconds = idle_seconds
        self.rules = keep_rules(shared)
        self._notes: list[tuple[Path, str]] | None = None

    def busy(self, path: Path) -> bool:
        return self.idle_seconds > 0 and path.exists() and self.now - path.stat().st_mtime < self.idle_seconds

    def notes(self) -> list[tuple[Path, str]]:
        if self._notes is None:
            self._notes = [(p, rel.as_posix()) for p, rel in iter_md(self.personal) if rel.parts[0] != DIST]
        return self._notes

    def rewrite_links(self, note_id: str, rel_name: str, new_url: str, old_url: str | None = None) -> bool:
        """リンクを書き換える。書いている途中のノートがあれば何もしないで False。"""
        changes = []
        for p, rel in self.notes():
            own = ids.split_filename(p.stem)[0] == note_id
            text = read(p)
            new = relink(text, note_id, rel_name, new_url, own, old_url)
            if new != text:
                if self.busy(p):
                    return False
                changes.append((p, rel, new))
        for p, rel, new in changes:
            self.report.record(f"リンクを書き換えた: {rel}({rel_name.split('/')[-1]})")
            if not self.dry_run:
                self.backup.save(self.personal, p)
                write(p, new)
        return True

    def place_for(self, note_id: str) -> Path:
        top = shared_folder_of(self.shared, note_id)
        if top:
            return self.data_root / top / note_id
        return self.data_root / PERSONAL_DIR / self.member / note_id

    def move_file(self, src: Path, dest: Path) -> Path | None:
        if dest.exists() and digest(dest) == digest(src):
            final = dest  # もう同じものがある(前回、移したあとで止まったなど)
        else:
            final = free_name(dest)
        if not self.dry_run:
            final.parent.mkdir(parents=True, exist_ok=True)
            if final == dest and dest.exists():
                src.unlink()
            else:
                shutil.move(str(src), str(final))
        return final

    def run(self) -> None:
        base = self.personal / ATTACH
        if not base.exists():
            return
        for note_dir in sorted(d for d in base.iterdir() if d.is_dir()):
            note_id = note_dir.name
            dest_dir = self.place_for(note_id)
            for f in sorted(note_dir.rglob("*")):
                if not f.is_file() or any(is_hidden(x) for x in f.relative_to(note_dir).parts):
                    continue
                if box_copy_of(f)[0] or not is_heavy(f, self.rules):
                    continue
                if self.busy(f):
                    self.report.record(f"{ATTACH}/{note_id}/{f.name} はコピー中かもしれないので、次の同期で移します")
                    continue
                rel_name = f.relative_to(note_dir).as_posix()
                target = dest_dir / rel_name
                final = free_name(target) if not (target.exists() and digest(target) == digest(f)) else target
                url = file_url(final)
                if not self.rewrite_links(note_id, rel_name, url):
                    self.report.record(f"{ATTACH}/{note_id}/{rel_name} を指すノートが書いている途中なので、次の同期で移します")
                    continue
                self.move_file(f, target)
                shown = final.relative_to(self.data_root).as_posix()
                self.report.record(f"重い添付を移した: {ATTACH}/{note_id}/{rel_name} → 開発データ/{shown}")
            self.promote(note_id)

    def promote(self, note_id: str) -> None:
        """F-20: 共有されたノートの添付を、_個人/ からプロジェクトのフォルダへ移す。"""
        src_dir = self.data_root / PERSONAL_DIR / self.member / note_id
        top = shared_folder_of(self.shared, note_id)
        if not top or not src_dir.exists():
            return
        dest_dir = self.data_root / top / note_id
        for f in sorted(src_dir.rglob("*")):
            if not f.is_file():
                continue
            rel_name = f.relative_to(src_dir).as_posix()
            target = dest_dir / rel_name
            final = free_name(target) if not (target.exists() and digest(target) == digest(f)) else target
            if not self.rewrite_links(note_id, rel_name, file_url(final), old_url=file_url(f)):
                self.report.record(f"開発データ/{PERSONAL_DIR}/{self.member}/{note_id} を指すノートが書いている途中なので、次の同期で移します")
                return
            self.move_file(f, target)
            self.report.record(f"共有されたので添付を移した: 開発データ/{PERSONAL_DIR}/{self.member}/{note_id}/{rel_name}"
                               f" → 開発データ/{final.relative_to(self.data_root).as_posix()}")


def move_heavy(personal: Path, shared: Path | None, data_root: Path | None, member: str,
               report: Report, backup: Backup, dry_run: bool, now: float, idle_seconds: int) -> None:
    if not data_root:
        rules = keep_rules(shared)
        base = personal / ATTACH
        heavy = [f for f in base.rglob("*") if f.is_file() and is_heavy(f, rules)] if base.exists() else []
        if heavy:
            report.todo(f"開発データの場所が設定にありません: 重い添付が {len(heavy)} 件 {ATTACH}/ にたまっています。"
                        "個人設定に shared_data を書いてください")
        return
    if not data_root.exists():
        report.warn(f"開発データのフォルダが見つかりません: {data_root}(Box Drive が止まっていないか確かめてください)。"
                    "重い添付は移していません")
        return
    Mover(personal, shared, data_root, member, report, backup, dry_run, now, idle_seconds).run()
