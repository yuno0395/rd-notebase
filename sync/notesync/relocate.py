"""F-50: vault の名前や場所が変わっても、各 PC の同期が新しい場所を見つけて設定を直す。

- 各 vault の `_仕組み/記録/vault_id.txt` に、その vault だけの印を置く(なければ同期プログラムが作る)。
- 印と場所の組を、config.yaml の隣の `vault_ids_<config の名前>.json` に覚えておく。
- 設定の場所が見つからないとき、覚えた印と同じ印を持つフォルダを近くから探す。元の場所の上で残っている
  いちばん近いフォルダから下へ 3 段、なければその 1 つ上から下へ 3 段(ホームとドライブの一番上は歩かない)。ちょうど 1 つ見つかれば config.yaml のその行だけを書き直す(コメントは残す)。
- 個人と共有は、印を覚えていなくても中身で見分ける(個人は 個人設定.md の name、共有は メンバー.csv に
  自分の名前がある)。候補が 2 つ以上あれば選ばずに知らせる。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import time
import uuid
from pathlib import Path

VAULT_ID = Path("_仕組み/記録") / "vault_id.txt"
SYSTEM_DIR = "_仕組み"
UP = 3          # 元の場所から上へたどる段数
DOWN = 3        # 探すフォルダから下へ見る段数
MAX_DIRS = 5000  # Box 全体を歩き回らないための上限


def record_path(config_path: Path) -> Path:
    return config_path.parent / f"vault_ids_{config_path.stem}.json"


def _key(p: Path | str) -> str:
    return os.path.normcase(os.path.normpath(str(p)))


def read_id(root: Path) -> str:
    try:
        return (root / VAULT_ID).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def ensure_id(root: Path) -> str:
    """vault の印を読む。なければ作る(ノートではないので試し運転でも置く)。"""
    got = read_id(root)
    if got:
        return got
    new = uuid.uuid4().hex
    try:
        (root / VAULT_ID).parent.mkdir(parents=True, exist_ok=True)
        (root / VAULT_ID).write_text(new + "\n", encoding="utf-8")
    except OSError:
        return ""
    return new


def _load_record(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in (data.get("paths") or {}).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def _save_record(path: Path, rec: dict[str, str]) -> None:
    try:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps({"version": 1, "paths": rec}, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def _search_roots(old: Path) -> list[Path]:
    """探す順のフォルダ。残っているいちばん近い上のフォルダ、次にその1つ上。ホームやドライブの一番上は歩かない。"""
    p = old.parent
    for _ in range(UP):
        if p.exists() or p.parent == p:
            break
        p = p.parent
    if not p.exists():
        return []
    stop = {_key(Path.home()), _key(Path.home().parent)}
    out = []
    for d in (p, p.parent):
        if d.parent == d or _key(d) in stop:
            break
        out.append(d)
    return out


def _vault_dirs(roots: list[Path]):
    """roots の下の vault(_仕組み を持つフォルダ)を返す。vault の中には入らない。"""
    seen: set[str] = set()
    count = 0
    for root in roots:
        stack = [(root, 0)]
        while stack:
            d, depth = stack.pop()
            k = _key(d)
            if k in seen:
                continue
            seen.add(k)
            count += 1
            if count > MAX_DIRS:
                return
            if (d / SYSTEM_DIR).is_dir():
                yield d
                continue
            if depth >= DOWN:
                continue
            try:
                children = [c for c in d.iterdir() if c.is_dir() and not c.name.startswith((".", "$")) and c.name != "AppData"]
            except OSError:
                continue
            stack += [(c, depth + 1) for c in sorted(children, reverse=True)]


def _is_personal_of(d: Path, member: str) -> bool:
    from .config import read_my_code
    try:
        name, _code = read_my_code(d)
    except Exception:
        return False
    return bool(name) and name == member


def _is_shared_for(d: Path, member: str) -> bool:
    from .config import read_members
    if not (d / SYSTEM_DIR / "同期設定.yaml").exists():
        return False
    try:
        return member in read_members(d)
    except Exception:
        return False


def find_moved(old: Path, vault_id: str, kind: str, member: str, taken: set[str]) -> tuple[list[Path], str]:
    """old にあった vault の新しい場所の候補。近いフォルダから探し、見つかった所で止める。返すのは (候補, 見分け方)。"""
    for root in _search_roots(old):
        dirs = [d for d in _vault_dirs([root]) if _key(d) not in taken]
        if vault_id:
            hit = [d for d in dirs if read_id(d) == vault_id]
            if hit:
                return hit, "印"
        if kind == "個人":
            hit, how = [d for d in dirs if _is_personal_of(d, member)], "個人設定.md の name"
        elif kind == "共有":
            hit, how = [d for d in dirs if _is_shared_for(d, member)], "メンバー.csv"
        else:
            hit, how = [], ""
        if hit:
            return hit, how
    return [], ""


LINE = re.compile(r"^(?P<head>\s*(?:-\s+|[A-Za-z_]+:\s*))(?P<q>[\"']?)(?P<val>[^\"'#\r\n]*?)(?P=q)(?P<tail>\s*(?:#.*)?)$")


def rewrite_config(config_path: Path, old: Path, new: Path) -> bool:
    """config.yaml の old を書いた行だけを new にする。コメントや並びはそのまま。直したら True。"""
    try:
        raw = config_path.read_bytes()
    except OSError:
        return False
    text = raw.decode("utf-8-sig")
    lines = text.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        body = line.rstrip("\r\n")
        end = line[len(body):]
        m = LINE.match(body)
        if not m or not m.group("val").strip() or _key(m.group("val").strip()) != _key(old):
            continue
        val = m.group("val").strip()
        shown = str(new)
        if "/" in val and "\\" not in val:
            shown = shown.replace("\\", "/")
        lines[i] = f"{m.group('head')}{m.group('q')}{shown}{m.group('q')}{m.group('tail')}{end}"
        changed = True
    if not changed:
        # すでに直してある(watch が古い設定のまま動いていたとき)
        return any((m := LINE.match(l.rstrip("\r\n"))) and m.group("val").strip()
                   and _key(m.group("val").strip()) == _key(new) for l in lines)
    try:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(config_path, config_path.with_name(f"{config_path.name}.{stamp}.bak"))
        tmp = config_path.with_name(config_path.name + ".tmp")
        tmp.write_bytes(("﻿" if raw.startswith(b"\xef\xbb\xbf") else "").encode("utf-8") + "".join(lines).encode("utf-8"))
        os.replace(tmp, config_path)
    except OSError:
        return False
    return True


def follow(cfg, dry: bool = False) -> tuple[list[str], list[str]]:
    """設定の場所が見つからない vault を探して直す。返すのは (記録, 警告)。cfg の場所もその場で直す。"""
    records: list[str] = []
    warnings: list[str] = []
    if not cfg.config_path:
        return records, warnings
    rec_path = record_path(cfg.config_path)
    rec = _load_record(rec_path)
    before = dict(rec)
    slots: list[tuple[str, Path, int]] = [("個人", cfg.personal, -1)]
    if cfg.shared:
        slots.append(("共有", cfg.shared, -1))
    slots += [("機密", p, i) for i, p in enumerate(cfg.secret)]
    taken = {_key(p) for _k, p, _i in slots if p.exists()}

    for kind, path, idx in slots:
        if path.exists():
            vid = ensure_id(path)
            if vid:
                rec[_key(path)] = vid
            continue
        vid = rec.get(_key(path), "")
        found, how = find_moved(path, vid, kind, cfg.member, taken)
        if len(found) != 1:
            if len(found) > 1:
                warnings.append(f"{kind} vault が {path} に見つからず、似たフォルダが {len(found)} つあるので選べません: "
                                f"{'、'.join(str(f) for f in found)}。設定ファイル {cfg.config_path} を手で直してください")
            continue
        new = found[0]
        taken.add(_key(new))
        if dry:
            records.append(f"{kind} vault の場所が変わっていたので、設定を {path} → {new} に直す({how}で見つけた)")
        elif rewrite_config(cfg.config_path, path, new):
            records.append(f"{kind} vault の場所が変わっていたので、設定を直した: {path} → {new}({how}で見つけた)")
        else:
            warnings.append(f"{kind} vault を {new} に見つけましたが、設定ファイル {cfg.config_path} を書き直せませんでした。"
                            "今回は見つけた場所で同期します。手で直してください")
        if kind == "個人":
            cfg.personal = new
        elif kind == "共有":
            cfg.shared = new
        else:
            cfg.secret[idx] = new
        nid = ensure_id(new)
        if nid:
            rec[_key(new)] = nid
            rec.setdefault(_key(path), nid)  # 古い場所も覚えておく(watch 中の古い設定から引けるように)
    if rec != before:
        _save_record(rec_path, rec)
    return records, warnings
