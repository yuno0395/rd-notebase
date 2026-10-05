"""PDF出力"""
import sys, os, re, json, sqlite3, html, base64, datetime, subprocess, hashlib, functools, yaml, markdown
sys.path.insert(0, os.path.dirname(__file__))
from kv import ROOT, SRV, DB, reg, parse_drawing, embedded_files, LINK_RE, hash_of, can_see, read_note, split_fm
from core import *
from access import *
from render import *

def pdf(nid, size='A4', user=None):
    from reportlab.lib.pagesizes import A4, A3, A2, A1, A0, landscape
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.ttfonts import TTFont
    # 日本語フォント（埋め込み）。環境変数 RDNB_FONT で指定、なければよくある場所を探す
    cands = [os.environ.get('RDNB_FONT', ''), '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf', '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
             'C:/Windows/Fonts/BIZ-UDGothicR.ttc', 'C:/Windows/Fonts/msgothic.ttc', '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc']
    fp = next((x for x in cands if x and os.path.exists(x)), None)
    if not fp: raise SystemExit('日本語フォントが見つかりません。環境変数 RDNB_FONT にTTF/TTCのパスを指定してください')
    pdfmetrics.registerFont(TTFont('IPAGothic', fp, subfontIndex=0) if fp.endswith('.ttc') else TTFont('IPAGothic', fp))
    F = 'IPAGothic'
    c = db(); r = reg(); notes = all_notes(c); n = notes[nid]; hmap = by_hash(notes)
    if user and not can_see(user, n['access']): raise SystemExit('PDF出力不可：閲覧権限なし')
    for t in json.loads(n['access']):
        if not r['tags'][t].get('pdf', True): raise SystemExit(f'PDF出力不可：タグ {t}')
    PW, PH = landscape({'A4': A4, 'A3': A3, 'A2': A2, 'A1': A1, 'A0': A0}[size])
    os.makedirs(os.path.join(ROOT, 'out'), exist_ok=True)
    fn = os.path.join(ROOT, 'out', f"{nid}_{size}.pdf")
    cv = canvas.Canvas(fn, pagesize=(PW, PH)); k = PW / 842  # A4基準の倍率
    seq = []  # (図ノート, フレーム, 要素)
    if n['type'] == 'report':
        for bang, tgt, frid, ver, _ in LINK_RE.findall(n['body']):
            tn = hmap.get(hash_of(tgt))
            if not bang or not tn or not has_drawing(tn): continue
            tv = at_version(tn, ver.lstrip('@') if ver else None); fs_, es_ = frames_of(tv)
            for f in fs_:
                if not frid or (f.get('customData') or {}).get('kvFrame') == frid.lstrip('#'): seq.append((tv, f, es_))
    else:
        fs_, es_ = frames_of(n); seq = [(n, f, es_) for f in fs_]
    frs = [x[1] for x in seq]
    def hexc(s):
        from reportlab.lib.colors import HexColor
        return HexColor(s) if s and s.startswith('#') else None
    for pi, (dn, fr, els) in enumerate(seq, 1):
        files = embedded_files(dn['body'])
        mx, my, fh = 28 * k, 46 * k, 30 * k
        s = min((PW - 2 * mx) / fr['width'], (PH - my - fh) / fr['height'])
        ox = (PW - fr['width'] * s) / 2; oy = PH - fh - (PH - my - fh - fr['height'] * s) / 2
        T = lambda x, y: (ox + (x - fr['x']) * s, oy - (y - fr['y']) * s)
        for e in els:
            if e.get('frameId') != fr['id']: continue
            sc = hexc(e.get('strokeColor', '#1e1e1e')); bg = hexc(e.get('backgroundColor'))
            cv.setStrokeColor(sc); cv.setLineWidth(e.get('strokeWidth', 1.5) * s)
            if bg: cv.setFillColor(bg)
            X, Y = T(e['x'], e['y']); W, H = e.get('width', 0) * s, e.get('height', 0) * s
            t = e['type']
            if t == 'rectangle': cv.roundRect(X, Y - H, W, H, 3 * s, stroke=1, fill=1 if bg else 0)
            elif t == 'ellipse': cv.ellipse(X, Y - H, X + W, Y, stroke=1, fill=1 if bg else 0)
            elif t in ('line', 'arrow'):
                pts = [T(e['x'] + p[0], e['y'] + p[1]) for p in e['points']]
                p = cv.beginPath(); p.moveTo(*pts[0])
                for q in pts[1:]: p.lineTo(*q)
                cv.drawPath(p, stroke=1, fill=0)
                if t == 'arrow' and len(pts) > 1:
                    import math
                    (x1, y1), (x2, y2) = pts[-2], pts[-1]; a = math.atan2(y2 - y1, x2 - x1); L = 9 * s
                    cv.setFillColor(sc); ah = cv.beginPath(); ah.moveTo(x2, y2)
                    ah.lineTo(x2 - L * math.cos(a - .4), y2 - L * math.sin(a - .4)); ah.lineTo(x2 - L * math.cos(a + .4), y2 - L * math.sin(a + .4)); ah.close()
                    cv.drawPath(ah, stroke=0, fill=1)
            elif t == 'text':
                fs = e.get('fontSize', 20) * s; cv.setFillColor(sc); cv.setFont(F, fs)
                for i, line in enumerate(str(e.get('text', '')).split('\n')):
                    cv.drawString(X, Y - fs * (i + 1) + fs * .2, line)
            elif t == 'image':
                side = hmap.get(hash_of(files.get(e.get('fileId')) or ''))
                if side and (not user or can_see(user, side['access'])):
                    p = os.path.join(os.path.dirname(work_path(side)), json.loads(side['fm'])['file'])
                    cv.drawImage(ImageReader(p), X, Y - H, W, H)
                else:
                    cv.setFillColorRGB(.93, .94, .95); cv.rect(X, Y - H, W, H, fill=1)
                    cv.setFillColorRGB(.3, .33, .37); cv.setFont(F, 12 * s); cv.drawCentredString(X + W / 2, Y - H / 2, 'アクセス権なし')
        # 余白の追跡情報
        cv.setFillColorRGB(.25, .28, .32); cv.setFont(F, 7.5 * k)
        fm = json.loads(n['fm'])
        info = f"ID {nid}  版 {n['commit_']}  状態 {fm.get('status')}  機密 {' / '.join(json.loads(n['access'])) or 'なし'}  出力 {datetime.datetime.now():%Y-%m-%d %H:%M}  {user or ''}"
        cv.drawString(mx, 18 * k, info); cv.drawRightString(PW - mx - 40 * k, 18 * k, f"{pi} / {len(frs)}")
        cv.setFont(F, 10 * k); src = '' if dn['id'] == nid else f"  （引用: {dn['title']}）"
        cv.drawString(mx, PH - 20 * k, f"{fm.get('title')}  #{(fr.get('customData') or {}).get('kvFrame')} {fr.get('name','')}{src}")
        q = QrCodeWidget(f"https://viewer.example/#n-{nid}"); b = q.getBounds(); sz = 34 * k
        d = Drawing(sz, sz, transform=[sz / (b[2] - b[0]), 0, 0, sz / (b[3] - b[1]), 0, 0]); d.add(q)
        renderPDF.draw(d, cv, PW - mx - sz, 4 * k)
        cv.showPage()
    cv.save(); print('PDF', os.path.relpath(fn, ROOT), len(frs), 'ページ', size)
    return fn
