"""設定(要件書「設定ファイル」)。

個人設定(%APPDATA%\\知見同期\\config.yaml)と、共有の メンバー.csv を読む。
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import ids

MEMBER_CSV = Path("_仕組み/tools") / "同期プログラム" / "メンバー.csv"
MY_SETTINGS = Path("_仕組み") / "個人設定.md"   # 名前と6桁の番号(Yu 2026-10-25)
MY_YAML = Path("_仕組み/記録") / "私.yaml"       # v0.38 までの形。個人設定.md がなければ読む
# 前回同期の記録(F-14)と同期中の札。個人 vault に置き、どの PC からも同じものを使う(複数の PC で使う)
STATE_FILE = Path("_仕組み/記録") / "同期の記録.json"
LOCK_FILE = Path("_仕組み/記録") / "同期中.lock"


class ConfigError(Exception):
    pass


@dataclass
class Config:
    member: str
    personal: Path
    shared: Path | None = None
    shared_data: Path | None = None  # 開発データ(重い添付の置き場所。F-17〜20)
    report_dir: Path | None = None   # 開発ノート_報告(管理者向けの週報。F-29)
    secret: list[Path] = field(default_factory=list)
    dry_run: bool = False
    idle_seconds: int = 10
    backup_dir: Path | None = None
    state_dir: Path | None = None  # 前回同期の記録(F-14)の置き場所。省略時は個人 vault の中
    old_state_dir: Path | None = None  # v0.45 までの置き場所(%APPDATA%\知見同期)。新しい方がなければ読む
    code: str = ""

    @property
    def state_path(self) -> Path:
        if self.state_dir:
            return self.state_dir / f"state_{self.member}.json"
        return self.personal / STATE_FILE

    @property
    def old_state_path(self) -> Path | None:
        return self.old_state_dir / f"state_{self.member}.json" if self.old_state_dir else None

    @property
    def lock_path(self) -> Path:
        return self.personal / LOCK_FILE


def default_config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "知見同期" / "config.yaml"


def load(path: Path) -> Config:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError(f"個人設定を読めません: {path}: {e}") from e
    for key in ("member", "personal"):
        if not data.get(key):
            raise ConfigError(f"個人設定に {key} がありません: {path}")
    cfg = Config(
        member=str(data["member"]),
        personal=Path(data["personal"]),
        shared=Path(data["shared"]) if data.get("shared") else None,
        shared_data=Path(data["shared_data"]) if data.get("shared_data") else None,
        report_dir=Path(data["report"]) if data.get("report") else None,
        secret=[Path(p) for p in (data.get("secret") or [])],
        dry_run=bool(data.get("dry_run", False)),
        idle_seconds=int(data.get("idle_seconds", 10)),
        backup_dir=Path(data["backup_dir"]) if data.get("backup_dir") else path.parent / "backup",
        state_dir=Path(data["state_dir"]) if data.get("state_dir") else None,
        old_state_dir=path.parent,
    )
    cfg.code = member_code(cfg)
    return cfg


def read_members(shared: Path) -> dict[str, str]:
    """メンバー.csv の 名前 → 人の記号。2列目が6桁の番号なら36進数の4文字に、古い3文字の記号はそのまま。"""
    path = shared / MEMBER_CSV
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    out = {}
    for row in rows[1:]:
        if len(row) >= 2 and row[0].strip() and row[1].strip():
            try:
                out[row[0].strip()] = ids.code_of(row[1])
            except ValueError as e:
                raise ConfigError(f"メンバー.csv の {row[0].strip()} の番号: {e}") from e
    return out


def _field(text: str, key: str) -> str:
    """属性欄の1行を文字のまま読む(YAML に読ませると 012345 が数になり先頭の0が消えるため)。"""
    m = re.search(rf"^{key}:[ \t]*[\"']?([^\"'#\r\n]*?)[\"']?[ \t]*(?:#.*)?$", text, re.M)
    return m.group(1).strip() if m else ""


def read_my_code(personal: Path) -> tuple[str, str]:
    """個人 vault の自分の名前と人の記号。個人設定.md の number(6桁)を36進数にする。"""
    path = personal / MY_SETTINGS
    if path.exists():
        text = path.read_text(encoding="utf-8")
        number = _field(text, "number")
        try:
            code = ids.code_from_number(number) if number else ""
        except ValueError as e:
            raise ConfigError(f"個人設定.md の number は6桁の数字にしてください(今は {number!r})") from e
        return _field(text, "name"), code
    path = personal / MY_YAML
    if not path.exists():
        return "", ""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return str(data.get("name") or ""), str(data.get("code") or "").upper()


def member_code(cfg: Config) -> str:
    """人の記号を決める。個人設定.md と メンバー.csv が食い違えば止める(F-44)。"""
    name, mine = read_my_code(cfg.personal)
    members = read_members(cfg.shared) if cfg.shared else {}
    listed = members.get(cfg.member, "")
    if mine and listed and mine != listed:
        raise ConfigError(
            f"人の記号が食い違っています: 個人設定.md は {mine}、メンバー.csv の {cfg.member} は {listed}"
        )
    if name and name != cfg.member:
        raise ConfigError(f"個人設定.md の name({name})が個人設定の member({cfg.member})と違います")
    code = mine or listed
    if not code:
        raise ConfigError("人の記号がありません。個人 vault の _仕組み/個人設定.md に number(6桁の数字)を書いてください")
    dup = [n for n, c in members.items() if c == code and n != cfg.member]
    if dup:
        raise ConfigError(f"人の記号 {code} が {', '.join(dup)} と重なっています")
    return code
