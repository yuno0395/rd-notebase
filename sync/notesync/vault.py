"""vault の中のノートを探す。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import frontmatter, ids

# ノートとして扱わないフォルダ(vault の一番上からの名前)
# あまり開かない仕組みのもの(添付・記録・テンプレート・設定・同期レポート)は _仕組み/ にまとめる
SYSTEM_DIR = "_仕組み"
SKIP_DIRS = {SYSTEM_DIR, ".trash"}
# id をつけないフォルダ(デイリー・週報・inbox。仕様書「id をつけないもの」)
NO_ID_DIRS = {"00_日誌", "00_inbox", "00_週報", "90_共有", "99_archive"}


@dataclass
class Note:
    path: Path
    rel: str           # vault の一番上からの相対パス(/ 区切り)
    stem: str          # 拡張子なしのファイル名
    file_id: str | None  # ファイル名の先頭の id
    name: str          # ファイル名の名前の部分
    fm_id: str | None  # 属性欄の id
    aliases: list[str]
    top: str           # 一番上のフォルダ名(直下なら "")


def is_hidden(part: str) -> bool:
    return part.startswith(".")


def iter_md(root: Path):
    """root の下の .md を返す。隠しフォルダ(.obsidian など)と SKIP_DIRS は見ない。"""
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        parts = rel.parts
        if any(is_hidden(x) for x in parts):
            continue
        if parts[0] in SKIP_DIRS:
            continue
        if p.name.endswith(".excalidraw.md"):
            continue
        yield p, rel


def read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as f:
        return f.read()


def write(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)


def load_note(root: Path, path: Path, rel: Path) -> Note:
    text = read(path)
    data = frontmatter.load(text)
    file_id, name = ids.split_filename(path.stem)
    fm_id = data.get("id")
    fm_id = str(fm_id).strip().upper() if fm_id else None
    aliases = data.get("aliases") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    return Note(
        path=path,
        rel=rel.as_posix(),
        stem=path.stem,
        file_id=file_id,
        name=name,
        fm_id=fm_id,
        aliases=[str(a) for a in aliases if a],
        top=rel.parts[0] if len(rel.parts) > 1 else "",
    )


def notes(root: Path) -> list[Note]:
    return [load_note(root, p, rel) for p, rel in iter_md(root)]


def is_root_doc(note: Note) -> bool:
    """vault 直下の 00_ で始まる案内ファイル(README・仕様書・同期レポートなど)。"""
    return note.top == "" and note.stem.startswith("00_")


def needs_id(note: Note) -> bool:
    if is_root_doc(note) or note.top in NO_ID_DIRS:
        return False
    return note.file_id is None
