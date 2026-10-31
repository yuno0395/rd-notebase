import re

import pytest

from notesync import config
from notesync.run import run_once

from .conftest import text


def stems(folder):
    return sorted(p.stem for p in folder.glob("*.md"))


def find(folder, name):
    [p] = [p for p in folder.glob(f"*_{name}.md")]
    return p


def test_assigns_ids_and_fixes_links(cfg):
    run_once(cfg)
    nodes = cfg.personal / "02_ノード"
    water = find(nodes, "水")
    assert re.fullmatch(r"[0-9A-Z]{6}0001_水", water.stem)
    assert text(water).startswith(f"---\nid: {water.stem[:10]}\nauthor: Yu\n---\n")

    # 属性欄のほかの行とコメントは残す
    ice = find(nodes, "氷")
    assert "type: ノード   # 物のノード\naliases: [氷, こおり]" in text(ice)
    # 属性欄の中の [[水]] も直す
    assert f'parts: ["[[{water.stem}|水]]"]' in text(ice)

    daily = text(cfg.personal / "00_日誌/デイリー" / "2026-10-24.md")
    assert f"[[{water.stem}|水]]" in daily
    assert f"[[{ice.stem}|氷の別名]]" in daily      # 別名で引いて、表示はそのまま
    assert "[[2026-10-23]]" in daily                 # 日付のリンクはそのまま
    assert "[[鉄]]" in daily                          # 行き先が2つあるので直さない
    assert "[[まだないノード]]" in daily

    issue = text(cfg.personal / "03_イシュー" / "0RBDMG001_ヒケ.md")
    assert f"[[{water.stem}|水]]" in issue


def test_uses_id_already_in_frontmatter(cfg):
    run_once(cfg)
    assert stems(cfg.personal / "04_タスク") == ["0RDGPG001_保圧を変えて試作する"]
    t = text(cfg.personal / "04_タスク" / "0RDGPG001_保圧を変えて試作する.md")
    assert t.count("id: 0RDGPG001") == 1 and "author: Yu" in t


def test_keeps_crlf(cfg):
    run_once(cfg)
    iron = find(cfg.personal / "02_ノード", "鉄")
    assert "\r\n" in text(iron) and "\n" not in text(iron).replace("\r\n", "")


def test_does_not_touch_shared_copies_and_secret_links(cfg):
    before = text(cfg.personal / "90_共有" / "0RAYFN003_配られた.md")
    run_once(cfg)
    assert text(cfg.personal / "90_共有" / "0RAYFN003_配られた.md") == before
    fact = find(cfg.secret[0] / "06_事実", "顧客仕様")
    assert "[[水]]" in text(fact)  # 機密の中から外のノートへはつながない
    assert "author: Yu" in text(fact)


def test_report(cfg):
    r = run_once(cfg)
    rep = text(cfg.personal / "_仕組み/同期レポート.md")
    # 共有の「鉄」と名前が重なるので、まとめるかを聞く(F-04 の「同じ名前」の代わり、F-47)
    assert "## 対応が必要" in rep and "同じもの: [[" in rep and "|鉄]] を [[0RAYFN002_鉄|鉄]]" in rep
    assert any("行き先が 2 つ" in t for t in r.todos)
    assert "id をつけた 02_ノード/水.md" in rep
    # 2回目は記録が積み重なり、やることがなければ id はつけない
    r2 = run_once(cfg)
    assert not any("id をつけた" in x for x in r2.records)
    assert text(cfg.personal / "_仕組み/同期レポート.md").count("id をつけた 02_ノード/水.md") == 1


def test_dry_run_writes_only_report(cfg):
    before = {p: text(p) for p in cfg.personal.rglob("*.md")}
    r = run_once(cfg, dry_run=True)
    after = {p: text(p) for p in cfg.personal.rglob("*.md") if p.name != "同期レポート.md"}
    assert after == before
    rep = text(cfg.personal / "_仕組み/同期レポート.md")
    assert "試し運転" in rep and "予定: 個人: id をつけた 02_ノード/水.md" in rep
    assert any("リンクを id つきに直した 00_日誌/デイリー/2026-10-24.md" in x for x in r.records)


def test_backup_before_change(cfg):
    run_once(cfg)
    saved = list(cfg.backup_dir.rglob("水.md"))
    assert saved and text(saved[0]) == "0℃以下で [[氷]] になる。\n"


def test_skips_note_being_written(cfg):
    import time
    p = cfg.personal / "02_ノード" / "水.md"
    now = time.time()
    import os
    os.utime(p, (now, now))
    r = run_once(cfg, now=now)
    assert p.exists()
    assert any("書いている途中" in x for x in r.records)


def test_member_code_mismatch_stops(cfg):
    (cfg.personal / "_仕組み/個人設定.md").write_text('---\nname: Yu\nnumber: "229999"\n---\n', encoding="utf-8")
    with pytest.raises(config.ConfigError, match="食い違って"):
        config.member_code(cfg)


def test_report_is_not_rewritten_on_second_run(cfg):
    run_once(cfg)
    r2 = run_once(cfg)
    assert not any("00_同期レポート" in t for t in r2.todos + r2.records)


def test_member_code_from_personal_settings(cfg):
    # 個人設定.md の6桁の番号を36進数にする。先頭の0も残す
    (cfg.personal / "_仕組み/個人設定.md").write_text(
        '---\nname: "Yu"   # 名前\nnumber: "000001"   # 6桁\n---\n# 個人設定\n', encoding="utf-8")
    members = cfg.shared / config.MEMBER_CSV
    members.write_text("名前,番号,使い始めた日\nYu,000001,2026-10-25\n佐藤,229999,2026-10-25\n", encoding="utf-8")
    assert config.member_code(cfg) == "0001"
    assert config.read_members(cfg.shared)["佐藤"] == "4XGV"
    (cfg.personal / "_仕組み/個人設定.md").write_text("---\nnumber: 12345\n---\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="6桁"):
        config.member_code(cfg)
