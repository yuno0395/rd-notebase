"""工程管理：工程表・ロードマップ・週報・やることを集計し、ガント図を描く。
描画は layout() 1つだけ。SVG（Web閲覧・画像保存）とExcalidraw（書き込み）は、その結果を変換するだけ（見た目のずれを防ぐ）"""
import os, re, json, datetime, subprocess, secrets
from kv import ROOT, SRV, reg, read_note, join_fm, parse_drawing, split_fm
D = datetime.date
def d(s): return s if isinstance(s, D) else D.fromisoformat(str(s))
def esc(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

# ---------- 暦 ----------
def holidays(): return {d(x) for x in reg().get('holidays', [])}
def workday(x, hol=None): return x.weekday() < 5 and x not in (hol if hol is not None else holidays())
def wdays(a, b, hol=None):
    """a→b の実働日数（b が後なら正）"""
    hol = holidays() if hol is None else hol
    if a == b: return 0
    s, e, sg = (a, b, 1) if b > a else (b, a, -1)
    return sg * sum(1 for i in range(1, (e - s).days + 1) if workday(s + datetime.timedelta(i), hol))
def monday(x): return x - datetime.timedelta(x.weekday())
def week_name(x): m = monday(d(x)); return f'{m.month}月{m.day}日週'
def half_start(x): return D(x.year, 4, 1) if 4 <= x.month <= 9 else D(x.year if x.month >= 10 else x.year - 1, 10, 1)
def fy(x): return x.year if x.month >= 4 else x.year - 1
def add_months(x, n): y, m = divmod(x.month - 1 + n, 12); return D(x.year + y, m + 1, 1)

VIEWS = {  # 名前: (表示名, 1マス)
    'm1': ('月間', '日'), 'm3': ('3か月', '週'), 'm6': ('半年', '週'), 'y5': ('5年', '半期'), 'y10': ('10年', '年度')}

def period(view, start=None, today=None):
    """表示期間と列。start なし＝今日起点"""
    t = today or D.today()
    if view == 'm1':
        s = d(start) if start else monday(t)        # 1か月＝5週（35日）
        cols = [(s + datetime.timedelta(i), s + datetime.timedelta(i + 1)) for i in range(35)]
    elif view in ('m3', 'm6'):
        s = monday(d(start)) if start else monday(t); n = 13 if view == 'm3' else 26
        cols = [(s + datetime.timedelta(7 * i), s + datetime.timedelta(7 * i + 7)) for i in range(n)]
    elif view == 'y5':
        s = half_start(d(start) if start else t); cols = []
        for i in range(10): a = add_months(s, 6 * i); cols.append((a, add_months(a, 6)))
    else:
        s = D(fy(d(start) if start else t), 4, 1); cols = [(D(s.year + i, 4, 1), D(s.year + i + 1, 4, 1)) for i in range(10)]
    return cols[0][0], cols[-1][1], cols

def col_label(view, a):
    if view == 'm1': return f'{a.day}'
    if view in ('m3', 'm6'): return f'{a.month}/{a.day}'
    if view == 'y5': return f'{fy(a)}{"上" if a.month == 4 else "下"}'
    return f'{a.year}年度'

# ---------- データの集計 ----------
TODO_RE = re.compile(r'^\s*- \[( |x|X|-)\] (.*?)\[task:: ([0-9]{6}-[a-z0-9]{5}#[TM]\d+)\]', re.M)

def todo_counts(notes):
    """やること（task:: 付きチェックボックス）を工程タスクごとに数える"""
    cnt = {}
    for n in notes.values():
        for st, txt, tid in TODO_RE.findall(n['body'] or ''):
            c = cnt.setdefault(tid, {'done': 0, 'total': 0, 'items': []})
            if st == '-': continue                     # 中止は数えない
            dn = st in 'xX'; c['total'] += 1; c['done'] += dn
            c['items'].append((dn, re.sub(r'(📅|✅).*$', '', txt).strip(), n['id']))
    return cnt

def weekly_of(notes, sched_id):
    """週報（type: weekly）からタスクごとの記入を集める（週の古い順）"""
    out = {}
    for n in sorted([n for n in notes.values() if n['type'] == 'weekly'], key=lambda n: json.loads(n['fm']).get('week', '')):
        fm = json.loads(n['fm'])
        for it in fm.get('items') or []:
            t = it.get('task', '')
            if t.startswith(sched_id + '#') or t == 'unplanned':
                out.setdefault(t.split('#')[-1], []).append(dict(it, week=fm['week'], who=n['owner'], note=n['id']))
    return out

def history(n):
    """工程表ノートのGit履歴から、タスクごとの計画変更（いつ・何日から何日へ・理由・承認者）を作る"""
    work = os.path.join(SRV, 'work', n['vault']); bare = os.path.join(SRV, n['vault'] + '.git')
    log = subprocess.run(['git', f'--git-dir={bare}', 'log', '--reverse', '--format=%h%x09%ad%x09%s', '--date=format:%Y-%m-%d %H:%M', 'main', '--', n['path']],
                         capture_output=True, text=True).stdout.strip().splitlines()
    prev, ch = None, {}
    for line in log:
        h, at, msg = line.split('\t', 2)
        txt = subprocess.run(['git', f'--git-dir={bare}', 'show', f'{h}:{n["path"]}'], capture_output=True, text=True).stdout
        tasks = {t['id']: t for t in (split_fm(txt)[0].get('tasks') or [])}
        meta = {k: v for k, _, v in (x.partition(':') for x in msg.split('|')[1:])}; meta['kind'] = msg.split('|')[0]
        if prev is not None:
            for tid, t in tasks.items():
                p = prev.get(tid)
                key = ('date',) if t.get('milestone') else ('start', 'end')
                if p is None: ch.setdefault(tid, []).append({'at': at, 'what': '追加', 'meta': meta})
                elif t.get('group') and not p.get('group'): ch.setdefault(tid, []).append({'at': at, 'what': '工程に分解', 'meta': meta})
                elif t.get('group'): continue
                elif any(str(p.get(k)) != str(t.get(k)) for k in key):
                    f = lambda x: f'{d(x).month}/{d(x).day}'
                    fr = '〜'.join(f(p.get(k)) for k in key); to = '〜'.join(f(t.get(k)) for k in key)
                    ch.setdefault(tid, []).append({'at': at, 'what': f'{fr} → {to}', 'meta': meta})
        prev = tasks
    return ch

def next_wd(x, hol):
    x += datetime.timedelta(1)
    while not workday(x, hol): x += datetime.timedelta(1)
    return x

def add_wd(x, k, hol):
    while k > 0:
        x += datetime.timedelta(1)
        if workday(x, hol): k -= 1
    return x

def ripple(tasks, fixed, hol=None):
    """後ろへの連鎖：前の作業の終わりが開始に食い込む時だけ、次の稼働日まで押す（空きがあればそこで止まる）。
    期間は実働日数で保つ。申請の「後ろも一緒にずらす」と見込みの計算の両方で使う"""
    hol = holidays() if hol is None else hol; out = {}
    kids = {}
    for t in tasks:
        if t.get('parent'): kids.setdefault(t['parent'], []).append(t['id'])
    def end_of(p):
        if p in out: return out[p].get('end', out[p].get('date'))
        ks = [end_of(k) for k in kids.get(p, [])]; ks = [k for k in ks if k]
        return max(ks) if ks else None
    for t in tasks:
        if t.get('group'): continue
        if t['id'] in fixed: out[t['id']] = fixed[t['id']]; continue
        lat = max([x for x in (end_of(p) for p in t.get('after') or []) if x], default=None)
        if t.get('milestone'):
            dt = d(t['date']); out[t['id']] = {'date': next_wd(lat, hol) if lat and lat >= dt else dt}
        else:
            s0, e0 = d(t['start']), d(t['end'])
            if lat and lat >= s0:
                ns = next_wd(lat, hol); e0 = add_wd(e0, wdays(s0, ns, hol), hol); s0 = ns
            out[t['id']] = {'start': s0, 'end': e0}
    return out

def ids_ever(n):
    """工程表の履歴に一度でも出たタスクID（番号は再利用しない）"""
    bare = os.path.join(SRV, n['vault'] + '.git'); out = set()
    for h in subprocess.run(['git', f'--git-dir={bare}', 'log', '--format=%h', 'main', '--', n['path']], capture_output=True, text=True).stdout.split():
        txt = subprocess.run(['git', f'--git-dir={bare}', 'show', f'{h}:{n["path"]}'], capture_output=True, text=True).stdout
        out |= {t['id'] for t in (split_fm(txt)[0].get('tasks') or [])}
    return out

def build(n, notes, today=None, base='当初計画'):
    """工程表ノート1件 → 表示用のタスク一覧（計画・当初計画・実績・見込み・進捗・遅れ）"""
    t0 = today or D.today(); hol = holidays()
    fm = json.loads(n['fm']); sid = n['id']
    bl = next((b for b in fm.get('baselines') or [] if b['name'] == base), None)
    btask = {t['id']: t for t in (bl or {}).get('tasks', [])}
    cnt = todo_counts(notes); wk = weekly_of(notes, sid)
    reqs = [json.loads(r['fm']) for r in notes.values() if r['type'] == 'planreq' and json.loads(r['fm']).get('schedule') == sid
            and json.loads(r['fm']).get('decision') == 'requested']
    rows = []
    for t in fm.get('tasks') or []:
        r = dict(t); tid = t['id']; full = f'{sid}#{tid}'
        b = btask.get(tid, {}); r['base'] = b
        ws = wk.get(tid, [])
        if t.get('group'):
            r.update(done=0, total=0, delay=0, weekly=ws, full=full, req=None, todos=[], state='', warn=False); rows.append(r); continue
        for k in ('actual_start', 'actual_end'):   # 本人が週報で確定した日付
            v = [w[k] for w in ws if w.get(k)]; r[k] = d(v[-1]) if v else None
        fc = [w['forecast_end'] for w in ws if w.get('forecast_end')]
        if t.get('milestone'):
            r['date'] = d(t['date']); r['fc'] = r['actual_end'] or (d(fc[-1]) if fc else r['date'])
            r['delay'] = wdays(d(b['date']), r['fc'], hol) if b.get('date') else 0
        else:
            r['start'], r['end'] = d(t['start']), d(t['end'])
            r['fc'] = r['actual_end'] or (d(fc[-1]) if fc else r['end'])
            r['delay'] = wdays(d(b['end']), r['fc'], hol) if b.get('end') else 0
        c = cnt.get(full, {'done': 0, 'total': 0, 'items': []}); r['done'], r['total'], r['todos'] = c['done'], c['total'], c['items']
        r['weekly'] = ws; r['full'] = full
        r['req'] = next((x for x in reqs for ch in x['changes'] if ch['task'] == tid), None)
        # 状態
        if r.get('actual_end'): r['state'] = '完了'
        elif r.get('actual_start'): r['state'] = '実行中'
        else: r['state'] = '未着手'
        late_start = not t.get('milestone') and not r.get('actual_start') and r['start'] < t0
        r['warn'] = r['delay'] > 0 or late_start
        rows.append(r)
    # 見込みを後ろへ伝える（申請と同じ ripple）。本人が見込み・実績を書いたタスクは固定
    plan = fm.get('tasks') or []; fixed = {}
    for r in rows:
        if r.get('group'): continue
        if r.get('milestone'):
            if r['fc'] != r['date']: fixed[r['id']] = {'date': r['fc']}
        elif r.get('actual_start') or r['fc'] != r['end']:
            fixed[r['id']] = {'start': r.get('actual_start') or r['start'], 'end': r['fc']}
    res = ripple(plan, fixed, hol)
    for r in rows:
        if r.get('group') or r['id'] in fixed: continue
        x = res[r['id']]
        if r.get('milestone'): r['fc'] = x['date']
        elif x['start'] != r['start']: r['fs'], r['fc'] = x['start'], x['end']
        b = r.get('base') or {}
        r['delay'] = wdays(d(b['date']), r['fc'], hol) if r.get('milestone') and b.get('date') else wdays(d(b['end']), r['fc'], hol) if b.get('end') else 0
        r['warn'] = r['warn'] or r['delay'] > 0
    # 親（グループ）は子から積み上げ
    def depth(r, k=0):
        p = next((x for x in rows if x['id'] == r.get('parent')), None)
        return depth(p, k + 1) if p and k < 6 else k
    for g in sorted([r for r in rows if r.get('group')], key=depth, reverse=True):     # 深い階層から積み上げる
        ch = [r for r in rows if r.get('parent') == g['id'] and r.get('fc')]
        if not ch: continue
        g['start'] = min(r['start'] for r in ch if 'start' in r); g['end'] = max(r['end'] for r in ch if 'end' in r)
        g['fc'] = max(r['fc'] for r in ch); g['done'] = sum(r['done'] for r in ch); g['total'] = sum(r['total'] for r in ch)
        g['delay'] = max(r['delay'] for r in ch); g['actual_start'] = min([r['actual_start'] for r in ch if r.get('actual_start')] or [None]) if any(r.get('actual_start') for r in ch) else None
        g['actual_end'] = max(r['actual_end'] for r in ch) if all(r.get('actual_end') for r in ch) else None
        g['state'] = '完了' if g['actual_end'] else '実行中' if g['actual_start'] else '未着手'
        own = g.get('base') or {}
        g['base'] = own if own.get('start') and not any(r['base'].get('start') for r in ch) else {'start': min((r['base'].get('start') for r in ch if r['base'].get('start')), default=None),
                     'end': max((r['base'].get('end') for r in ch if r['base'].get('end')), default=None)}
        if own.get('end'): g['delay'] = max(g['delay'], wdays(d(own['end']), g['fc'], hol))
        g['warn'] = any(r['warn'] for r in ch) or g['delay'] > 0
    return rows

def build_roadmap(rn, notes, today=None):
    """ロードマップ項目＋紐づく案件（工程表の見込み）＋関門。案件の見込みが半期をまたいで遅れたら「見直し」"""
    fm = json.loads(rn['fm']); rows = []
    scheds = {json.loads(n['fm']).get('project'): n for n in notes.values() if n['type'] == 'schedule'}
    for it in fm.get('items') or []:
        r = {'id': it['id'], 'name': it['name'], 'start': d(it['start']), 'end': d(it['end']), 'fc': d(it['end']), 'delay': 0,
             'base': {'start': it['start'], 'end': it['end']}, 'done': 0, 'total': 0, 'label2': f"{it.get('status', '')} {it.get('budget', '')}人月"}
        rows.append(r)
        sn = scheds.get(it.get('project'))
        if sn:
            pr = build(sn, notes, today); tasks = [x for x in pr if not x.get('group')]
            st = [x for x in tasks if x.get('start')]
            p = {'id': f"{it['id']}-{it['project']}", 'name': f"{it['project']} の見込み", 'parent': it['id'],
                 'start': min(x['start'] for x in st), 'end': max(x['end'] for x in st), 'fc': max(x['fc'] for x in tasks),
                 'actual_start': min([x['actual_start'] for x in tasks if x.get('actual_start')] or [None]) if any(x.get('actual_start') for x in tasks) else None,
                 'base': {'start': it['start'], 'end': it['end']}, 'done': sum(x['done'] for x in tasks), 'total': sum(x['total'] for x in tasks), 'delay': 0}
            p['label2'] = f"やること {p['done']}/{p['total']}"
            p['delay'] = 0
            if half_start(p['fc']) > half_start(r['end']):          # 半期をまたぐ遅れ
                r['review'] = True; r['label2'] = '見直し ' + r['label2']; r['fc'] = p['fc']
            rows.append(p)
        for i, g in enumerate(it.get('gates') or []):
            rows.append({'id': f"{it['id']}-G{i + 1}", 'name': g['name'], 'milestone': True, 'date': d(g['date']), 'fc': d(g['date']), 'delay': 0,
                         'parent': it['id'], 'base': {}, 'done': 0, 'total': 0})
    return rows

# ---------- 描画（1つだけ） ----------
W, H = 1188, 840          # A4横（1:1.414）
C = {'plan': '#5a6672', 'done': '#2f855a', 'ink': '#1c2631', 'sub': '#5a6672', 'line': '#d5dbe1', 'grid': '#eef1f4', 'base': '#c3cad2', 'act': '#1f6f8b', 'fc': '#1f6f8b',
     'late': '#c0392b', 'today': '#c0392b', 'off': '#f2f4f6', 'req': '#b7791f', 'ms': '#1c2631', 'grp': '#4a5560'}

def layout(title, rows, view, start=None, today=None, sub='', base_label='当初計画', roadmap=False):
    """行データ → 図形の一覧。図形は (種類, 属性dict)。meta に task を入れておくと、書き込みの追従とクリックに使う"""
    t0 = today or D.today(); s, e, cols = period(view, start, t0); hol = holidays()
    P = []; add = lambda k, **a: P.append((k, a))
    L, R, T = 24, W - 24, 24
    LW = 300                                    # 名前の列
    X0, X1 = L + LW, R - 70                    # 棒の領域（右端は遅れ日数）
    span = (e - s).days
    X = lambda x: X0 + (X1 - X0) * (d(x) - s).days / span
    # 見出し
    add('text', x=L, y=T + 18, s=title, size=20, bold=True)
    add('text', x=L, y=T + 40, s=f'{VIEWS[view][0]}（1マス＝{VIEWS[view][1]}） ・ {s}〜{e - datetime.timedelta(1)} ・ {sub}', size=12, color=C['sub'])
    add('text', x=R, y=T + 18, s=f'今日 {t0}', size=12, color=C['sub'], anchor='end')
    # 軸（上段：月・年度、下段：マス）
    HY = T + 56; AY = HY + 40
    top = []
    for a, b in cols:
        key = (a.year, a.month) if view == 'm1' else (a.year, a.month) if view in ('m3', 'm6') else (fy(a),)
        if not top or top[-1][0] != key: top.append([key, a, b])
        else: top[-1][2] = b
    if view in ('m1', 'm3', 'm6'):
        for key, a, b in top:
            x = X(max(a, s)); add('line', x1=x, y1=HY, x2=x, y2=AY, stroke=C['line'])
            if X(min(b, e)) - x >= 64: add('text', x=x + 4, y=HY + 14, s=f'{key[0]}年{key[1]}月', size=12, color=C['sub'])
    nlab = len(cols); fs = 11 if nlab <= 26 else 10
    for i, (a, b) in enumerate(cols):
        x = X(a)
        if view == 'm1' and not workday(a, hol): add('rect', x=x, y=AY - 18, w=X(b) - x, h=0, fill=C['off'], meta={'off': 1})
        add('line', x1=x, y1=AY - 18, x2=x, y2=AY, stroke=C['line'])
        if view != 'm6' or i % 2 == 0:
            add('text', x=(x + X(b)) / 2, y=AY - 5, s=col_label(view, a), size=fs, color=C['ink'] if view != 'm1' or workday(a, hol) else C['late'], anchor='middle')
    add('line', x1=L, y1=AY, x2=R, y2=AY, stroke=C['ink'])
    add('text', x=L, y=AY - 5, s='工程・タスク', size=11, color=C['sub']); add('text', x=L + LW - 8, y=AY - 5, s='担当・やること', size=11, color=C['sub'], anchor='end')
    add('text', x=R, y=AY - 5, s='当初比', size=11, color=C['sub'], anchor='end')
    if roadmap: P[-1][1]['s'] = '目標比'
    # 行：
    #  ・親を持たない節目は一番上の1行にまとめ、名前を◆の横に書く
    #  ・グループの子が一直線の流れ（設計検討→まとめ→詳細設計→小DR…）なら、グループの1行に区切って並べる（レーン）
    #  ・それ以外は1行1タスク
    by = {r['id']: r for r in rows}
    lane_of = {}                                   # 子ID → グループID（1行にまとめる子）
    for g in [r for r in rows if r.get('group') and not r.get('expand')]:
        ch = [r for r in rows if r.get('parent') == g['id']]
        if len(ch) < 2: continue
        ok_ = all((ch[i].get('after') or []) == [ch[i - 1]['id']] for i in range(1, len(ch)))
        ok_ &= len({r.get('owner') for r in ch if not r.get('milestone') and not r.get('group')}) <= 1
        if ok_:
            for r in ch: lane_of[r['id']] = g['id']
    msr = [r for r in rows if r.get('milestone') and not r.get('hidden') and r['id'] not in lane_of]
    shown = [r for r in rows if not r.get('milestone') and not r.get('hidden') and r['id'] not in lane_of]
    rh = max(18, min(30, (H - AY - 60) / max(1, len(shown) + (1.5 if msr else 0))))
    ymap, hits = {}, []
    y0 = AY

    def draw_ms(r, mid, big=True):
        meta = {'task': r['id']}; b = r.get('base') or {}; rr = 7 if big else 6
        if b.get('date') and d(b['date']) != r['date'] and s <= d(b['date']) < e:
            add('diamond', x=X(b['date']), y=mid, r=rr - 1, fill='none', stroke=C['base'], meta=meta)
        if r.get('actual_end'):
            if s <= r['actual_end'] < e: add('diamond', x=X(r['actual_end']), y=mid, r=rr, fill=C['done'], meta=meta)
        else:
            if s <= r['date'] < e: add('diamond', x=X(r['date']), y=mid, r=rr, fill=C['ms'] if r['fc'] == r['date'] else 'none', stroke=C['ms'], meta=meta)
            if r['fc'] != r['date'] and s <= r['fc'] < e: add('diamond', x=X(r['fc']), y=mid, r=rr, fill=C['late'], meta=meta)
        rq = next((c for c in (r.get('req') or {}).get('changes', []) if c['task'] == r['id']), None)
        if rq and s <= d(rq['date']) < e: add('diamond', x=X(rq['date']), y=mid, r=rr + 2, fill='none', stroke=C['req'], dash=True, meta={**meta, 'req': 1})

    def draw_bar(r, mid, label=None):
        meta = {'task': r['id']}; b = r.get('base') or {}
        if b.get('start'):
            bs, be = max(d(b['start']), s), min(d(b['end']) + datetime.timedelta(1), e)
            if bs < be: add('rect', x=X(bs), y=mid + rh * 0.2, w=X(be) - X(bs), h=rh * 0.16, fill=C['base'], meta=meta)
        g = bool(r.get('group')) and label is None; top, hh = (mid - rh * 0.1, rh * 0.2) if g else (mid - rh * 0.28, rh * 0.42)
        p1, p2 = max(r['start'], s), min(r['end'] + datetime.timedelta(1), e)          # 今の計画（枠）
        if p1 < p2: add('rect', x=X(p1), y=top, w=X(p2) - X(p1), h=hh, fill='#fff' if not g else C['grid'], stroke=C['plan'], sw=1, meta={**meta, 'plan': 1})
        if r.get('actual_start'):                                                       # 実績（塗り）
            a1 = r['actual_start']; a2 = (r['actual_end'] + datetime.timedelta(1)) if r.get('actual_end') else max(t0, a1 + datetime.timedelta(1))
            a1, a2 = max(a1, s), min(a2, e)
            if a1 < a2: add('rect', x=X(a1), y=top, w=X(a2) - X(a1), h=hh, fill=C['grp'] if g else C['act'], meta=meta)
        if not r.get('actual_end') and r['fc'] > r['end'] or r.get('fs'):              # 見込みの遅れ（赤の点線）
            f1 = r['fs'] if r.get('fs') else r['end'] + datetime.timedelta(1)
            f1, f2 = max(f1, s), min(r['fc'] + datetime.timedelta(1), e)
            if f1 < f2: add('rect', x=X(f1), y=top, w=X(f2) - X(f1), h=hh, fill='none', stroke=C['late'], dash=True, sw=1.5, meta=meta)
        rq = next((c for c in (r.get('req') or {}).get('changes', []) if c['task'] == r['id']), None)
        if rq:
            q1, q2 = max(d(rq['start']), s), min(d(rq['end']) + datetime.timedelta(1), e)
            if q1 < q2: add('rect', x=X(q1), y=mid - rh * 0.4, w=X(q2) - X(q1), h=rh * 0.62, fill='none', stroke=C['req'], dash=True, sw=2, meta={**meta, 'req': 1})
        if label and p1 < p2:                     # レーンの区切りの名前（棒の上。入らなければ省略）
            wpx = X(p2) - X(p1); fs = 9
            txt = label if fs * len(label) <= wpx + 6 else label[:max(1, int((wpx + 6) // fs) - 1)] + '…' if wpx > 2 * fs else ''
            if txt: add('text', x=X(p1) + 2, y=top - 2, s=txt, size=fs, color=C['sub'], meta=meta)

    if msr:
        mh = rh * 1.5; mid = AY + mh / 2
        add('rect', x=L, y=AY, w=R - L, h=mh, fill='#f6f8fa')
        add('text', x=L + 4, y=mid + 4, s='節目', size=12, bold=True, color=C['grp'])
        busy = [[], []]          # 名前の重なりを避ける（上下2段）
        for r in sorted(msr, key=lambda r: r.get('actual_end') or r['fc']):
            ymap[r['id']] = AY; meta = {'task': r['id']}
            draw_ms(r, mid)
            at = r.get('actual_end') or r['fc']
            if not (s <= at < e): continue
            x = X(at); dl = r.get('delay', 0)
            lab = f"{r['name']} {at.month}/{at.day}" + (' 済' if r.get('actual_end') else f' +{dl}日' if dl > 0 else '')
            wdt = 11 * len(lab) + 4
            lv = next((k for k in (0, 1) if all(x + 10 > b2 or x + 10 + wdt < a2 for a2, b2 in busy[k])), 0)
            busy[lv].append((x + 10, x + 10 + wdt))
            left = x + 10 + wdt > R            # 右端からはみ出すなら◆の左に書く
            add('text', x=x - 10 if left else x + 10, y=mid - 3 if lv == 0 else mid + 11, s=lab, size=11, bold=True, anchor='end' if left else 'start',
                color=C['done'] if r.get('actual_end') else C['late'] if dl > 0 else C['ink'], meta=meta)
            hits.append((r['id'], x - 9, AY, wdt + 20, mh))
        y0 = AY + mh
    if lane_of: rh = max(rh, 24)                   # 区切りの名前を書く分、少し高く
    for i, r in enumerate(shown):
        y = y0 + i * rh; ymap[r['id']] = y; mid = y + rh / 2 + (3 if r['id'] in lane_of.values() else 0); meta = {'task': r['id']}
        hits.append((r['id'], L, y, R - L, rh))
        if i % 2: add('rect', x=L, y=y, w=R - L, h=rh, fill='#fafbfc')
        lane = [x for x in rows if lane_of.get(x['id']) == r['id']]
        ind = 14 if r.get('parent') else 0
        nm = r['name'] + (f'（{len(lane)}工程）' if lane else '')
        name = nm if len(nm) <= 18 else nm[:17] + '…'
        add('text', x=L + 4 + ind, y=mid + 4, s=name, size=12, bold=bool(r.get('group')), color=C['grp'] if r.get('group') else C['ink'], meta={**meta, 'name': 1})
        add('text', x=L + LW - 74, y=mid + 4, s=r.get('owner_ja', '') or (lane[0].get('owner_ja', '') if lane else ''), size=11, color=C['sub'], anchor='end')
        if r.get('label2'):
            add('text', x=L + LW - 8, y=mid + 4, s=r['label2'], size=11, color=C['late'] if r.get('review') else C['sub'], anchor='end', bold=bool(r.get('review')))
        elif r.get('total') or not r.get('group'):
            lab = f"{r['done']}/{r['total']}" if r.get('total') else '0/0 未分解'
            add('text', x=L + LW - 8, y=mid + 4, s=lab, size=11, color=C['sub'] if r.get('total') else C['req'], anchor='end')
            if r.get('total'):
                add('rect', x=L + LW - 68, y=mid - 3, w=24, h=5, fill=C['grid'])
                add('rect', x=L + LW - 68, y=mid - 3, w=24 * r['done'] / r['total'], h=5, fill=C['act'])
        if lane:
            gb = r.get('base') or {}
            if gb.get('start') and not any((x.get('base') or {}).get('start') for x in lane):   # 分解前の当初計画をレーン全体の影に
                bs, be = max(d(gb['start']), s), min(d(gb['end']) + datetime.timedelta(1), e)
                if bs < be: add('rect', x=X(bs), y=mid + rh * 0.2, w=X(be) - X(bs), h=rh * 0.16, fill=C['base'], meta=meta)
            for x_ in lane:
                ymap[x_['id']] = y
                if x_.get('milestone'):
                    draw_ms(x_, mid, big=False)
                    at = x_.get('actual_end') or x_['fc']
                    if s <= at < e: add('text', x=X(at), y=mid - rh * 0.3 - 2, s=x_['name'], size=9, color=C['sub'], anchor='middle', meta={'task': x_['id']})
                else: draw_bar(x_, mid, label=x_['name'])
        else: draw_bar(r, mid)
        st, en = (r.get('actual_start') or r.get('start'), r.get('fc'))
        if st and st >= e: add('text', x=X1 - 2, y=mid + 4, s=f'{st.month}/{st.day}〜 ▶', size=11, color=C['sub'], anchor='end', meta=meta)
        elif en and en < s: add('text', x=X0 + 2, y=mid + 4, s=f'◀ 〜{en.month}/{en.day}', size=11, color=C['sub'], meta=meta)
        if r.get('delay'):
            add('text', x=R, y=mid + 4, s=f"{'+' if r['delay'] > 0 else ''}{r['delay']}日", size=11, bold=r['delay'] > 0, color=C['late'] if r['delay'] > 0 else C['act'], anchor='end', meta=meta)
    yend = y0 + len(shown) * rh
    # 依存の矢印（レーンの中は引かない）
    for r in rows:
        if r.get('group') or r.get('milestone') or r['id'] not in ymap: continue
        for p in r.get('after') or []:
            q = by.get(p)
            if not q or q['id'] not in ymap or q.get('milestone') or q.get('group'): continue   # 節目は上の行にまとめたので矢印は引かない
            if lane_of.get(p) and lane_of.get(p) == lane_of.get(r['id']): continue      # 同じレーンの中は区切りで分かる
            pe = (q['fc'] if q.get('milestone') else q['fc'] + datetime.timedelta(1)); rs = r.get('date') or r.get('start')
            if not (s <= pe <= e and s <= rs <= e): continue
            x1, x2 = X(pe), X(rs); y1, y2 = ymap[p] + rh / 2, ymap[r['id']] + rh / 2
            add('path', pts=[(x1, y1), (x1 + 4, y1), (x1 + 4, y2 - rh * 0.3)] if x2 <= x1 + 4 else [(x1, y1), (x1 + 4, y1), (x1 + 4, y2), (x2, y2)], stroke='#9aa3ad', arrow=True)
    # 週末の網掛け（行の領域まで伸ばす）と今日線
    for k, a in P:
        if k == 'rect' and (a.get('meta') or {}).get('off'): a['h'] = yend - a['y']
    if s <= t0 < e: add('line', x1=X(t0), y1=AY - 18, x2=X(t0), y2=yend, stroke=C['today'], sw=1.5); add('text', x=X(t0), y=yend + 14, s='今日', size=11, color=C['today'], anchor='middle')
    add('line', x1=L, y1=yend, x2=R, y2=yend, stroke=C['line'])
    # 凡例（行のすぐ下）
    lx, ly = L, yend + 34
    items = [('rect', dict(w=26, h=5, fill=C['base'], dy=-6), base_label), ('rect', dict(w=26, h=11, fill='#fff', stroke=C['plan'], dy=-11), '今の計画'),
             ('rect', dict(w=26, h=11, fill=C['act'], dy=-11), '実績'), ('rect', dict(w=26, h=11, fill='none', stroke=C['late'], dash=True, dy=-11), '見込みの遅れ'),
             ('rect', dict(w=26, h=11, fill='none', stroke=C['req'], dash=True, sw=2, dy=-11, meta={'req': 1}), '申請中')]
    for k, a, lab in items:
        dy = a.pop('dy'); add(k, x=lx, y=ly + dy, **a); add('text', x=lx + 30, y=ly, s=lab, size=11, color=C['sub'], meta=a.get('meta')); lx += 40 + 12 * len(lab)
    for fill, stroke, lab in [('none', C['base'], '当初'), (C['ms'], C['ms'], '計画'), (C['late'], C['late'], '見込み'), (C['done'], C['done'], '済')]:
        add('diamond', x=lx + 6, y=ly - 5, r=6, fill=fill, stroke=stroke); add('text', x=lx + 16, y=ly, s=lab, size=11, color=C['sub']); lx += 28 + 12 * len(lab)
    if not roadmap: add('text', x=lx + 8, y=ly, s='3/8＝やることの完了/総数 ・ 当初比＝実働日', size=11, color=C['sub'])
    starts = {r['id']: str(r.get('actual_start') or r.get('start') or r.get('date')) for r in rows if r['id'] in ymap}
    spans = {}   # 棒の左右の端（書き込みが「棒の近く」かの判定用）
    for k, a in P:
        t = (a.get('meta') or {}).get('task')
        if not t or k not in ('rect', 'diamond'): continue
        x1, x2 = (a['x'], a['x'] + a['w']) if k == 'rect' else (a['x'] - a['r'], a['x'] + a['r'])
        sp = spans.setdefault(t, [x1, x2]); sp[0] = min(sp[0], x1); sp[1] = max(sp[1], x2)
    geo = {'s': str(s), 'e': str(e), 'x0': X0, 'x1': X1, 'ay': AY, 'yend': yend, 'rh': rh, 'rows': ymap, 'starts': starts, 'spans': spans, 'view': view,
           'h': max(360, int(yend + 50)), 'hits': hits}
    return P, geo

def to_svg(P, geo, cls='gantt', interactive=False, crop=True):
    """crop：Web閲覧・画像保存は行の下で切る（PDF・Excalidrawは A4 のまま）"""
    HH = geo['h'] if crop else H
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {HH}" class="{cls}" data-geo="{esc(json.dumps(geo))}" font-family="BIZ UDPGothic, Hiragino Sans, sans-serif">',
         '<defs><marker id="ga" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="#9aa3ad"/></marker></defs>',
         f'<rect width="{W}" height="{HH}" fill="#fff"/>']
    for k, a in P:
        m = a.get('meta') or {}; cl = ' '.join(k for k in ('req', 'plan', 'name') if m.get(k))
        da = (f' data-task="{m["task"]}"' if m.get('task') and interactive else '') + (f' class="{cl}"' if cl else '')
        if k == 'rect':
            dash = ' stroke-dasharray="4 3"' if a.get('dash') else ''
            o.append(f'<rect x="{a["x"]:.1f}" y="{a["y"]:.1f}" width="{max(a["w"], 0):.1f}" height="{max(a["h"], 0):.1f}" rx="2" fill="{a.get("fill", "none")}" stroke="{a.get("stroke", "none")}" stroke-width="{a.get("sw", 1)}"{dash}{da}/>')
        elif k == 'line':
            o.append(f'<line x1="{a["x1"]:.1f}" y1="{a["y1"]:.1f}" x2="{a["x2"]:.1f}" y2="{a["y2"]:.1f}" stroke="{a["stroke"]}" stroke-width="{a.get("sw", 1)}"/>')
        elif k == 'path':
            o.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in a["pts"])}" fill="none" stroke="{a["stroke"]}" stroke-width="1" marker-end="url(#ga)"/>')
        elif k == 'diamond':
            x, y, r = a['x'], a['y'], a['r']
            o.append(f'<path d="M{x:.1f},{y - r:.1f}L{x + r:.1f},{y:.1f}L{x:.1f},{y + r:.1f}L{x - r:.1f},{y:.1f}Z" fill="{a.get("fill")}" stroke="{a.get("stroke", a.get("fill"))}" stroke-width="1.5"{da}/>')
        elif k == 'text':
            o.append(f'<text x="{a["x"]:.1f}" y="{a["y"]:.1f}" font-size="{a["size"]}" fill="{a.get("color", C["ink"])}" text-anchor="{a.get("anchor", "start")}"{" font-weight=\"700\"" if a.get("bold") else ""}{da}>{esc(a["s"])}</text>')
    if interactive:   # 押せる範囲（作業は行全体、節目は◆と名前のまわり）。棒より下に敷く
        hit = ''.join(f'<rect class="hit" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="transparent" data-task="{t}"/>' for t, x, y, w, h in geo['hits'])
        o.insert(3, hit)
    o.append('</svg>')
    return ''.join(o)

# ---------- Excalidraw へ書き出し（書き込みは残し、付き先に合わせて動かす） ----------
def _xid(): return secrets.token_hex(8)

def to_excalidraw(P, geo, old_elements, frame_name):
    keep = [e for e in old_elements if not (e.get('customData') or {}).get('kvGen') and e['type'] != 'frame']
    old_frame = next((e for e in old_elements if e['type'] == 'frame'), None)
    og = (old_frame or {}).get('customData', {}).get('geo')
    fr = {'id': (old_frame or {}).get('id') or _xid(), 'type': 'frame', 'x': 0, 'y': 0, 'width': W, 'height': H, 'name': frame_name,
          'customData': {'kvFrame': 'F01', 'geo': geo}}
    els = [fr]
    base = {'strokeWidth': 1, 'roughness': 0, 'opacity': 100, 'frameId': fr['id']}
    for k, a in P:
        cd = {'kvGen': True, **(a.get('meta') or {})}
        if k == 'rect':
            els.append({**base, 'id': _xid(), 'type': 'rectangle', 'x': a['x'], 'y': a['y'], 'width': max(a['w'], 0), 'height': max(a['h'], 0),
                        'backgroundColor': 'transparent' if a.get('fill', 'none') == 'none' else a['fill'], 'fillStyle': 'solid',
                        'strokeColor': a.get('stroke', 'transparent') if a.get('stroke') not in (None, 'none') else 'transparent',
                        'strokeStyle': 'dashed' if a.get('dash') else 'solid', 'strokeWidth': a.get('sw', 1), 'customData': cd})
        elif k in ('line', 'path'):
            pts = [(a['x1'], a['y1']), (a['x2'], a['y2'])] if k == 'line' else a['pts']
            els.append({**base, 'id': _xid(), 'type': 'arrow' if a.get('arrow') else 'line', 'x': pts[0][0], 'y': pts[0][1],
                        'points': [[x - pts[0][0], y - pts[0][1]] for x, y in pts], 'strokeColor': a['stroke'], 'customData': cd})
        elif k == 'diamond':
            els.append({**base, 'id': _xid(), 'type': 'diamond', 'x': a['x'] - a['r'], 'y': a['y'] - a['r'], 'width': 2 * a['r'], 'height': 2 * a['r'],
                        'backgroundColor': 'transparent' if a.get('fill') == 'none' else a['fill'], 'fillStyle': 'solid', 'strokeColor': a.get('stroke', a.get('fill')), 'customData': cd})
        elif k == 'text':
            wdt = a['size'] * 0.95 * len(a['s']); x = a['x'] - (wdt if a.get('anchor') == 'end' else wdt / 2 if a.get('anchor') == 'middle' else 0)
            els.append({**base, 'id': _xid(), 'type': 'text', 'x': x, 'y': a['y'] - a['size'], 'width': wdt, 'height': a['size'] * 1.25, 'text': a['s'],
                        'fontSize': a['size'], 'fontFamily': 2, 'strokeColor': a.get('color', C['ink']), 'customData': cd,
                        'textAlign': {'end': 'right', 'middle': 'center'}.get(a.get('anchor'), 'left')})
    # 書き込みの付き先を判定（初回）し、新しい配置へ動かす
    out_cnt, lost = 0, 0
    s1, e1 = d(geo['s']), d(geo['e'])
    X = lambda x: geo['x0'] + (geo['x1'] - geo['x0']) * (d(x) - s1).days / (e1 - s1).days
    groups = {}
    for e in keep: groups.setdefault((e.get('groupIds') or [e['id']])[0], []).append(e)
    for gid, es in groups.items():
        cd0 = es[0].get('customData') or {}
        anc = cd0.get('anchor')
        gx, gy = min(e['x'] for e in es), min(e['y'] for e in es)
        if not anc:
            anc = {'kind': 'sheet'}
            if og:
                s0, e0 = d(og['s']), d(og['e'])
                X0 = lambda x: og['x0'] + (og['x1'] - og['x0']) * (d(x) - s0).days / (e0 - s0).days
                inside = og['x0'] <= gx <= og['x1'] and og['ay'] <= gy <= og['yend'] + 20
                sp = og.get('spans', {})
                near = [(abs(gy - (y + og['rh'] / 2)), t, y) for t, y in og['rows'].items()
                        if t in sp and sp[t][0] - 40 <= gx <= sp[t][1] + 40]       # 棒の近く（左右40px以内）
                near.sort()
                day = s0 + datetime.timedelta(days=round((gx - og['x0']) / (og['x1'] - og['x0']) * (e0 - s0).days))
                if inside and near and near[0][0] < og['rh'] * 1.2:
                    tk = near[0][1]; st0 = d(og.get('starts', {}).get(tk, str(day)))
                    anc = {'kind': 'task', 'task': tk, 'off': (day - st0).days, 'dy': gy - near[0][2]}   # タスクの開始からの日数で覚える
                elif inside:
                    anc = {'kind': 'date', 'date': str(day), 'y': gy}
        if anc['kind'] == 'sheet': nx, ny = gx, gy; vis = True
        elif anc['kind'] == 'task':
            if anc['task'] not in geo['rows']: lost += 1; vis = None; nx, ny = gx, gy
            else:
                at = d(geo['starts'][anc['task']]) + datetime.timedelta(days=anc['off'])
                vis = s1 <= at < e1
                nx, ny = X(at), geo['rows'][anc['task']] + anc['dy']
        else:
            vis = s1 <= d(anc['date']) < e1; nx, ny = X(anc['date']), anc['y']
        if vis is False: out_cnt += 1
        for e in es:
            e['x'] += nx - gx; e['y'] += ny - gy
            c = e.setdefault('customData', {}); c['anchor'] = anc
            if not vis: c.setdefault('op', e.get('opacity', 100)); e['opacity'] = 0
            elif 'op' in c: e['opacity'] = c.pop('op')
            e['frameId'] = fr['id']
    if out_cnt or lost:
        msg = '・'.join(x for x in [f'範囲外のコメント {out_cnt} 件' if out_cnt else '', f'行き先のないコメント {lost} 件' if lost else ''] if x)
        els.append({**base, 'id': _xid(), 'type': 'text', 'x': 24, 'y': H - 22, 'width': 300, 'height': 15, 'text': msg, 'fontSize': 12, 'fontFamily': 2,
                    'strokeColor': C['req'], 'customData': {'kvGen': True}})
    return els + keep
