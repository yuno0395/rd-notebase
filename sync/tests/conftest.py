import os
import shutil
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notesync.config import Config, member_code  # noqa: E402

SAMPLE = Path(__file__).parent / "sample_vault"
OLD = time.time() - 3600  # 1時間前に書いたことにする(書いている途中と見なされないように)


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    root = tmp_path / "Box"
    shutil.copytree(SAMPLE, root)
    for p in root.rglob("*"):
        os.utime(p, (OLD, OLD))
    c = Config(member="Yu", personal=root / "個人", shared=root / "共有",
               secret=[root / "機密"], backup_dir=tmp_path / "backup",
               state_dir=tmp_path / "state")
    c.code = member_code(c)
    return c


def text(p: Path) -> str:
    with p.open(encoding="utf-8", newline="") as f:
        return f.read()
