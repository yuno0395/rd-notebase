"""仕様書 v0.67 の個人 vault のフォルダの変更を、今ある個人 vault に当てる(個人 vault だけに使う)。

    python migrate_v067.py <個人 vault> [<個人 vault> ...] [--run] [--backup <控えのフォルダ>]

--run をつけないと、することを表示するだけで何も変えない。
--run をつけると、最初に vault ごとの控え(zip)を作ってから、次のことをする。
控えは vault の隣に作る。--backup を渡すとそのフォルダに作る(準備の bat はこれで共有クラウドフォルダの外に作る)。

1. 90_共有/ の中のファイル(配られた他の人のノート・添付・工程表)を、90_共有/ を外した同じ場所へ移す
   (90_共有/<プロジェクト>/03_イシュー/x.md → <プロジェクト>/03_イシュー/x.md)。
   移す先に同じ名前のファイルがあり、中身も同じなら 90_共有/ の方を消す。中身が違えば 90_共有/ の方を
   99_archive/90_共有の残り/ へ移して知らせる(移す先にある方を残す。配られたものは次の同期で共有の中身になる)。
2. 同期の記録(_仕組み/記録/同期の記録.json)の、配ったノートの場所から 90_共有/ を外し、配った印をつける。
3. 空になった 90_共有/ を消す。

自分のノート(01_目的/ や 03_イシュー/ など一番上の種類のフォルダにあるもの)は動かさない。
同期プログラムが振り分け先(<プロジェクト>/03_イシュー/ など)へ移す(要件書 F-57)。
何度走らせても同じ結果になる。標準ライブラリだけを使う。
"""

from __future__ import annotations

import filecmp
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

OLD = "90_共有"
STATE = Path("_仕組み/記録/同期の記録.json")
LEFT = Path("99_archive/90_共有の残り")


def is_vault(v: Path) -> bool:
    """個人 vault の印(仕組みのフォルダ)があるか。書き間違えた場所のファイルを動かさないため。"""
    return (v / "_仕組み").is_dir()


def plan(v: Path) -> tuple[list[tuple[Path, Path]], list[Path], list[tuple[Path, Path]]]:
    """(移すもの, 同じ中身なので消すもの, 中身が違うので 99_archive へ移すもの)。"""
    moves, drops, stuck = [], [], []
    old = v / OLD
    if not old.is_dir():
        return moves, drops, stuck
    for p in sorted(old.rglob("*")):
        if not p.is_file():
            continue
        dest = v / p.relative_to(old)
        if not dest.exists():
            moves.append((p, dest))
        elif filecmp.cmp(p, dest, shallow=False):
            drops.append(p)
        else:
            stuck.append((p, v / LEFT / p.relative_to(old)))
    return moves, drops, stuck


def fix_state(v: Path, run: bool) -> int:
    path = v / STATE
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0  # 壊れていれば同期プログラムが作り直す(F-34)
    n = 0
    for rec in (data.get("items") or {}).values():
        p = rec.get("p") if isinstance(rec, dict) else None
        if isinstance(p, str) and p.startswith(OLD + "/"):
            rec["p"] = p[len(OLD) + 1:]
            rec["m"] = "down"
            n += 1
    if n and run:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    return n


def remove_empty(d: Path) -> None:
    if not d.is_dir():
        return
    for sub in sorted((x for x in d.rglob("*") if x.is_dir()), key=lambda x: len(x.parts), reverse=True):
        if not any(sub.iterdir()):
            sub.rmdir()
    if not any(d.iterdir()):
        d.rmdir()


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
        moves, drops, stuck = plan(v)
        states = fix_state(v, run=False)
        if not (moves or drops or stuck or states or (v / OLD).is_dir()):
            print("  することはありません")
            continue
        if run and (moves or drops or stuck or states):
            (backup or v.parent).mkdir(parents=True, exist_ok=True)
            zip_base = (backup or v.parent) / f"移行前の控え_{v.name}_{stamp}"
            shutil.make_archive(str(zip_base), "zip", root_dir=v)
            print(f"  控え: {zip_base}.zip")
        for src, dest in moves:
            print(f"  移す: {src.relative_to(v).as_posix()} → {dest.relative_to(v).as_posix()}")
            if run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dest)
        for src in drops:
            print(f"  同じものが移す先にあるので消す: {src.relative_to(v).as_posix()}")
            if run:
                src.unlink()
        for src, dest in stuck:
            print(f"  移す先に中身の違う同じ名前のファイルがあるので、{dest.relative_to(v).as_posix()} へ移す:"
                  f" {src.relative_to(v).as_posix()}(要るものがあれば見比べて書き写してください)")
            if run and not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                src.rename(dest)
        if states:
            print(f"  同期の記録: 配ったノート {states} 件の場所を直す")
            if run:
                fix_state(v, run=True)
        if run:
            remove_empty(v / OLD)
            if (v / OLD).is_dir():
                print(f"  {OLD}/ が残っています(中のファイルを確かめてください)")
    if not run:
        print("\n(試し運転です。何も変えていません。--run をつけると実行します)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
