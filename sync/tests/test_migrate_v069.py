"""tools/migrate_v069.py: status の言い回しを10通りにそろえる(仕様書 v0.69)。"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "migrate_v069.py"


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
    t = write(v / "_仕組み/templates/イシュー.md", "---\nstatus: 未対応\n---\n")
    a = write(v / "PJ/03_イシュー/0RA001001_ヒケ.md", "---\nid: 0RA001001\ntype: イシュー\nstatus: 低減済み   # メモ\n---\nstatus: 解消 は本文\n")
    b = write(v / "PJ/01_目的/0RA002001_電池3年.md", "---\r\ntype: 仮説\r\nstatus: \"外れた\"\r\n---\r\n")
    c = write(v / "PJ/01_設計案/0RA003001_A案.md", "---\ntype: 設計案\nstatus: 変更\n---\n")
    d = write(v / "PJ/0RA004001_PJ.md", "---\ntype: プロジェクト\nstatus: 中断\n---\n")
    e = write(v / "PJ/04_タスク/0RA005001_試作.md", "---\ntype: タスク\nstatus: 進行中\n---\n")
    assert "試し運転" in run(v) and "低減済み" in read(a)
    run(v, "--run")
    assert read(a) == "---\nid: 0RA001001\ntype: イシュー\nstatus: 一部解決   # メモ\n---\nstatus: 解消 は本文\n"
    assert read(b) == "---\r\ntype: 仮説\r\nstatus: \"仮説が誤っていた\"\r\n---\r\n"
    assert "status: 中止" in read(c) and "status: 待ち" in read(d)
    assert read(e) == "---\ntype: タスク\nstatus: 進行中\n---\n"
    assert read(t) == "---\nstatus: 未対応\n---\n"          # _仕組み の中は変えない
    assert list(tmp_path.glob("移行前の控え_個人_*.zip"))
    assert "することはありません" in run(v, "--run")      # 何度走らせても同じ


def test_not_a_vault(tmp_path):
    (tmp_path / "x").mkdir()
    r = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "x")], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 1
