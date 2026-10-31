"""仕様書 v0.54 の「設計案」への改名を、今ある vault に当てる(個人・共有のどちらにも使える)。

    python migrate_v054.py <vault> [<vault> ...] [--run] [--backup <控えのフォルダ>]

--run をつけないと、することを表示するだけで何も変えない。
--run をつけると、最初に vault ごとの控え(zip)を作ってから、次のことをする。
控えは vault の隣に作る。--backup を渡すとそのフォルダに作る(準備の bat はこれで共有クラウドフォルダの外に作る)。

1. どの深さの 01_目的/ にあっても、type が ソリューション か 設計記録 のノートを、
   隣の 01_設計案/ へ移し、type を 設計案 にする。添付(_仕組み/attachments/<id>/)は動かさない。
   リンクは id_名前 で書いているので、フォルダを移しても切れない。
2. 一覧 00_ソリューション一覧.base・00_設計記録一覧.base は、新しい 00_設計案一覧.base があれば消し、
   なければ 00_設計案一覧.base に名前を変える。
3. ノート(.md)の中の「00_ソリューション一覧.base」を「00_設計案一覧.base」に書き換える。

同期プログラムと Obsidian の仕組みは古い type も読み続けるので、急いで当てなくてもよい。
何度走らせても同じ結果になる。標準ライブラリだけを使う。
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

OLD_TYPES = ("ソリューション", "設計記録")
NEW_TYPE = "設計案"
OLD_DIR = "01_目的"
NEW_DIR = "01_設計案"
NEW_BASE = "00_設計案一覧.base"
OLD_BASES = ("00_ソリューション一覧.base", "00_設計記録一覧.base")
FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
TYPE_LINE = re.compile(r"^(type\s*:\s*)[\"']?(ソリューション|設計記録)[\"']?(\s*(?:#.*)?)$", re.M)


def skip(p: Path, vault: Path) -> bool:
    parts = p.relative_to(vault).parts
    return any(x.startswith(".") for x in parts) or "_仕組み" in parts


def old_type(text: str) -> bool:
    m = FRONT.match(text)
    return bool(m and TYPE_LINE.search(m.group(1)))


def retype(text: str) -> str:
    m = FRONT.match(text)
    if not m:
        return text
    head = TYPE_LINE.sub(lambda t: t.group(1) + NEW_TYPE + t.group(3), m.group(1))
    return text[:m.start(1)] + head + text[m.end(1):]


def plan(vault: Path) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """移すノート(元, 先)と、その場で type だけ直すノート。"""
    moves, fixes = [], []
    for p in sorted(vault.rglob("*.md")):
        if skip(p, vault):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not old_type(text):
            continue
        rel = p.relative_to(vault).parts
        if OLD_DIR in rel[:-1]:
            i = len(rel) - 1 - rel[::-1].index(OLD_DIR)
            dest = vault.joinpath(*rel[:i], NEW_DIR, *rel[i + 1:])
            if dest.exists():
                fixes.append(p)          # 先に同じ名前があれば動かさず、type だけ直す
            else:
                moves.append((p, dest))
        else:
            fixes.append(p)
    return moves, fixes



VAULT_MARKS = ("_仕組み", "_templates", "_記録", "06_事実")


def is_vault(v: Path) -> bool:
    """vault の印(仕組みのフォルダ)があるか。書き間違えた場所のノートを書き換えないため。"""
    return any((v / m).is_dir() for m in VAULT_MARKS)

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
        if not is_vault(v):
            print(f"vault ではないようです(_仕組み フォルダがありません): {v}")
            return 1
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for v in vaults:
        print(f"== {v}")
        moves, fixes = plan(v)
        bases = [v / b for b in OLD_BASES if (v / b).exists()]
        notes = [p for p in v.rglob("*.md") if not skip(p, v)]
        links = []
        for p in notes:
            try:
                if any(b in p.read_text(encoding="utf-8") for b in OLD_BASES[:1]):
                    links.append(p)
            except (UnicodeDecodeError, OSError):
                pass
        if not (moves or fixes or bases or links):
            print("  することはありません")
            continue
        if run:
            (backup or v.parent).mkdir(parents=True, exist_ok=True)
            zip_base = (backup or v.parent) / f"移行前の控え_{v.name}_{stamp}"
            shutil.make_archive(str(zip_base), "zip", root_dir=v)
            print(f"  控え: {zip_base}.zip")
        for src, dst in moves:
            print(f"  移す: {src.relative_to(v)} → {dst.relative_to(v)}")
            if run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                text = src.read_text(encoding="utf-8")
                dst.write_bytes(retype(text).encode("utf-8"))
                src.unlink()
        for p in fixes:
            print(f"  type を {NEW_TYPE} に: {p.relative_to(v)}")
            if run:
                p.write_bytes(retype(p.read_text(encoding="utf-8")).encode("utf-8"))
        for b in bases:
            if (v / NEW_BASE).exists():
                print(f"  消す(新しい一覧があるため): {b.name}")
                if run:
                    b.unlink()
            else:
                print(f"  名前を変える: {b.name} → {NEW_BASE}")
                if run:
                    b.rename(v / NEW_BASE)
        for p in links:
            print(f"  一覧へのリンクを直す: {p.relative_to(v)}")
            if run:
                t = p.read_text(encoding="utf-8")
                p.write_bytes(t.replace(OLD_BASES[0], NEW_BASE).encode("utf-8"))
    if not run:
        print("\n(試し運転です。何も変えていません。--run をつけると実行します)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
