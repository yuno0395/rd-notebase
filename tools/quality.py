"""確定の流れ（必須項目・承認後の変更・ゲート）と、要求の対応表（一本の糸）

■ 必須項目（台帳 config/registry.yml の required）
  下書き（status: draft）は何も強制しない。status を review（レビュー待ち）・approved にした時だけ、種類ごとの必須の節・項目を
  push の検査で確かめて止める（progress を レビュー待ち・完了 にした時は警告だけ）。
■ 承認後の変更
  文書の承認は、承認ノートに書いた版（version）に対して有効。承認した後に中身を変えると「承認後に変更あり（再承認が必要）」
■ ゲート（type: gate）
  案件の節目（dotpm の M02 など）に、出すべき資料をリンクで並べる（items）。全部が承認済み（承認後の変更なし）で「準備完了」。
  ゲートそのものの通過は、案件の責任者が承認ノートで判断する
■ 要求の対応表
  要求（type: req）← 設計（derived_from: [[要求]]）・試験（type: test、verifies: [[要求]]、test_result）・不具合（type: issue、affects）。
  設計がない・試験がない・不合格・試験の後に要求が変わった（再検証が必要）を目立たせる
"""
import os, re, json, subprocess, datetime
import kv

STATUS_CHECK = ('review', 'approved')
PROGRESS_CHECK = ('レビュー待ち', '完了')

def checking(fm):
    return fm.get('status') in STATUS_CHECK or fm.get('progress') in PROGRESS_CHECK

def section_text(body, names):
    """見出し（names のどれか）の下の文（次の同じか上の見出しまで）。コメントと空の箇条書きは除く。見出しがなければ None"""
    text = kv.text_part(body or '')
    lines = text.split('\n')
    for i, l in enumerate(lines):
        m = re.match(r'^(#{1,6})\s*(.+?)\s*$', l)
        if not m or m.group(2) not in names: continue
        lv = len(m.group(1)); out = []
        for l2 in lines[i + 1:]:
            m2 = re.match(r'^(#{1,6})\s', l2)
            if m2 and len(m2.group(1)) <= lv: break
            out.append(l2)
        s = re.sub(r'<!--.*?-->', '', '\n'.join(out), flags=re.S)
        s = '\n'.join(x for x in s.split('\n') if x.strip() not in ('', '-', '- [ ]', '1.', '2.', '3.'))
        return s.strip()
    return None

def required_errors(fn, fm, body, r):
    """必須項目の検査 → (拒否, 警告)。status（review・approved）で止める。progress（レビュー待ち・完了）は警告だけ（以前からのノートで push が止まらないように）"""
    if not checking(fm): return [], []
    req = (r.get('required') or {}).get(fm.get('type') or '')
    if not req: return [], []
    errs = []; why = f"status {fm.get('status')}" if fm.get('status') in STATUS_CHECK else f"progress {fm.get('progress')}"
    for sec in req.get('sections') or []:
        names = sec.split('|'); s = section_text(body, names)
        if not s: errs.append(f"{fn}: 「{names[0]}」の節が{'ありません' if s is None else '空です'}（{why} の時は必須）")
    for p in req.get('props') or []:
        if fm.get(p) in (None, '', []): errs.append(f"{fn}: プロパティ「{p}」が空です（{why} の時は必須）")
    return (errs, []) if fm.get('status') in STATUS_CHECK else ([], errs)

# ---------- 承認後の変更 ----------
def _norm(text):
    fm, body = kv.split_fm(text or '')
    for k in ('status', 'updated', 'progress', 'next'): fm.pop(k, None)   # 状態の書き換えだけは変更に数えない
    return json.dumps(fm, sort_keys=True, ensure_ascii=False, default=str) + '\n' + (body or '').strip()

def changed_since(vault, nid, path_now, ver):
    """承認した版（ver）から中身が変わったか。調べられない時は None"""
    if not ver: return None
    bare = kv.bare_of(vault); ref = kv.index_ref(bare)
    g = lambda *a: subprocess.run(['git', f'--git-dir={bare}', '-c', 'core.quotepath=off', *a], capture_output=True, text=True, encoding='utf-8', errors='replace')
    hit = g('grep', '-l', f'^id: {nid}$', ver, '--', '*.md')
    if hit.returncode or not hit.stdout.strip(): return None
    old = hit.stdout.strip().split('\n')[0].split(':', 1)[1]
    a, b = g('show', f'{ver}:{old}'), g('show', f'{ref}:{path_now}')
    if a.returncode or b.returncode: return None
    return _norm(a.stdout) != _norm(b.stdout)

def last_changes(bare, ref):
    """各ファイルを最後に変えた日時 {パス: ISO 日時}（1回の git log で）"""
    out = subprocess.run(['git', f'--git-dir={bare}', '-c', 'core.quotepath=off', 'log', '--format=@%cI', '--name-only', ref],
                         capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    res, at = {}, None
    for l in out.splitlines():
        if l.startswith('@'): at = l[1:]
        elif l.strip() and l not in res: res[l] = at
    return res

# ---------- ゲート ----------
def gate_state(g, notes, byname):
    """ゲート → (状態, [(項目名, ノート or None, 状態)])。状態：通過・準備完了・準備中"""
    fm = json.loads(g['fm']); items = []
    for it in fm.get('items') or []:
        n = byname.get(kv.link_key(str(it)))
        if not n: items.append((kv.link_key(str(it)), None, '見つからない')); continue
        f = json.loads(n['fm'])
        st = ('承認後に変更あり' if f.get('approved_changed') else '承認済み') if f.get('approval') and f.get('status') == 'approved' or (f.get('approval') and f.get('approved_changed')) else \
             ('レビュー待ち' if n.get('status') == 'review' or n.get('progress') == 'レビュー待ち' else '未承認')
        items.append((n['title'], n, st))
    ready = items and all(s == '承認済み' for _, _, s in items)
    passed = fm.get('approval') and fm.get('status') == 'approved' and not fm.get('approved_changed')
    return ('通過' if passed else '準備完了' if ready else '準備中'), items

# ---------- 要求の対応表 ----------
def trace(pid, notes, links):
    """案件の要求の対応表 → [{req, designs, tests, issues, flags}]。links は [(src, dst, kind)]"""
    by_dst = {}
    for s, d, k in links: by_dst.setdefault(d, []).append((s, k))
    rows = []
    for rq in sorted((n for n in notes.values() if n['type'] == 'req' and n['project'] == pid), key=lambda n: n['title']):
        f = json.loads(rq['fm']); src = by_dst.get(rq['id'], [])
        designs = [notes[s] for s, k in src if k == 'derived_from' and s in notes and notes[s]['type'] not in ('test', 'issue')]
        tests = [notes[s] for s, k in src if k == 'verifies' and s in notes]
        issues = [notes[s] for s, k in src if k == 'affects' and s in notes and notes[s]['type'] == 'issue']
        flags = []
        if not designs: flags.append('設計なし')
        if not tests: flags.append('試験なし')
        res = [json.loads(t['fm']).get('test_result') or '未実施' for t in tests]
        if any(x == '不合格' for x in res): flags.append('不合格あり')
        rc = f.get('changed_at') or ''
        for t in tests:
            tf = json.loads(t['fm']); tat = str(tf.get('tested') or tf.get('changed_at') or '')
            if rc and tat and rc[:10] > tat[:10]: flags.append('再検証が必要'); break
        if any(json.loads(i['fm']).get('state', 'open') != 'closed' for i in issues): flags.append('未解決の不具合')
        rows.append({'req': rq, 'designs': designs, 'tests': tests, 'results': res, 'issues': issues, 'flags': flags})
    return rows

def trace_pdf(pid, rows, out, user=''):
    """要求の対応表を PDF（A3 横）に"""
    from reportlab.lib.pagesizes import A3, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    cands = [os.environ.get('RDNB_FONT', ''), '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf', '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
             'C:/Windows/Fonts/BIZ-UDGothicR.ttc', 'C:/Windows/Fonts/msgothic.ttc', '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc']
    fp = next((c for c in cands if c and os.path.exists(c)), None)
    if not fp: raise SystemExit('日本語フォントが見つかりません。環境変数 RDNB_FONT にTTF/TTCのパスを指定してください')
    pdfmetrics.registerFont(TTFont('JP', fp, subfontIndex=0) if fp.endswith('.ttc') else TTFont('JP', fp)); F = 'JP'   # PDF のフォントは埋め込む（pdf_out.py と同じ）
    ps = ParagraphStyle('p', fontName=F, fontSize=9, leading=12); hs = ParagraphStyle('h', fontName=F, fontSize=16, leading=22)
    P = lambda s: Paragraph(str(s).replace('&', '&amp;').replace('<', '&lt;'), ps)
    names = lambda ns: '<br/>'.join(n['title'] for n in ns) or '—'
    data = [[P(x) for x in ('要求', '出所', '合否基準', '設計', '試験（結果）', '不具合', '気になる点')]]
    for r in rows:
        f = json.loads(r['req']['fm'])
        data.append([P(r['req']['title']), P(f'{f.get("source_kind", "")} {f.get("source", "")}'), P(f.get('criteria', '')),
                     Paragraph(names(r['designs']), ps), Paragraph('<br/>'.join(f"{t['title']}（{x}）" for t, x in zip(r['tests'], r['results'])) or '—', ps),
                     Paragraph(names(r['issues']), ps), P('・'.join(r['flags']) or 'なし')])
    doc = SimpleDocTemplate(out, pagesize=landscape(A3), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    t = Table(data, colWidths=[150, 120, 170, 170, 200, 110, 140], repeatRows=1)
    st = [('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#adb5bd')), ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9ecef')), ('VALIGN', (0, 0), (-1, -1), 'TOP')]
    for i, r in enumerate(rows, 1):
        if r['flags']: st.append(('BACKGROUND', (6, i), (6, i), colors.HexColor('#fff3bf' if '再検証が必要' in r['flags'] or '試験なし' in r['flags'] else '#ffe3e3' if '不合格あり' in r['flags'] else '#fff3bf')))
    t.setStyle(TableStyle(st))
    doc.build([Paragraph(f'要求の対応表 {pid}', hs), Paragraph(f'出力 {datetime.datetime.now():%Y-%m-%d %H:%M} {user}・要求 {len(rows)} 件', ps), Spacer(1, 10), t])
    return out
