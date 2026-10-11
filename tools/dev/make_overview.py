"""docs/システム構成と要件適合.md（Excalidraw の図付きノート）を作る台本。
中身（構成・役割・判定）はこの台本に書いてあり、作り直す時はここを直して実行する：
  python3 tools/dev/make_overview.py docs/システム構成と要件適合.md
PDF は notebase の PDF 出力（tools/pdf_out.py）で作る（README「PDF に出す」）"""
import sys, os, json, secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from kv import join_fm

FW, FH = 1600, 1131   # A 判の比率（1:1.414）
OK, PART, NG = '#d3f9d8', '#fff3bf', '#ffe3e3'
JUDGE = {'○': OK, '△': PART, '×': NG}
INK, MUTED, LINE = '#1e1e1e', '#495057', '#868e96'
BLUE, TEAL, ORANGE, GRAPE = '#d0ebff', '#c3fae8', '#ffe8cc', '#eebefa'

def cw(ch, fs): return fs * (0.56 if ord(ch) < 0x2E80 else 1.0)
def width(s, fs): return max((sum(cw(c, fs) for c in line) for line in s.split('\n')), default=0)
def wrap(s, w, fs):
    out = []
    for para in str(s).split('\n'):
        line, lw = '', 0
        for c in para:
            if lw + cw(c, fs) > w and line: out.append(line); line, lw = '', 0
            line += c; lw += cw(c, fs)
        out.append(line)
    return '\n'.join(out)

class D:
    def __init__(self): self.els = []; self.n = 0; self.fr = None
    def _base(self, d):
        d.update({'id': secrets.token_hex(8), 'angle': 0, 'strokeWidth': d.get('strokeWidth', 1.5), 'strokeStyle': d.get('strokeStyle', 'solid'),
                  'roughness': 0, 'opacity': 100, 'groupIds': [], 'seed': secrets.randbelow(2**31), 'version': 1, 'versionNonce': secrets.randbelow(2**31),
                  'isDeleted': False, 'boundElements': None, 'updated': 1, 'link': None, 'locked': False})
        if self.fr and d['type'] != 'frame': d['frameId'] = self.fr['id']
        self.els.append(d); return d
    def frame(self, name, i):
        self.n += 1; x = (i % 3) * (FW + 200); y = (i // 3) * (FH + 200)
        self.fr = None
        f = self._base({'type': 'frame', 'x': x, 'y': y, 'width': FW, 'height': FH, 'name': name, 'strokeColor': '#bbb',
                        'backgroundColor': 'transparent', 'fillStyle': 'solid', 'customData': {'kvFrame': f'F{self.n:02d}'}, 'roundness': None})
        self.fr = f; return f
    def X(self, x): return self.fr['x'] + x
    def Y(self, y): return self.fr['y'] + y
    def rect(self, x, y, w, h, bg='transparent', sc=INK, sw=1.5, dash=False):
        return self._base({'type': 'rectangle', 'x': self.X(x), 'y': self.Y(y), 'width': w, 'height': h, 'backgroundColor': bg, 'strokeColor': sc,
                           'fillStyle': 'solid', 'strokeWidth': sw, 'strokeStyle': 'dashed' if dash else 'solid', 'roundness': {'type': 3}})
    def text(self, x, y, s, fs=18, sc=INK, w=None, align='left'):
        s = wrap(s, w, fs) if w else str(s)
        tw = w if (w and align != 'left') else width(s, fs); th = fs * 1.25 * (s.count('\n') + 1)
        self._base({'type': 'text', 'x': self.X(x), 'y': self.Y(y), 'width': tw, 'height': th, 'text': s, 'originalText': s, 'fontSize': fs,
                    'fontFamily': 2, 'textAlign': align, 'verticalAlign': 'top', 'lineHeight': 1.25, 'strokeColor': sc,
                    'backgroundColor': 'transparent', 'fillStyle': 'solid', 'containerId': None, 'autoResize': True, 'baseline': fs})
        return th
    def arrow(self, x1, y1, x2, y2, sc=LINE, sw=1.8, dash=False):
        return self._base({'type': 'arrow', 'x': self.X(x1), 'y': self.Y(y1), 'width': abs(x2 - x1), 'height': abs(y2 - y1),
                           'points': [[0, 0], [x2 - x1, y2 - y1]], 'strokeColor': sc, 'backgroundColor': 'transparent', 'fillStyle': 'solid',
                           'strokeWidth': sw, 'strokeStyle': 'dashed' if dash else 'solid', 'startArrowhead': None, 'endArrowhead': 'arrow', 'roundness': None})
    def box(self, x, y, w, h, title, lines='', bg=BLUE, fs=16, tfs=19):
        self.rect(x, y, w, h, bg)
        th = self.text(x + 12, y + 10, title, tfs, INK, w - 24)
        if lines: self.text(x + 12, y + 16 + th, lines, fs, MUTED, w - 24)
    def title(self, t, sub=''):
        self.text(50, 34, t, 34)
        if sub: self.text(52, 84, sub, 17, MUTED, FW - 100)

# ---------- 中身 ----------
DOCS = {}
DOCS['基本方針'] = [
    ('目的', '探す・転記・説明し直す工数をなくす', '△', '全 vault の索引（名前→id・改名履歴）、Web 閲覧、閲覧.html、全文検索（アーカイブ済みも）', 'Obsidian から横断検索できない。他人のノートの本文は Web 閲覧でしか読めない'),
    ('原則1', '思考と確定事項を ID でつなぐ。却下した案と理由を残す', '○', 'リンクは id で解決。検討をレビュー待ちにすると「結論」「却下した案と理由」が必須（台帳 required）', '下書きの間は空でもよい（意図どおり）'),
    ('原則2', 'データごとに正本を1つ', '○', 'vault＝Git の正本。索引・スタブ・SVG・閲覧.html は作り直せる派生物。重いデータは置き場に1つ（sha256 で照合）', 'マスタ（品目など）と権限台帳は registry.yml で代用'),
    ('原則3', '製品の一生を一本の糸でつなぐ', '△', '要求の対応表（要求←設計・試験・不具合、再検証の検出）、品番から辿るページ', '量産・出荷後（ロット・顧客の不具合）までは未接続'),
    ('原則4', '思考は自由に、確定は厳格に', '○', '下書きは自由。レビュー待ちで必須項目を検査、確定は承認者の承認ノート（版を記録）、承認後に変えると再承認', 'Web から直接は承認できない（PC のコマンド）'),
    ('原則5', '業務をこなすと記録が自動で残る', '△', '30分ごとの自動保存、承認ノート、ゲートの準備状況、アーカイブの記録', '設計変更（ECR/ECO）の流れ、監査用の抽出がない'),
    ('原則6', '使う人に合わせた入口、裏は同じデータ', '△', '技術者は Obsidian、管理職は Web 閲覧（閲覧者ごと）', '共通の API がない（Web は事前に作る静的 HTML）'),
    ('原則7', '正しい運用が最も楽', '○', 'テンプレートが名前と id を付ける、id の自動付与、添付の手入れ・アーカイブ・PDF が1コマンド', 'Obsidian で project を入れても案件の既定の鍵が付かない'),
    ('原則8', '特定の技術に依存しない・AI なしで動く', '○', 'Markdown・Excalidraw JSON・SVG・PDF、Python＋SQLite、プラグインは版と sha256 で固定', 'Obsidian のプラグイン（Templater・dotpm）への依存は大きい'),
    ('品質', 'ISO 9001 をシステムの仕様に組み込む', '△', '7.5（版・承認者の確認）、8.3（要求・ゲート・対応表）', '8.7 不適合・是正、電子署名がない'),
    ('文書体系', '基本方針の下に個別の文書', '○', 'docs/ に要件書がそろう（基本方針・非機能・ID体系・vault設計・工程管理・ISO 整理）', '—'),
    ('導入', '出口は A4〜A0 の PDF、各ページに ID・版', '○', 'pdf_out.py（フレーム単位、A4〜A0、ID・版・状態・機密・QR）', 'Web 閲覧から PDF を取れない'),
    ('導入', '管理職は Obsidian なしで読める', '○', 'Web 閲覧の案件ページ・今週の更新・スライド表示', '—'),
    ('導入', '下書きは本人だけが既定', '○', '鍵なし＝本人だけ（access: []）、デイリーも本人だけ', '「下書きは評価しない」の運用文書がない'),
    ('第1期', 'テンプレート（デイリー・議事録・要求・検討・計算・報告）', '△', '01〜10（基本・議事録・報告・デイリー・週・案件まとめ・要求・試験・ゲート・不具合）', '検討・計算の専用テンプレートがない（01-base で代用）'),
    ('第1期', '自動コミット（10分ごと）', '△', 'タスクスケジューラで 30 分ごとに検査→push', '間隔が 30 分'),
    ('第2期', '索引・スタブ・版固定の引用・更新の通知・ノート単位の権限', '△', '索引・_refs のスタブ・@版・配信時の鍵の判定まで実装', '引用元の更新の通知が引用した人に届かない'),
    ('計測', '開始前の基準値、効果の自動集計', '×', '—', '引用・再利用の回数、回答時間などの記録がない'),
]
DOCS['工程管理要件'] = [
    ('2 表示', '月間〜10年、A4 横1枚', '△', 'gantt.py（月間・3か月・半年・5年・10年）', '案件の Web は半年まで。表示設定の保存がない'),
    ('2.1 暦', '月曜始まり・4月年度・休日', '○', '台帳の休日を dotpm と集計に配る', '—'),
    ('2.3 描き方', 'レーン・節目を最上段・依存の矢印', '○', 'layout() のレーン・節目、まとめのノートのプレビュー', '30 行を超えた時の折りたたみがない'),
    ('3 階層', '親は子から積み上げ、目標からはみ出したら警告', '△', '深い階層から積み上げ', 'target を警告に使っていない'),
    ('3.2 負荷', '見積・割当率、人×週の負荷', '×', 'est・alloc を持つだけ', '負荷表がない'),
    ('3.3 ロードマップ', '目標期間・状態・見直し', '○', 'build_roadmap、見直しの表示', '見直しが確認待ちに入らない'),
    ('3.4 ID', '工程表ID#T02、番号を再利用しない', '○', '番号はサーバが振る（task_no）', '—'),
    ('4.1 取りまとめ役', '複数人、休む・辞めても続く', '○', '案件リポジトリを 20_工程/<案件>/ に同期、衝突は _衝突/ に控える。dotpm を実機で確認', '—'),
    ('4.3 照合', 'dotpm の変更を申請にし、却下で戻す', '○', 'server.py が1分ごとに取り込み、dotpm の変更を照合・承認ノートの判断を反映', '—'),
    ('5・6 書き込み', '書き込みが付き先に追従', '△', 'Excalidraw のガント図に自動の層と書き込み', '書いた人ごとの保存・重ね表示がない'),
    ('7.1 線', '当初・今の計画・実績・見込み・申請中', '○', 'layout・build・ripple', '—'),
    ('7.2 確定', '計画の版を名前付きで承認', '×', '版（baselines）を読むだけ', '版を作る・承認する操作がない'),
    ('7.3 進捗', 'やることの完了数／総数、実績は週報で', '△', 'todo_counts、週報（未来の実績は拒否）', '週の増減、実績の候補の自動表示がない'),
    ('7.5 辿り方', '変更の履歴、任意の日の計画、遅れ一覧', '△', '履歴と遅れの表', '任意の日の計画の再現がない'),
    ('8 連携', 'Web の工程・確認待ち・画像保存', '△', 'pm_pages.py、画像の保存', '承認は画面から書き戻せない（試作）'),
    ('9 承認', '実働5日超の遅れ・節目・範囲の変更は承認', '△', '申請の判定（5日・20%）、理由の区分、承認者の本人確認（承認ノート）、代理（deputies）', '放置の通知がない'),
    ('10 週報', '1人1画面、案件ごとに保存、締め・未提出の通知', '△', '週報の作成（1人×1週×1案件）、週ノートの書式', '週ノートを案件ごとに分ける処理・通知がない'),
    ('10.6 工数', '机上作業の自動記録', '×', '—', '未実装'),
]
DOCS['非機能要件'] = [
    ('1 規模', '1人約4万件、ホットは数千件', '△', '案件アーカイブで vault を軽く、重いデータは Git の外へ', '数万件の試験をしていない。コールド化は未実装'),
    ('2 ID', '30年以上一意、再利用しない', '○', '採番の記録、全 vault の重複検査、形式の検査', '—'),
    ('2 保管', '保守終了＋10年、廃棄のルール', '△', 'Git の全履歴、アーカイブの記録（版・sha256）、照合', '保管期限・廃棄の機能がない'),
    ('2 形式', '公開形式（MD・JSON・SVG・PDF）', '○', 'Markdown＋Excalidraw JSON、SVG、PDF', '—'),
    ('3 文字', 'UTF-8・NFC', '○', 'ファイル名が NFC でなければ拒否', '本文の NFC は見ていない'),
    ('4 可用性', 'サーバ停止中も作業、消失は最大1時間', '○', '手元で作業、30分ごとに検査→push', '—'),
    ('4 復旧', 'Git と索引を日次で保管、1営業日で復旧', '○', 'server.py backup（ミラー・LFS・索引と台帳の30日分）、restore-test で作り直しを試す', '定期実行はサーバのスケジューラに登録する'),
    ('5 性能', '検索2秒・索引の反映1分・PDF 30秒', '△', '1分ごとの取り込み、変わった vault だけ入れ直す差分の索引', '大規模では測っていない'),
    ('6 認証', '社内アカウント、将来は SSO', '×', 'Git ホスティングのログインだけ', 'Web 閲覧に認証がない'),
    ('6 権限', '機密タグでノート単位に制御', '○', '配信時の判定、許可した項目だけのスタブ、サーバ側の検査（不合格の版は出さない）', '—'),
    ('6 監査', '暗号化、閲覧・出力・承認の記録', '×', 'PDF に出力者・日時、承認はノートとコミット', '閲覧・出力の記録がない'),
    ('7 品番', '形式の検査と品番から検索', '△', '形式の警告、部品ページ', '大文字への自動変換がない'),
    ('8 差し替え', '索引 DB を差し替えられる層', '△', 'DB 接続は core.py にまとまる', 'SQL を各所に直接書いている'),
    ('6 AI', '既定は使わない', '○', 'AI なしで全機能が動く', '—'),
]
DOCS['ISO 9001'] = [
    ('7.5.2 識別', 'ID・作成者・日付・版', '○', 'id・owner・created、索引の版、PDF の余白（ID・版・状態・QR）', '—'),
    ('7.5.3 版', '版・変更理由・変更者・日時', '△', 'Git の全履歴、改名の履歴、版を固定した引用', '普段の保存に変更理由が残らない'),
    ('7.5 承認', '権限者による承認・電子署名', '△', '承認は承認者の vault の承認ノートだけ有効（台帳の権限）、承認した版を記録', '電子署名（コミットの署名）がない'),
    ('7.5.3 保護', '権限管理と承認の記録', '○', '機密タグ、承認ノート（誰がどの版を判断したか）、再承認の依頼', '—'),
    ('7.5.3 保管', '保管期間、旧版の誤使用防止', '△', '退避は削除でない、アーカイブの sha256・照合・取り消し、添付の verify', '保管期限がない。旧版の使用を止める仕組みがない'),
    ('8.3.2 計画', '段階・DR・責任者', '○', '工程表と節目、ゲート（出す資料の一覧と準備状況、通過は責任者の承認）', '—'),
    ('8.3.3 インプット', '要求の必須項目（出所・合否基準）', '○', '要求のテンプレート、レビュー待ちで出所・合否基準を必須に', '法規のチェックリストはない'),
    ('8.3.4 レビュー', 'DR 指摘の管理、要求と試験の対応', '○', '指摘（担当・期限）、要求の対応表（試験なし・不合格・再検証）、ゲート', '—'),
    ('8.3.5 アウトプット', '出図の承認', '×', '—', 'PDM・出図承認がない'),
    ('8.3.6 変更', 'ECR/ECO・影響の評価', '△', '計画変更の申請→承認、affects・supersedes', '設計変更の流れ、使用先の展開がない'),
    ('8.5.2 トレーサビリティ', 'ID でつなぐ、版を追う', '△', 'id でリンク、要求の対応表、品番の索引、コピー元と版', '試作品のロット追跡がない'),
    ('7.2 力量', '権限のない者は承認できない', '△', '承認の権限を台帳で確かめる（権限のない承認は無効）', '力量の登録がない'),
    ('7.1.6 知識', '横断検索・再利用', '○', '全文検索（アーカイブ済みも）、スタブ、コピー', '—'),
    ('7.1.5 ほか', '校正・リスク・是正', '×', '—', '未実装'),
    ('9.2 監査', '記録の抽出', '△', 'Git の履歴、承認ノート、アーカイブの記録.md', '監査用の抽出がない'),
]
NEXT = [
    ('1', 'Web からの承認と認証', 'Web 閲覧にログイン（SSO）を付け、画面から承認ノートを書けるように。閲覧・出力の記録', '非機能 6、ISO 7.5'),
    ('2', '電子署名', 'コミットの署名（SSH 鍵）で、承認ノートを書いた本人をさらに確かめる', 'ISO 7.5'),
    ('3', '計画の版と負荷', '計画の版の確定（承認）、人×週の負荷、工数', '工程 7.2・3.2・10.6'),
    ('4', '規模の試験と計測', '数万件の vault での試験、効果の計測（基準値・引用回数）', '非機能 1・5、基本方針 7.4.5'),
    ('5', '設計変更と是正', '設計変更（ECR/ECO）の流れ、不具合からの是正処置（CAPA）', 'ISO 8.3.6・10.2'),
    ('6', '保管期限と監査', '記録の保管期限・廃棄のルール、監査用の記録の抽出', '非機能 2、ISO 9.2'),
    ('7', '残りのテンプレートと通知', '検討・計算のテンプレート、承認待ちの放置・週報の未提出の通知', '基本方針 第1期、工程 9・10'),
]

def counts(rows):
    return {k: sum(r[2] == k for r in rows) for k in '○△×'}

def table(d, rows, title, start_i, cols=(150, 330, 64, 470, 466), fs=15):
    """判定の表。入りきらなければフレームを足す → 使ったフレームの数"""
    heads = ['区分', '要件', '判定', '根拠（機能・ファイル）', '足りない点']
    used = 0; k = 0
    while k < len(rows):
        d.frame(f'{title}' + ('（続き）' if used else ''), start_i + used); used += 1
        c = counts(rows)
        d.title(f'要件適合：{title}' + ('（続き）' if used > 1 else ''),
                f'○ 適合 {c["○"]}　△ 一部 {c["△"]}　× 未対応 {c["×"]}（全 {len(rows)} 項目）。判定はコードと設定を読んで決めた（2026-10-11 時点・承認と要求管理の後）')
        x0, y = 50, 130; xs = [x0]
        for w in cols: xs.append(xs[-1] + w)
        d.rect(x0, y, sum(cols), 34, '#e9ecef', LINE, 1)
        for i, h in enumerate(heads): d.text(xs[i] + 8, y + 7, h, 16)
        y += 34
        while k < len(rows):
            r = rows[k]; cells = [wrap(v, cols[i] - 16, fs) for i, v in enumerate(r)]
            h = max(c.count('\n') + 1 for c in cells) * fs * 1.25 + 14
            if y + h > FH - 40: break
            d.rect(x0, y, sum(cols), h, JUDGE[r[2]] if False else 'transparent', '#ced4da', 1)
            d.rect(xs[2], y, cols[2], h, JUDGE[r[2]], '#ced4da', 1)
            for i, cell in enumerate(cells):
                if i == 2: d.text(xs[2], y + 7, cell, 20, INK, cols[2], 'center')
                else: d.text(xs[i] + 8, y + 7, cell, fs, INK if i in (0, 1) else MUTED)
            y += h; k += 1
    return used

def build():
    d = D(); i = 0
    # F01 全体の構成
    d.frame('システム構成', i); i += 1
    d.title('rd-notebase のシステム構成', '1人1 vault（Obsidian）＝1つの Git リポジトリ（正本）。他人のノートはサーバの索引を通して参照する。AI なしで全機能が動く')
    d.rect(40, 130, 700, 930, '#f8f9fa', LINE, 1.5, True); d.text(60, 142, '各人の PC（Windows：Git for Windows＋Obsidian だけ）', 20)
    d.box(70, 190, 640, 150, 'notebase.cmd → client/run.py', '初期設定（何度でも）・更新・添付の手入れ・検査・push（30分ごと）・閲覧.html・PDF・コピー・照合・アーカイブ。Python は uv が用意')
    d.box(70, 365, 640, 330, 'vault（Obsidian で開く）', '01_daily デイリー・週ノート（Periodic Notes）\n10_notes ノート（作成日_タイトル.md、一意なのは id）。図は同じ .md に Excalidraw\n20_工程 案件の工程表（取りまとめ役だけ。dotpm）\n40_attachments 貼った画像（Git LFS）＋説明の .md\n50_data 実験データの説明の .md（本体は置き場）\n90_templates テンプレート（Templater）\n_refs 他人のノートのスタブ・アーカイブのスタブ', TEAL)
    d.box(70, 720, 640, 150, 'プラグイン（版と sha256 を固定して配る）', 'Excalidraw・Templater・Tasks・Periodic Notes・Calendar・Day Planner・Iconic・dotpm（project-manager）', '#ffffff')
    d.box(70, 895, 640, 140, '手元の控え', '閲覧.html（自分の vault の Web 閲覧）、pdf/（ID・版・QR 入りの PDF）、アーカイブの依存マップ（ブラウザ）', '#ffffff')
    d.rect(820, 130, 340, 560, '#f8f9fa', LINE, 1.5, True); d.text(840, 142, '正本（GitHub など）', 20)
    d.box(845, 190, 290, 170, 'vault-<人>.git', '1人1つ。全部の保存の履歴。画像は LFS', BLUE)
    d.box(845, 385, 290, 170, 'proj-<案件>.git', '案件の工程表（dotpm）。取りまとめ役は複数人', BLUE)
    d.box(845, 580, 290, 90, 'rd-notebase', 'このシステム（stable・main）', '#ffffff', 15, 17)
    d.rect(1240, 130, 320, 930, '#f8f9fa', LINE, 1.5, True); d.text(1260, 142, 'サーバ（tools/）', 20)
    d.box(1260, 190, 280, 200, '索引（kv.py）', '検査、索引 DB（名前→id・改名の履歴・アーカイブ済み）、スタブと図の SVG、コピー', ORANGE)
    d.box(1260, 410, 280, 170, '閲覧・出力', 'Web 閲覧（pages・render・access）、PDF（pdf_out）', ORANGE)
    d.box(1260, 600, 280, 190, '工程（pm・gantt・pm_pages）', '週報・計画変更の申請と承認・ガント図・ロードマップ', ORANGE)
    d.box(1260, 810, 280, 140, '台帳 registry.yml', '人・鍵（機密タグ）・案件・取りまとめ役・休日・上限', '#ffffff')
    d.rect(820, 760, 340, 300, '#f8f9fa', LINE, 1.5, True); d.text(840, 772, 'データの置き場（クラウド）', 20)
    d.box(845, 815, 290, 110, 'data/<人>/', '50_data の本体、画像の原寸（Git の外。sha256 で照合）', GRAPE, 15, 17)
    d.box(845, 940, 290, 100, 'アーカイブ/<人>/', '案件ごとの写しと記録.md', GRAPE, 15, 17)
    d.arrow(710, 260, 845, 260); d.text(722, 226, 'push', 15, MUTED)
    d.arrow(845, 300, 710, 300, LINE, 1.8, True); d.text(722, 306, 'clone', 15, MUTED)
    d.arrow(710, 470, 845, 470); d.text(722, 436, '同期', 15, MUTED)
    d.arrow(1135, 275, 1260, 275); d.text(1150, 241, '取り込み', 15, MUTED)
    d.arrow(1135, 470, 1260, 680); d.text(1170, 520, '工程表', 15, MUTED)
    a = d.arrow(1260, 360, 710, 640, '#1971c2', 1.8, True)   # 正本の列の下を回る
    a['points'] = [[0, 0], [-60, 0], [-60, 365], [-490, 365], [-550, 280]]; a['width'], a['height'] = 550, 365
    d.text(800, 700, 'スタブ・図の SVG（見てよいものだけ）', 15, '#1971c2')
    d.arrow(710, 560, 845, 870); d.text(735, 760, '重いデータ・原寸', 15, MUTED)
    d.arrow(710, 860, 845, 990); d.text(735, 900, 'アーカイブ', 15, MUTED)
    # F02 プログラムの役割
    d.frame('プログラムの役割', i); i += 1
    d.title('各プログラムの役割', '利用者の PC で動くもの（client/）と、サーバで動くもの（tools/）。同じ部品を手元でも使う（閲覧.html・PDF）')
    items = [
        ('client/notebase.cmd', '入口。rd-notebase を取得・更新し、uv で Python を用意して run.py を呼ぶ', TEAL),
        ('client/run.py', '初期設定（再実行可・ログインの保存）、vault の更新（vault.yml の範囲だけ）、id の付与、検査→push、工程表の同期、スタブ、閲覧.html、PDF、コピー、verify、archive', TEAL),
        ('client/vault.yml', '配るもの：テンプレート、設定の項目、プラグインの版と sha256、やめたもの', TEAL),
        ('tools/attach.py', '添付の手入れ：説明の .md を作る・付け直す（sha256）、重複を消す、大きい画像を縮めて原寸を残す、50_data をデータの置き場へ、照合', TEAL),
        ('tools/archive.py', '案件のアーカイブ：リンクを全部たどる依存マップ、移す／写す／残すの選択、記録（版・sha256）、スタブ、取り消し、日誌のルール', TEAL),
        ('tools/kv.py', '検査（予約プロパティ・日付・鍵・顧客名・id）、索引 DB、名前→id、改名の履歴、スタブと図の SVG、コピー、開示申請・コメント', ORANGE),
        ('tools/access.py・core.py', '鍵（機密タグ）と開示の判定、DB と共通の部品', ORANGE),
        ('tools/render.py・pages.py', 'Web 閲覧：本文・図（Excalidraw を直接描く）・版・見せる相手、閲覧者ごとのページ', ORANGE),
        ('tools/pdf_out.py', 'PDF：図のフレームを1枚ずつ、A4〜A0、余白に ID・版・状態・機密・QR', ORANGE),
        ('tools/pm.py・gantt.py・pm_pages.py', '工程：週報、計画変更の申請と承認、ガント図・ロードマップ、遅れ一覧', ORANGE),
        ('tools/dotpm.py', '工程表と dotpm の形式の行き来（番号 task_no・変更理由）', ORANGE),
        ('tools/server.py', '取り込み（1分ごと）：サーバ側の検査、差分の索引、工程の照合、Web 閲覧。バックアップと復旧の試験', ORANGE),
        ('tools/approve.py', '承認：承認者の vault の承認ノートだけを有効に（台帳の権限）。notebase.cmd approve', ORANGE),
        ('tools/quality.py', '確定の流れ：必須項目、承認後の変更、ゲート、要求の対応表（Web・PDF）', ORANGE),
        ('tools/setup_demo.py・draw.py', 'サンプルデータから試作環境を作る（山田・鈴木・上司・一般社員）', '#ffffff'),
    ]
    y = 140
    for k, (name, desc, bg) in enumerate(items):
        col = k % 3; x = 50 + col * 505
        if col == 0 and k: y += 185
        d.rect(x, y, 485, 170, bg); d.text(x + 14, y + 12, name, 18); d.text(x + 14, y + 44, desc, 15, MUTED, 455)
    # F03 データの流れ
    d.frame('データの流れ', i); i += 1
    d.title('データの流れ', '書く → 保存（push）→ 索引 → 参照・閲覧・PDF。終わった案件はアーカイブ')
    steps = [('書く', 'Obsidian でノート・図・デイリー。Ctrl+N でテンプレート（01〜10）', TEAL),
             ('添付の手入れ', '説明の .md、重複、縮小、50_data を置き場へ（attach.py）', TEAL),
             ('検査', 'id・予約プロパティ・日付・鍵・顧客名・コピーの範囲（kv.check）', TEAL),
             ('保存', 'コミットして正本へ push（30分ごと・手動）', BLUE),
             ('取り込み', 'サーバが1分ごとに検査（不合格は前の版のまま）、差分の索引、承認ノートの確認', ORANGE),
             ('参照・閲覧', 'スタブ（_refs）と図の SVG、Web 閲覧、PDF', ORANGE)]
    for k, (t, s, bg) in enumerate(steps):
        x = 50 + k * 255
        d.rect(x, 170, 225, 230, bg); d.text(x + 12, 182, f'{k + 1}. {t}', 20); d.text(x + 12, 222, s, 16, MUTED, 200)
        if k < len(steps) - 1: d.arrow(x + 225, 285, x + 255, 285, INK)
    d.text(50, 450, '工程表（取りまとめ役）', 22)
    flow2 = [('dotpm で直す', '20_工程/<案件>/', TEAL), ('同期', '案件リポジトリへ。衝突は _衝突/ に控える', BLUE),
             ('照合', 'サーバが承認済みの計画と比べ、承認が要る変更は申請に', ORANGE), ('承認・却下', '上司の確認待ち。却下なら計画を戻す', ORANGE)]
    for k, (t, s, bg) in enumerate(flow2):
        x = 50 + k * 380
        d.rect(x, 495, 340, 140, bg); d.text(x + 12, 507, t, 20); d.text(x + 12, 545, s, 16, MUTED, 316)
        if k < 3: d.arrow(x + 340, 565, x + 380, 565, INK)
    d.text(50, 690, 'アーカイブ（案件の完了）', 22)
    flow3 = [('起点', '案件まとめ（type: project）と project が同じノート', TEAL), ('依存のマップ', 'リンクを全部たどる。移す／写す／残すを選ぶ', TEAL),
             ('置き場へ', 'アーカイブ/<人>/<案件>_<日付>/ に vault と同じ並びで。記録.md に版・sha256', GRAPE),
             ('vault は軽く', '移したノートはスタブに。索引には残る（検索・Web・PDF）。取り消しもできる', ORANGE)]
    for k, (t, s, bg) in enumerate(flow3):
        x = 50 + k * 380
        d.rect(x, 735, 340, 160, bg); d.text(x + 12, 747, t, 20); d.text(x + 12, 785, s, 16, MUTED, 316)
        if k < 3: d.arrow(x + 340, 815, x + 380, 815, INK)
    d.text(50, 925, '確定：下書き（自由）→ レビュー待ち（必須項目を検査）→ 承認（承認者が自分の vault に承認ノート。notebase.cmd approve）。承認後に変えると再承認', 17, MUTED, 1500)
    d.text(50, 960, '鍵（機密タグ）：ノートごとに access。空なら本人だけ。見せる範囲はサーバが配信の時に判定し、必要な図だけ「開示」（申請→承認）できる', 17, MUTED, 1500)
    d.text(50, 995, '記録：保存のたびに Git の履歴。PDF の余白に ID・版・状態・QR。コピーはコピー元と版、アーカイブは元の版と sha256 を残す', 17, MUTED, 1500)
    # F04 適合のまとめ
    d.frame('要件適合のまとめ', i); i += 1
    d.title('要件適合のまとめ', '基本方針・工程管理要件・非機能要件・ISO 9001（開発業務システム 要件整理）に、今のシステムがどこまで合っているか')
    y = 160
    for name, rows in DOCS.items():
        c = counts(rows); tot = len(rows)
        d.text(50, y + 10, name, 24); d.text(330, y + 14, f'○ {c["○"]}　△ {c["△"]}　× {c["×"]}', 19, MUTED)
        x = 560; W = 980
        for k, col in (('○', OK), ('△', PART), ('×', NG)):
            w = W * c[k] / tot
            if w: d.rect(x, y, w, 50, col, '#adb5bd', 1); d.text(x, y + 13, f'{c[k]}', 18, INK, w, 'center')
            x += w
        y += 90
    d.text(50, y + 10, '見立て', 24); y += 55
    notes = ['記録を残す土台（Git の全履歴・一意な id・版を固定した引用・PDF の余白・sha256）は強い。基本方針の原則2・7・8 と非機能の ID・形式・可用性は合っている',
             '「確定を厳格に」を入れた：承認は承認者の vault の承認ノートだけ有効、レビュー待ちで必須項目、承認後の変更で再承認、ゲート、要求の対応表',
             'サーバは1分ごとに取り込み、不合格の版は出さず、差分の索引・工程の照合・バックアップと復旧の試験まで動く',
             '残るのは、認証付きの Web（画面からの承認・監査ログ）、電子署名、計画の版と負荷、規模の試験、設計変更・是正']
    for s in notes:
        y += d.text(70, y, '・' + s, 18, INK, 1460) + 14
    used = 0
    for name, rows in DOCS.items():
        used += table(d, rows, name, i + used)
    i += used
    # 次の一手
    d.frame('主な課題と次の一手', i); i += 1
    d.title('主な課題と次の一手', '上から優先。右は関係する要件')
    y = 140
    for no, t, s, ref in NEXT:
        d.rect(50, y, 1500, 120, '#ffffff', '#ced4da', 1); d.text(70, y + 14, no, 30, '#c92a2a')
        d.text(120, y + 16, t, 21); d.text(120, y + 52, s, 17, MUTED, 1000); d.text(1150, y + 18, ref, 16, MUTED, 380)
        y += 135
    return d

def save(path):
    d = build()
    texts = '\n\n'.join(e['text'] for e in d.els if e['type'] == 'text')
    fm = {'id': '261011-sysxv', 'type': 'memo', 'owner': 'rdnb', 'project': '', 'status': 'draft', 'access': [],
          'created': '2026-10-11', 'updated': '2026-10-11',
          'summary': '今のシステム構成と各プログラムの役割、基本方針・工程管理要件・非機能要件・ISO 9001 への適合の判定と次の一手',
          'excalidraw-plugin': 'parsed'}
    c = {k: counts(v) for k, v in DOCS.items()}
    body = ('# システム構成と要件適合\n\n2026-10-11 時点・承認と要求管理の後。図は Excalidraw（この .md を Obsidian で開くと図で見られる）。PDF は同じフォルダの .pdf。\n\n'
            + ''.join(f'- {k}：○ {v["○"]}・△ {v["△"]}・× {v["×"]}\n' for k, v in c.items())
            + '\n%%\n# Excalidraw Data\n\n## Text Elements\n' + texts + '\n\n## Drawing\n```json\n'
            + json.dumps({'type': 'excalidraw', 'version': 2, 'source': 'rd-notebase', 'elements': d.els,
                          'appState': {'viewBackgroundColor': '#ffffff', 'gridSize': None}, 'files': {}}, ensure_ascii=False, indent=1)
            + '\n```\n%%\n')
    open(path, 'w', encoding='utf-8').write(join_fm(fm, body))
    print('作成:', path, '要素', len(d.els), 'フレーム', d.n)

if __name__ == '__main__':
    save(sys.argv[1] if len(sys.argv) > 1 else 'docs/システム構成と要件適合.md')
