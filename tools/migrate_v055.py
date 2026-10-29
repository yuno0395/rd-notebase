"""仕様書 v0.55 の属性名の変更を、今ある vault に当てる(個人・共有のどちらにも使える)。

    python migrate_v055.py <vault> [<vault> ...] [--run] [--backup <控えのフォルダ>]

--run をつけないと、することを表示するだけで何も変えない。
--run をつけると、最初に vault ごとの控え(zip)を作ってから、次のことをする。
控えは vault の隣に作る。--backup を渡すとそのフォルダに作る(準備の bat はこれで Box の外に作る)。

1. type が イシュー のノート: 属性欄の `parent:` を `脅かす:` に名前だけ変える(値はそのまま)。
   脅かす がもうあるノートは変えない。
2. type が 設計案(古い ソリューション・設計記録 も)のノート: friend のうち、行き先が価値の仮説(type: 仮説)の
   ものを `価値仮説:` へ移す。ノードなど、ほかの friend は残す。行き先の種類は、同じ vault のノートから調べる。

同期プログラムと Obsidian の仕組みは古い parent・friend も読み続けるので、急いで当てなくてもよい。
当てると、K-Plex で設計案を中心にしたとき、左に価値仮説、右にイシューが出る。
何度走らせても同じ結果になる。標準ライブラリだけを使う。
"""

from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
TYPE = re.compile(r"^type\s*:\s*[\"']?([^\"'#\r\n]+?)[\"']?\s*(?:#.*)?$", re.M)
ID_PREFIX = re.compile(r"^[0-9A-Z]{6}[0-9A-Z]+_", re.I)
LINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
DESIGN = {"設計案", "ソリューション", "設計記録"}


def skip(p: Path, vault: Path) -> bool:
    parts = p.relative_to(vault).parts
    return any(x.startswith(".") for x in parts) or "_仕組み" in parts


def type_of(text: str) -> str:
    m = FRONT.match(text)
    t = m and TYPE.search(m.group(1))
    return t.group(1).strip() if t else ""


def block(lines: list[str], key: str) -> tuple[int, int] | None:
    """属性欄の key の行と、続く `  - …` の行の範囲。"""
    for i, l in enumerate(lines):
        if re.match(rf"^{re.escape(key)}\s*:", l):
            end = i + 1
            while end < len(lines) and re.match(r"^(\s+\S|-\s)", lines[end]):
                end += 1
            return i, end
    return None


def flow(items: list[str]) -> str:
    return "[" + ", ".join(f'"{x}"' for x in items) + "]"


def convert(text: str, types: dict[str, str]) -> str:
    m = FRONT.match(text)
    if not m:
        return text
    t = type_of(text)
    lines = m.group(1).split("\n")
    if t == "イシュー":
        if block(lines, "脅かす") or not block(lines, "parent"):
            return text
        i, _ = block(lines, "parent")
        lines[i] = re.sub(r"^parent", "脅かす", lines[i])
    elif t in DESIGN:
        b = block(lines, "friend")
        if not b:
            return text
        links = [x.group(0) for x in LINK.finditer("\n".join(lines[b[0]:b[1]]))]
        hyp = [x for x in links if types.get(LINK.match(x).group(1).strip().lower()) == "仮説"]
        if not hyp:
            return text
        rest = [x for x in links if x not in hyp]
        old = block(lines, "価値仮説")
        have = [x.group(0) for x in LINK.finditer("\n".join(lines[old[0]:old[1]]))] if old else []
        new = have + [x for x in hyp if x not in have]
        repl = [f"friend: {flow(rest)}"] if rest else []
        lines[b[0]:b[1]] = repl
        old = block(lines, "価値仮説")
        if old:
            lines[old[0]:old[1]] = [f"価値仮説: {flow(new)}"]
        else:
            lines.insert(b[0], f"価値仮説: {flow(new)}")
    else:
        return text
    head = "\n".join(lines)
    return text[:m.start(1)] + head + text[m.end(1):]


def note_types(vault: Path) -> dict[str, str]:
    """リンクの書き方(id_名前・名前・id)から種類を引く表。名前が重なれば、その名前では引かない。"""
    out: dict[str, str] = {}
    dup: set[str] = set()
    for p in vault.rglob("*.md"):
        if skip(p, vault):
            continue
        try:
            t = type_of(p.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, OSError):
            continue
        stem = p.name[:-3]
        keys = {stem.lower(), ID_PREFIX.sub("", stem).lower()}
        m = ID_PREFIX.match(stem)
        if m:
            keys.add(m.group(0)[:-1].lower())
        for k in keys:
            if k in out and out[k] != t:
                dup.add(k)
            out[k] = t
    return {k: v for k, v in out.items() if k not in dup}



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
        types = note_types(v)
        todo = []
        for p in sorted(v.rglob("*.md")):
            if skip(p, v):
                continue
            try:
                t = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            n = convert(t, types)
            if n != t:
                todo.append((p, n))
        if not todo:
            print("  することはありません")
            continue
        if run:
            (backup or v.parent).mkdir(parents=True, exist_ok=True)
            zip_base = (backup or v.parent) / f"移行前の控え_{v.name}_{stamp}"
            shutil.make_archive(str(zip_base), "zip", root_dir=v)
            print(f"  控え: {zip_base}.zip")
        for p, n in todo:
            what = "parent → 脅かす" if type_of(n) == "イシュー" else "friend の仮説 → 価値仮説"
            print(f"  {what}: {p.relative_to(v)}")
            if run:
                p.write_bytes(n.encode("utf-8"))
    if not run:
        print("\n(試し運転です。何も変えていません。--run をつけると実行します)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
