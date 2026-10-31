import json
import os
import time

from notesync.now import run_now, take_signals, wait
from notesync.run import run_once

from .test_share import PJ, cloud, write  # noqa: F401


def put(folder, name, vault, age=0):
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{name}.json"
    p.write_text(json.dumps({"vault": str(vault)}), encoding="utf-8")
    t = time.time() - age
    os.utime(p, (t, t))
    return p


def test_takes_only_own_vault(tmp_path, cfg):
    sig = tmp_path / "今すぐ"
    mine = put(sig, "1", cfg.personal)
    other = put(sig, "2", tmp_path / "ほかの人")
    old_other = put(sig, "3", tmp_path / "ほかの人", age=3600)
    results = take_signals(sig, cfg.personal)
    assert results == [sig / "1.done.json"]
    assert not mine.exists()
    assert other.exists()          # ほかの人の watch が拾う
    assert not old_other.exists()  # 動いていない人あての古い合図は消す


def test_sends_just_saved_note(tmp_path, cloud):
    # 保存した直後のノートは、ふだんの同期では待つが、ボタンを押したら待たずに共有へ送る
    yu = cloud["yu"]
    run_once(yu)
    task = yu.personal / f"{PJ}/04_タスク/0RB003001_保圧を変える.md"
    write(task, task.read_text(encoding="utf-8") + "書き足し\n")
    shared_task = cloud["shared"] / f"{PJ}/04_タスク/0RB003001_保圧を変える.md"
    yu.idle_seconds = 10
    run_once(yu)
    assert "書き足し" not in shared_task.read_text(encoding="utf-8")
    sig = tmp_path / "今すぐ"
    put(sig, "1", yu.personal)
    run_now(yu, take_signals(sig, yu.personal), run_once)
    res = json.loads((sig / "1.done.json").read_text(encoding="utf-8"))
    assert res["ok"]
    assert "書き足し" in shared_task.read_text(encoding="utf-8")
    assert yu.idle_seconds == 10  # 設定は変えない


def test_wait_runs_on_signal(tmp_path, cfg):
    sig = tmp_path / "今すぐ"
    put(sig, "1", cfg.personal)
    calls = []
    wait(cfg, 0.1, lambda c: calls.append(c.idle_seconds) or run_once(c), folder=sig, step=0.05)
    assert calls == [0]
    assert (sig / "1.done.json").exists()


def test_error_is_reported(tmp_path, cfg):
    sig = tmp_path / "今すぐ"
    put(sig, "1", cfg.personal)

    def boom(c):
        raise RuntimeError("こわれた")
    run_now(cfg, take_signals(sig, cfg.personal), boom)
    res = json.loads((sig / "1.done.json").read_text(encoding="utf-8"))
    assert not res["ok"] and "こわれた" in res["message"]


def test_other_pc_syncing_is_reported(tmp_path, cfg):
    """同じ個人 vault を別の PC が同期している間は、送れなかったと返す(F-49)。"""
    lock = cfg.lock_path
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pc": "WORK-PC", "time": time.time()}), encoding="utf-8")
    sig = tmp_path / "今すぐ"
    put(sig, "1", cfg.personal)
    run_now(cfg, take_signals(sig, cfg.personal), run_once)
    res = json.loads((sig / "1.done.json").read_text(encoding="utf-8"))
    assert not res["ok"] and "WORK-PC" in res["message"]
