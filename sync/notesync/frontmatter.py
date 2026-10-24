"""属性欄(先頭の YAML)を、ほかの行を変えずに読み書きする(非機能要件「属性欄の保存」)。

YAML として読み直して書き出すと、順番・コメント・書き方が変わってしまう。
そこで、書き換えるのは必要な行だけにし、ほかは文字のまま残す。
"""

from __future__ import annotations

import re

import yaml


def split(text: str) -> tuple[str | None, str]:
    """(属性欄の中身, 本文) に分ける。属性欄がなければ (None, text)。"""
    if not text.startswith("---"):
        return None, text
    m = re.match(r"^---[ \t]*\r?\n(.*?)(?:\r?\n)?^---[ \t]*(?:\r?\n|$)", text, re.S | re.M)
    if not m:
        return None, text
    return m.group(1), text[m.end():]


def load(text: str) -> dict:
    fm, _ = split(text)
    if not fm:
        return {}
    try:
        data = yaml.safe_load(fm)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def newline_of(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def set_values(text: str, values: dict[str, str]) -> str:
    """属性欄の key の行を値に書き換える。なければ属性欄の先頭(id の行があればその下)に足す。属性欄がなければ作る。"""
    nl = newline_of(text)
    fm, body = split(text)
    if fm is None:
        lines = [f"{k}: {v}" for k, v in values.items()]
        return "---" + nl + nl.join(lines) + nl + "---" + nl + text
    lines = fm.splitlines()
    head = []
    for key, value in values.items():
        pat = re.compile(rf"^{re.escape(key)}\s*:")
        for i, line in enumerate(lines):
            if pat.match(line):
                lines[i] = f"{key}: {value}"
                break
        else:
            head.append(f"{key}: {value}")
    # 新しい行は先頭に足す。id の行があれば、その下に足す
    at = next((i + 1 for i, line in enumerate(lines) if re.match(r"^id\s*:", line)), 0)
    lines = lines[:at] + head + lines[at:]
    return "---" + nl + nl.join(lines) + nl + "---" + nl + body
