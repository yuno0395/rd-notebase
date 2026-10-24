"""ノートの id(仕様書「ノートの id」)。

id = 時刻6文字 + 人の記号。時刻は 2026-01-01 00:00(日本時間)からの秒数を
Crockford Base32(数字と大文字。I・L・O・U を除く)で表す。
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
# ファイル名 "<id>_<名前>"。id は時刻6文字＋人3文字以上
ID_FILENAME = re.compile(rf"^([{_CHARS}]{{6}}[{_CHARS}]{{3,}})_(.+)$", re.I)


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
