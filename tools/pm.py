#!/usr/bin/env python3
"""pm: 工程管理の操作（プラグイン＋サーバの処理を再現）
  vault <名前> <所有者>                         : vault（案件リポジトリ等）を作る
  weekly <vault> <案件> <週の月曜> <items.json>  : 週報（1人×1週×1案件）。進捗の数は自動で記録
  request <vault> <工程表ID> <changes.json> <区分> <理由> : 計画変更のリクエスト
  edit <vault> <工程表ID> <ops.json> <区分> <理由>     : 編集画面からの申請（追加・削除・分解・担当替えなど）
  decide <リクエストID> <approved|rejected> <承認者> <コメント> : 承認・却下（承認なら工程表に反映）
  gantt <工程表ID> <m1|m3|m6|y5|y10> [開始日]     : Excalidrawのガント図を作る・作り直す（書き込みは残す）
"""
import os, sys, json, glob, datetime, subprocess, yaml
sys.path.insert(0, os.path.dirname(__file__))
from kv import ROOT, SRV, reg, REG, read_note, join_fm, cmd_new, cmd_push, cmd_index, sh, scan_vault, parse_drawing, fname, DB
import gantt as G

REASONS = ['見積の誤り', '仕様変更', '外部待ち（部品・外注・顧客）', '不具合・やり直し', '人の都合（他案件・休み）', 'その他']
LIMIT_DAYS, EST_UP = 5, 0.20   # 承認が要る境目：実働5日超の遅れ、見積20%超の増加

def make_vault(name, owner):
    vp = os.path.join(ROOT, name); bare = os.path.join(SRV, name + '.git')
    if os.path.exists(vp): return
    sh(f'git init -q --bare -b main {bare}')
    os.makedirs(vp); sh('git init -q -b main', vp)
    open(os.path.join(vp, '.gitattributes'), 'w').write(open(os.path.join(ROOT, 'vault-boss', '.gitattributes')).read())
    for f in ('10_notes', '20_drawings', '40_attachments'):
        os.makedirs(os.path.join(vp, f)); open(os.path.join(vp, f, '.gitkeep'), 'w').close()
    sh(f'git config user.name {owner}; git config user.email {owner}@example.com', vp)
    sh('git add -A && git commit -qm init', vp); sh(f'git remote add origin {bare}', vp); sh('git push -q origin main', vp)
    r = yaml.safe_load(open(REG, encoding='utf-8')); r['vaults'][name] = owner
    yaml.safe_dump(r, open(REG, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)

def find(nid):
    for v in reg()['vaults']:
        n = scan_vault(os.path.join(ROOT, v)).get(nid)
        if n: return v, n
    raise SystemExit(f'見つからない {nid}')

def commit(vault, msg):
    vp = os.path.join(ROOT, vault); sh('git add -A', vp)
    if sh('git status --porcelain', vp): sh(f'git commit -qm "{msg}"', vp)
    sh('git push -q origin main', vp); cmd_index()

def cmd_weekly(vault, project, week, items):
    """週報：入力は1画面、保存は案件ごと。進捗（やることの完了数／総数）は保存時に自動で記録（人は入力しない）"""
    import sqlite3
    cmd_index(); c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    notes = {r['id']: dict(r) for r in c.execute('select * from notes')}
    cnt = G.todo_counts(notes); today = datetime.date.today()
    names = {}
    for n in notes.values():
        if n['type'] == 'schedule':
            for t in json.loads(n['fm']).get('tasks') or []: names[f"{n['id']}#{t['id']}"] = t['name']
    for it in items:
        for k in ('actual_start', 'actual_end'):
            if it.get(k) and G.d(it[k]) > today: raise SystemExit(f"{k} {it[k]} は未来の日付です（実績は終わってから書く）")
        k = cnt.get(it.get('task', ''), {'done': 0, 'total': 0}); it['count'] = f"{k['done']}/{k['total']}"
    wk = str(G.monday(G.d(week)))
    p = cmd_new(vault, 'weekly', f'週報 {G.week_name(wk)} {project}', project=project, week=wk, items=items)
    md = lambda x: f'{G.d(x).month}/{G.d(x).day}'
    def line(it):
        nm = names.get(it.get('task'), '予定外の作業'); st = []
        if it.get('actual_end'): st.append(f"実績 {md(it.get('actual_start') or it['actual_end'])}〜{md(it['actual_end'])}" if it.get('actual_start') else f"実績 {md(it['actual_end'])}")
        elif it.get('forecast_end'): st.append(f"見込み {md(it['forecast_end'])}")
        if it.get('count') and it['count'] != '0/0': st.append(f"やること {it['count']}")
        return (f"### {nm}\n- {' ・ '.join(st)}\n- やったこと：{it.get('did', '')}" + (f"\n- 課題：{it['issue']}" if it.get('issue') else '') + f"\n- 工程タスク：{it.get('task', '')}")
    body = '\n\n'.join(line(it) for it in items)
    fm, _ = read_note(p); open(p, 'w', encoding='utf-8').write(join_fm(fm, '## 今週\n' + body + '\n'))
    return p

def cmd_request(vault, sched_id, changes, code, reason):
    """計画変更のリクエスト。申請は案件リポジトリ（工程表の隣）に置く。
    変えない日付は省略できる（終了日だけ等）。shift_after なら後ろのタスクを「食い込む分だけ」押す（ripple）"""
    assert code in REASONS, f'理由区分は {REASONS}'
    sv, sn = find(sched_id); fm = sn['fm']; plan = fm['tasks']; tasks = {t['id']: t for t in plan}; hol = G.holidays()
    fixed, shift_any = {}, False
    for ch in changes:
        t = tasks[ch['task']]; shift_any |= bool(ch.get('shift_after'))
        fixed[t['id']] = {'date': G.d(ch['date'])} if t.get('milestone') else {'start': G.d(ch.get('start') or t['start']), 'end': G.d(ch.get('end') or t['end'])}
    if shift_any: res = G.ripple(plan, fixed, hol)
    else: res = {**{t['id']: ({'date': G.d(t['date'])} if t.get('milestone') else {'start': G.d(t['start']), 'end': G.d(t['end'])}) for t in plan if not t.get('group')}, **fixed}
    full, need, why = [], [], []
    for t in plan:
        if t.get('group'): continue
        x = res[t['id']]; cur = {k: G.d(t[k]) for k in x}
        if x == cur: continue
        full.append({'task': t['id'], **{k: str(v) for k, v in x.items()}, **({} if t['id'] in fixed else {'auto': True})})
        if t.get('milestone'): need.append(t['id']); why.append(f"節目 {t['name']} {G.d(t['date']).month}/{G.d(t['date']).day}→{x['date'].month}/{x['date'].day}")
        else:
            late = G.wdays(G.d(t['end']), x['end'], hol)
            if late > LIMIT_DAYS: need.append(t['id']); why.append(f"{t['name']} 実働{late}日の遅れ")
    if not full: raise SystemExit('変更がありません')
    pr = cmd_new(sv, 'planreq', f"計画変更 {fm['title']}"[:40], project=fm.get('project'), schedule=sched_id, changes=full,
                 code=code, reason=reason, needs_approval=bool(need), why=why, decision='requested' if need else 'auto',
                 requested_by=reg()['vaults'][vault], approvers=[reg()['projects'][fm['project']]['owner']])
    rfm, _ = read_note(pr); rfm['access'] = list(fm.get('access') or []); rfm['owner'] = reg()['vaults'][vault]
    open(pr, 'w', encoding='utf-8').write(join_fm(rfm, ''))
    commit(sv, f"計画変更の申請|申請:{rfm['owner']}|区分:{code}")
    print('承認が要る：' + '、'.join(why) if need else '承認不要（記録のみ）', f'変更 {len(full)} 件')
    if not need: cmd_decide(rfm['id'], 'approved', '（承認不要）', '実働5日以内・節目に影響なし')
    return pr

def apply_ops(plan, ops):
    """編集画面の操作（追加・削除・変更・分解・並べ替え）を計画に当てる"""
    tasks = [dict(t) for t in plan]; by = lambda i: next((t for t in tasks if t['id'] == i), None)
    for op in ops:
        if op['op'] == 'add':
            t = {k: v for k, v in op['task'].items() if v not in ('', None, [])}; tasks.append(t)
        elif op['op'] == 'del':
            t = by(op['id'])
            if not t: continue
            for x in tasks:
                if op['id'] in (x.get('after') or []): x['after'] = list(dict.fromkeys([a for a in x['after'] if a != op['id']] + (t.get('after') or [])))
                if x.get('parent') == op['id']:
                    if t.get('parent'): x['parent'] = t['parent']
                    else: x.pop('parent', None)
            tasks.remove(t)
        elif op['op'] == 'set':
            t = by(op['id'])
            if not t: continue
            for k, v in op['f'].items():
                if v in ('', None) or (k == 'after' and v == []): t.pop(k, None)
                else: t[k] = v
        elif op['op'] == 'order':
            pos = {i: n for n, i in enumerate(op['ids'])}; tasks.sort(key=lambda t: pos.get(t['id'], 10 ** 6))
    return tasks

def cmd_edit(vault, sched_id, ops, code, reason):
    """編集画面からの申請。範囲の変更（追加・削除・分解・担当替え・グループ替え・見積20%超）と、実働5日超の遅れ・節目の移動は承認が要る"""
    assert code in REASONS, f'理由区分は {REASONS}'
    sv, sn = find(sched_id); fm = sn['fm']; plan = fm['tasks']; hol = G.holidays()
    import sqlite3
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    used = G.ids_ever(dict(c.execute('select * from notes where id=?', (sched_id,)).fetchone()))
    remap = {}
    for op in ops:                                  # 番号は再利用しない（使われたことのある番号なら振り直す）
        if op['op'] == 'add' and op['task']['id'] in used | {t['id'] for t in plan}:
            k = op['task']['id'][0]; n = 1
            while f'{k}{n:02d}' in used | {t['id'] for t in plan} | set(remap.values()): n += 1
            remap[op['task']['id']] = f'{k}{n:02d}'
    fix = lambda i: remap.get(i, i)
    for op in ops:
        if op['op'] == 'add':
            t = op['task']; t['id'] = fix(t['id']); t['after'] = [fix(a) for a in t.get('after') or []]
            if t.get('parent'): t['parent'] = fix(t['parent'])
        if op['op'] == 'set' and 'after' in op['f']: op['f']['after'] = [fix(a) for a in op['f']['after']]
        if op['op'] == 'order': op['ids'] = [fix(i) for i in op['ids']]
    new = apply_ops(plan, ops); old = {t['id']: t for t in plan}; nw = {t['id']: t for t in new}
    why, summary, changes = [], [], []
    md = lambda x: f'{G.d(x).month}/{G.d(x).day}'
    span = lambda t: md(t['date']) if t.get('milestone') else f"{md(t['start'])}〜{md(t['end'])}" if t.get('start') else ''
    for t in new:
        o = old.get(t['id'])
        if not o:
            if not (t.get('parent') in nw and nw[t['parent']].get('group') and not old.get(t['parent'], {}).get('group', True)):
                summary.append(f"追加：{t['name']} {span(t)}"); why.append('タスクの追加')
            continue
        if t.get('group') and not o.get('group'):
            summary.append(f"段階に分解：{t['name']} → {'・'.join(x['name'] for x in new if x.get('parent') == t['id'])}"); why.append('段階に分解'); continue
        if o.get('name') != t.get('name'): summary.append(f"名前：{o['name']} → {t['name']}")
        if o.get('owner') != t.get('owner') and not t.get('group'): U = reg()['users']; summary.append(f"担当：{t['name']} {U.get(o.get('owner'), '—').split('（')[0]} → {U.get(t.get('owner'), '—').split('（')[0]}"); why.append('担当替え')
        if o.get('parent') != t.get('parent'): summary.append(f"グループ：{t['name']}"); why.append('グループの変更')
        if (o.get('after') or []) != (t.get('after') or []): summary.append(f"前のタスク：{t['name']} ← {'、'.join(nw.get(a, old.get(a, {'name': a}))['name'] for a in t.get('after') or []) or '（なし）'}")
        if o.get('est') and t.get('est') and float(t['est']) > float(o['est']) * (1 + EST_UP): summary.append(f"見積：{t['name']} {o['est']} → {t['est']} 人日"); why.append('見積の20%超の増加')
        if span(o) != span(t) and not t.get('group'):
            summary.append(f"日程：{t['name']} {span(o)} → {span(t)}")
            changes.append({'task': t['id'], **({'date': str(t['date'])} if t.get('milestone') else {'start': str(t['start']), 'end': str(t['end'])})})
            if t.get('milestone'): why.append(f"節目 {t['name']} の移動")
            elif G.wdays(G.d(o['end']), G.d(t['end']), hol) > LIMIT_DAYS: why.append(f"{t['name']} 実働{G.wdays(G.d(o['end']), G.d(t['end']), hol)}日の遅れ")
    for o in plan:
        if o['id'] not in nw: summary.append(f"削除：{o['name']}"); why.append('タスクの削除')
    if [i for i in (t['id'] for t in plan) if i in nw] != [i for i in (t['id'] for t in new) if i in old]: summary.append('並び順の変更')
    why = list(dict.fromkeys(why))
    pr = cmd_new(sv, 'planreq', f"工程表の編集 {fm['title']}"[:40], project=fm.get('project'), schedule=sched_id, ops=ops, changes=changes, lines=summary,
                 code=code, reason=reason, needs_approval=bool(why), why=why, decision='requested' if why else 'auto',
                 requested_by=reg()['vaults'][vault], approvers=[reg()['projects'][fm['project']]['owner']], remap=remap)
    rfm, _ = read_note(pr); rfm['access'] = list(fm.get('access') or []); rfm['owner'] = reg()['vaults'][vault]
    open(pr, 'w', encoding='utf-8').write(join_fm(rfm, '\n'.join('- ' + x for x in summary) + '\n'))
    commit(sv, f"工程表の編集の申請|申請:{rfm['owner']}|区分:{code}")
    print('承認が要る：' + '、'.join(why) if why else '承認不要（記録のみ）', f'変更 {len(summary)} 件', f'番号の振り直し {remap}' if remap else '')
    if not why: cmd_decide(rfm['id'], 'approved', '（承認不要）', '範囲・節目に影響なし、遅れ実働5日以内')
    return pr

def shift(x, n, hol):
    step = 1 if n >= 0 else -1; k = 0
    while k != n:
        x += datetime.timedelta(step)
        if G.workday(x, hol): k += step
    return x

def cmd_decide(req_id, decision, by, comment):
    rv, rn = find(req_id); rfm = rn['fm']
    rfm.update(decision=decision, decided_by=by, comment=comment, decided_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M'))
    open(rn['path'], 'w', encoding='utf-8').write(join_fm(rfm, rn['body'])); commit(rv, f'計画変更の判断|{decision}')
    if decision != 'approved': return
    sv, sn = find(rfm['schedule']); fm = sn['fm']
    if rfm.get('ops'):
        fm['tasks'] = apply_ops(fm['tasks'], rfm['ops'])
        open(sn['path'], 'w', encoding='utf-8').write(join_fm(fm, sn['body']))
        commit(sv, f"{'範囲の変更' if any(o['op'] in ('add', 'del') for o in rfm['ops']) else '計画変更'}|承認:{by}|区分:{rfm['code']}|理由:{rfm['reason']}|リクエスト:{req_id}")
        return
    for ch in rfm['changes']:
        t = next(t for t in fm['tasks'] if t['id'] == ch['task'])
        for k in ('start', 'end', 'date'):
            if k in ch: t[k] = G.d(ch[k])
    open(sn['path'], 'w', encoding='utf-8').write(join_fm(fm, sn['body']))
    commit(sv, f"計画変更|承認:{by}|区分:{rfm['code']}|理由:{rfm['reason']}|リクエスト:{req_id}")

def cmd_gantt(sched_id, view, start=None):
    """工程表 → Excalidrawのガント図（自動生成の層だけ作り直し、書き込みは付き先に合わせて動かす）"""
    import sqlite3
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    notes = {r['id']: dict(r) for r in c.execute('select * from notes')}
    n = notes[sched_id]; fm = json.loads(n['fm'])
    rows = G.build(n, notes); users = reg()['users']
    for r in rows: r['owner_ja'] = users.get(r.get('owner'), '').split('（')[0]
    title = f"{fm['project']} {reg()['projects'][fm['project']]['name']} 工程表"
    P, geo = G.layout(title, rows, view, start, sub=f'比較：当初計画')
    vp = os.path.join(ROOT, n['vault'])
    ex = [x for x in scan_vault(vp).values() if x['fm'].get('type') == 'drawing' and (x['fm'].get('gantt') or {}).get('schedule') == sched_id
          and x['fm']['gantt']['view'] == view]
    if ex: path = ex[0]['path']
    else:
        path = cmd_new(n['vault'], 'drawing', f"工程表 {fm['project']} {G.VIEWS[view][0]}", project=fm['project'], gantt={'schedule': sched_id, 'view': view, 'start': start or ''})
    dfm, body = read_note(path)
    old = parse_drawing(body)['elements']
    els = G.to_excalidraw(P, geo, old, f"{G.VIEWS[view][0]} {geo['s']}〜")
    dfm['gantt'] = {'schedule': sched_id, 'view': view, 'start': start or ''}
    texts = '\n\n'.join(e['text'] for e in els if e['type'] == 'text')
    open(path, 'w', encoding='utf-8').write(join_fm(dfm, f"\n## Text Elements\n{texts}\n\n## Embedded Files\n\n## Drawing\n```json\n"
                                                    + json.dumps({'type': 'excalidraw', 'elements': els, 'files': {}}, ensure_ascii=False, indent=1) + "\n```\n"))
    commit(n['vault'], f'ガント図の作り直し|{view}')
    return path

if __name__ == '__main__':
    c, *a = sys.argv[1:] or ['help']
    if c == 'vault': make_vault(a[0], a[1])
    elif c == 'weekly': print(cmd_weekly(a[0], a[1], a[2], json.load(open(a[3], encoding='utf-8'))))
    elif c == 'request': print(cmd_request(a[0], a[1], json.load(open(a[2], encoding='utf-8')), a[3], a[4]))
    elif c == 'decide': cmd_decide(a[0], a[1], a[2], a[3])
    elif c == 'edit': print(cmd_edit(a[0], a[1], json.load(open(a[2], encoding='utf-8')), a[3], a[4]))
    elif c == 'gantt': print(cmd_gantt(a[0], a[1], a[2] if len(a) > 2 else None))
    else: print(__doc__)
