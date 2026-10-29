"""F-55 設定の場所の確かめ と F-56 外へ送る機能の見張り。"""

import json
from pathlib import Path

from notesync.guard import check_places
from notesync.report import Report
from notesync.run import run_once
from notesync.outward import check_outward


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_sample_places_are_fine(cfg):
    assert check_places(cfg) == []


def test_secret_pointing_at_wrong_folder_stops_without_renaming(cfg, tmp_path):
    """secret に機密フォルダでない広い場所を書いても、その下の .md を改名しない。"""
    wrong = tmp_path / "Box_others"
    other = write(wrong / "他の部署/議事録.md", "# 他の人のノート\n")
    cfg.secret = [wrong]
    report = run_once(cfg, dry_run=False)
    assert report.stopped and "vault の印" in report.stopped
    assert other.exists() and other.read_text(encoding="utf-8") == "# 他の人のノート\n"
    assert not (wrong / "_仕組み").exists()  # 印も作らない
    assert "設定の場所がおかしい" in (cfg.personal / "_仕組み/同期レポート.md").read_text(encoding="utf-8")


def test_shared_pointing_at_wrong_folder_stops_without_copying(cfg, tmp_path):
    wrong = tmp_path / "外部と共有しているフォルダ"
    wrong.mkdir()
    cfg.shared = wrong
    report = run_once(cfg, dry_run=False)
    assert report.stopped
    assert list(wrong.iterdir()) == []


def test_overlapping_places_stop(cfg):
    cfg.secret = [cfg.personal / "02_ノード"]
    (cfg.personal / "02_ノード" / "_仕組み").mkdir()
    problems = check_places(cfg)
    assert any("重なっています" in p for p in problems)


def test_data_folder_containing_a_vault_stops(cfg):
    cfg.shared_data = cfg.shared.parent
    assert any("開発データ" in p for p in check_places(cfg))


def test_drive_root_is_refused(cfg):
    cfg.secret = [Path(cfg.personal.anchor)]
    assert any("一番上" in p for p in check_places(cfg))


def _conf(root: Path, plugins: list[str], core=None) -> Path:
    c = root / ".obsidian"
    write(c / "community-plugins.json", json.dumps(plugins))
    if core is not None:
        write(c / "core-plugins.json", json.dumps(core))
    return c


def test_publish_sync_git_and_api_keys_are_reported(cfg):
    c = _conf(cfg.personal, ["quickadd", "obsidian-git"], {"publish": True, "sync": False, "bases": True})
    write(c / "plugins/quickadd/data.json", json.dumps({"ai": {"providers": [{"name": "OpenAI", "apiKey": "sk-xxx"}]}}))
    report = Report()
    check_outward(cfg, report)
    text = "\n".join(report.todos)
    assert "Publish" in text and "Sync(" not in text
    assert "Obsidian Git" in text
    assert "quickadd に外のサービスの鍵" in text


def test_old_core_plugins_list_is_read(cfg):
    _conf(cfg.personal, [], ["file-explorer", "sync"])
    report = Report()
    check_outward(cfg, report)
    assert any("Sync(" in t for t in report.todos)


def test_empty_api_key_is_fine(cfg):
    c = _conf(cfg.personal, ["quickadd"])
    write(c / "plugins/quickadd/data.json", json.dumps({"ai": {"OpenAIApiKey": ""}}))
    report = Report()
    check_outward(cfg, report)
    assert report.todos == []


def test_extra_plugin_in_shared_is_todo_and_in_personal_is_warning(cfg):
    write(cfg.shared / "_仕組み/設定/.obsidian/community-plugins.json", json.dumps(["templater-obsidian"]))
    write(cfg.personal / "_仕組み/個人設定.md", "---\nname: Yu\nnumber: 999999\n---\n")
    mine = cfg.shared / ".obsidian-999999_pc1"
    write(mine / "community-plugins.json", json.dumps(["templater-obsidian", "some-sync-plugin"]))
    write(cfg.shared / ".obsidian-123456_pc9" / "community-plugins.json", json.dumps(["others-plugin"]))
    write(cfg.shared / "_仕組み/tools/準備/最新の版.txt", "0.3.0\n")
    write(cfg.shared / "_仕組み/tools/配布/0.3.0/個人/.obsidian/community-plugins.json", json.dumps(["templater-obsidian"]))
    _conf(cfg.personal, ["templater-obsidian", "trying-this"])
    report = Report()
    check_outward(cfg, report)
    assert any("some-sync-plugin" in t and ".obsidian-999999_pc1" in t for t in report.todos)
    assert not any("others-plugin" in t for t in report.todos)  # 他の人の設定は見ない
    assert any("trying-this" in w for w in report.warnings)
    assert not any("trying-this" in t for t in report.todos)
