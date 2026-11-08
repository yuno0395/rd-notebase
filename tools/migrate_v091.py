"""仕様書 v0.91 の「共有する範囲」と 00_PIP を、今ある個人 vault に当てる。

    python migrate_v091.py <個人 vault> [--run] [--backup <控えのフォルダ>]

--run をつけないと、することを表示するだけで何も変えない。
--run をつけると、最初に控え(zip)を作ってから、次のことをする。控えは vault の隣に作る。
--backup を渡すとそのフォルダに作る(準備の bat はこれで共有クラウドフォルダの外に作る)。

1. フォルダ: 00_日誌/ を 00_PIP/ にする(デイリー/・メモ/ はそのまま)。00_日誌/週報/ の週報は 00_週報/ へ
   (00_PIP/ は絶対に共有しないフォルダなので。)。同じ名前のファイルが先にあれば動かさずに知らせる。
2. visibility(自分のノートだけ。他の人のノートは同期プログラムが共有の中身に合わせる):
   | 古い | いま |
   | 個人・type: メモ | [PIP](00_PIP/ の外にあれば 00_PIP/メモ/ へ移す) |
   | 社内 | [Internal use only] |
   | チーム・書いていない | 置き場所のプロジェクト名。共通/ と 00_週報/ は [Internal use only] |
   台帳(type: プロジェクト)・機密の窓口・00_inbox/ のノートは書かない(置き場所が決まっていないため)。

自分のノートかは、_仕組み/個人設定.md の name と number を author と比べて決める。
同期プログラムは古い値も同じ意味で読むので、急いで当てなくてもよい。何度走らせても同じ結果になる。標準ライブラリだけを使う。
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
VIS = re.compile(r"^visibility\s*:[^\r\n]*(?:\r?\n[ \t]+-[^\r\n]*)*", re.M)
OLD_TOP, PIP_TOP, WEEKLY_TOP = "00_日誌", "00_PIP", "00_週報"
PIP, INTERNAL = "PIP", "Internal use only"
NOT_PROJECT = {"共通", "00_inbox", "00_週報", "99_archive", "00_マニュアル", PIP_TOP, OLD_TOP}
NO_VIS_TYPES = {"プロジェクト", "窓口"}
VAULT_MARKS = ("_仕組み",)


def field(head: str, key: str) -> str:
    m = re.search(rf"^{key}\s*:\s*(.*)$", head, re.M)
    return m.group(1).split(" #")[0].strip().strip("[]").strip("\"'") if m else ""


def values(head: str) -> list[str]:
    m = VIS.search(head)
    if not m:
        return []
    text = m.group(0).split(":", 1)[1]
    text = re.sub(r"(?m)^\s*#.*$", "", text)
    text = text.split(" #")[0] if "\n" not in text.strip() else text
    items = re.findall(r"[^\[\],\n\r\-\"']+", text)
    return [x.strip() for x in items if x.strip()]


def me_of(vault: Path) -> set[str]:
    f = vault / "_仕組み" / "個人設定.md"
    try:
        head = FRONT.match(f.read_text(encoding="utf-8")).group(1)
    except (OSError, AttributeError):
        return set()
    return {x for x in (field(head, "name"), field(head, "number")) if x}


def own(head: str, me: set[str]) -> bool:
    if not me:
        return True
    m = re.search(r"^author\s*:(.*(?:\r?\n[ \t]+-.*)*)", head, re.M)
    if not m:
        return True   # author がまだない = 自分が作ったばかり
    who = re.findall(r"[^\[\],\n\r\-\"'\s][^\[\],\n\r\"']*", m.group(1))
    for w in who:
        w = w.strip()
        num, _, name = w.partition("_")
        if w in me or num in me or name in me:
            return True
    return False


def set_vis(text: str, head: str, value: list[str]) -> str:
    line = "visibility: [" + ", ".join(value) + "]"
    nl = "\r\n" if "\r\n" in head else "\n"
    m = VIS.search(head)
    if m:
        first = m.group(0).splitlines()[0]
        c = re.search(r"\s+#\s.*$", first)
        if c and "\n" not in m.group(0):
            line += c.group(0)   # 行の後ろのコメントは残す
    new_head = head[:m.start()] + line + head[m.end():] if m else head + nl + line
    start = text.index(head)
    return text[:start] + new_head + text[start + len(head):]


def plan_vis(rel: Path, head: str) -> list[str] | None:
    """書く visibility。変えなければ None。"""
    typ = field(head, "type")
    vs = values(head)
    if typ == "メモ" or "個人" in vs:
        return [PIP] if vs != [PIP] else None
    if any(v not in ("チーム", "社内") for v in vs):
        return None   # もう新しい書き方
    if vs and set(vs) == {"社内"}:
        return [INTERNAL]
    if typ in NO_VIS_TYPES or rel.parts[0] in ("00_inbox", PIP_TOP, OLD_TOP, "99_archive", "00_マニュアル"):
        return None
    if rel.parts[0] in ("共通", WEEKLY_TOP) or len(rel.parts) < 2:
        return [INTERNAL]
    if rel.parts[0] in NOT_PROJECT:
        return None
    return [rel.parts[0]]


def plan(vault: Path) -> tuple[list[tuple[Path, Path]], list[tuple[Path, str, str]], list[str]]:
    """(移すファイル, 書き換えるノート, 知らせること)。"""
    moves: list[tuple[Path, Path]] = []
    edits: list[tuple[Path, str, str]] = []
    notes: list[str] = []
    old = vault / OLD_TOP
    if old.is_dir():
        for p in sorted(old.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(old)
            dest = vault / WEEKLY_TOP / Path(*rel.parts[1:]) if rel.parts[0] == "週報" else vault / PIP_TOP / rel
            if dest.exists():
                notes.append(f"移せません(同じ名前があります): {p.relative_to(vault)} → {dest.relative_to(vault)}")
            else:
                moves.append((p, dest))
    me = me_of(vault)
    moved_to = {src: dest for src, dest in moves}
    for p in sorted(vault.rglob("*.md")):
        rel = p.relative_to(vault)
        if any(x.startswith(".") for x in rel.parts) or rel.parts[0] == "_仕組み":
            continue
        try:
            text = p.read_bytes().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        m = FRONT.match(text)
        if not m:
            continue
        head = m.group(1)
        dest = moved_to.get(p, p)
        drel = dest.relative_to(vault)
        if not own(head, me):
            continue
        new = plan_vis(drel, head)
        if new is None:
            continue
        edits.append((p, set_vis(text, head, new), ", ".join(new)))
        if new == [PIP] and drel.parts[0] != PIP_TOP:
            target = vault / PIP_TOP / "メモ" / p.name
            if target.exists():
                notes.append(f"移せません(同じ名前があります): {rel} → {target.relative_to(vault)}")
            else:
                moved_to[p] = target
                moves = [(s, d) for s, d in moves if s != p] + [(p, target)]
    return moves, edits, notes


def main(argv: list[str]) -> int:
    run = "--run" in argv
    backup: Path | None = None
    vaults = []
    rest = iter(argv)
    for a in rest:
        if a == "--backup":
            backup = Path(next(rest, ""))
        elif a != "--run":
            vaults.append(Path(a))
    if not vaults:
        print(__doc__)
        return 2
    for v in vaults:
        if not v.is_dir():
            print(f"見つかりません: {v}")
            return 1
        if not any((v / m).is_dir() for m in VAULT_MARKS):
            print(f"vault ではないようです(_仕組み フォルダがありません): {v}")
            return 1
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for v in vaults:
        print(f"== {v}")
        moves, edits, notes = plan(v)
        for n in notes:
            print(f"  {n}")
        if not moves and not edits:
            print("  することはありません")
            continue
        if run:
            (backup or v.parent).mkdir(parents=True, exist_ok=True)
            zip_base = (backup or v.parent) / f"移行前の控え_{v.name}_{stamp}"
            shutil.make_archive(str(zip_base), "zip", root_dir=v)
            print(f"  控え: {zip_base}.zip")
        for p, text, what in edits:
            print(f"  visibility → [{what}]: {p.relative_to(v)}")
            if run:
                p.write_bytes(text.encode("utf-8"))
        for src, dest in moves:
            print(f"  移す: {src.relative_to(v)} → {dest.relative_to(v)}")
            if run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dest)
        if run:
            old = v / OLD_TOP
            for d in sorted((x for x in old.rglob("*") if x.is_dir()), key=lambda x: -len(x.parts)) if old.is_dir() else []:
                if not any(d.iterdir()):
                    d.rmdir()
            if old.is_dir() and not any(old.iterdir()):
                old.rmdir()
    if not run:
        print("\n(試し運転です。何も変えていません。--run をつけると実行します)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
