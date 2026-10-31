"""vault の中のノートを探す。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter, ids

# ノートとして扱わないフォルダ(vault の一番上からの名前)
# あまり開かない仕組みのもの(添付・記録・テンプレート・設定・同期レポート)は _仕組み/ にまとめる
SYSTEM_DIR = "_仕組み"
SKIP_DIRS = {SYSTEM_DIR, ".trash"}
# id をつけないフォルダ(デイリー・週報・inbox。仕様書「id をつけないもの」)
GUIDE_DIRS = {"00_マニュアル"}  # 配布物の案内(仕組みの正本で上書きされる)。id をつけず、書き換えない
NO_ID_DIRS = {"00_日誌", "00_inbox", "00_週報", "99_archive"} | GUIDE_DIRS
# 種類ごとのフォルダの名前。個人 vault も共有 vault と同じ並び(<プロジェクト>/03_イシュー/ や 共通/02_ノード/)にする
TYPE_FOLDERS = ("01_目的", "01_設計案", "02_ノード", "03_イシュー", "04_タスク", "05_ナレッジ")
COMMON = "共通"
# ノートを置かない一番上のフォルダ。ここ以外(共通・プロジェクトのフォルダ・99_archive)のノートが、集めて配る相手
NOT_NOTE_TOPS = {"00_日誌", "00_inbox", "00_週報"} | GUIDE_DIRS | SKIP_DIRS
# v0.66 までの「配られた他の人のノート」の置き場。v0.67 でなくした(tools/migrate_v067.py で移す)
OLD_DIST = "90_共有"


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


def plain_name(value: str) -> str:
    """[[0RAYFN001_Yu|Yu]] や Yu を、名前 Yu にする。"""
    t = frontmatter.link_targets(value)
    t = t[0] if t else value
    return ids.split_filename(t)[1] if ids.split_filename(t)[0] else t


# 人の書き方(author・reviewed_by・members・review_request・attendees)。v0.68 から「番号_名前」(例 229999_Yu)。
# 同姓同名がいても番号で見分けるため(Yu 2026-10-31)。名前だけの書き方(Yu)もそのまま読む。
# 番号は個人設定.md の6桁の number。古い3文字の記号しかない人は名前だけで書く。
PERSON = re.compile(r"^(\d{6})_(.+)$")


def person(value: str) -> tuple[str, str]:
    """(6桁の番号, 名前)。"229999_Yu" → ("229999", "Yu")、"Yu" → ("", "Yu")。[[ ]] のリンクでもよい。"""
    t = frontmatter.link_targets(value)
    t = (t[0] if t else str(value)).strip()
    m = PERSON.match(t)
    if m:
        return m.group(1), m.group(2).strip()
    return "", plain_name(t).strip()


def person_name(value: str) -> str:
    """名前だけ(画面や週報に出すとき)。"""
    return person(value)[1]


def same_person(a: str, b: str) -> bool:
    """同じ人か。両方に番号があれば番号で、どちらかが名前だけなら名前で比べる。"""
    na_, a_ = person(a)
    nb_, b_ = person(b)
    if na_ and nb_:
        return na_ == nb_
    return bool(a_) and a_ == b_


def person_labels(values) -> dict[str, str]:
    """書いてある値 → 週報などに出す名前。同じ名前で番号の違う人がいるときだけ「名前(番号)」にする。
    名前だけの古い書き方は、その名前の人が1人ならその人にまとめる。"""
    numbers: dict[str, set[str]] = {}
    for v in values:
        n, name = person(v)
        numbers.setdefault(name, set())
        if n:
            numbers[name].add(n)
    out = {}
    for v in values:
        n, name = person(v)
        out[v] = f"{name}({n})" if n and len(numbers[name]) > 1 else name
    return out


def has_person(values, who: str) -> bool:
    return any(same_person(v, who) for v in values)


def me_value(name: str, number: str) -> str:
    """自分を書くときの形。番号がわからなければ名前だけ。"""
    return f"{number}_{name}" if number else name


def authors_of(fm: dict) -> list[str]:
    """書いた人(書いてあるまま。"229999_Yu" か "Yu")。まとめたノードは [佐藤, Yu] のように並ぶ(先頭が最初に書いた人)。"""
    return [plain_name(a).strip() for a in frontmatter.as_list(fm.get("author")) if a.strip()]


def is_theirs(fm: dict, member: str) -> bool:
    """他の人のノートか。author に自分が入っていなければ他の人のもの(配られたもの)。
    member は自分("229999_Yu" か "Yu")。author が空のノートは自分のもの(同期プログラムがあとで author を書く)。"""
    a = authors_of(fm)
    return bool(a) and not has_person(a, member)


def theirs_file(path: Path, member: str) -> bool:
    """個人 vault のファイルが他の人のノートか(属性欄の author で見分ける)。"""
    if not member or not path.name.endswith(".md"):
        return False
    try:
        return is_theirs(frontmatter.load(read(path)), member)
    except (OSError, UnicodeDecodeError):
        return False


def is_hidden(part: str) -> bool:
    return part.startswith(".")


# F-16: 同期アプリが作った競合の複製(copies.py)。ノートとしては扱わない
COPY_MARK = re.compile(r"\((?=[^)]*(?:conflict|競合|コンフリクト))[^)]*\)", re.I)
COPY_NUMBERED = re.compile(r"^(.*\S) \(\d{1,3}\)$")


def split_ext(name: str) -> tuple[str, str]:
    if name.endswith(".excalidraw.md"):
        return name[: -len(".excalidraw.md")], ".excalidraw.md"
    stem, dot, ext = name.rpartition(".")
    return (stem, "." + ext) if dot and stem else (name, "")


def sync_copy_of(path: Path) -> tuple[bool, Path | None]:
    """(同期アプリの複製か, 元のファイル(あれば))。番号つきは、元のファイルがあるときだけ複製とみなす。"""
    stem, ext = split_ext(path.name)
    if "_競合_" in stem:  # 同期プログラムが置くもの(F-15)
        return False, None
    if COPY_MARK.search(stem):
        orig = path.with_name(COPY_MARK.sub("", stem).rstrip() + ext)
        return True, orig if orig.exists() else None
    m = COPY_NUMBERED.match(stem)
    if m:
        orig = path.with_name(m.group(1) + ext)
        if orig.exists():
            return True, orig
    return False, None


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
        if sync_copy_of(p)[0]:
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


# 同期プログラムがプロジェクトのフォルダに作るファイル(工程表、F-53)。id をつけず、人は書き換えない
GENERATED_PREFIX = "00_工程表_"


def is_root_doc(note: Note) -> bool:
    """vault 直下の 00_ で始まる案内ファイル(README・仕様書・同期レポートなど)と、同期プログラムが作る工程表。"""
    return (note.top == "" and note.stem.startswith("00_")) or note.stem.startswith(GENERATED_PREFIX)


def needs_id(note: Note) -> bool:
    if is_root_doc(note) or note.top in NO_ID_DIRS:
        return False
    return note.file_id is None
