"""配布物を組み立てる(仕様書「仕組みの正本と配布」)。

使い方:  python tools/build.py 0.1.0
できるもの: dist/0.1.0/{共有,個人,機密}/ と dist/0.1.0/manifest.toml、plugins.py・プラグインを入れる.bat、
          準備/setup.py(準備の bat の中身)、同期プログラム/(notesync と起動用の bat)、移し替え/(manifest の migrate)
続けて python tools/plugins.py pack 0.1.0 --from <プラグインが入った設定フォルダ> で dist/0.1.0/プラグイン/ をそろえる。
これを Box の共有 _仕組み/tools/配布/0.1.0/ に置く。

Python 3.11 以上。標準ライブラリだけを使う。
"""
import fnmatch
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        for f in src.rglob("*"):
            if f.is_file():
                copy(f, dst / f.relative_to(src))
        return
    if src.name == ".gitkeep":
        dst.parent.mkdir(parents=True, exist_ok=True)  # 空のフォルダだけ作る
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def kind(path: str, v: dict) -> str | None:
    for k in ("system", "seed"):
        if any(fnmatch.fnmatchcase(path, p) for p in v.get(k, [])):
            return k
    return None


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    version = sys.argv[1]
    manifest = tomllib.loads((ROOT / "manifest.toml").read_text(encoding="utf-8"))
    out = ROOT / "dist" / version
    if out.exists():
        shutil.rmtree(out)
    errors = []
    for v in manifest["vault"]:
        dst = out / v["name"]
        copy(ROOT / v["src"], dst)
        for inc in v.get("include", []):
            copy(ROOT / inc["from"], dst / inc["to"])
        (dst / "_仕組み/記録").mkdir(parents=True, exist_ok=True)
        (dst / "_仕組み/記録" / "版.txt").write_text(version + "\n", encoding="utf-8")
        counts = {"system": 0, "seed": 0}
        for f in sorted(dst.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(dst).as_posix()
            if rel == "_仕組み/記録/版.txt":
                continue
            k = kind(rel, v)
            if k is None:
                errors.append(f"{v['name']}: {rel} が manifest.toml の system にも seed にもありません")
            else:
                counts[k] += 1
        print(f"{v['name']}: 仕組み {counts['system']} / 最初だけ {counts['seed']}")
    shutil.copy2(ROOT / "manifest.toml", out / "manifest.toml")
    # プラグインを入れる道具(本体は tools/plugins.py pack で dist/<版>/プラグイン/ にそろえる)
    for f in ("plugins.py", "プラグインを入れる.bat"):
        shutil.copy2(ROOT / "tools" / f, out / f)
    # 準備の bat の中身と、各 PC に入れる同期プログラム(メンバーが GitHub を使わなくてよいように)
    (out / "準備").mkdir()
    shutil.copy2(ROOT / "tools" / "setup.py", out / "準備" / "setup.py")
    skip = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "sync" / "notesync", out / "同期プログラム" / "notesync", ignore=skip)
    shutil.copytree(ROOT / "sync" / "起動", out / "同期プログラム" / "起動", ignore=skip)
    shutil.copy2(ROOT / "sync" / "config.example.yaml", out / "同期プログラム" / "config.example.yaml")
    # 版ごとの移し替え(要件書 F-46。飛ばした版も古い順に当てる)
    for m in manifest.get("migrate", []):
        src = ROOT / m["script"]
        if not src.is_file():
            errors.append(f"移し替え {m['script']}(版 {m['version']})がありません")
            continue
        (out / "移し替え").mkdir(exist_ok=True)
        shutil.copy2(src, out / "移し替え" / src.name)
    for e in errors:
        print("エラー:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
