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
    code: str = ""
    number: str = ""  # 個人設定.md の6桁の番号(author に「番号_名前」と書くため。v0.68)
    config_path: Path | None = None  # 読んだ config.yaml。vault の場所が変わったときに書き直す(F-50)
    moved: list[str] = field(default_factory=list)       # load のときに直した場所(次の同期レポートに書く)
    move_warnings: list[str] = field(default_factory=list)

    @property
    def state_path(self) -> Path:
        if self.state_dir:
            return self.state_dir / f"state_{self.member}.json"
        return self.personal / STATE_FILE

    @property
    def me(self) -> str:
        """ノートに自分を書くときの形(author・reviewed_by など)。例 229999_Yu。番号がなければ名前だけ。"""
        from .vault import me_value
        return me_value(self.member, self.number)

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
        config_path=path,
    )
    # F-50: vault の名前や場所が変わっていたら、新しい場所を見つけて設定を直す(人の記号を読む前に)
    from .relocate import follow
    cfg.moved, cfg.move_warnings = follow(cfg, dry=cfg.dry_run)
    cfg.code = member_code(cfg)
    cfg.number = member_number(cfg)
    return cfg


def read_member_numbers(shared: Path) -> dict[str, str]:
    """メンバー.csv の 名前 → 2列目そのまま(6桁の番号か、古い3文字の記号)。"""
    path = shared / MEMBER_CSV
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return {row[0].strip(): row[1].strip() for row in rows[1:]
            if len(row) >= 2 and row[0].strip() and row[1].strip()}


def read_members(shared: Path) -> dict[str, str]:
    """メンバー.csv の 名前 → 人の記号。2列目が6桁の番号なら36進数の4文字に、古い3文字の記号はそのまま。"""
    out = {}
    for name, raw in read_member_numbers(shared).items():
        try:
            out[name] = ids.code_of(raw)
        except ValueError as e:
            raise ConfigError(f"メンバー.csv の {name} の番号: {e}") from e
    return out


def _field(text: str, key: str) -> str:
    """属性欄の1行を文字のまま読む(YAML に読ませると 012345 が数になり先頭の0が消えるため)。"""
    m = re.search(rf"^{key}:[ \t]*[\"']?([^\"'#\r\n]*?)[\"']?[ \t]*(?:#.*)?$", text, re.M)
    return m.group(1).strip() if m else ""


def read_my_number(personal: Path) -> str:
    path = personal / MY_SETTINGS
    return _field(path.read_text(encoding="utf-8"), "number") if path.exists() else ""


def member_number(cfg: Config) -> str:
    """author に書く6桁の番号。個人設定.md の number、なければ メンバー.csv の6桁の番号。
    古い3文字の記号しかない人は空(author は名前だけで書く)。"""
    n = read_my_number(cfg.personal)
    if not n and cfg.shared:
        n = read_member_numbers(cfg.shared).get(cfg.member, "")
    return n if re.fullmatch(r"\d{6}", n or "") else ""


def read_my_code(personal: Path) -> tuple[str, str]:
    """個人 vault の自分の名前と人の記号。個人設定.md の number(6桁)を36進数にする。"""
    path = personal / MY_SETTINGS
    if not path.exists():
        return "", ""
    text = path.read_text(encoding="utf-8")
    number = _field(text, "number")
    try:
        code = ids.code_from_number(number) if number else ""
    except ValueError as e:
        raise ConfigError(f"個人設定.md の number は6桁の数字にしてください(今は {number!r})") from e
    return _field(text, "name"), code


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
