"""tools/migrate_v067.py: 個人 vault の 90_共有/ をなくす(仕様書 v0.67)。"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "migrate_v067.py"


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=True).stdout


def test_migrate(tmp_path):
    v = tmp_path / "個人"
    a = write(v / "90_共有/試しPJ/03_イシュー/0RA001002_ヒケ.md", "---\nauthor: 佐藤\n---\n")
    write(v / "90_共有/_仕組み/attachments/0RA001002/図.png", "png")
    write(v / "90_共有/共通/02_ノード/0RA002002_水.md", "同じ")
    write(v / "共通/02_ノード/0RA002002_水.md", "同じ")
    write(v / "90_共有/共通/02_ノード/0RA003002_鉄.md", "共有の古い方")
    write(v / "共通/02_ノード/0RA003002_鉄.md", "新しい方")
    own = write(v / "03_イシュー/0RA004001_そり.md", "---\nauthor: Yu\n---\n")
    state = write(v / "_仕組み/記録/同期の記録.json", json.dumps({"version": 1, "items": {
        "note:0RA001002": {"p": "90_共有/試しPJ/03_イシュー/0RA001002_ヒケ.md", "s": "試しPJ/03_イシュー/0RA001002_ヒケ.md", "h": "x"},
        "note:0RA004001": {"p": "03_イシュー/0RA004001_そり.md", "s": "試しPJ/03_イシュー/0RA004001_そり.md", "h": "y"},
    }}, ensure_ascii=False))
    out = run(v)
    assert "試し運転" in out and a.exists()
    run(v, "--run", "--backup", tmp_path / "控え")
    assert not (v / "90_共有").exists()
    assert (v / "試しPJ/03_イシュー/0RA001002_ヒケ.md").read_text(encoding="utf-8") == "---\nauthor: 佐藤\n---\n"
    assert (v / "_仕組み/attachments/0RA001002/図.png").exists()
    assert (v / "共通/02_ノード/0RA003002_鉄.md").read_text(encoding="utf-8") == "新しい方"
    assert (v / "99_archive/90_共有の残り/共通/02_ノード/0RA003002_鉄.md").read_text(encoding="utf-8") == "共有の古い方"
    assert own.exists()                                       # 自分のノートは同期プログラムが移す
    items = json.loads(state.read_text(encoding="utf-8"))["items"]
    assert items["note:0RA001002"] == {"p": "試しPJ/03_イシュー/0RA001002_ヒケ.md",
                                       "s": "試しPJ/03_イシュー/0RA001002_ヒケ.md", "h": "x", "m": "down"}
    assert items["note:0RA004001"]["p"] == "03_イシュー/0RA004001_そり.md"
    assert list((tmp_path / "控え").glob("移行前の控え_個人_*.zip"))
    assert "することはありません" in run(v, "--run")             # 何度でも同じ


def test_not_a_vault(tmp_path):
    (tmp_path / "x").mkdir()
    r = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "x")], capture_output=True, text=True,
                       encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 1
