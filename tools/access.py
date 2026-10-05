"""権限：開示（グラント）の判定"""
import sys, os, re, json, sqlite3, html, base64, datetime, subprocess, hashlib, functools, yaml, markdown
sys.path.insert(0, os.path.dirname(__file__))
from kv import ROOT, SRV, DB, reg, parse_drawing, embedded_files, LINK_RE, hash_of, can_see, read_note, split_fm
from core import *

def approved_grants(notes):
    gs = sorted((json.loads(n['fm']) for n in notes.values() if n['type'] == 'grant'), key=lambda f: str(f.get('approved_at', '')))
    out = []
    for fm in gs:
        if fm.get('decision') == 'approved': out.append(dict(fm))
        elif fm.get('decision') == 'revoked':   # 取り消しは、それ以前の開示から対象を外す
            rv = set(fm.get('approved_targets') or [])
            for g in out: g['approved_targets'] = [t for t in g.get('approved_targets') or [] if t not in rv and t.split('#')[0] not in rv]
    return out

def granted(user, notes, target):
    """target（'ノートID' または 'ノートID#Fnn'）が開示されていれば承認版を返す"""
    for g in approved_grants(notes):
        tg = g.get('approved_targets') or []
        if (target in tg or target.split('#')[0] in tg) and can_see(user, g.get('audience')):   # ノートの開示はフレームも含む
            return g.get('approved_version') or None
    return None

def is_mgr(user):
    return any(user in (g['owner'], g.get('deputy')) for g in reg()['tags'].values())

def ok(user, notes, n):
    return can_see(user, n['access']) or bool(granted(user, notes, n['id']))

