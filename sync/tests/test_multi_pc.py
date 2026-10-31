"""1人が2台以上の PC で同じ個人 vault を使う(仕様書「複数の PC で使う」)。"""

import json
from pathlib import Path

from notesync.config import Config, load
from notesync.heavy import to_shared
from notesync.lock import STALE_SECONDS, Busy, Lock
from notesync.report import Report
from notesync.boxcopies import tidy_layout_copies
from notesync.safety import Backup

import pytest


def test_lock_blocks_other_pc_until_stale(tmp_path):
    path = tmp_path / "同期中.lock"
    a = Lock(path, me="HOME-PC", now=1000).acquire()
    with pytest.raises(Busy) as e:
        Lock(path, me="WORK-PC", now=1010).acquire()
    assert e.value.pc == "HOME-PC"
    Lock(path, me="HOME-PC", now=1020).acquire()          # 自分の PC の札は取り直せる
    late = Lock(path, me="WORK-PC", now=1020 + STALE_SECONDS + 1).acquire()  # 古い札は止まった PC のもの
    a.release()                                           # 人の札は外さない
    assert path.exists()
    late.release()
    assert not path.exists()


def test_state_lives_in_personal_vault(tmp_path):
    cfg_dir = tmp_path / "appdata"
    cfg_dir.mkdir()
    personal = tmp_path / "個人"
    (personal / "_仕組み").mkdir(parents=True)
    (personal / "_仕組み/個人設定.md").write_text('---\nname: Yu\nnumber: "229999"\n---\n', encoding="utf-8")
    p = cfg_dir / "config.yaml"
    p.write_text(f"member: Yu\npersonal: {personal}\n", encoding="utf-8")
    cfg = load(p)
    assert cfg.state_path == personal / "_仕組み/記録/同期の記録.json"
    assert cfg.old_state_path == cfg_dir / "state_Yu.json"


def test_old_state_is_read_once(tmp_path):
    from notesync.state import State
    old = tmp_path / "old.json"
    old.write_text(json.dumps({"version": 1, "items": {"k": {"h": "1"}}}), encoding="utf-8")
    new = tmp_path / "v" / "同期の記録.json"
    s = State(new, old)
    assert s.get("k") == {"h": "1"}
    s.save()
    assert new.exists()


def test_link_from_other_pc_user_name():
    root = Path("C:/Users/tanaka/Box/開発データ")
    work = "[a.xlsx](file:///C:/Users/satoh/Box/%E9%96%8B%E7%99%BA%E3%83%87%E3%83%BC%E3%82%BF/PJ/0R/a.xlsx)"
    mine = work.replace("satoh", "tanaka")
    assert to_shared(work, root) == "[a.xlsx](開発データ/PJ/0R/a.xlsx)"
    assert to_shared(mine, root) == "[a.xlsx](開発データ/PJ/0R/a.xlsx)"
    other = "[b](file:///D:/data/b.xlsx)"
    assert to_shared(other, root) == other


def test_layout_copies_are_tidied(tmp_path):
    personal = tmp_path / "個人"
    ob = personal / ".obsidian"
    ob.mkdir(parents=True)
    (ob / "workspace.json").write_text("{}", encoding="utf-8")
    (ob / "workspace (Yu's conflicted copy 2026-10-25).json").write_text("{}", encoding="utf-8")
    (ob / "hotkeys (1).json").write_text("{}", encoding="utf-8")
    (ob / "hotkeys.json").write_text("{}", encoding="utf-8")
    r = Report()
    tidy_layout_copies(personal, r, Backup(tmp_path / "backup"), False)
    names = sorted(p.name for p in ob.iterdir())
    assert names == ["hotkeys (1).json", "hotkeys.json", "workspace.json"]
    assert list((tmp_path / "backup").rglob("workspace (*"))
