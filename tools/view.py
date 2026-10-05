#!/usr/bin/env python3
"""view: Web閲覧とPDFの生成
  build <user> [出力名]           : site/ にWeb閲覧を生成（user が見られる資料だけ）
  pdf <note_id> [A4..A0] [user]  : out/ にPDF出力

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
