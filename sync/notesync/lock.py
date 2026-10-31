"""1人が2台以上の PC で同じ個人 vault を使うときの札(仕様書「複数の PC で使う」)。

個人 vault は共有クラウドフォルダ(Box Drive・OneDrive など)でどの PC にも同じものが見える。
2台で同時に同期すると、同じノートの改名やコピーがぶつかって競合の複製が増える。そこで同期する間だけ札を置き、
別の PC の札が新しいうちは、その回の同期を見送る。

- 札は JSON 1つ(どの PC が、いつ置いたか)。同期が終わったら外す。
- 自分の PC の札、または古い札(止まった PC が残したもの)は取り直してよい。
- 同期アプリの届く遅れがあるので、完全には防げない。ぶつかったときは F-16 が知らせる。
"""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

STALE_SECONDS = 15 * 60   # これより古い札は、止まった PC が残したものとみなす


def pc_name() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname() or "?"


class Busy(Exception):
    """別の PC が札を持っている。"""

    def __init__(self, pc: str, since: float):
        super().__init__(pc)
        self.pc = pc
        self.since = since


class Lock:
    def __init__(self, path: Path, me: str | None = None, now: float | None = None):
        self.path = path
        self.me = me or pc_name()
        self.now = time.time() if now is None else now
        self.held = False

    def holder(self) -> tuple[str, float] | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return str(data.get("pc") or "?"), float(data.get("time") or 0)
        except (OSError, ValueError, AttributeError):
            return None

    def acquire(self) -> "Lock":
        got = self.holder()
        if got:
            pc, since = got
            if pc != self.me and self.now - since < STALE_SECONDS:
                raise Busy(pc, since)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps({"pc": self.me, "time": self.now}, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)
        self.held = True
        return self

    def release(self) -> None:
        if not self.held:
            return
        got = self.holder()
        if got and got[0] == self.me:
            try:
                self.path.unlink()
            except OSError:
                pass
        self.held = False

    def __enter__(self) -> "Lock":
        return self.acquire()

    def __exit__(self, *exc) -> None:
        self.release()
