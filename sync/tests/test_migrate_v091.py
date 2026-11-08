"""tools/migrate_v091.py: 00_日誌 → 00_PIP、週報は 00_週報、visibility を新しい書き方に(仕様書 v0.91)。"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "migrate_v091.py"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body.encode("utf-8"))
    return path


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True).stdout


def test_migrate(tmp_path):
    v = tmp_path / "個人"
    write(v / "_仕組み/個人設定.md", "---\nname: 山田\nnumber: 229999\n---\n")
    tpl = write(v / "_仕組み/templates/メモ.md", "---\nvisibility: 個人\n---\n")
    daily = write(v / "00_日誌/デイリー/2026-11-08.md", "# 今日\n")
    memo = write(v / "00_日誌/メモ/0RA001001_考え.md", "---\nid: 0RA001001\ntype: メモ\nauthor: [229999_山田]\nvisibility: 個人\n---\n")
    week = write(v / "00_日誌/週報/2026-W45.md", "---\ntype: 週報\nauthor: [229999_山田]\n---\n今週\n")
    team = write(v / "試しPJ/03_イシュー/0RA002001_ヒケ.md",
                 "---\nid: 0RA002001\ntype: イシュー\nauthor: [229999_山田]\nvisibility: チーム   # 共有する範囲\n---\n")
    none = write(v / "試しPJ/04_タスク/0RA003001_試す.md", "---\r\nid: 0RA003001\r\ntype: タスク\r\nauthor: [229999_山田]\r\n---\r\n")
    inner = write(v / "共通/02_ノード/0RA004001_水.md", "---\nid: 0RA004001\ntype: ノード\nauthor: [229999_山田]\nvisibility: 社内\n---\n")
    node = write(v / "共通/02_ノード/0RA005001_鉄.md", "---\nid: 0RA005001\ntype: ノード\nauthor: [229999_山田]\n---\n")
    private = write(v / "試しPJ/03_イシュー/0RA006001_見込み.md",
                    "---\nid: 0RA006001\ntype: イシュー\nauthor: [229999_山田]\nvisibility: 個人\n---\n売上\n")
    theirs = write(v / "試しPJ/03_イシュー/0RA007002_割れ.md", "---\nid: 0RA007002\ntype: イシュー\nauthor: [100000_田中]\n---\n")
    newer = write(v / "試しPJ/03_イシュー/0RA008001_新.md",
                  "---\nid: 0RA008001\ntype: イシュー\nauthor: [229999_山田]\nvisibility: [試しPJ, EXT_A]\n---\n")
    ledger = write(v / "試しPJ/0RA009001_試しPJ.md", "---\nid: 0RA009001\ntype: プロジェクト\nauthor: [229999_山田]\n---\n")

    out = run(v)
    assert "試し運転" in out and daily.exists()
    run(v, "--run")
    run(v, "--run")   # 何度でも同じ
    assert not (v / "00_日誌").exists()
    assert read(v / "00_PIP/デイリー/2026-11-08.md") == "# 今日\n"
    assert "visibility: [PIP]" in read(v / "00_PIP/メモ/0RA001001_考え.md")
    w = read(v / "00_週報/2026-W45.md")
    assert "visibility: [Internal use only]" in w and w.endswith("今週\n")
    assert "visibility: [試しPJ]   # 共有する範囲" in read(team)
    assert read(none) == "---\r\nid: 0RA003001\r\ntype: タスク\r\nauthor: [229999_山田]\r\nvisibility: [試しPJ]\r\n---\r\n"
    assert "visibility: [Internal use only]" in read(inner) and "visibility: [Internal use only]" in read(node)
    assert not private.exists()
    assert read(v / "00_PIP/メモ/0RA006001_見込み.md").endswith("visibility: [PIP]\n---\n売上\n")
    assert "visibility" not in read(theirs)                # 他の人のノートは変えない
    assert "visibility: [試しPJ, EXT_A]" in read(newer)
    assert "visibility" not in read(ledger)
    assert read(tpl) == "---\nvisibility: 個人\n---\n"   # _仕組み の中は変えない
    assert not memo.exists() and not week.exists()
