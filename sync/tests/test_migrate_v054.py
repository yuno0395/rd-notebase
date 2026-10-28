"""tools/migrate_v054.py: ソリューションを設計案に改め、01_設計案/ へ移す(仕様書 v0.54)。"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "migrate_v054.py"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True).stdout


def test_migrate(tmp_path):
    v = tmp_path / "共有"
    write(v / "PJ/01_目的/0RA001001_目的.md", "---\nid: 0RA001001\ntype: 目的\n---\n")
    write(v / "PJ/01_目的/0RA002001_A案.md", "---\nid: 0RA002001\ntype: ソリューション   # 候補\nstatus: 候補\n---\n本文 type: ソリューション\n")
    write(v / "PJ/01_目的/0RA003001_古い案.md", '---\nid: 0RA003001\ntype: "設計記録"\n---\n')
    write(v / "00_ソリューション一覧.base", "old")
    write(v / "PJ/0RA004001_PJ.md", "---\ntype: プロジェクト\n---\n![[00_ソリューション一覧.base]]\n")
    write(v / "_仕組み/templates/ソリューション.md", "---\ntype: ソリューション\n---\n")

    out = run(v)
    assert "試し運転" in out and (v / "PJ/01_目的/0RA002001_A案.md").exists()

    run(v, "--run")
    a = (v / "PJ/01_設計案/0RA002001_A案.md").read_text(encoding="utf-8")
    assert a.startswith("---\nid: 0RA002001\ntype: 設計案   # 候補\n") and "本文 type: ソリューション" in a
    assert not (v / "PJ/01_目的/0RA002001_A案.md").exists()
    assert "type: 設計案\n" in (v / "PJ/01_設計案/0RA003001_古い案.md").read_text(encoding="utf-8")
    assert (v / "PJ/01_目的/0RA001001_目的.md").exists()
    assert (v / "00_設計案一覧.base").read_text(encoding="utf-8") == "old"
    assert "00_設計案一覧.base" in (v / "PJ/0RA004001_PJ.md").read_text(encoding="utf-8")
    assert "ソリューション" in (v / "_仕組み/templates/ソリューション.md").read_text(encoding="utf-8")  # 仕組みは配布で入れ替える
    assert list(tmp_path.glob("移行前の控え_共有_*.zip"))
    # 2回目は何もしない
    assert "することはありません" in run(v, "--run")
