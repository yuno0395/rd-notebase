"""Obsidian の中で動くスクリプト(_仕組み/templates/_scripts/*.js)を、Obsidian のまね(tests/js/)で動かす。

キーを押したときに、ノートが決まった場所にできるか(作業の決まり R-10)、属性欄が YAML として読めて
入れ子がないか(R-03)、type・author・id・aliases が入るか(R-05)を確かめる。
node がない PC では飛ばす(CI の windows には node がある)。
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "vault" / "共有" / "_仕組み" / "templates"
SCENARIOS = Path(__file__).resolve().parent / "js" / "scenarios.js"
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def created(tmp_path_factory):
    if not NODE:
        pytest.skip("node がない")
    out = tmp_path_factory.mktemp("js") / "created.json"
    run = subprocess.run([NODE, str(SCENARIOS), str(TEMPLATES), str(out)],
                         capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def frontmatter(text):
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    return m.group(1) if m else None


def test_scenarios_pass(created):
    assert created, "作ったノートが1つもない"


def test_created_notes_have_valid_frontmatter(created):
    for name, text in created.items():
        assert "<%" not in text and "%>" not in text, f"{name}: テンプレートの命令が残っている"
        raw = frontmatter(text)
        assert raw is not None, f"{name}: 属性欄がない"
        fm = yaml.safe_load(raw)
        assert isinstance(fm, dict), f"{name}: 属性欄が読めない"
        for key, value in fm.items():
            items = value if isinstance(value, list) else [value]
            assert not any(isinstance(v, (dict, list)) for v in items), f"{name}: {key} が入れ子"
        assert fm.get("type"), f"{name}: type がない"
        assert fm.get("author"), f"{name}: author がない"
        if fm["type"] != "メモ":
            assert re.fullmatch(r"[0-9A-Z]{10}", str(fm.get("id"))), f"{name}: id がない"
            assert fm.get("aliases"), f"{name}: aliases がない"
