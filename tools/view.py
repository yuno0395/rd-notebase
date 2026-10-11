#!/usr/bin/env python3
"""view: Web閲覧とPDFの生成
  build <user> [出力名]           : site/ にWeb閲覧を生成（user が見られる資料だけ）
  pdf <note_id> [A4..A0] [user]  : out/ にPDF出力
  trace <案件> [user]             : out/ に要求の対応表の PDF（A3 横）

モジュール構成
  core.py    : DB接続・定数
  access.py  : 権限（公開の判定）
  render.py  : 図・本文・版・鍵・見せる相手の表示部品
  pages.py   : ページ生成（1ページ＝1関数）
  pdf_out.py : PDF出力
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

if __name__ == '__main__':
    c, *a = sys.argv[1:]
    if c == 'build':
        from pages import build; build(a[0], a[1] if len(a) > 1 else 'index.html')
    elif c == 'pdf':
        from pdf_out import pdf; pdf(a[0], a[1] if len(a) > 1 else 'A4', a[2] if len(a) > 2 else None)
    elif c == 'trace':
        import quality, core, access
        con = core.db(); notes = core.all_notes(con); u = a[1] if len(a) > 1 else None
        if u: notes = {i: n for i, n in notes.items() if access.ok(u, notes, n)}   # 見てよい資料だけ
        links = [(x['src'], x['dst'], x['kind']) for x in con.execute('select src, dst, kind from links')]
        os.makedirs(os.path.join(core.OUT, 'out'), exist_ok=True)
        print('作成:', quality.trace_pdf(a[0], quality.trace(a[0], notes, links), os.path.join(core.OUT, 'out', f'要求の対応表_{a[0]}.pdf'), u or ''))
