"""F-16: Box Drive が作った競合の複製を見つけて、同期レポートに出す。

Box Drive は、2台で同じファイルを同時に直すと、片方を別の名前で残す。
名前の形は版や言語で違うので、次のどれかに当たるものを拾う。

- かっこの中に「conflict」「競合」「コンフリクト」がある: `メモ (Yu's conflicted copy 2026-10-24).md`
- 名前の最後が「 (1)」のような番号: `メモ (1).md`(同じ名前の元のファイルがあるときだけ)

同期プログラムが自分で置く競合ファイル(`_競合_`、F-15)は、作ったときに知らせているので数えない。
中身は読まず、消しもしない。どちらを残すかは人が決める。
"""

from __future__ import annotations

from pathlib import Path

from .report import Report
from .vault import box_copy_of, is_hidden


def find_copies(root: Path) -> list[tuple[Path, Path | None]]:
    """[(複製, 元のファイル(わかれば))]"""
    out = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(is_hidden(x) for x in p.relative_to(root).parts[:-1]):
            continue
        is_copy, orig = box_copy_of(p)
        if is_copy:
            out.append((p, orig))
    return out


def report_box_copies(vaults: list[tuple[str, Path]], report: Report) -> None:
    for label, root in vaults:
        for copy, orig in find_copies(root):
            rel = copy.relative_to(root).as_posix()
            if orig:
                o = orig.relative_to(root).as_posix()
                report.todo(f"Box の競合の複製: {label}/{rel} があります。{label}/{o} と見比べて、"
                            "残す方に書き足してから、複製を消してください")
            else:
                report.todo(f"Box の競合の複製: {label}/{rel} があります。中身を確かめて、"
                            "必要なら元のノートに書き足してから消してください")
