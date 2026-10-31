"""設定の場所の確かめ(F-55)。

config.yaml に書いた場所が、本当にその vault かを同期の前に確かめる。違っていれば何も書かずに止める。
書き間違い(例: secret に共有クラウドフォルダの一番上を書く)で、関係ないフォルダの .md を改名したり、
外部の人がいるフォルダへノートを集めたりしないため。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

SYSTEM_DIR = "_仕組み"

# ホームの直下にできる、同期アプリの一番上のフォルダ(Box・OneDrive・Dropbox・Google ドライブ・iCloud Drive)。
# OneDrive は「OneDrive - 会社名」の形にもなる。NAS やネットワークドライブの一番上は、ドライブの一番上として扱う
CLOUD_TOP = re.compile(r"^(box|dropbox|onedrive( - .+)?|google ?drive|icloud ?drive)$", re.I)


def _key(p: Path) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def looks_like_vault(root: Path) -> bool:
    """vault の印があるか。どれも _仕組み/ を持つ。"""
    return (root / SYSTEM_DIR).is_dir()


def _too_broad(root: Path) -> bool:
    """ドライブの一番上・ホーム・Users のような、vault にはならない広い場所。"""
    try:
        home = Path.home()
    except RuntimeError:
        home = None
    k = _key(root)
    if root.parent == root:
        return True
    if home is not None and k in {_key(home), _key(home.parent)}:
        return True
    return bool(CLOUD_TOP.match(root.name)) and home is not None and _key(root.parent) == _key(home)


def _inside(a: Path, b: Path) -> bool:
    """a が b と同じか、b の下にあるか。"""
    ka, kb = _key(a), _key(b)
    return ka == kb or ka.startswith(kb.rstrip("\\/") + os.sep)


def check_places(cfg) -> list[str]:
    """設定の場所のおかしな所。空なら同期してよい。見つからない場所は、ここでは見ない(F-50 が扱う)。"""
    slots: list[tuple[str, Path]] = [("個人 vault(personal)", cfg.personal)]
    if cfg.shared:
        slots.append(("共有 vault(shared)", cfg.shared))
    slots += [(f"機密フォルダ(secret の {i})", p) for i, p in enumerate(cfg.secret, 1)]
    problems: list[str] = []
    for label, root in slots:
        if not root.exists():
            continue
        if _too_broad(root):
            problems.append(f"{label} が {root} になっています。ドライブやホーム、共有クラウドフォルダ(Box・OneDrive など)の一番上は vault にできません")
        elif not looks_like_vault(root):
            problems.append(f"{label} の {root} に vault の印(_仕組み フォルダ)がありません。"
                            "場所を書き間違えていないか確かめてください")
    for i, (la, a) in enumerate(slots):
        for lb, b in slots[i + 1:]:
            if _inside(a, b) or _inside(b, a):
                problems.append(f"{la} と {lb} が重なっています({a} / {b})。別々のフォルダにしてください")
    for label, p in (("開発データ(shared_data)", cfg.shared_data), ("報告フォルダ(report)", cfg.report_dir)):
        if not p:
            continue
        for lb, root in slots:
            if _inside(root, p):
                problems.append(f"{label} の {p} の中に {lb} があります。別々のフォルダにしてください")
            elif lb.startswith("機密") and _inside(p, root):
                problems.append(f"{label} の {p} が {lb} の中にあります。機密フォルダの外にしてください")
    return problems
