"""dotpm（Obsidian の工程管理プラグイン）の形式と、工程表（type: schedule の tasks）の行き来

案件リポジトリの直下に dotpm の形で置く（取りまとめ役の vault では 20_工程/<案件>/ に入る）：
  <案件>.md            プロジェクト（pm-project: true）
  _tasks/<名前>.md      タスク1件1ファイル（pm-task: true）

dotpm が使う名前（id・title・status・type・progress など）は dotpm のもの。こちらの番号・見積は dotpm が触らない項目に持つ：
  task_no   工程タスクの番号（T02、M01、G1）。ガント・週報・[task:: 工程表ID#T02] の紐づけはこれを使う
  est       見積（人日）  alloc  割当率%  note  まとめのノート
変更の理由は、プロジェクトの独自項目（customFields）「変更理由」「理由の区分」に書く。
"""
import os, re, glob, datetime, yaml

TASKS = '_tasks'
REASON_FIELDS = [
    {'id': 'reason', 'name': '変更理由', 'type': 'text'},
    {'id': 'code', 'name': '理由の区分', 'type': 'select',
     'options': ['見積の誤り', '仕様変更', '外部待ち（部品・外注・顧客）', '不具合・やり直し', '人の都合（他案件・休み）', 'その他']},
]
OURS = ('task_no', 'est', 'alloc', 'note', 'expand', 'target')   # dotpm の外の項目（そのまま残る）

def _fm(p):
    t = open(p, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', t, re.S)
    return (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, t)

def _write(p, fm, body=''):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write('---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + '\n---\n' + body)

def ds(x):
    return '' if x in (None, '') else str(x)[:10]

def project_file(root):
    """案件リポジトリ（root）の dotpm プロジェクト（無ければ None）"""
    for p in glob.glob(os.path.join(root, '*.md')):
        if _fm(p)[0].get('pm-project') is True: return p
    return None

def read(root):
    """dotpm のタスクを読む → [{file, fm, body}]（アーカイブも含めて全部）"""
    out = []
    for p in sorted(glob.glob(os.path.join(root, TASKS, '**', '*.md'), recursive=True)):
        fm, body = _fm(p)
        if fm.get('pm-task') is True: out.append({'file': p, 'fm': fm, 'body': body})
    return out

def _resolver(items):
    """dotpm の参照（id・[[名前]]・[[パス|表示]]）→ dotpm の id"""
    by = {}
    for it in items:
        i = str(it['fm'].get('id')); by[i] = i
        stem = os.path.basename(it['file'])[:-3]; by[stem] = i
    def res(v):
        if v in (None, ''): return None
        s = str(v).strip()
        m = re.match(r'^\[\[([^\]|#]+)', s)
        if m: s = os.path.basename(m.group(1)).removesuffix('.md')
        return by.get(s)
    return res

def to_plan(items):
    """dotpm のタスク → 工程表の tasks（task_no のないものは '?<dotpmのid>' のまま返す）。アーカイブは計画から外れたものとして扱う"""
    items = [it for it in items if '/Archive/' not in it['file'].replace(os.sep, '/')]
    res = _resolver(items); no = {}
    for it in items: no[str(it['fm']['id'])] = it['fm'].get('task_no') or f"?{it['fm']['id']}"
    parents = {res(it['fm'].get('parentId')) for it in items} - {None}
    plan = []
    for it in items:
        f = it['fm']; did = str(f['id'])
        t = {'id': no[did], 'name': str(f.get('title') or '')}
        if did in parents: t['group'] = True
        elif f.get('type') == 'milestone': t.update(milestone=True, date=ds(f.get('due') or f.get('start')))
        else: t.update(start=ds(f.get('start')), end=ds(f.get('due')))
        own = [a for a in f.get('assignees') or [] if a]
        if own and not t.get('group'): t['owner'] = str(own[0])
        after = [no[x] for x in (res(d) for d in f.get('dependencies') or []) if x]
        if after: t['after'] = after
        par = res(f.get('parentId'))
        if par: t['parent'] = no[par]
        for k in ('est', 'alloc', 'note', 'expand', 'target'):
            if f.get(k) not in (None, ''): t[k] = f[k]
        plan.append({k: v for k, v in t.items() if v not in ('', None, [])})
    return plan

def reasons(items):
    """タスクに書かれた変更理由（区分, 理由）。無ければ (None, None)"""
    codes, texts = [], []
    for it in items:
        cf = it['fm'].get('customFields') or {}
        if cf.get('code'): codes.append(str(cf['code']))
        if cf.get('reason'): texts.append(f"{it['fm'].get('title')}：{cf['reason']}")
    return (codes[0] if codes else None), ('／'.join(dict.fromkeys(texts)) or None)

def slug(s):
    return re.sub(r'[\\/:*?"<>|#^\[\]]', '_', s).strip()[:60] or 'task'

def write_plan(root, pid, title, plan, keep_reason=False):
    """工程表の tasks → dotpm のファイル（既にあるタスクは dotpm の id・状態・独自項目を残して、計画の項目だけ書き換える）"""
    items = read(root); by_no = {it['fm'].get('task_no'): it for it in items if it['fm'].get('task_no')}
    pf = project_file(root) or os.path.join(root, f'{pid}.md')
    pfm, pbody = _fm(pf) if os.path.exists(pf) else ({}, '')
    now = datetime.datetime.now().isoformat(timespec='seconds')
    did = {t['id']: (str(by_no[t['id']]['fm']['id']) if t['id'] in by_no else f"{pid}-{t['id']}") for t in plan}
    pfm.update({'pm-project': True, 'id': pfm.get('id') or pid, 'title': pfm.get('title') or title,
                'taskIds': [did[t['id']] for t in plan if not t.get('parent')],
                'teamMembers': sorted({t['owner'] for t in plan if t.get('owner')} | set(pfm.get('teamMembers') or []))})
    have = {f['id'] for f in pfm.get('customFields') or []}
    pfm['customFields'] = list(pfm.get('customFields') or []) + [f for f in REASON_FIELDS if f['id'] not in have]
    pfm.setdefault('createdAt', now); pfm['updatedAt'] = now
    _write(pf, pfm, pbody or f'# {title}\n\n工程表（計画）。日程は dotpm のガントで直す。承認が要る変更は、タスクの「変更理由」「理由の区分」を書いてから保存する。\n')
    keep = set()
    for t in plan:
        old = by_no.get(t['id']); fm = dict(old['fm']) if old else {}
        kids = [did[x['id']] for x in plan if x.get('parent') == t['id']]
        fm.update({'pm-task': True, 'projectId': pfm['id'], 'parentId': did.get(t.get('parent')) if t.get('parent') else None,
                   'id': did[t['id']], 'title': t['name'],
                   'type': 'milestone' if t.get('milestone') else ('subtask' if t.get('parent') else 'task'),
                   'status': fm.get('status') or 'todo', 'priority': fm.get('priority') or 'medium',
                   'start': ds(t.get('date') if t.get('milestone') else t.get('start')),
                   'due': ds(t.get('date') if t.get('milestone') else t.get('end')),
                   'progress': fm.get('progress') or 0,
                   'assignees': [t['owner']] if t.get('owner') else [], 'tags': fm.get('tags') or [],
                   'subtaskIds': kids, 'dependencies': [did[a] for a in t.get('after') or [] if a in did],
                   'createdAt': fm.get('createdAt') or now, 'updatedAt': now, 'task_no': t['id']})
        if t.get('group'): fm['start'] = fm['due'] = ''   # まとめ（グループ）の期間は子から積み上げる
        for k in ('est', 'alloc', 'note', 'expand', 'target'):
            if t.get(k) not in (None, ''): fm[k] = t[k]
            else: fm.pop(k, None)
        if not keep_reason and fm.get('customFields'):
            fm['customFields'] = {k: v for k, v in fm['customFields'].items() if k not in ('reason', 'code')}
            if not fm['customFields']: fm.pop('customFields')
        p = old['file'] if old else os.path.join(root, TASKS, f"{slug(t['name'])}_{t['id']}.md")
        _write(p, fm, old['body'] if old else ''); keep.add(os.path.abspath(p))
    for it in items:   # 計画にないタスク（却下された追加など）は消す
        if os.path.abspath(it['file']) not in keep and '/Archive/' not in it['file'].replace(os.sep, '/'): os.remove(it['file'])
    return pf

def set_task_no(root, mapping):
    """dotpm で足されたタスク（dotpm の id → 新しい番号）に task_no を書く"""
    for it in read(root):
        n = mapping.get(str(it['fm'].get('id')))
        if n: it['fm']['task_no'] = n; _write(it['file'], it['fm'], it['body'])

def clear_reasons(root):
    for it in read(root):
        cf = it['fm'].get('customFields') or {}
        if 'reason' in cf or 'code' in cf:
            cf = {k: v for k, v in cf.items() if k not in ('reason', 'code')}
            if cf: it['fm']['customFields'] = cf
            else: it['fm'].pop('customFields', None)
            _write(it['file'], it['fm'], it['body'])
