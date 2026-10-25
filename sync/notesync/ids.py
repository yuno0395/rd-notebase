"""ノートの id(仕様書「ノートの id」)。

id = 時刻6文字 + 人の記号。時刻は 2026-01-01 00:00(日本時間)からの秒数を
Crockford Base32(数字と大文字。I・L・O・U を除く)で表す。
人の記号は、各自が決めた6桁の数字(例: 229999)を36進数(数字と大文字 A〜Z)にした4文字
(例: 4XGV。Yu 2026-10-25)。v0.38 までの3文字の記号(例: 001)の id もそのまま読む。
id は「先頭6文字が時刻、`_` までが人」と読み、長さを決め打ちしない。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

ABC = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
JST = timezone(timedelta(hours=9))
EPOCH = datetime(2026, 1, 1, tzinfo=JST)
TIME_LEN = 6

_CHARS = "0-9A-HJKMNP-TV-Z"
B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CODE_LEN = 4
# ファイル名 "<id>_<名前>"。id は時刻6文字＋人3文字以上(人は36進数なので I・L・O・U も入る)
ID_FILENAME = re.compile(rf"^([{_CHARS}]{{6}}[0-9A-Z]{{3,}})_(.+)$", re.I)
NUMBER = re.compile(r"^\d{6}$")


def code_from_number(number: str) -> str:
    """6桁の数字を36進数4文字の人の記号にする。"229999" → "4XGV"、"000001" → "0001"。"""
    number = str(number).strip()
    if not NUMBER.match(number):
        raise ValueError(f"6桁の数字ではありません: {number!r}")
    n, s = int(number), ""
    for _ in range(CODE_LEN):
        s = B36[n % 36] + s
        n //= 36
    return s


def code_of(value: str) -> str:
    """メンバー.csv や個人設定の値を人の記号にする。6桁の数字なら36進数に、それ以外(古い3文字の記号)はそのまま。"""
    value = str(value or "").strip()
    return code_from_number(value) if NUMBER.match(value) else value.upper()


def encode_time(seconds: int) -> str:
    if seconds < 0 or seconds >= 32**TIME_LEN:
        raise ValueError(f"id の時刻にできない秒数です: {seconds}")
    s = ""
    for _ in range(TIME_LEN):
        s = ABC[seconds % 32] + s
        seconds //= 32
    return s


def decode_time(text: str) -> datetime:
    n = 0
    for ch in text[:TIME_LEN].upper():
        n = n * 32 + ABC.index(ch)
    return EPOCH + timedelta(seconds=n)


def seconds_since_epoch(when: datetime) -> int:
    if when.tzinfo is None:
        when = when.astimezone()  # PC の時刻帯とみなす
    return int((when - EPOCH).total_seconds())


def make_id(when: datetime, code: str, used: set[str]) -> str:
    """when の時刻と人の記号から id を作る。used にあれば1秒ずつずらす(F-02)。"""
    sec = seconds_since_epoch(when)
    code = code.upper()
    while True:
        new = encode_time(sec) + code
        if new not in used:
            return new
        sec += 1


def split_filename(stem: str) -> tuple[str | None, str]:
    """"0RDGPG001_保圧を変えて試作する" → ("0RDGPG001", "保圧を変えて試作する")。id がなければ (None, stem)。"""
    m = ID_FILENAME.match(stem)
    if m:
        return m.group(1).upper(), m.group(2)
    return None, stem
