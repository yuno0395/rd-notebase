"""これまでの試作（rd-notebase）のまとめを A3 1枚の Excalidraw の図付きノートにする台本（過去検討として残す）。
  python3 tools/dev/make_summary.py docs/過去検討/rd-notebase_試作のまとめ.md
中身はこの台本に書いてある。図の部品は make_overview.py の D を使う"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import make_overview as m
from kv import join_fm

m.FW, m.FH = 2000, 1414          # A 判の比率（1:1.414）。A3 横に出すと 16px ≒ 9pt
D, INK, MUTED, LINE = m.D, m.INK, m.MUTED, m.LINE
BLUE, TEAL, ORANGE, GRAPE = m.BLUE, m.TEAL, m.ORANGE, m.GRAPE
OK, PART, NG = m.OK, m.PART, m.NG
PAPER, RED, GREEN = '#f8f9fa', '#c92a2a', '#2b8a3e'

def ellipse(d, x, y, w, h, bg, sc=INK):
    return d._base({'type': 'ellipse', 'x': d.X(x), 'y': d.Y(y), 'width': w, 'height': h, 'backgroundColor': bg, 'strokeColor': sc,
                    'fillStyle': 'solid', 'strokeWidth': 1, 'roundness': None})

def section(d, x, y, w, h, no, title, sub=''):
    d.rect(x, y, w, h, PAPER, '#ced4da', 1)
    ellipse(d, x + 14, y + 12, 34, 34, INK, INK); d.text(x + 14, y + 17, no, 18, '#ffffff', 34, 'center')
    d.text(x + 58, y + 14, title, 24)
    if sub: d.text(x + 60 + m.width(title, 24) + 14, y + 22, sub, 15, MUTED, w - m.width(title, 24) - 90)

def build():
    d = D(); d.frame('試作のまとめ', 0)
    # ---------- 見出し ----------
    d.text(40, 26, 'rd-notebase 試作のまとめ（過去検討）', 40)
    d.text(42, 82, '2026-10-05〜10-18。研究開発の「判断の根拠」を普段のノートから残す基幹システムの試作（Obsidian＋Excalidraw＋Git＋Python）。'
                   '実装は白紙に戻し、考え方だけを引き継ぐ', 17, MUTED, 1300)
    chips = [('コミット', '28'), ('Python', '約 4,600 行'), ('Python ファイル', '19'), ('テンプレート', '10 種'), ('要件書', '6')]
    x = 1390
    for k, v in chips:
        w = max(m.width(k, 14), m.width(v, 22)) + 26
        d.rect(x, 26, w, 70, '#ffffff', '#ced4da', 1); d.text(x, 34, k, 14, MUTED, w, 'center'); d.text(x, 56, v, 22, INK, w, 'center'); x += w + 10

    # ---------- 1. 目指したこと ----------
    section(d, 40, 130, 600, 440, '1', '目指したこと')
    goals = [('判断の根拠が、信頼の根拠', 'なぜそう決めたか（検討・計算・却下した案と理由）を、説明できる形で残す', '#fff3bf'),
             ('1人1 vault', '自分の考えは自分の vault に。他人のノートは索引を通して参照する', TEAL),
             ('ノート単位の鍵', '見せる範囲（機密タグ）はサーバが配信の時に判定。必要な図だけ「開示」する', BLUE),
             ('思考は自由に、確定は厳格に', '下書きは何も強制しない。確定は必須項目の検査と、権限のある人の承認', ORANGE),
             ('普段の作業で記録が残る', 'ISO 9001（7.5・8.3）の記録が自動で残る。AI なしで全機能が動く', GRAPE)]
    y = 186
    for t, s, bg in goals:
        d.rect(60, y, 560, 70, bg, '#adb5bd', 1); d.text(76, y + 8, t, 19); d.text(76, y + 36, s, 14, MUTED, 530); y += 76

    # ---------- 2. 全体の構成 ----------
    section(d, 670, 130, 700, 440, '2', '全体の構成', 'Git が正本、サーバが索引と配信')
    d.box(690, 186, 220, 300, '各人の PC', 'Obsidian＋Excalidraw\nプラグインは版と\nsha256 で固定して配る\n\nnotebase.cmd 1つで\n設定・更新・検査・push\n（30 分ごと）\n\nvault のフォルダ：\n01_daily・10_notes\n40_attachments\n50_data・90_templates\n_refs（他人のスタブ）', TEAL, 15, 19)
    d.box(960, 186, 170, 140, '正本（Git）', 'vault-<人>.git\nproj-<案件>.git\n画像は LFS', BLUE, 15, 19)
    d.box(960, 346, 170, 140, 'データの置き場', '重いデータ・原寸\n案件のアーカイブ\n（sha256 で照合）', GRAPE, 15, 19)
    d.box(1180, 186, 170, 300, 'サーバ', '1分ごとに取り込み\n検査（不合格は\n前の版のまま）\n差分の索引\n承認の反映\n工程の照合\nWeb 閲覧・PDF\nバックアップ', ORANGE, 15, 19)
    d.arrow(910, 240, 960, 240, INK); d.text(912, 216, 'push', 13, MUTED)
    d.arrow(910, 420, 960, 420, INK); d.text(912, 396, '原寸', 13, MUTED)
    d.arrow(1130, 250, 1180, 250, INK)
    d.arrow(1180, 470, 910, 470, '#1971c2', 1.8, True)
    d.text(912, 492, 'スタブ・図の SVG（見てよいものだけ）', 13, '#1971c2')
    viewers = [('技術者', 'Obsidian（スタブ）'), ('管理職', 'Web 閲覧・承認'), ('他チーム', '公開分だけ🔒')]
    x = 690
    for t, s in viewers:
        d.rect(x, 518, 216, 40, '#ffffff', '#adb5bd', 1); d.text(x + 10, 528, t, 15); d.text(x + 76, 530, s, 13, MUTED); x += 226

    # ---------- 3. 経緯 ----------
    section(d, 1400, 130, 560, 440, '3', '経緯')
    hist = [('10/05', '初版：要件書・Python・サンプル vault', BLUE),
            ('10/06', 'notebase.cmd 1つで設定・更新・push', BLUE),
            ('10/07', 'スタブ・Web 閲覧・PDF、工程を dotpm に', BLUE),
            ('10/08', '工程を Project Planner に（10/11 に dotpm へ戻す）', '#ffffff'),
            ('10/11', '添付の手入れ・案件アーカイブ・承認ノート・ゲート・要求の対応表・要件適合の図', BLUE),
            ('〜10/16', '実機でロールプレイ → 使いづらさが多い（7）', PART),
            ('10/16', 'GitHub をやめ Box へ。セットベース開発を前提に', NG),
            ('10/18', 'Box 版の仕様。A3 は Excalidraw、表は別のプラグインへ', TEAL),
            ('10/21', '白紙に戻す（考え方だけ引き継ぐ）', NG)]
    d.rect(1478, 196, 3, 358, '#adb5bd', '#adb5bd', 0)
    y = 186
    for day, s, bg in hist:
        d.text(1416, y + 6, day, 14, INK); ellipse(d, 1470, y + 7, 18, 18, bg, LINE)
        d.text(1500, y + 4, s, 14, INK, 440); y += 41

    # ---------- 4. データの流れ ----------
    section(d, 40, 600, 1330, 340, '4', 'データの流れ', '書く → 保存 → 索引 → 参照。確定・見せる範囲・工程にはそれぞれの流れがある')
    steps = [('書く', 'テンプレート（Ctrl+N）で\nノート・図・デイリー', TEAL), ('手入れ', '添付の説明の .md・重複\n・縮小・重いデータを外へ', TEAL),
             ('検査', 'id・プロパティ・日付・\n鍵・顧客名', TEAL), ('保存', 'コミット → 正本へ push\n（30 分ごと）', BLUE),
             ('取り込み', 'サーバが検査・差分の索引\n・承認の反映（1分ごと）', ORANGE), ('参照・出力', 'スタブ・SVG・Web 閲覧・\nPDF（ID・版・QR）', ORANGE)]
    x = 60
    for k, (t, s, bg) in enumerate(steps):
        d.rect(x, 656, 196, 104, bg, '#adb5bd', 1); d.text(x + 10, 664, f'{k + 1}. {t}', 18); d.text(x + 10, 694, s, 13, MUTED, 180)
        if k < len(steps) - 1: d.arrow(x + 196, 708, x + 220, 708, INK)
        x += 220
    flows = [('確定', [('下書き', '自由', '#ffffff'), ('レビュー待ち', '必須項目', PART), ('承認', '承認ノート', OK)], '承認した版より後に変えると再承認'),
             ('見せる範囲', [('鍵なし', '本人だけ', '#ffffff'), ('開示申請', '図ごと', PART), ('承認', '見える', OK)], '配信の時にサーバが判定する'),
             ('工程', [('dotpm', '取りまとめ役', '#ffffff'), ('照合', 'サーバ', PART), ('申請・承認', '5日超の遅れなど', OK)], '却下なら計画を戻す')]
    x = 60
    for name, chain, note in flows:
        d.text(x, 780, name, 18)
        xx = x
        for k, (t, s, bg) in enumerate(chain):
            d.rect(xx, 810, 118, 64, bg, '#adb5bd', 1); d.text(xx, 818, t, 15, INK, 118, 'center'); d.text(xx, 844, s, 13, MUTED, 118, 'center')
            if k < 2: d.arrow(xx + 118, 842, xx + 140, 842, INK)
            xx += 140
        d.text(x, 886, note, 13, MUTED, 400); x += 445

    # ---------- 5. 機能の地図 ----------
    section(d, 1400, 600, 560, 340, '5', '機能の地図')
    tiles = [('書く', 'テンプレート 10 種（基本・議事録・報告・デイリー・週・案件・要求・試験・ゲート・不具合）', TEAL),
             ('つなぐ', 'id で一意・名前→id・改名の履歴・スタブ・図ごとのコピー', BLUE),
             ('見せる', '鍵（機密タグ）・開示申請・Web 閲覧（閲覧者ごと）・閲覧.html', BLUE),
             ('確定', '必須項目・承認ノート・再承認・ゲート・要求の対応表', ORANGE),
             ('工程', 'dotpm・週報・計画変更の申請・ガント図・ロードマップ', ORANGE),
             ('保管・出力', '添付の手入れ・50_data・案件アーカイブ・バックアップ・PDF（A4〜A0）', GRAPE)]
    for k, (t, s, bg) in enumerate(tiles):
        x = 1418 + (k % 2) * 266; y = 656 + (k // 2) * 92
        d.rect(x, y, 256, 84, bg, '#adb5bd', 1); d.text(x + 10, y + 6, t, 16); d.text(x + 10, y + 30, s, 13, MUTED, 238)

    # ---------- 6. 要件適合 ----------
    section(d, 40, 970, 600, 410, '6', '要件適合', '10/11 時点')
    y = 1030
    for name, rows in m.DOCS.items():
        c = m.counts(rows); tot = len(rows)
        d.text(60, y + 4, name, 16); d.text(60, y + 26, f'○{c["○"]} △{c["△"]} ×{c["×"]}', 13, MUTED)
        x = 200; W = 420
        for k, col in (('○', OK), ('△', PART), ('×', NG)):
            w = W * c[k] / tot
            if w: d.rect(x, y + 4, w, 36, col, '#adb5bd', 1); d.text(x, y + 12, str(c[k]), 15, INK, w, 'center')
            x += w
        y += 56
    d.rect(200, y + 2, 16, 16, OK, '#adb5bd', 1); d.text(222, y, '適合', 13, MUTED)
    d.rect(280, y + 2, 16, 16, PART, '#adb5bd', 1); d.text(302, y, '一部', 13, MUTED)
    d.rect(360, y + 2, 16, 16, NG, '#adb5bd', 1); d.text(382, y, '未対応', 13, MUTED)
    d.text(60, y + 32, '記録の土台（Git の全履歴・一意な id・版を固定した引用・PDF の余白・sha256）は強い。'
                       '残ったのは、認証付きの Web と画面からの承認、電子署名、計画の版と負荷、規模の試験、設計変更と是正', 14, INK, 560)

    # ---------- 7. 実機で分かったこと ----------
    section(d, 670, 970, 700, 410, '7', '実機で分かったこと', 'ロールプレイで出た使いづらさ')
    probs = [('始めにくい', 'Git・GitHub の準備とログイン。毎回 GitHub の画面が出る'),
             ('遅い', '1回の実行に 2〜3 分。進み具合が見えない'),
             ('止まる', '必須項目の検査で、定期 push 全体が止まる'),
             ('揺れる', '更新のたびに設定ファイル（休日・リボン）が行き来する'),
             ('壊す', '既にある画像まで縮める。説明の .md が添付のフォルダを埋める'),
             ('伝わらない', 'テンプレートが英語。YAML のコメントが Obsidian で消える'),
             ('動かせない', '引数の要るコマンドはダブルクリックで動かない（Obsidian から動かしたい）'),
             ('散らかる', 'Project Planner の残り（警告の山・ログ 530KB）、同期エラーが毎回出る')]
    y = 1028
    for t, s in probs:
        ellipse(d, 690, y + 2, 22, 22, NG, RED); d.text(690, y + 3, '×', 14, RED, 22, 'center')
        d.text(722, y + 2, t, 15); d.text(822, y + 3, s, 14, MUTED, 530); y += 42

    # ---------- 8. 引き継ぐもの ----------
    section(d, 1400, 970, 560, 410, '8', '引き継ぐもの・やめるもの')
    keep = ['判断の根拠を残す（却下した案と理由も）',
            'ノートは id で一意。リンクと参照は id でたどる',
            '正しいやり方が一番楽。性善説で作る',
            '判断は誰でも記入。判断者と記入者をログに（vault の外）',
            'Box・プロジェクトごとの vault（Box 版の仕様）',
            'セットベース開発：要求は範囲、問いは A3 1枚',
            'A3 は Excalidraw。表は Excalidraw Table（別リポジトリで継続）']
    drop = ['Git・GitHub 前提、push の時の検査で止める',
            '本人の vault の承認ノートで本人確認、鍵の配信判定']
    y = 1026
    for s in keep:
        ellipse(d, 1418, y + 2, 20, 20, OK, GREEN); d.text(1418, y + 3, '✓', 13, GREEN, 20, 'center'); d.text(1446, y + 1, s, 14, INK, 500); y += 36
    y += 6; d.text(1418, y, 'やめる', 15, RED); y += 26
    for s in drop:
        ellipse(d, 1418, y + 2, 20, 20, NG, RED); d.text(1418, y + 3, '×', 13, RED, 20, 'center'); d.text(1446, y + 1, s, 14, MUTED, 500); y += 32

    d.text(40, 1388, '作成 2026-10-21。詳しくは docs/過去検討/ の要件書・仕様書（基本方針・非機能・ID 体系・vault 設計・工程管理・ISO 9001 の整理・Box 版の仕様・システム構成と要件適合）',
           13, MUTED, 1900)
    return d

def save(path):
    d = build()
    texts = '\n\n'.join(e['text'] for e in d.els if e['type'] == 'text')
    fm = {'id': '261021-summ0', 'type': 'memo', 'owner': 'rdnb', 'project': '', 'status': 'draft', 'access': [],
          'created': '2026-10-21', 'updated': '2026-10-21',
          'summary': 'rd-notebase の試作（2026-10-05〜10-18）のまとめ。目指したこと・構成・経緯・データの流れ・機能・要件適合・実機で分かったこと・引き継ぐもの',
          'excalidraw-plugin': 'parsed'}
    body = ('# rd-notebase 試作のまとめ（過去検討）\n\nA3 横 1 枚の図。Obsidian で開くと Excalidraw の図で見られる。PDF は同じフォルダの .pdf。\n'
            '作り直す時は tools/dev/make_summary.py を直して実行する。\n'
            '\n%%\n# Excalidraw Data\n\n## Text Elements\n' + texts + '\n\n## Drawing\n```json\n'
            + json.dumps({'type': 'excalidraw', 'version': 2, 'source': 'rd-notebase', 'elements': d.els,
                          'appState': {'viewBackgroundColor': '#ffffff', 'gridSize': None}, 'files': {}}, ensure_ascii=False, indent=1)
            + '\n```\n%%\n')
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    open(path, 'w', encoding='utf-8').write(join_fm(fm, body))
    print('作成:', path, '要素', len(d.els))

if __name__ == '__main__':
    save(sys.argv[1] if len(sys.argv) > 1 else 'docs/過去検討/rd-notebase_試作のまとめ.md')
