"""visibility(だれに見せるか)の値を読む(仕様書「共有する範囲」v0.90)。

書けるのは決まった言葉だけ:
- PIP: 自分だけ。ほかと組み合わせない。個人 vault の 00_PIP/ に置き、同期プログラムは読まない
- Internal use only: 社内全般。プロジェクト名とは一緒に書かない
- <プロジェクト名>: そのプロジェクトの所属者だけ(台帳の名前。2つ以上も可)
- EXT_<相手>: 特定の社外。PIP 以外に足せる(相手は 共有の _仕組み/EXT_一覧.csv に登録したものだけ)
当面は「印」だけで、共有 vault は全員が見られる(フォルダの権限で守るのは後で)。

v0.89 までの値も読む: 個人 → PIP、社内 → Internal use only、チーム・空 → 範囲を決めていない(置き場所のプロジェクト)。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

PIP = "PIP"
INTERNAL = "Internal use only"
EXT_PREFIX = "EXT_"
OLD = {"個人": PIP, "社内": INTERNAL}
OLD_OPEN = {"チーム", ""}          # v0.89 までの「チーム」と空。範囲を決めていない
PIP_TOP = "00_PIP"                 # 個人 vault の、絶対に共有しないフォルダ(v0.89 までの 00_日誌)
OLD_PIP_TOP = "00_日誌"
EXT_LIST = Path("_仕組み") / "EXT_一覧.csv"


def values(fm: dict) -> list[str]:
    """属性欄の visibility を、前後の空白を取ったリストにする(1つだけ書いたものもリストに)。"""
    v = fm.get("visibility")
    if v is None:
        return []
    items = v if isinstance(v, list) else [v]
    return [str(x).strip() for x in items if str(x).strip()]


def is_pip(fm: dict) -> bool:
    """自分だけ(PIP)か。古い 個人 も同じ。メモ(type: メモ)も共有しない。"""
    if str(fm.get("type") or "").strip() == "メモ":
        return True
    return any(OLD.get(v, v) == PIP for v in values(fm))


@dataclass
class Scope:
    internal: bool = False
    projects: list[str] = field(default_factory=list)
    ext: list[str] = field(default_factory=list)
    pip: bool = False
    open: bool = False     # 範囲を書いていない(古いチーム・空)


def parse(fm: dict) -> Scope:
    s = Scope()
    vs = values(fm)
    if not vs or all(v in OLD_OPEN for v in vs):
        s.open = True
        return s
    for v in vs:
        v = OLD.get(v, v)
        if v == PIP:
            s.pip = True
        elif v == INTERNAL:
            s.internal = True
        elif v.startswith(EXT_PREFIX):
            s.ext.append(v)
        elif v in OLD_OPEN:
            continue
        else:
            s.projects.append(v)
    return s


def read_ext(shared: Path) -> set[str]:
    """登録した社外の相手(EXT_一覧.csv の1列目。EXT_ がなければ足す)。"""
    f = shared / EXT_LIST
    out: set[str] = set()
    try:
        with f.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.reader(fh):
                if not row or not row[0].strip() or row[0].strip() in ("名前", "name") or row[0].startswith("#"):
                    continue
                n = row[0].strip()
                out.add(n if n.startswith(EXT_PREFIX) else EXT_PREFIX + n)
    except OSError:
        pass
    return out


def problems(fm: dict, projects: set[str], ext: set[str]) -> list[str]:
    """決まりに合わないところ。なければ空。projects は台帳の名前、ext は登録した社外の相手。"""
    s = parse(fm)
    if s.open:
        return []
    out = []
    if s.pip and (s.internal or s.projects or s.ext):
        out.append("PIP はほかと一緒に書けません")
    if s.internal and s.projects:
        out.append("Internal use only とプロジェクト名は一緒に書けません")
    for p in s.projects:
        if p not in projects:
            out.append(f"「{p}」は決まった言葉でも台帳のプロジェクト名でもありません")
    for e in s.ext:
        if e not in ext:
            out.append(f"「{e}」は EXT_一覧.csv に登録されていません")
    if len(set(values(fm))) != len(values(fm)):
        out.append("同じ値が2回あります")
    return out


def visible_in(fm: dict, project: str | None) -> bool:
    """週報・説明資料に載せてよいか。PIP は載せない。プロジェクト名だけのものは、そのプロジェクトのときだけ。"""
    s = parse(fm)
    if s.pip:
        return False
    if s.open or s.internal or not s.projects or project is None:
        return True
    return project in s.projects
