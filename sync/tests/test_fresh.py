"""F-28: 作ったばかりでテンプレートのままのノートには触らない。"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from notesync.fresh import matches_template
from notesync.run import run_once

from .test_heavy import NOW, box, issue, write  # noqa: F401

TEMPLATES = Path(__file__).resolve().parents[2] / "vault/共有/_仕組み/templates"


def body_of(path: Path) -> str:
    t = path.read_text(encoding="utf-8")
    return t[t.find("\n---", 4) + 4:]


def log(c, nid, seconds_ago, template="イシュー.md"):
    when = datetime.fromtimestamp(NOW - seconds_ago, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    write(c.personal / "_仕組み/記録/作成履歴.csv", f"﻿日時,id,テンプレート\r\n{when},{nid},{template}\r\n")


def in_shared(box, nid):
    return list(box["shared"].rglob(f"{nid}_*.md"))


def setup(box, extra=""):
    yu = box["yu"]
    shutil.copy(TEMPLATES / "イシュー.md", write(box["shared"] / "_仕組み/templates/イシュー.md", ""))
    issue(yu, body=body_of(TEMPLATES / "イシュー.md") + extra)
    log(yu, "0RB001001", 120)
    return yu


def test_fresh_template_note_is_not_shared(box):
    yu = setup(box)
    rep = run_once(yu, now=NOW)
    assert not in_shared(box, "0RB001001")
    assert any("テンプレートのまま" in r for r in rep.records)
    # 10分たてば集める
    run_once(yu, now=NOW + 11 * 60)
    assert in_shared(box, "0RB001001")


def test_edited_note_is_shared_right_away(box):
    yu = setup(box, extra="\n型の温度を上げたら直った\n")
    run_once(yu, now=NOW)
    assert in_shared(box, "0RB001001")


def test_matches_template_ignores_templater_tags():
    tpl = "---\nid: <% x %>\n---\n# <% tp.file.title %>\n## やること\n\n## 完了の条件\n"
    assert matches_template("---\nid: 1\n---\n# ヒケ\n## やること\n## 完了の条件\n", tpl)
    assert not matches_template("---\nid: 1\n---\n# ヒケ\n## やること\n書いた\n## 完了の条件\n", tpl)
