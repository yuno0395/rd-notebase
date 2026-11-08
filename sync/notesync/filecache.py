"""同じファイルを何度も読まないための控え。

1回の同期で同じノートを10回以上読み、添付は毎回中身のハッシュを取っていた。共有クラウドフォルダ(Box Drive など)では
ファイルを開くたびに時間がかかるので、読んだ中身とハッシュを覚えておく。
ファイルの更新時刻か大きさが変わっていたら読み直す(ほかのアプリや人が書き換えても気づく)。
watch で動いている間は、次の同期でも使い回す。
"""

from __future__ import annotations

import os
from pathlib import Path

MAX_ITEMS = 20000  # これを超えたら一度忘れる(覚えすぎて PC のメモリを使いすぎないように)

_text: dict[str, tuple[int, int, str]] = {}
_hash: dict[str, tuple[int, int, str]] = {}


def _sign(path: Path) -> tuple[str, int, int]:
    st = os.stat(path)
    return os.fspath(path), st.st_mtime_ns, st.st_size


def read_text(path: Path, load) -> str:
    """load(path) で読んだ中身を、ファイルが変わるまで覚えておく。"""
    key, mtime, size = _sign(path)
    hit = _text.get(key)
    if hit and hit[0] == mtime and hit[1] == size:
        return hit[2]
    text = load(path)
    if len(_text) >= MAX_ITEMS:
        _text.clear()
    _text[key] = (mtime, size, text)
    return text


def hash_of(path: Path, compute) -> str:
    """compute(path) で取ったハッシュを、ファイルが変わるまで覚えておく。"""
    key, mtime, size = _sign(path)
    hit = _hash.get(key)
    if hit and hit[0] == mtime and hit[1] == size:
        return hit[2]
    h = compute(path)
    if len(_hash) >= MAX_ITEMS:
        _hash.clear()
    _hash[key] = (mtime, size, h)
    return h


def forget(path: Path) -> None:
    """書き換えたファイルの控えを消す(同じ時刻・同じ大きさで書き換わったときにも読み直すように)。"""
    key = os.fspath(path)
    _text.pop(key, None)
    _hash.pop(key, None)


def clear() -> None:
    _text.clear()
    _hash.clear()


def walk_md(root: Path, skip_tops=frozenset(), only_tops=None) -> list[Path]:
    """root の下の .md を、sorted(root.rglob("*.md")) と同じ並びで返す。
    隠しフォルダ(.obsidian など)と、一番上の skip_tops のフォルダ(_仕組み など)には入らない
    (呼ぶ側はどれも、その中のファイルを読まずに捨てていた。添付のフォルダをたどる分が減る)。
    only_tops を渡すと、一番上はそのフォルダにだけ入る(00_inbox だけを見たいときに、vault 全体をたどらない)。"""
    nt = os.name == "nt"
    return [p for p in walk_files(root, skip_tops, only_tops) if (p.name.lower() if nt else p.name).endswith(".md")]


def walk_files(root: Path, skip_tops=frozenset(), only_tops=None, hidden: bool = False) -> list[Path]:
    """root の下のファイルを、sorted(root.rglob("*")) のファイルだけと同じ並びで返す。
    ファイルかどうかはフォルダの一覧から見分け、1つずつ調べない(共有クラウドフォルダでは1つずつ調べると遅い)。
    hidden が False なら隠しフォルダ(.obsidian など)には入らない。"""
    out = []
    root_s = os.fspath(root)
    for dirpath, dirnames, filenames in os.walk(root_s):
        if dirpath == root_s:
            dirnames[:] = [d for d in dirnames if d not in skip_tops and (only_tops is None or d in only_tops)]
            if only_tops is not None:
                filenames = []
        if not hidden:
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for f in filenames:
            out.append(Path(dirpath, f))
    return sorted(out)
