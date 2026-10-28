"""tools/plugins.py: プラグインを配布物にそろえる(pack)、vault に入れる(install)。"""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("plugins", Path(__file__).resolve().parents[2] / "tools" / "plugins.py")
plugins = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugins)

MIT = b"MIT License\n\nPermission is hereby granted, free of charge, ..."
AGPL = b"GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007"


def put_plugin(root: Path, pid: str, ver: str, extra: str = "") -> Path:
    d = root / pid
    d.mkdir(parents=True, exist_ok=True)
    (d / "main.js").write_text(f"// {pid} {ver}{extra}", encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"id": pid, "name": pid.upper(), "version": ver}), encoding="utf-8")
    return d


def source(tmp_path: Path, plist: dict[str, str]) -> Path:
    s = tmp_path / "配布" / "プラグイン"
    for pid, ver in plist.items():
        put_plugin(s, pid, ver)
        (s / pid / "LICENSE").write_bytes(MIT)
    (s / plugins.CREDITS).write_text("# 出典\n", encoding="utf-8")
    return s


def test_license_kind():
    assert plugins.license_kind(MIT.decode()) == "MIT"
    assert plugins.license_kind(AGPL.decode()) == "AGPL-3.0"
    assert plugins.license_kind("GNU GENERAL PUBLIC LICENSE\nVersion 3") == "GPL-3.0"
    assert plugins.license_kind("MIT No Attribution") == "MIT-0"
    assert plugins.license_kind("何か") == "要確認"
    # GPL-3.0 の本文は後ろの方で「GNU Affero General Public License」に触れる
    gpl = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n" + "x" * 2000 + "13. Use with the GNU Affero General Public License."
    assert plugins.license_kind(gpl) == "GPL-3.0"


def test_install_shared_vault_copies_bodies_and_settings(tmp_path):
    src = source(tmp_path, {"quickadd": "1.0.0", "templater-obsidian": "2.0.0", "k-plex": "0.5.0"})
    vault = tmp_path / "共有"
    st = vault / plugins.SHARED_SETTINGS
    (st / "plugins/quickadd").mkdir(parents=True)
    (st / "plugins/quickadd/data.json").write_text('{"x": 1}', encoding="utf-8")
    (st / "hotkeys.json").write_text("{}", encoding="utf-8")
    (st / "community-plugins.json").write_text('["quickadd", "templater-obsidian", "omnisearch"]', encoding="utf-8")
    cfg = ".obsidian-229999_aa11234567"
    (vault / cfg).mkdir()
    (vault / cfg / "community-plugins.json").write_text('["my-own"]', encoding="utf-8")

    done = plugins.install(vault, cfg, src)
    t = vault / cfg
    assert (t / "plugins/quickadd/main.js").read_text(encoding="utf-8") == "// quickadd 1.0.0"
    assert (t / "plugins/quickadd/LICENSE").is_file()
    assert (t / "plugins/quickadd/data.json").read_text(encoding="utf-8") == '{"x": 1}'  # 配る設定
    assert (t / "hotkeys.json").is_file()
    assert not (t / "plugins/k-plex").exists()  # この vault の一覧にないものは入れない
    # 自分で足した my-own は残し、配布物にない omnisearch は有効にしない
    assert json.loads((t / "community-plugins.json").read_text(encoding="utf-8")) == ["my-own", "quickadd", "templater-obsidian"]
    assert any("omnisearch は配布物にない" in d for d in done)


def test_install_personal_vault_uses_its_own_list_and_skips_same_version(tmp_path):
    src = source(tmp_path, {"quickadd": "1.1.0", "periodic-notes": "0.9.0"})
    vault = tmp_path / "個人"
    ob = vault / ".obsidian"
    ob.mkdir(parents=True)
    (ob / "community-plugins.json").write_text('["quickadd", "periodic-notes"]', encoding="utf-8")
    put_plugin(ob / "plugins", "periodic-notes", "0.9.0", extra=" 手元")
    (ob / "plugins/periodic-notes/data.json").write_text('{"mine": true}', encoding="utf-8")
    put_plugin(ob / "plugins", "quickadd", "1.0.0")

    done = plugins.install(vault, ".obsidian", src)
    assert (ob / "plugins/quickadd/main.js").read_text(encoding="utf-8") == "// quickadd 1.1.0"  # 版が違えば入れ替える
    assert "手元" in (ob / "plugins/periodic-notes/main.js").read_text(encoding="utf-8")  # 同じ版は触らない
    assert (ob / "plugins/periodic-notes/data.json").read_text(encoding="utf-8") == '{"mine": true}'
    assert done == ["quickadd を入れた(1.0.0 → 1.1.0)"]


def test_config_dirs(tmp_path):
    for d in (".obsidian", ".obsidian-229999_pc1", ".trash", "02_ノード"):
        (tmp_path / d).mkdir()
    assert plugins.config_dirs(tmp_path) == [".obsidian", ".obsidian-229999_pc1"]


def test_pack(tmp_path, monkeypatch):
    lists = tmp_path / "root"
    for rel, ids in [(plugins.DIST_LISTS[0], ["quickadd", "templater-obsidian"]), (plugins.DIST_LISTS[1], ["quickadd", "nowhere"])]:
        (lists / rel).parent.mkdir(parents=True, exist_ok=True)
        (lists / rel).write_text(json.dumps(ids), encoding="utf-8")
    monkeypatch.setattr(plugins, "ROOT", lists)
    installed = tmp_path / ".obsidian"
    put_plugin(installed / "plugins", "quickadd", "1.0.0")
    put_plugin(installed / "plugins", "templater-obsidian", "2.1.0")
    (installed / "plugins/quickadd/data.json").write_text("{}", encoding="utf-8")
    pages = {
        plugins.REGISTRY: json.dumps([{"id": "quickadd", "repo": "a/quickadd"}, {"id": "templater-obsidian", "repo": "b/Templater"}]).encode(),
        "https://raw.githubusercontent.com/a/quickadd/1.0.0/LICENSE": MIT,
        "https://raw.githubusercontent.com/b/Templater/2.1.0/LICENSE": AGPL,
        "https://github.com/b/Templater/archive/refs/tags/2.1.0.zip": b"PK zip",
    }

    def get(url):
        if url in pages:
            return pages[url]
        raise OSError("404")

    out = tmp_path / "dist"
    errors = plugins.pack("0.2.0", installed, out, get=get)
    p = out / plugins.PLUGIN_DIR
    assert (p / "quickadd/main.js").is_file() and (p / "quickadd/LICENSE").read_bytes() == MIT
    assert not (p / "quickadd/data.json").exists()  # 本体だけ。設定は配布物の別のところ
    assert (p / "ソース/templater-obsidian-2.1.0.zip").read_bytes() == b"PK zip"
    assert not (p / "ソース/quickadd-1.0.0.zip").exists()  # MIT はソース不要
    credits = (p / plugins.CREDITS).read_text(encoding="utf-8")
    assert "| TEMPLATER-OBSIDIAN | 2.1.0 | templater-obsidian | https://github.com/b/Templater | AGPL-3.0 |" in credits
    assert errors == ["nowhere: " + str(installed / "plugins" / "nowhere") + " に本体がありません。Obsidian で入れてからやり直してください"]


def test_pack_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(plugins, "ROOT", tmp_path)

    def get(url):
        raise OSError("offline")

    errors = plugins.pack("0.2.0", tmp_path, tmp_path / "dist", get=get)
    assert errors and "ネット" in errors[0]


def test_pack_license_from_api(tmp_path, monkeypatch):
    """LICENSE のファイル名が一覧にないときは、GitHub のライセンス API から取る。"""
    import base64
    lists = tmp_path / "root"
    (lists / plugins.DIST_LISTS[0]).parent.mkdir(parents=True, exist_ok=True)
    (lists / plugins.DIST_LISTS[0]).write_text(json.dumps(["templater-obsidian"]), encoding="utf-8")
    monkeypatch.setattr(plugins, "ROOT", lists)
    installed = tmp_path / ".obsidian"
    put_plugin(installed / "plugins", "templater-obsidian", "2.1.0")
    pages = {
        plugins.REGISTRY: json.dumps([{"id": "templater-obsidian", "repo": "b/Templater"}]).encode(),
        "https://api.github.com/repos/b/Templater/license": json.dumps({"content": base64.b64encode(AGPL).decode()}).encode(),
        "https://github.com/b/Templater/archive/refs/tags/2.1.0.zip": b"PK zip",
    }

    def get(url):
        if url in pages:
            return pages[url]
        raise OSError("404")

    errors = plugins.pack("0.2.0", installed, tmp_path / "dist", get=get)
    p = tmp_path / "dist" / plugins.PLUGIN_DIR
    assert (p / "templater-obsidian/LICENSE").read_bytes() == AGPL
    assert errors == []
