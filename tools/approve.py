"""承認：承認者の本人確認（承認ノート）

承認・却下・取り消しは、承認する人が**自分の vault に「承認ノート」（type: approval）を書く**ことで行う。
各人の vault のリポジトリは本人だけが書き込める（Git ホスティングの権限）ので、「誰の vault にあるか」が本人の証明になる。
サーバの索引は、台帳で権限のある人の vault にある承認ノートだけを有効にし、対象のノートに書いてある判断（decision・status）は信用しない。

  対象の種類     権限のある人（台帳 config/registry.yml）
  開示（grant）   開示する資料の鍵（tags）の owner と deputy
  計画変更（planreq） 案件（projects.<案件>）の owner と deputies
  文書（status: approved）  案件の owner と deputies。案件のないノートは台帳の approvers

承認ノートの項目：about（対象の id）、decision（approved／rejected／revoked）、version（判断した時の対象の版）、
  approved_targets（開示で一部だけ許す時）、reason（理由・コメント）、checks、decided_at
"""
import os, re, json, datetime
import kv

KIND_JA = {'grant': '開示', 'planreq': '計画変更', 'doc': '文書'}
DEC_JA = {'approved': '承認', 'rejected': '却下', 'revoked': '取り消し'}
DEC_IN = {'承認': 'approved', '公開': 'approved', '許可': 'approved', 'approved': 'approved', 'ok': 'approved',
          '却下': 'rejected', 'rejected': 'rejected', 'ng': 'rejected', '取り消し': 'revoked', '取消': 'revoked', 'revoked': 'revoked'}

def kind_of(fm):
    t = fm.get('type')
    return 'grant' if t == 'grant' else 'planreq' if t == 'planreq' else 'doc'

def personal_vaults(r):
    """本人だけが書く vault（案件のリポジトリは複数人が書くので、承認の置き場にはならない）"""
    shared = {(p.get('repo') or '') for p in (r.get('projects') or {}).values()} | {v for v in r['vaults'] if v.startswith('proj-')}
    return {v: u for v, u in r['vaults'].items() if v not in shared}

def authority(fm, r, notes=None):
    """対象（frontmatter）を承認できる人の集合"""
    k = kind_of(fm); tags = r.get('tags') or {}; out = set()
    if k == 'grant':
        acc = set()
        for t in fm.get('targets') or []:
            n = (notes or {}).get(str(t).split('#')[0])
            if n: acc |= set(json.loads(n['access']) if isinstance(n.get('access'), str) else n.get('access') or [])
        if not acc: acc = set(fm.get('access') or [])
        for t in acc:
            if t in tags: out |= {tags[t].get('owner'), tags[t].get('deputy')}
    else:
        p = (r.get('projects') or {}).get(fm.get('project') or '')
        if p: out |= {p.get('owner')} | set(p.get('deputies') or [])
        elif k == 'doc': out |= set(r.get('approvers') or [])
    return {u for u in out if u}

def resolve(db, r):
    """索引の後処理：承認ノートから、対象の判断（decision・status）を決め直す。
    返り値：問題の一覧 [(対象の id, 承認ノートの id, 理由)]（索引の approval_issues 表にも入れる）"""
    import sqlite3
    db.row_factory = sqlite3.Row
    rows = {x['id']: dict(x) for x in db.execute('select n.id, n.vault, n.path, n.type, n.title, n.status, n.access, coalesce(r.fm, n.fm) as fm, n.commit_ '
                                                 'from notes n left join fm_raw r on r.id = n.id')}   # 書いてあるままの項目から毎回やり直す
    pv = personal_vaults(r); issues = []; got = {}
    for i, a in rows.items():
        if a['type'] != 'approval': continue
        fm = json.loads(a['fm']); tgt = str(fm.get('about') or '').split('#')[0]; who = pv.get(a['vault'])
        if not who: issues.append((tgt, i, f"承認ノートが個人の vault 以外（{a['vault']}）にある")); continue
        t = rows.get(tgt)
        if not t: issues.append((tgt, i, '対象のノートが見つからない')); continue
        dec = DEC_IN.get(str(fm.get('decision') or '').lower(), None)
        if not dec: issues.append((tgt, i, f"判断「{fm.get('decision')}」が分からない")); continue
        if who not in authority(json.loads(t['fm']), r, rows):
            issues.append((tgt, i, f"{who} にはこの{KIND_JA[kind_of(json.loads(t['fm']))]}を判断する権限がない（台帳）")); continue
        got.setdefault(tgt, []).append({'id': i, 'by': who, 'decision': dec, 'at': str(fm.get('decided_at') or fm.get('created') or ''),
                                        'version': str(fm.get('version') or ''), 'targets': fm.get('approved_targets'),
                                        'reason': fm.get('reason') or fm.get('comment') or '', 'checks': fm.get('checks') or []})
    for i, t in rows.items():
        fm = json.loads(t['fm']); k = kind_of(fm); ch = False
        best = max(got.get(i, []), key=lambda a: a['at'], default=None)
        if k in ('grant', 'planreq'):
            if best:
                fm.update(decision=best['decision'], decided_by=best['by'], decided_at=best['at'], approval=best['id'],
                          comment=best['reason'], reason=best['reason'] if k == 'grant' else fm.get('reason'))
                if k == 'grant':
                    fm.update(approved_by=best['by'], approved_at=best['at'], approved_version=best['version'] or fm.get('approved_version', ''),
                              approved_targets=best['targets'] if best['targets'] else (fm.get('targets') or []), checks=best['checks'])
                ch = True
            elif fm.get('decision') in ('approved', 'rejected', 'revoked') and not (k == 'planreq' and fm.get('needs_approval') is False):
                issues.append((i, '', f"「{DEC_JA[fm['decision']]}」と書いてあるが、権限のある人の承認ノートがない（申請中として扱う）"))
                fm['claimed_decision'] = fm['decision']; fm['decision'] = 'requested'; ch = True
        else:
            if best and best['decision'] == 'approved':
                fm.update(approved_by=best['by'], approved_at=best['at'], approved_version=best['version'], approval=best['id'])
                import quality   # 承認した版から中身が変わっていたら、再承認が要る（レビュー待ちに戻す）
                if quality.changed_since(t['vault'], i, t['path'], best['version']):
                    fm['approved_changed'] = True; fm['status'] = 'review'
                elif fm.get('status') != 'approved': fm['status'] = 'approved'
                ch = True
            elif fm.get('status') == 'approved':
                issues.append((i, '', '状態が approved だが、権限のある人の承認ノートがない（レビュー待ちとして扱う）'))
                fm['status_claimed'] = 'approved'; fm['status'] = 'review'; ch = True
        db.execute('update notes set fm = ?, status = ? where id = ?', (json.dumps(fm, ensure_ascii=False, default=str), fm.get('status'), i))
    db.execute('create table if not exists approval_issues(target, approval, why)')
    db.execute('delete from approval_issues')
    db.executemany('insert into approval_issues values(?,?,?)', issues)
    db.commit(); db.row_factory = None
    return issues

# ---------- 承認ノートを書く（承認する人の PC・サーバの代行どちらからも） ----------
def write(vp, user, target_row, decision, reason='', targets=None, checks=None, today=None, at=None):
    """承認する人の vault に承認ノートを作る → パス"""
    import secrets
    today = today or datetime.date.today(); dec = DEC_IN.get(str(decision).lower())
    if not dec: raise SystemExit(f'判断は 承認・却下・取り消し のどれか（{decision}）')
    tfm = json.loads(target_row['fm']) if isinstance(target_row['fm'], str) else target_row['fm']
    used = {kv.read_note(p)[0].get('id') for p in __import__('glob').glob(os.path.join(vp, '**', '*.md'), recursive=True)}
    while True:
        nid = f"{today:%y%m%d}-{''.join(secrets.choice(kv.ALPH) for _ in range(5))}"
        if nid not in used: break
    label = target_row.get('title') or kv.title_of(target_row['path'], tfm)
    fm = {'id': nid, 'type': 'approval', 'owner': user, 'project': tfm.get('project') or '', 'status': 'draft',
          'access': list(tfm.get('access') or []), 'created': str(today), 'updated': str(today), 'summary': f"{DEC_JA[dec]}：{label}",
          'about': target_row['id'], 'about_label': label, 'decision': dec, 'version': target_row.get('commit_') or '',
          'reason': reason, 'decided_at': str(at or datetime.datetime.now().strftime('%Y-%m-%dT%H:%M'))}
    if targets: fm['approved_targets'] = list(targets)
    if checks: fm['checks'] = list(checks)
    d = os.path.join(vp, '10_notes'); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, kv.fname(nid, f"{DEC_JA[dec]} {label}", 'md', d))
    kind = KIND_JA[kind_of(tfm)]
    body = (f"{kind}の{DEC_JA[dec]}。対象 [[{kv.link_key(target_row['path'])}]]（版 `{fm['version']}`）\n\n"
            f"## 理由\n{reason or '（なし）'}\n")
    kv.write_note(p, fm, body)
    return p

def find_target(con, key):
    import sqlite3
    con.row_factory = sqlite3.Row
    t = con.execute('select * from notes where id = ?', (key,)).fetchone()
    if t: return dict(t)
    hits = [dict(x) for x in con.execute('select * from notes where title like ? and type in ("grant", "planreq")', (f'%{key}%',))]
    if len(hits) != 1: raise SystemExit(f'「{key}」に合う申請が' + ('見つかりません' if not hits else f' {len(hits)} 件あります（id で指定）'))
    return hits[0]

def migrate(root, r):
    """以前の形（判断を申請のノートに直接書いていた）から、判断した人の vault に承認ノートを作る（試作環境の移行）。返り値：{vault: 作った数}"""
    import glob
    pv = personal_vaults(r); vault_of = {u: v for v, u in pv.items()}; made = {}
    have = set()
    for v in pv:
        for p in glob.glob(os.path.join(root, v, '**', '*.md'), recursive=True):
            fm = kv.read_note(p)[0]
            if fm.get('type') == 'approval': have.add(str(fm.get('about')))
    for v in r['vaults']:
        for p in sorted(glob.glob(os.path.join(root, v, '**', '*.md'), recursive=True)):
            fm, _ = kv.read_note(p)
            if fm.get('type') not in ('grant', 'planreq') or fm.get('decision') not in ('approved', 'rejected', 'revoked'): continue
            if fm.get('type') == 'planreq' and fm.get('needs_approval') is False: continue
            if str(fm.get('id')) in have: continue
            who = fm.get('decided_by') or fm.get('approved_by') or (fm.get('approvers') or [None])[0]
            if who not in vault_of: continue
            row = {'id': fm['id'], 'path': p, 'fm': fm, 'title': kv.title_of(p, fm), 'commit_': fm.get('approved_version') or ''}
            write(os.path.join(root, vault_of[who]), who, row, fm['decision'], fm.get('comment') or fm.get('reason') or '',
                  targets=fm.get('approved_targets') if fm.get('type') == 'grant' else None, checks=fm.get('checks'),
                  today=datetime.date.fromisoformat(str(fm.get('created') or datetime.date.today())),
                  at=fm.get('approved_at') or fm.get('decided_at'))
            made[vault_of[who]] = made.get(vault_of[who], 0) + 1
    return made
