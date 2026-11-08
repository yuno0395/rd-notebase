"""Ctrl+N(QuickAdd の「新しいノート」)は、いつも名前を聞く(仕様書 v0.77)。

QuickAdd は名前の形が {{VALUE}}(形を決めていないときも同じ)だと、文字を選んでいればそれを聞かずに名前にする。
改行や「/ :」を含む文字を選んだまま Ctrl+N を押すと、ノートが正しく作れなかった。
名前のある {{VALUE:名前}} は選んだ文字を使わず、いつも窓で聞く。
"""

import json
from pathlib import Path

import pytest

VAULT = Path(__file__).resolve().parents[2] / "vault"
FILES = sorted(VAULT.glob("**/plugins/quickadd/data.json"))


def template_choices(data):
    for c in data.get("choices", []):
        if c.get("type") == "Template":
            yield c
        yield from template_choices(c)


def test_found_quickadd_settings():
    assert len(FILES) >= 3


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(VAULT)))
def test_new_note_always_asks_name(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    for c in template_choices(data):
        fmt = c.get("fileNameFormat") or {}
        assert fmt.get("enabled"), f"{c['name']}: 名前の形を決めていない(選んだ文字が名前になる)"
        assert "{{VALUE}}" not in fmt.get("format", ""), f"{c['name']}: {{{{VALUE}}}} は選んだ文字が名前になる"
        assert "{{VALUE:" in fmt.get("format", ""), f"{c['name']}: 名前を聞く {{{{VALUE:名前}}}} がない"


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(VAULT)))
def test_selection_is_never_used_as_name(path):
    """文字を選んだまま Ctrl+N を押しても、選んだ文字を名前にしない。

    QuickAdd は全体の設定 useSelectionAsCaptureValue(既定は使う)でも選んだ文字を使うので、
    全体と各テンプレートの両方で「使わない」にしておく。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("useSelectionAsCaptureValue") is False, "全体の設定で選んだ文字を使う"
    for c in template_choices(data):
        assert c.get("useSelectionAsCaptureValue") is False, f"{c['name']}: 選んだ文字を使う"
