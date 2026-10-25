import pytest

from datetime import datetime

from notesync import ids


def test_spec_example():
    # 仕様書の例: Yu(001)が 2026-10-24 09:35:12 に作ると 0RDGPG001、1秒後は 0RDGPH001
    when = datetime(2026, 10, 24, 9, 35, 12, tzinfo=ids.JST)
    assert ids.make_id(when, "001", set()) == "0RDGPG001"
    assert ids.make_id(when, "001", {"0RDGPG001"}) == "0RDGPH001"


def test_decode_roundtrip():
    when = datetime(2026, 10, 24, 9, 35, 12, tzinfo=ids.JST)
    assert ids.decode_time("0RDGPG001") == when


def test_split_filename_any_length_person():
    assert ids.split_filename("0RDGPG001_水") == ("0RDGPG001", "水")
    assert ids.split_filename("0RDGPG0012_水") == ("0RDGPG0012", "水")  # 人4文字になっても読める
    assert ids.split_filename("水") == (None, "水")
    assert ids.split_filename("2026-10-24") == (None, "2026-10-24")
    assert ids.split_filename("0rdgpg001_水") == ("0RDGPG001", "水")  # 大文字小文字は区別しない


def test_sort_order_is_creation_order():
    a = ids.make_id(datetime(2026, 3, 1, tzinfo=ids.JST), "002", set())
    b = ids.make_id(datetime(2026, 3, 1, 0, 0, 1, tzinfo=ids.JST), "001", set())
    assert sorted([b, a]) == [a, b]


def test_code_from_six_digit_number():
    # 人の記号は6桁の番号を36進数にした4文字(Yu 2026-10-25)
    assert ids.code_from_number("229999") == "4XGV"
    assert ids.code_from_number("000001") == "0001"
    assert ids.code_from_number("999999") == "LFLR"
    for bad in ("12345", "1234567", "12a456", ""):
        with pytest.raises(ValueError):
            ids.code_from_number(bad)
    assert ids.code_of("001") == "001"          # 古い3文字の記号はそのまま
    # 36進数の記号(I・L・O・U を含む)の id も読める
    assert ids.split_filename("0RDGPGLFLR_水") == ("0RDGPGLFLR", "水")
    assert ids.make_id(ids.EPOCH, "4XGV", set()) == "0000004XGV"
