"""tools/migrate_v055.py: イシューの parent を 脅かす に変える(仕様書 v0.55)。"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "migrate_v055.py"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True).stdout


def test_migrate(tmp_path):
    v = tmp_path / "個人"
    a = write(v / "03_イシュー/0RA001001_ヒケ.md",
              '---\nid: 0RA001001\ntype: イシュー\nparent:\n  - "[[0RA009001_A案]]"\n---\nparent: 本文はそのまま\n')
    b = write(v / "04_タスク/0RA002001_試作.md", '---\ntype: タスク\nparent: ["[[0RA001001_ヒケ]]"]\n---\n')
    c = write(v / "03_イシュー/0RA003001_済み.md", '---\ntype: イシュー\n脅かす: ["[[X]]"]\nparent: ["[[Y]]"]\n---\n')
    write(v / "01_目的/0RA004001_電池3年.md", "---\ntype: 仮説\n---\n")
    write(v / "02_ノード/0RA005001_電池.md", "---\ntype: ノード\n---\n")
    d = write(v / "01_設計案/0RA009001_A案.md",
              '---\ntype: 設計案\nparent: ["[[0RA000001_目的]]"]\n'
              'friend: ["[[0RA004001_電池3年|電池3年]]", "[[0RA005001_電池|電池]]"]\n---\n本文\n')
    e = write(v / "01_設計案/0RA009002_B案.md", '---\ntype: ソリューション\nfriend:\n  - "[[電池3年]]"\n---\n')
    assert "試し運転" in run(v) and "parent:\n" in a.read_text(encoding="utf-8")
    run(v, "--run")
    assert a.read_text(encoding="utf-8") == ('---\nid: 0RA001001\ntype: イシュー\n脅かす:\n  - "[[0RA009001_A案]]"\n'
                                             '---\nparent: 本文はそのまま\n')
    assert "parent:" in b.read_text(encoding="utf-8")            # タスクは変えない
    assert "parent:" in c.read_text(encoding="utf-8")            # 脅かす があれば変えない
    assert d.read_text(encoding="utf-8") == ('---\ntype: 設計案\nparent: ["[[0RA000001_目的]]"]\n'
                                             '価値仮説: ["[[0RA004001_電池3年|電池3年]]"]\n'
                                             'friend: ["[[0RA005001_電池|電池]]"]\n---\n本文\n')
    assert e.read_text(encoding="utf-8") == '---\ntype: ソリューション\n価値仮説: ["[[電池3年]]"]\n---\n'
    assert list(tmp_path.glob("移行前の控え_個人_*.zip"))
    assert "することはありません" in run(v, "--run")


def test_backup_folder(tmp_path):
    v = tmp_path / "box" / "個人"
    write(v / "03_イシュー/0RA001001_ヒケ.md", '---\ntype: イシュー\nparent: ["[[A案]]"]\n---\n')
    run(v, "--run", "--backup", tmp_path / "控え")             # 準備の bat の呼び方
    assert list((tmp_path / "控え").glob("移行前の控え_個人_*.zip"))
    assert not list((tmp_path / "box").glob("*.zip"))          # Box の中には作らない
