"""コミュニティプラグインを配布物に入れる(pack)、vault に入れる(install)。

    python plugins.py pack <版> --from <プラグインが入った設定フォルダ> [--download]
        正本(rd-notebase)で版を出すときに使う。dist/<版>/プラグイン/ に、配る vault の
        community-plugins.json にあるプラグインの本体(main.js・manifest.json・styles.css)と LICENSE を、
        AGPL・GPL のものは同じ版のソース zip を、出典一覧 プラグインの出典.md を置く。ネットを使う。
        --download をつけると、設定フォルダにないもの(--from なしなら全部)を GitHub の最新のリリースから取る。
    python plugins.py install [--vault <vault のフォルダ>] [--config <設定フォルダの名前>] [--source <プラグインのフォルダ>]
        各自の PC で使う(プラグインを入れる.bat から)。配布物のプラグイン本体を、vault の設定フォルダ
        (.obsidian や .obsidian-229999_aa11234567)にコピーして有効にする。
        共有・機密 vault では、_仕組み/設定/.obsidian/ の配る設定(app.json・hotkeys.json・各プラグインの data.json)も上書きする。

ライセンスの決まり(2026-10-26、スレッド「ライセンスと著作権の問題を確かめる」):
  - 本体は rd-notebase に入れない(dist/ と Box の配布物だけ)。main.js は書き換えない。
  - 各プラグインの LICENSE を main.js と同じフォルダに置く(MIT-0 は不要だが、取れれば置く)。
  - AGPL・GPL は同じ版の GitHub の Source code (zip) を同じ版のフォルダに置く。
  - プラグイン名・版・入手元・ライセンスを並べた出典一覧を1枚置く。社外・有償では配らない。

Python 3.11 以上。標準ライブラリだけを使う。
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BODY = ("main.js", "manifest.json", "styles.css")
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "license", "license.md")
REGISTRY = "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json"
# 配る vault の一覧(正本の中)
DIST_LISTS = (
    "vault/個人/.obsidian/community-plugins.json",
    "vault/共有/_仕組み/設定/.obsidian/community-plugins.json",
    "vault/機密/_仕組み/設定/.obsidian/community-plugins.json",
)
PLUGIN_DIR = "プラグイン"
SOURCE_DIR = "ソース"
CREDITS = "プラグインの出典.md"
SHARED_SETTINGS = "_仕組み/設定/.obsidian"


def read_list(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [x for x in data if isinstance(x, str)] if isinstance(data, list) else []


def merge(*lists: list[str]) -> list[str]:
    out: list[str] = []
    for lst in lists:
        for x in lst:
            if x not in out:
                out.append(x)
    return out


def version_of(plugin_dir: Path) -> str:
    try:
        return str(json.loads((plugin_dir / "manifest.json").read_text(encoding="utf-8")).get("version") or "")
    except (OSError, ValueError):
        return ""


def license_kind(text: str) -> str:
    """LICENSE の文面の書き出しから種類を見る。わからなければ「要確認」。
    (GPL-3.0 の本文は後ろの方で AGPL に触れるので、書き出しだけを見る)"""
    t = text.lstrip()[:600].upper()
    if "GNU AFFERO GENERAL PUBLIC LICENSE" in t:
        return "AGPL-3.0"
    if "GNU LESSER GENERAL PUBLIC LICENSE" in t:
        return "LGPL"
    if "GNU GENERAL PUBLIC LICENSE" in t:
        return "GPL-3.0" if "VERSION 3" in t else "GPL"
    if "MIT NO ATTRIBUTION" in t:
        return "MIT-0"
    if "MIT LICENSE" in t or "PERMISSION IS HEREBY GRANTED, FREE OF CHARGE" in t:
        return "MIT"
    if "APACHE LICENSE" in t:
        return "Apache-2.0"
    return "要確認"


def copyleft(kind: str) -> bool:
    return "GPL" in kind or kind == "要確認"


# ---------- pack ----------

def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def download(repo: str, dst: Path, get=fetch) -> bool:
    """GitHub の最新のリリースから本体を取る(入れて試した設定フォルダにないとき)。"""
    for f in BODY:
        try:
            data = get(f"https://github.com/{repo}/releases/latest/download/{f}")
        except Exception:
            if f == "styles.css":
                continue
            return False
        dst.mkdir(parents=True, exist_ok=True)
        (dst / f).write_bytes(data)
    return True


def pack(version: str, installed: Path | None, out: Path, get=fetch, allow_download: bool = False) -> list[str]:
    """installed(プラグインが入った設定フォルダ)から、配る分だけを out/プラグイン/ にそろえる。
    allow_download なら、installed にないものを GitHub の最新のリリースから取る。
    できなかったことを返す(空ならそろった)。"""
    ids = merge(*(read_list(ROOT / p) for p in DIST_LISTS))
    dst_root = out / PLUGIN_DIR
    if dst_root.exists():
        shutil.rmtree(dst_root)
    dst_root.mkdir(parents=True)
    errors: list[str] = []
    try:
        registry = {p["id"]: p for p in json.loads(get(REGISTRY).decode("utf-8"))}
    except Exception as e:  # ネットにつながらないなど
        return [f"プラグインの一覧を取れませんでした({e})。ネットにつながる PC でやり直してください"]
    rows = []
    tmp = out / "_取ってきた本体"
    for pid in ids:
        src = installed / "plugins" / pid if installed else tmp / pid
        if not (src / "main.js").is_file() or not (src / "manifest.json").is_file():
            repo0 = (registry.get(pid) or {}).get("repo", "")
            if allow_download and repo0 and download(repo0, tmp / pid, get):
                src = tmp / pid
            else:
                errors.append(f"{pid}: {src} に本体がありません。Obsidian で入れてからやり直してください")
                continue
        ver = version_of(src)
        manifest = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
        name = manifest.get("name") or pid
        dst = dst_root / pid
        dst.mkdir()
        for f in BODY:
            if (src / f).is_file():
                shutil.copy2(src / f, dst / f)  # 書き換えない
        repo = (registry.get(pid) or {}).get("repo", "")
        if not repo:
            errors.append(f"{pid}: 入手元のリポジトリがわかりません(Obsidian の一覧にない)")
            rows.append((name, ver, pid, "", "要確認"))
            continue
        lic_text = None
        for ref in (ver, f"v{ver}", "HEAD"):
            for fn in LICENSE_NAMES:
                try:
                    lic_text = get(f"https://raw.githubusercontent.com/{repo}/{ref}/{fn}")
                    break
                except Exception:
                    continue
            if lic_text is not None:
                break
        if lic_text is None:
            # ファイル名が上の一覧にないとき(COPYING など)は GitHub にライセンスのファイルを聞く
            try:
                info = json.loads(get(f"https://api.github.com/repos/{repo}/license"))
                lic_text = base64.b64decode(info["content"])
            except Exception:
                pass
        kind = license_kind(lic_text.decode("utf-8", "replace")) if lic_text is not None else "要確認"
        if lic_text is not None:
            (dst / "LICENSE").write_bytes(lic_text)
        elif kind != "MIT-0":
            errors.append(f"{pid}: LICENSE を取れませんでした(https://github.com/{repo})。手で置いてください")
        if copyleft(kind):
            zdir = dst_root / SOURCE_DIR
            zdir.mkdir(exist_ok=True)
            zip_bytes = None
            for ref in (ver, f"v{ver}"):
                try:
                    zip_bytes = get(f"https://github.com/{repo}/archive/refs/tags/{ref}.zip")
                    break
                except Exception:
                    continue
            if zip_bytes is None:
                errors.append(f"{pid}: 版 {ver} のソース zip を取れませんでした(https://github.com/{repo}/releases)。手で置いてください")
            else:
                (zdir / f"{pid}-{ver}.zip").write_bytes(zip_bytes)
        if kind == "要確認":
            errors.append(f"{pid}: ライセンスの種類がわかりません。LICENSE を読んで出典一覧を直してください")
        rows.append((name, ver, pid, f"https://github.com/{repo}", kind))
    lines = [
        "# プラグインの出典",
        "",
        f"配布の版 {version} に入れたコミュニティプラグインです。本体は書き換えていません。",
        "各フォルダに LICENSE があります。AGPL・GPL のものは、同じ版のソースを `ソース/` に置いています。",
        "社内だけで使い、社外や有償では配りません。",
        "",
        "| プラグイン | 版 | フォルダ | 入手元 | ライセンス |",
        "| --- | --- | --- | --- | --- |",
    ] + [f"| {n} | {v} | {p} | {u} | {k} |" for n, v, p, u, k in rows]
    (dst_root / CREDITS).write_text("\n".join(lines) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return errors


# ---------- install ----------

def config_dirs(vault: Path) -> list[str]:
    return sorted(p.name for p in vault.iterdir() if p.is_dir() and (p.name == ".obsidian" or p.name.startswith(".obsidian-")))


def install(vault: Path, config: str, source: Path) -> list[str]:
    """source(配布物の プラグイン/)の本体を vault/config にコピーして有効にする。したことを返す。"""
    target = vault / config
    target.mkdir(exist_ok=True)
    done: list[str] = []
    settings = vault / SHARED_SETTINGS
    shared_like = settings.is_dir() and settings.resolve() != target.resolve()
    if shared_like:
        # 共有・機密 vault: 配る設定を上書きする(一覧はあとで合わせる)
        for f in settings.rglob("*"):
            if not f.is_file() or f.name == "community-plugins.json":
                continue
            rel = f.relative_to(settings)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target / rel)
        done.append("配る設定(app.json・hotkeys.json・プラグインの設定)を入れた")
        wanted = read_list(settings / "community-plugins.json")
    else:
        wanted = read_list(target / "community-plugins.json")
    if not wanted:
        wanted = sorted(p.name for p in source.iterdir() if (p / "main.js").is_file())
    have = read_list(target / "community-plugins.json")
    missing = []
    for pid in wanted:
        src = source / pid
        if not (src / "main.js").is_file():
            missing.append(pid)
            continue
        dst = target / "plugins" / pid
        new, old = version_of(src), version_of(dst)
        if old == new and (dst / "main.js").is_file():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for f in BODY + ("LICENSE",):
            if (src / f).is_file():
                shutil.copy2(src / f, dst / f)
        done.append(f"{pid} を入れた({old or 'なし'} → {new})")
    enabled = merge(have, [p for p in wanted if p not in missing])
    if enabled != have:
        (target / "community-plugins.json").write_text(json.dumps(enabled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done.append(f"有効にするプラグインを {len(enabled)} 個にした")
    for pid in missing:
        done.append(f"注意: {pid} は配布物にないので入れていません")
    return done


def ask(prompt: str) -> str:
    return input(prompt).strip().strip('"')


def choose_config(vault: Path, given: str | None) -> str | None:
    if given:
        return given
    dirs = config_dirs(vault)
    if len(dirs) == 1:
        return dirs[0]
    if dirs:
        print("どの設定フォルダに入れますか。")
        for i, d in enumerate(dirs, 1):
            print(f"  {i}. {d}")
        a = ask("番号: ")
        if a.isdigit() and 1 <= int(a) <= len(dirs):
            return dirs[int(a) - 1]
        return None
    a = ask("設定フォルダの名前(個人 vault なら .obsidian、共有・機密なら .obsidian-<番号>_<PCの記号>): ")
    return a or None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="plugins", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("version")
    p.add_argument("--from", dest="installed", type=Path)
    p.add_argument("--download", action="store_true", help="--from にないものは GitHub の最新のリリースから取る")
    i = sub.add_parser("install")
    i.add_argument("--vault", type=Path)
    i.add_argument("--config")
    i.add_argument("--source", type=Path, default=Path(__file__).resolve().parent / PLUGIN_DIR)
    a = ap.parse_args(argv)
    if a.cmd == "pack":
        out = ROOT / "dist" / a.version
        if not a.installed and not a.download:
            print("--from <設定フォルダ> か --download をつけてください")
            return 2
        errors = pack(a.version, a.installed, out, allow_download=a.download)
        print(f"{out / PLUGIN_DIR} にそろえました")
        for e in errors:
            print("要対応:", e)
        return 1 if errors else 0
    if not (a.source / CREDITS).is_file():
        print(f"配布物のプラグインが見つかりません: {a.source}")
        return 2
    vault = a.vault or Path(ask("vault のフォルダをここにドラッグして Enter: "))
    if not vault.is_dir():
        print(f"フォルダが見つかりません: {vault}")
        return 2
    config = choose_config(vault, a.config)
    if not config or not config.startswith(".obsidian"):
        print("設定フォルダの名前は .obsidian で始めてください")
        return 2
    for line in install(vault, config, a.source):
        print(line)
    print("Obsidian を開き直してください。プラグインが止まっていたら、設定 → コミュニティプラグイン で有効にしてください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
