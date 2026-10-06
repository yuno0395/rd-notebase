"""共通：DB接続、エスケープ、定数"""
import sys, os, re, json, sqlite3, html, base64, datetime, subprocess, hashlib, functools, yaml, markdown
sys.path.insert(0, os.path.dirname(__file__))
from kv import has_drawing, text_part, OUT, SELF, ROOT, SRV, DB, reg, parse_drawing, embedded_files, LINK_RE, hash_of, can_see, read_note, split_fm
def db(): c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
def esc(s): return html.escape(str(s or ''))

def all_notes(c):
    return {r['id']: dict(r) for r in c.execute('select * from notes')}

def by_hash(notes):
    return {i.split('-')[1]: n for i, n in notes.items()}

def work_path(n): return os.path.join(SRV, 'work', n['vault'], n['path'])

KIND_JA = {'cites': 'スライド・図', 'based_on': '根拠', 'derived_from': '元の要求', 'link': '参照', 'verifies': '検証'}
def meta_row(n, r):
    a = json.loads(n['access'])
    tags = ''.join(f'<span class="tag">{esc(t)}</span>' for t in a)
    return tags

def week_start():
    d = datetime.date.today(); return d - datetime.timedelta(days=d.weekday())

TYPE_JA = {None: '未分類', '': '未分類', 'req': '要求', 'study': '検討', 'calc': '計算', 'report': '報告', 'meeting': '議事録', 'drawing': '図', 'attachment': '添付', 'daily': 'デイリー', 'memo': 'メモ', 'comment': 'コメント', 'weeknote': '週ノート'}
PROG = {'検討中': 'p-work', 'レビュー待ち': 'p-wait', '完了': 'p-done', '保留': 'p-hold'}
