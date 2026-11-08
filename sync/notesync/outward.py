"""外へ送る機能の見張り(F-56)。

Obsidian の設定を読み、ノートを社外へ送れる機能がオンになっていたら同期レポートで知らせる。止めはしない。
- Obsidian の Publish(ネットに公開)と Sync(Obsidian 社のサーバーに同期)
- Obsidian Git(リポジトリへ送る)
- プラグインの設定に入った AI などの外のサービスの鍵(ノートがそのサービスへ送られる)
- 共有・機密で、配っていないプラグイン(共有・機密は配ったものだけの決まり)
- 個人で、配っていないプラグイン(試すのはよいが、外へ送る機能がないかを確かめてもらう)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SEND_CORE = {"publish": "Publish(ノートをネットに公開する)", "sync": "Sync(Obsidian 社のサーバーに同期する)"}
SEND_PLUGINS = {"obsidian-git": "Obsidian Git(リポジトリへ送る)"}
KEY_NAME = re.compile(r"(api[_-]?key|api[_-]?token|secret[_-]?key|access[_-]?token|openai.*(key|token))", re.I)
DIST_SETTINGS = Path("_仕組み/設定/.obsidian")
DIST_DIR = Path("_仕組み/tools/配布")
LATEST = Path("_仕組み/tools/準備/最新の版.txt")
MY_SETTINGS = Path("_仕組み/個人設定.md")


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def enabled_core(conf: Path) -> set[str]:
    """core-plugins.json でオンのもの。古い形(並び)と新しい形({名前: true/false})の両方を読む。"""
    data = _json(conf / "core-plugins.json")
    if isinstance(data, dict):
        return {k for k, v in data.items() if v is True}
    if isinstance(data, list):
        return {x for x in data if isinstance(x, str)}
    return set()


def enabled_plugins(conf: Path) -> list[str]:
    data = _json(conf / "community-plugins.json")
    return [x for x in data if isinstance(x, str)] if isinstance(data, list) else []


def _has_key(data) -> bool:
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, str) and v.strip() and KEY_NAME.search(str(k)):
                return True
            if _has_key(v):
                return True
    elif isinstance(data, list):
        return any(_has_key(x) for x in data)
    return False


def plugins_with_keys(conf: Path, ids: list[str]) -> list[str]:
    return [pid for pid in ids if _has_key(_json(conf / "plugins" / pid / "data.json"))]


def _my_number(personal: Path) -> str:
    try:
        text = (personal / MY_SETTINGS).read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"^number:[ \t]*[\"']?(\d{6})", text, re.M)
    return m.group(1) if m else ""


def _config_dirs(root: Path, number: str) -> list[Path]:
    """共有・機密の、自分の設定フォルダ(.obsidian-<番号>_<PC> と .obsidian)。"""
    out = []
    for d in sorted(root.glob(".obsidian*")):
        if not d.is_dir():
            continue
        if d.name == ".obsidian" or not number or d.name.startswith(f".obsidian-{number}"):
            out.append(d)
    return out


def _personal_dist(shared: Path | None) -> list[str] | None:
    """いまの版で個人 vault に配ったプラグイン。わからなければ None。"""
    if not shared:
        return None
    try:
        ver = (shared / LATEST).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    data = _json(shared / DIST_DIR / ver / "個人" / ".obsidian" / "community-plugins.json")
    return [x for x in data if isinstance(x, str)] if isinstance(data, list) else None


def check_outward(cfg, report) -> None:
    number = _my_number(cfg.personal)
    places: list[tuple[str, Path, Path, list[str] | None]] = []
    places.append(("個人 vault", cfg.personal, cfg.personal / ".obsidian", _personal_dist(cfg.shared)))
    for label, root in ([("共有 vault", cfg.shared)] if cfg.shared and cfg.shared.exists() else []) + \
            [(f"機密フォルダ {i}", p) for i, p in enumerate(cfg.secret, 1) if p.exists()]:
        dist = _json(root / DIST_SETTINGS / "community-plugins.json")
        allowed = [x for x in dist if isinstance(x, str)] if isinstance(dist, list) else None
        for conf in _config_dirs(root, number):
            places.append((label, root, conf, allowed))

    for label, root, conf, allowed in places:
        if not conf.is_dir():
            continue
        where = f"{label} の {conf.name}"
        for core in sorted(enabled_core(conf) & SEND_CORE.keys()):
            report.todo(f"{where} で Obsidian の {SEND_CORE[core]} がオンです。社外へノートが出るので、"
                        "設定 → コアプラグインでオフにしてください")
        ids = enabled_plugins(conf)
        for pid in ids:
            if pid in SEND_PLUGINS:
                report.todo(f"{where} で {SEND_PLUGINS[pid]} がオンです。送り先が社外だとノートが出るので、"
                            "使うのをやめるか管理者に確かめてください")
        for pid in plugins_with_keys(conf, ids):
            report.todo(f"{where} のプラグイン {pid} に外のサービスの鍵(API キー)が入っています。"
                        "使うとノートがそのサービスへ送られるので、鍵を消すか管理者に確かめてください")
        if allowed is None:
            continue
        extra = [p for p in ids if p not in allowed and p not in SEND_PLUGINS]
        if not extra:
            continue
        if label == "個人 vault":
            report.warn(f"個人 vault で配っていないプラグインを使っています: {'、'.join(extra)}。"
                        "ノートをネットへ送る機能がないかを確かめてください(良ければ金曜の定例へ)")
        else:
            report.todo(f"{where} で配っていないプラグインがオンです: {'、'.join(extra)}。"
                        "共有・機密は配ったプラグインだけにしてください")
