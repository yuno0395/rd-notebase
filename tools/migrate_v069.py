"""仕様書 v0.69 の status の言い回しの統合を、今ある vault に当てる(個人・共有のどちらにも使える)。

    python migrate_v069.py <vault> [<vault> ...] [--run] [--backup <控えのフォルダ>]

--run をつけないと、することを表示するだけで何も変えない。
--run をつけると、最初に vault ごとの控え(zip)を作ってから、属性欄の `status:` の古い言い回しをいまの値に書き換える。
控えは vault の隣に作る。--backup を渡すとそのフォルダに作る(準備の bat はこれで共有クラウドフォルダの外に作る)。

どの種類も 未着手・進行中・待ち・確認待ち・完了・中止 の6つで進み具合を書き、わかったことを表す
一部解決(イシュー)・採用・不採用(設計案)・仮説が誤っていた(仮説)だけを足す。

| 古い | いま |
| 未対応 / 対策中 / 低減済み / 解消 | 未着手 / 進行中 / 一部解決 / 完了 |
| 検証中 / 確かめた / 外れた | 進行中 / 完了 / 仮説が誤っていた |
| 有効 / 達成 / 取り下げ | 進行中 / 完了 / 中止 |
| 候補 / 変更 | 進行中 / 中止 |
| 中断 | 待ち |

属性欄の status の行だけを変え、行の後ろのコメントと本文はそのまま残す。_仕組み/ の中は変えない。
同期プログラムと Obsidian の仕組みは古い言い回しも読むので、急いで当てなくてもよい。
何度走らせても同じ結果になる。標準ライブラリだけを使う。
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
OLD = {"未対応": "未着手", "対策中": "進行中", "低減済み": "一部解決", "解消": "完了",
       "検証中": "進行中", "確かめた": "完了", "外れた": "仮説が誤っていた",
       "有効": "進行中", "達成": "完了", "取り下げ": "中止",
       "候補": "進行中", "変更": "中止",
       "中断": "待ち"}
LINE = re.compile(r"^(status\s*:\s*)([\"']?)([^\"'#\r\n]+?)([\"']?)(\s*(?:#.*)?)$", re.M)
VAULT_MARKS = ("_仕組み", "_templates", "_記録", "06_事実")


def skip(p: Path, vault: Path) -> bool:
    parts = p.relative_to(vault).parts
    return any(x.startswith(".") for x in parts) or "_仕組み" in parts


def convert(text: str) -> tuple[str, str]:
    """書き換えた文と、「古い → いま」。変えなければ (text, "")。"""
    m = FRONT.match(text)
    if not m:
        return text, ""
    head = m.group(1)
    s = LINE.search(head)
    if not s or s.group(3).strip() not in OLD:
        return text, ""
    old = s.group(3).strip()
    new_head = head[:s.start()] + s.group(1) + s.group(2) + OLD[old] + s.group(4) + s.group(5) + head[s.end():]
    return text[:m.start(1)] + new_head + text[m.end(1):], f"{old} → {OLD[old]}"


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
        todo = []
        for p in sorted(v.rglob("*.md")):
            if skip(p, v):
                continue
            try:
                t = p.read_bytes().decode("utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            n, what = convert(t)
            if n != t:
                todo.append((p, n, what))
        if not todo:
            print("  することはありません")
            continue
        if run:
            (backup or v.parent).mkdir(parents=True, exist_ok=True)
            zip_base = (backup or v.parent) / f"移行前の控え_{v.name}_{stamp}"
            shutil.make_archive(str(zip_base), "zip", root_dir=v)
            print(f"  控え: {zip_base}.zip")
        for p, n, what in todo:
            print(f"  status {what}: {p.relative_to(v)}")
            if run:
                p.write_bytes(n.encode("utf-8"))
    if not run:
        print("\n(試し運転です。何も変えていません。--run をつけると実行します)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
