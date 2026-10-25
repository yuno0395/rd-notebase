"""仕様書 v0.31 のフォルダ整理を、今ある vault に当てる(1回だけ使う)。

    python migrate_v031.py <vault> [<vault> ...] [--state <state_dir> ...] [--run]

--run をつけないと、することを表示するだけで何も変えない。
--run をつけると、最初に vault ごとの控え(zip)を作ってから、次のことをする。

1. フォルダを移す: 00_daily → 00_日誌/デイリー、00_weekly → 00_日誌/週報、
   _attachments・_記録・_templates・_tools・_設定 → _仕組み/ の下、
   00_同期レポート.md・00_同期設定.yaml → _仕組み/ の下、05_結果 → 05_ナレッジ(どの深さでも)、
   _仕組み/templates/結果図.excalidraw.md → ナレッジ図.excalidraw.md
2. ノート(.md)・一覧(.base)・設定(.obsidian*/ の .json)・同期の記録(state_*.json)の中の
   パスと言葉を、新しいものに書き換える。

標準ライブラリだけを使う。
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

MOVES = [
    ("00_daily", "00_日誌/デイリー"),
    ("00_weekly", "00_日誌/週報"),
    ("00_同期レポート.md", "_仕組み/同期レポート.md"),
    ("00_同期設定.yaml", "_仕組み/同期設定.yaml"),
    ("_attachments", "_仕組み/attachments"),
    ("_記録", "_仕組み/記録"),
    ("_templates", "_仕組み/templates"),
    ("_tools", "_仕組み/tools"),
    ("_設定", "_仕組み/設定"),
]
TEXT = [
    ("00_同期レポート.md", "_仕組み/同期レポート.md"),
    ("00_同期設定.yaml", "_仕組み/同期設定.yaml"),
    ("_attachments", "_仕組み/attachments"),
    ("_記録", "_仕組み/記録"),
    ("_templates", "_仕組み/templates"),
    ("_tools", "_仕組み/tools"),
    ("_設定", "_仕組み/設定"),
    ("00_daily", "00_日誌/デイリー"),
    ("00_weekly", "00_日誌/週報"),
    ("05_結果", "05_ナレッジ"),
    ("結果図", "ナレッジ図"),
    ("_結果.excalidraw.md", "_ナレッジ図.excalidraw.md"),
    ("## 結果(大: ナレッジ図を貼る。", "## リスクはどう変わったか(大: ナレッジ図を貼る。"),
    ("「結果」欄", "「リスクはどう変わったか」欄"),
]
TEXT_SUFFIXES = {".md", ".base", ".yaml", ".csv", ".js"}


def rewrite(text: str) -> str:
    # 新しい言葉は古い言葉を含まないので、2回当てても変わらない。
    # 英数字のすぐ後ろは置き換えない(Templater の設定名 file_templates などを壊さないため)
    for a, b in TEXT:
        text = re.sub(r"(?<![A-Za-z0-9])" + re.escape(a), lambda m: b, text)
    return text


def plan_moves(vault: Path) -> list[tuple[Path, Path]]:
    out = [(vault / a, vault / b) for a, b in MOVES if (vault / a).exists() and not (vault / b).exists()]
    for d in sorted(vault.rglob("05_結果"), key=lambda p: -len(p.parts)):
        if d.is_dir() and ".obsidian" not in str(d):
            out.append((d, d.with_name("05_ナレッジ")))
    return out


def text_files(vault: Path):
    for p in vault.rglob("*"):
        if not p.is_file():
            continue
        parts = p.relative_to(vault).parts
        in_config = any(x.startswith(".obsidian") for x in parts)
        if in_config:
            if p.suffix == ".json" and "node_modules" not in parts:
                yield p
        elif p.suffix in TEXT_SUFFIXES:
            yield p


def main(argv: list[str]) -> int:
    run = "--run" in argv
    args = [a for a in argv if a != "--run"]
    vaults, states = [], []
    target = vaults
    for a in args:
        if a == "--state":
            target = states
            continue
        target.append(Path(a))
    if not vaults:
        print(__doc__)
        return 2
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for v in vaults:
        if not v.exists():
            print(f"見つかりません: {v}")
            return 1
    for v in vaults:
        print(f"== {v}")
        if run:
            zip_base = v.parent / f"移行前の控え_{v.name}_{stamp}"
            shutil.make_archive(str(zip_base), "zip", root_dir=v)
            print(f"  控え: {zip_base}.zip")
        for src, dst in plan_moves(v):
            print(f"  移す: {src.relative_to(v)} → {dst.relative_to(v)}")
            if run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
        old_t = v / "_仕組み/templates/結果図.excalidraw.md"
        new_t = v / "_仕組み/templates/ナレッジ図.excalidraw.md"
        if (old_t.exists() or (not run and (v / "_templates/結果図.excalidraw.md").exists())) and not new_t.exists():
            print("  名前を変える: 結果図.excalidraw.md → ナレッジ図.excalidraw.md")
            if run:
                old_t.rename(new_t)
        changed = 0
        for p in list(text_files(v)):
            try:
                t = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            n = rewrite(t)
            if n != t:
                changed += 1
                if run:
                    p.write_bytes(n.encode("utf-8"))
        print(f"  書き換えるファイル: {changed} 件")
    for s in states:
        for p in sorted(s.glob("state_*.json")):
            t = p.read_text(encoding="utf-8")
            n = rewrite(t)
            if n != t:
                print(f"  同期の記録を書き換える: {p}")
                if run:
                    p.write_bytes(n.encode("utf-8"))
    if not run:
        print("\n(試し運転です。何も変えていません。--run をつけると実行します)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
