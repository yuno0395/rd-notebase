# rd-notebase

研究開発・量産メーカー向けの「開発ノートを正本にする基幹システム」の試作です。
Obsidian（Markdown＋Excalidraw）で各人が考えを書き、Gitで集め、サーバが索引・権限・Web閲覧・PDF・工程管理を受け持ちます。

> 試作段階のコードです。サンプルデータの会社名・製品名・人物はすべて架空です。

## 考え方

- **判断の根拠が、信頼の根拠になる**。目的は顧客の信頼に応え続ける開発。そのために、なぜそう決めたか（検討・計算・却下した案）を説明できる形で残す。文書は引用で組み立てる（コピーしない）
- **1人1 vault**。他人のノートはサーバの索引を通して参照する（同期しない）
- **ノート単位の鍵（機密タグ）**。見せる範囲はサーバが配信時に判定。必要な図だけ「開示」できる
- **AIなしで全機能が動く**（AIは任意の拡張）
- ISO 9001（7.5 文書化した情報、8.3 設計・開発）の記録を、普段の作業から自動で残す

詳しくは `docs/` の要件書を参照してください。

## 中身

```
tools/           Pythonプログラム（索引・権限・Web閲覧・PDF・工程管理）と画面
  kv.py          ノート作成・ID採番・添付・push時の検査・索引・開示申請・コメント
  pm.py          工程管理：週報・計画変更の申請と承認・dotpm との同期（sync）・Excalidrawのガント図
  gantt.py       工程の集計（やることの数・見込み・遅れ）とガント図の描画
  pages.py ほか  Web閲覧のページ生成（render / access / pm_pages / core）
  pdf_out.py     PDF出力（日本語フォント埋め込み、ID・版・QRのフッター）
  site_template.html  画面（素のHTML/CSS/JavaScript）
  dotpm.py       工程表と dotpm（Obsidian の工程管理プラグイン）の形式の行き来
  approve.py     承認：承認者の vault の承認ノートだけを有効にする（台帳の権限）
  quality.py     確定の流れ（必須項目・承認後の変更・ゲート）と要求の対応表
  server.py      サーバの取り込み（検査・差分の索引・承認の反映・工程の照合・Web 閲覧）とバックアップ・復旧の試験
  attach.py      添付の手入れ（説明の .md・重複・縮小・50_data とデータの置き場・照合）。利用者の PC で push の前に動く
  archive.py     案件ごとのアーカイブ（依存のマップ・移す／写す／残す・記録・取り消し）
  setup_demo.py  サンプルデータから試作環境を作る
  dev/           サンプルデータを作った時の台本（参考）
sample-vault/    Obsidian vault の雛形（フォルダ・テンプレート・初期設定・LFS設定）。notebase が利用者の vault に配る
client/          利用者の PC で動く部分（notebase.cmd・run.py・配るものの一覧 vault.yml）
sample-data/     サンプルデータ（山田・上司・一般社員の vault、案件 P00001 の工程表）
config/          タグ台帳・利用者・案件・休日（registry.yml）
docs/            要件書（基本方針・非機能要件・ID体系・vault設計・工程管理・要件整理）とレビュー記録、やること、
                 システム構成と要件適合（Excalidraw の図付きノートと PDF。tools/dev/make_overview.py で作り直す）
```

## 試作を動かす

必要なもの：Python 3.10以上、Git、Git LFS、日本語フォント（PDF出力用）

```bash
pip install -r requirements.txt
python3 tools/setup_demo.py          # 作り直す時は --reset
```

`site/` にWeb閲覧ができます（ブラウザで開くだけ。サーバ不要）。

| ファイル | 閲覧者 | 見どころ |
|---|---|---|
| `site/index.html` | 上司（鍵の管理者） | 確認待ち（公開の判断・計画変更の承認）、見せる相手の変更、工程・ロードマップ |
| `site/yamada.html` | 開発担当（山田） | 工程・週報の経過、コメント（工程表の編集は Obsidian の dotpm） |
| `site/staff.html` | 別チームの一般社員 | 公開された資料だけが見える。見えない資料は🔒と相談先 |

### よく使うコマンド

```bash
python3 tools/kv.py push vault-yamada "メッセージ"     # 検査 → コミット → サーバへ → 索引更新
python3 tools/kv.py refs vault-yamada vault-suzuki     # 購読：見てよい他人のノートのスタブを _refs/ に作る
python3 tools/view.py build boss index.html            # Web閲覧を作り直す（閲覧者ごと）
python3 tools/view.py pdf <ノートID> A4 boss            # PDF出力（A4〜A0）
python3 tools/pm.py gantt <工程表ID> m3                 # Excalidrawのガント図（書き込みは残して作り直す）
python3 tools/pm.py sync proj-P00001                    # dotpm の変更を工程表へ（承認が要るものは申請。サーバの受け取り処理）
python3 tools/pm.py decide <申請ID> approved boss "コメント"               # 承認（boss の vault に承認ノートを書いて反映）
python3 tools/server.py once                            # サーバの取り込みを1回（検査→差分の索引→承認の反映→工程の照合→Web閲覧）
python3 tools/server.py run                             # 取り込みを1分ごとに続ける
python3 tools/server.py backup /backup/rdnb             # ミラー（LFS も）と索引・台帳の控え（30日分）
python3 tools/server.py restore-test /backup/rdnb       # 控えだけで索引を作り直せるか試す
python3 tools/view.py trace P00001 boss                 # 要求の対応表の PDF（A3 横）
```

PDFの日本語フォントは自動で探します。見つからない時は環境変数 `RDNB_FONT` にTTF/TTCのパスを指定してください。

### 試作の割り切り

- Web閲覧は「閲覧者ごとに、見てよいものだけを入れた1枚のHTML」を事前に作る方式です
- 画面での承認は、出てきたコマンド（`notebase.cmd approve …`）を承認者が自分の PC で実行します（自分の vault に承認ノートが残る）。コメント・申請は、出てきた文字を手で反映します。本番はログイン付きの Web から送ります
- 利用者の PC の `閲覧.html` は自分のノートだけ（他人のノート・案件全体はサーバの Web 閲覧）。コメント・見せる相手の変更などのボタンは出るが、自分だけの控えでは使わない
- 他人のノートの参照はスタブ（プロパティ・要約・リンク先・図の SVG）まで。スタブを開いて本文を取得する専用プラグインはまだ無く、本文は Web 閲覧で見ます
- 工程表の履歴（計画変更の経緯）は、`setup_demo.py` で作り直すと最初の1件からになります

## Obsidian で使う（利用者の PC）

利用者が用意するのは **Git for Windows と Obsidian だけ**です。Python などは `notebase.cmd` が自動で用意します。

```
workspace/              好きな場所に作る空のフォルダ
├─ notebase.cmd         入口。ダブルクリックするだけ（client/notebase.cmd を配る）
├─ 閲覧.html            自分のノートの控え（Obsidian なしで読める。notebase が作り直す）
├─ pdf/                 notebase.cmd pdf で出した PDF
├─ vault/               自分の Obsidian vault（自分の正本リポジトリ）
│   ├─ 01_daily/        デイリーノート・週ノート（01_daily/週）
│   ├─ 10_notes/        ノート本体。新しいノートと図は全部ここ（フラット。分類はプロパティ）
│   ├─ 30_calc/         計算（Pythonスクリプトと結果）
│   ├─ 40_attachments/  貼る画像など（中身は Git LFS）と説明の .md
│   ├─ 50_data/         実験データなど重いものの説明の .md（本体は下の data/。Git に入らない）
│   ├─ 90_templates/    テンプレート（notebase が配る。直接編集しない）
│   └─ .rdnb/           自分のID・正本の場所（config.yml）、構成の版、アーカイブの記録（archives/）
├─ data/                データの置き場（既定。config.yml の data_dir でクラウドの同期フォルダに変える）
│   ├─ <ID>/            50_data に入れた本体、画像の原寸（原寸/）
│   └─ アーカイブ/       案件ごとのアーカイブ（config.yml の archive_dir で変えられる）
└─ .notebase/           rd-notebase そのもの（隠しフォルダ。notebase.cmd が取得・更新）
```

### はじめて使う時

1. Git for Windows と Obsidian を入れる
2. 空のフォルダに `notebase.cmd` を置いてダブルクリック。ユーザーIDと、自分の vault の正本リポジトリのURL（未定なら空）を聞かれる
3. Obsidian で「保管庫としてフォルダを開く」→ `workspace/vault` を開く。「この保管庫の作成者を信頼しますか？」で「作成者を信頼しプラグインを有効化」を押す
4. 設定 → Templater →「Trigger Templater on new file creation」をオン（確認の画面で「I understand the risks」にチェックして Enable）。端末ごとの設定なのでファイルでは配れない。デイリー・週ノートにテンプレートが入るようになる

### 普段

- **何もしなくてよい**。30分ごとに自動で検査して正本に push する（Windows のタスクスケジューラ「rd-notebase push」）
- すぐ push したい時・システムを更新したい時は `notebase.cmd` をダブルクリック（本体の更新 → vault の更新 → 検査 → push）
- 状態の確認は `notebase.cmd status`
- **Obsidian なしで読む**：`workspace/閲覧.html` をダブルクリック（ブラウザで開く1つのファイル。中身が変わった時に push のついでに作り直す）。すぐ作り直して開くなら `notebase.cmd view`
- **PDF に出す**：`notebase.cmd pdf <ノートのid>`（A3〜A0 は2つ目に。例 `notebase.cmd pdf 261005-ir79w A3`）。図のフレームを1枚ずつ、余白に ID・版・状態・QR を入れて `workspace/pdf/` に出す。id の代わりにタイトルの一部でもよい（1件に決まる時）
- **保存できない時**：push や検査が止まると、vault に `_notebase のお知らせ.md` を置く（Obsidian の一覧とデイリーの「未分類」に出る）。理由と直し方が書いてあり、保存できるようになると自動で消える
- **毎回 GitHub などのログイン画面が出る時**：ログインが保存されていない。setup はどこにも設定がない時だけ、この vault に `credential.helper manager`（Git for Windows の資格情報マネージャー）を設定する。それでも出る時は、コマンドプロンプトで `git config --show-origin --get-all credential.helper` を見る。会社の PC で保存が禁止されている時は SSH 鍵に切り替える
- **自動 push を止める**：`schtasks /Change /TN "rd-notebase push" /DISABLE`（戻す時は `/ENABLE`。消す時は `schtasks /Delete /TN "rd-notebase push" /F`）。止めている間は notebase.cmd を手で実行すると送られる
- **途中で止まった初期設定**：`notebase.cmd` をもう一度実行すればよい（`.git` だけの vault・登録済みの送り先・空の正本の clone もそのまま使って続きをする）

### 添付と実験データ（40_attachments と 50_data）

- **貼る画像・小さいファイル**は今までどおり Obsidian で貼る（`40_attachments` に入り、Git LFS で送る）。push のたびに notebase が手入れする：
  - 説明の .md（`type: attachment`）がない本体には作る（id・sha256・大きさ。持ち主・案件・鍵は貼ったノートから引き継ぐ）
  - 既にある添付と同じ中身（sha256）の画像は、リンクを既にある方に直して重複を消す
  - 説明の .md の `file` はリンク（`file: "[[名前.png]]"`）。Obsidian で改名すると一緒に直る。Obsidian の外で改名した時は、同じ中身のファイルを探して付け直す
  - 新しく来た大きい画像（長辺が `image_max_px`＝既定 1920px 超）は、原寸をデータの置き場の `原寸/` に残して、vault には縮小版を置く（`image_max_px: 0` で縮めない）
- **実験データなど重いもの**は `50_data` に入れる。push の時に本体をデータの置き場（vault の外）へ移し、`50_data` に説明の .md（置き場の中の場所・sha256・本体を開くリンク）を残す。Git には説明の .md だけが入る。`40_attachments` に置いた大きすぎるファイル（台帳の `limits.attach_max_bytes`＝20MB 超）も同じように移し、貼ってあったリンクは説明の .md に付け替える
- **データの置き場**は `.rdnb/config.yml` の `data_dir`（例 `data_dir: D:/OneDrive/rd-data`）。クラウドの同期フォルダを指すと、容量を Git から切り離せる。版の履歴はクラウド側に任せる。vault ごとクラウドに置くと `.git` が同期で壊れることがあるので、vault はローカルに置き、データの置き場だけをクラウドにする
- `notebase.cmd verify`：添付とデータの置き場の本体を sha256 で照合する（差し替わり・欠けの確認）
- Obsidian の「除外するファイル」に `40_attachments/` を入れてある（検索・グラフ・リンク候補に出さない）。除外しても、改名した時のリンクの書き換えは効く

### 承認（承認ノート）と確定の流れ

- **状態**：`draft`（下書き。何も強制しない）→ `review`（レビュー待ち。push の検査で種類ごとの必須項目を確かめる）→ 承認
- **必須項目**は台帳 `config/registry.yml` の `required`。例：検討は「結論」「却下した案と理由」の節、要求は `source_kind`・`source`・`criteria`、試験は `verifies`・`test_result`（progress を レビュー待ち・完了 にした時は警告だけ）
- **承認は、承認する人が自分の vault に承認ノート（`type: approval`）を書く**：`notebase.cmd approve <申請・ノートのid> 承認 "理由"`（却下・取り消しも同じ。開示の一部だけ許す時は `--targets id#F01,id2`）。Web 閲覧の確認待ちの画面は、このコマンドを表示する
- 各人の vault は本人だけが書き込める（GitHub などの権限）ので、「誰の vault にあるか」が本人の証明になる。サーバの索引は、**台帳で権限のある人の vault の承認ノートだけ**を有効にする（開示＝資料の鍵の owner・deputy、計画変更・文書＝案件の owner・deputies、案件のない文書＝台帳の approvers）。申請やノートに「承認」と書いてあるだけのものは、承認待ちとして扱い Web 閲覧に ⚠ を出す
- 承認ノートには判断した時の版が残る。**承認した後に中身を変えると「承認後に変更あり（再承認が必要）」**になり、レビュー待ちに戻る（状態・更新日の書き換えだけは変更に数えない）
- **ゲート（DR）**：テンプレート `09-gate`。節目（`milestone: M02`）と出す資料（`items`）を並べる。案件ページに準備状況（承認済み n/m）を出し、全部が承認済みで「準備完了」、責任者がゲートを承認すると「通過」

### 要求の対応表（一本の糸）

- 要求（`07-req`：出所の区分・出所・合否基準・優先度）← 設計（`derived_from: [[要求]]`）・試験（`08-test`：`verifies`・`test_result`・`tested`）・不具合（`10-issue`：`affects`・`parts`・`state`）
- 案件ページの「要求の対応表」と `view.py trace <案件>`（PDF）で、設計なし・試験なし・不合格・**試験の後に要求が変わった（再検証が必要）**・未解決の不具合を目立たせる
- 品番（`parts`）からは品番のページで、その品番を参照する要求・設計・試験・不具合を辿れる

### サーバの取り込み（tools/server.py）

GitHub.com では push を拒否する仕組み（pre-receive）が使えないので、**受け取ってから、合格した版だけを有効にする**。

- 1分ごと（`server.py run`、またはスケジューラから `server.py once`）に、台帳の各リポジトリを取ってくる（`registry.yml` の `remotes` に URL があれば fetch）
- main が変わったリポジトリだけ検査する。合格なら `refs/rdnb/accepted` を進め、**変わった vault だけ索引を入れ直す（差分の索引）**。不合格なら前の合格した版のまま（索引・Web 閲覧・他の人のスタブには出ない）。本人の notebase は次の保存の時に `_notebase のお知らせ.md` で理由を知らせる
- 承認ノートで判断された計画変更を工程表に反映し、案件リポジトリの dotpm の変更を照合し、Web 閲覧を作り直す
- **保全**：`server.py backup <置き場>` を毎日（ミラーは消えた枝も残す。LFS の中身、索引と台帳は日付ごとに30日分）。`server.py restore-test <置き場>` を月1回（控えだけで索引を作り直し、件数を比べる）。復旧は「ミラーから戻す → `kv.py index`」の2段

### 案件のアーカイブ（notebase.cmd archive）

ノートと添付が増えすぎないように、終わった案件を vault の外へ移す。台帳の案件が「完了」になると、notebase が `notebase.cmd archive P00001` を案内する。

1. **起点**は案件のまとめ（テンプレート `06-project`。`type: project`・`project: P00001`）と、`project` がその案件のノート。そこからリンク（貼り付け・関係のプロパティを含む）を**全部たどる**（他の案件のまとめも止めずに）
2. **依存のマップ**がブラウザで開く（この PC の中だけ。線は「左が右をリンク」、左の色の帯は案件）。箱を押すか右の一覧で、ノート・添付ごとに **移す／写す／残す** を選ぶ。初期値は：
   - 移す：この案件だけのもの
   - 写す：続いている他の案件のもの、vault に残るノートから参照されているもの（移すとリンクが切れるので、vault に残して案件完了時点の写しを置く）。添付は使っているノートが1つでも残れば写す
   - 残す：デイリー・週ノート（下の「日誌」で扱う）
3. 「この内容でアーカイブ」で実行。置き場 `アーカイブ/<ID>/<案件>_<日付>/` に vault と同じ並びで置く（そのフォルダを Obsidian で開けば読める）。`記録.md`・`manifest.json` に、扱い・元の場所・元の版（コミット）・sha256・理由を残す
4. vault から消したノートは `_refs/アーカイブ/` に同じ名前のスタブを置くので、残るノートのリンクは切れない（記録の写し `.rdnb/archives/` から、別の PC でも置き直す）。サーバの索引は記録の版から読み出すので、**検索・Web 閲覧・PDF には残る**（「アーカイブ済み」と出る）

- `notebase.cmd archive P00001 --yes`：マップを開かず初期値のままアーカイブ
- `notebase.cmd archive 日誌 2`：2年より前のデイリー・週ノートと、どの案件にも属さずどこからもリンクされていない古いメモ
- `notebase.cmd archive --list`／`--verify <記録名>`（置き場の写しを sha256 で照合）／`--undo <記録名>`（取り消し。移したノートを元の版から vault に戻す）

### notebase.cmd がすること

| 処理 | 内容 |
|---|---|
| 本体の更新 | `.notebase` を `stable` ブランチに合わせる（開発者は `workspace/notebase.local.cmd` に `set "BRANCH=main"` を書くと main を使う） |
| vault の更新 | `client/vault.yml` に書いた範囲だけを `sample-vault/` に合わせる：テンプレート、プラグイン本体（版を固定・sha256 で照合）、システムが決める設定項目。**ノートには触らない**。更新の前に vault を自動でコミットするので戻せる |
| id の付与 | テンプレートを使わずに作ったノートに id を付ける（名前はそのまま）。以前の名前「作成日_タイトル_hash(.excalidraw).md」は、末尾の乱数と `.excalidraw` を一度だけ外す（vault 内のリンクも直す） |
| 添付の手入れ | 説明の .md の作成・付け直し、重複の削除、大きい画像の縮小、50_data と大きすぎるファイルをデータの置き場へ（上の「添付と実験データ」） |
| 検査 → push | `tools/kv.py` の検査（予約プロパティ、日付の書き方、顧客名、鍵など）を通ったものだけを push する。push はこれに一本化（Obsidian Git は使わない） |
| 控えの作成 | 自分の vault だけで索引を作り（`.notebase/.state/view`）、サーバの Web 閲覧と同じ部品で `閲覧.html` を作る（Web閲覧 段階1）。図は Excalidraw のデータから直接描く（フレームのない図・手描き・貼った画像も出る）。`#F02` と `#^frame=…` のどちらの引用も読める |

### vault に入っている設定（sample-vault/.obsidian）

- 新しいノート → `10_notes`、添付 → `40_attachments`、リンクは `[[…]]` 形式
- デイリーノート → `01_daily`（名前 `2026-10-05`）、週ノート → `01_daily/週`（名前 `2026-W41`）。Periodic Notes で作る
- **週の始まりは月曜**（Calendar の `weekStart: monday`）。日本語環境の既定は日曜始まりで、そのままだと Periodic Notes が月〜土曜に前の週（例 10/5 に `2026-W40`）を作ってしまう
- **Periodic Notes とコアのデイリーノートの「テンプレート」は空**。テンプレートは Templater がフォルダごとに当てる（01_daily＝periodic/daily、01_daily/週＝periodic/weekly）。Periodic Notes にテンプレートを指定すると、Templater の書き方が実行されずにプロパティにプログラムがそのまま入る。もしそうなったノートがあれば、開いて Templater の「Replace templates in the active file」を実行すると直る
- Tasks：全体の絞り込みに `path does not include 90_templates`（テンプレートの `- [ ]` がやることの一覧に出ないように）
- Templater の「Trigger Templater on new file creation」は**端末ごとの設定**（同梱できない）。オンにすると新規ノートの作成時にタイトルを聞いて名前・id を付ける。オフでも push 時に notebase が付ける
- Excalidraw：**図データの圧縮オフ**（`onceOffCompressFlagReset: true` を同梱。無いと初回起動でプラグインが圧縮をオンに戻す）、保存先 `10_notes`、スクリプトの置き場 `90_templates/excalidraw-scripts`、部品（ライブラリ）の置き場 `90_templates/excalidraw-libraries`、起動時の案内画面はオフ
- ホットキー：Ctrl+N ＝ テンプレートを選んで新規作成、Ctrl+Q ＝ 図付きノートの図と文章の切り替え
- 見やすさ：`40_attachments/` は除外ファイル（検索・クイックスイッチャー・リンク候補に出ない）、すべてのファイル形式を一覧に表示、使わないコア機能（グラフ・キャンバス・コアのテンプレート・ノートコンポーザー・同期）はオフ
- Iconic：ファイル・フォルダなどにアイコンと色を付けられる（ルールは未設定）
- リボン：Excalidraw・ベースの新規作成、コアのデイリーノート、Iconic のルールブックは隠す（更新のたびに戻す。表示名で記録されるので日本語表示の Obsidian 前提）
- 画面配置：左上にファイル一覧・検索など、左下に Timeline・Calendar・00_分類の「未分類」。`.obsidian/workspace.json` が無い時だけ置くので、その後は自由に変えてよい

### 新しいノート（Ctrl+N）

**Ctrl+N でテンプレートを選んで作ります**（Templater の「Create new note from template」に割り当て済み）。タイトルを聞かれ、ファイル名 `作成日_タイトル`（例 `261004_X200中間報告.md`。図付きでも `.excalidraw` は付けない。同じ名前があれば末尾に 2, 3）とプロパティ `id`（例 `261004-wfyzi`）が付きます。**ファイル名は後から自由に変えてかまいません**（一意なのは `id`。リンクは Obsidian が直し、索引は改名前の名前も覚えています）。題名はファイル名（「作成日_」より後ろ）で、プロパティ `title` は持ちません（以前のノートの `title` は notebase が外し、ファイル名と違う題名は `aliases` に移します）。ノートは全部 `10_notes` に入ります（フォルダ分けはしない）。

| テンプレート（90_templates/new） | 用途 |
|---|---|
| `01-base` | **基本（一番上に出る）**。検討・メモ・計算など何でも。文章と Excalidraw の図を1ファイルに（前半が文章、`%%` の後が図）。`type` は空＝未分類で、後で決める |
| `02-meeting` | 議事録。参加者・決まったこと・宿題（担当と期限付きのやること）＋ホワイトボード代わりの図 |
| `03-report` | 報告。要旨・スライド（各ノートの図のフレームを引用）・結論と依頼事項。PDF に出す |
| `04-daily` | 今日のデイリーノートを開く（無ければ `01_daily/2026-10-11.md` を作る） |
| `05-weekly` | 今週の週ノートを開く（無ければ `01_daily/週/2026-W41.md` を作る） |
| `06-project` | 案件まとめ（`type: project`）。目的・体制・節目と、案件のノートへのリンク。アーカイブの起点 |
| `07-req` | 要求（出所の区分・出所・合否基準・優先度）。レビュー待ちで出所・合否基準が必須 |
| `08-test` | 試験（`verifies: [[要求]]`・結果・試験日） |
| `09-gate` | ゲート（DR）。節目と出す資料の一覧 |
| `10-issue` | 不具合（`affects`・品番・`state`） |

デイリー・週ノートの中身は `90_templates/periodic` の daily・weekly です。Ctrl+N の `04-daily`・`05-weekly`、Periodic Notes のコマンド（「Open today's daily note」など）、カレンダーのどれから開いても、`01_daily` に日付の名前で作られ、Templater がフォルダごとに中身を入れます（ファイル名が日付なので、題名を聞かれません）。ファイル一覧の「新規ノート」やコマンドパレットで作った空のノートには、Templater が 01-base を入れます（フォルダテンプレート `/`）。Excalidraw の新規作成も 01-base から作ります（図のテンプレートに指定。実機では未確認）。それでも id のないノートには、push 時に notebase が id を付けます。

### 分類（00_分類.base）

フォルダで分けない代わりに、`00_分類.base` のビューで分けます。分類はプロパティ（主に `type`）を入れるだけで、ファイルは動かしません。

| ビュー | 出るもの |
|---|---|
| 未分類 | `type` が空のノート（inbox の代わり。デイリー・週ノートにも埋め込み） |
| 最近の更新 | 更新の新しい順に50件 |
| 案件別 | `project` ごとにまとめて表示 |
| 検討 / 議事録 / 報告 | `type` が study / meeting / report |
| 計算・要求・メモ | `type` が calc / req / memo |
| レビュー待ち | `progress` が「レビュー待ち」 |
| 図付き | Excalidraw の図を持つノート |

ビューを足す時は `00_分類.base` の `views` に条件を書いて足します（雛形を直すと notebase が全員に配る）。

### 他人のノートを参照（購読）

`.rdnb/config.yml` に `subscribe: [vault-suzuki]` のように購読する vault を書くと、notebase が更新・定期 push のたびに `_refs/vault-suzuki/` にスタブを作ります。

- スタブの名前は「元の名前（書いた人）」で、プロパティ（予約名と台帳で `stub: true` のもの）・要約・リンク先だけを持つ。`[[261007_X200 筐体材料の選定（鈴木）]]` のように自分のノートから直接リンクでき、被リンク・グラフもそのまま動く。書いた人が改名すると、スタブの名前と自分のノートの中のリンクを notebase が直す
- 自分が見てよいノート（`access` の鍵を全部持っている）だけが届く。鍵が変わって見られなくなると、次の更新でスタブが消える。見てよくないノートへのリンクはスタブに載せない
- `_refs/` は Git に入れず、`00_分類.base` にも出さない。一覧は `_refs/参照.base`（書いた人ごと）
- 図付きノートは、サーバがフレームごとに SVG に描いて `_refs/<vault>/_図/` に置き、スタブに埋め込む（Excalidraw のデータそのものは配らない。貼った画像も見てよいものだけ）。Obsidian でそのまま図が見える
- 本文はサーバの索引から Web 閲覧で見る（スタブを開いて本文を取る専用プラグインは未作成）

### 工程表（dotpm）

工程表は案件のリポジトリ（例 `proj-P00001`）に dotpm の形で置き、**取りまとめ役**（台帳 `projects.<案件>.managers`、複数人）が Obsidian の dotpm（表・ガント・カンバン）で直します。

- 取りまとめ役の vault には、notebase が案件のリポジトリを `20_工程/<案件>/` に取得し、更新・定期 push のたびに取り込み・送る。dotpm は全員に配るが、`20_工程` が空の人には何も出ない
- 休む・辞める時は、台帳の `managers` を書き換えるだけで続く（工程表は個人の vault にない）。外れた人の `20_工程/<案件>` は同期が止まる
- 2人が同じタスクを近い時間に直したら、先に送った人の内容に合わせ、後の人の変更は `_衝突/` に控えて `_notebase のお知らせ（工程表）.md` で知らせる
- 承認が要る変更（実働5日超の遅れ、節目の移動、追加・削除・担当替えなど）は、dotpm のタスクの「変更理由」「理由の区分」に書いてから保存する。サーバが承認済みの計画と比べて申請にし、上司の確認待ちに並ぶ。却下されると dotpm の日程は承認済みの計画に戻る
- 番号（`task_no`：T02 など）はサーバが振る。週報・やることの `[task:: 工程表ID#T02]` はこの番号を使う
- 休日は台帳から dotpm に入れる。週の見出しは日付
- **一人で使う**（セルフマネジメント）：dotpm で `20_工程/` に自分のプロジェクトを作れば、普通のノートと同じく保存・push される（Git から外すのは台帳の案件のフォルダだけ。この PC の `.git/info/exclude` に書く）
- dotpm は `id`・`title`・`status`・`type`・`progress` をこちらと別の意味で使うので、dotpm のファイル（`pm-project`・`pm-task`）と `20_工程/` は id の付与・検査・索引・分類の対象外。こちらの番号・見積は `task_no`・`est` に持つ。プロパティの型は `.obsidian/types.json` で文字に固定（`progress` が数と判断されて検討ノートの「検討中」が型違いにならないように）
- Project Planner は一度試したが、特定のフォルダ（テンプレート・`_refs` など）を読む対象から外せず使いづらかったのでやめた（入っていれば notebase が外す。書いた行はそのまま残る）

### 他人のノートをコピー（図・貼った画像ごと）

自分で手を入れたい時は、他人のノートを**新しい ID で自分の vault にコピー**します：`notebase.cmd copy <コピー元の id>`（試作では `python3 tools/kv.py copy vault-yamada 261007-gikgs`）。

- 本文・Excalidraw の図データ・図に貼った画像（`40_attachments/` に入る）をまとめてコピーし、Obsidian でそのまま図として編集できる
- **コピー元を残す**：プロパティ `copied_from: "[[コピー元]]"`（スタブがあればそこへリンク）と `copied_version: <その時の版>`。コミットの文言も「コピー: タイトル（鈴木 の 261007-gikgs@c160c27 から）」になり、履歴に残る。索引にも「コピー」の関係として入り、Web 閲覧のノートに「コピー元」と版が出る
- **見せる範囲**：鍵（`access`）はコピー元のまま引き継ぐ。鍵を外して本人だけにするのはよいが、別の鍵に替える・一部を外すと、コピー元より広く見せることになるので push の検査で止まる
- 見てよくないノート、見てよくない画像が貼ってある図はコピーできない。サーバの索引に届く時だけ使える

### 書き方の約束

- やること：`- [ ] 内容 📅 2026-10-14 [task:: 工程表ID#T02]`（`task::` で工程タスクに紐づき、進捗＝完了数／総数になる）
- 図のフレームの引用：`![[作成日_タイトル#F02]]`、版を固定する時は `#F02@コミット`（図付きノートも普通の `.md`。図かどうかはプロパティ `excalidraw-plugin` で Excalidraw が見分ける）
- 品番などの外部ID：`[[part:482015-BR1C]]`
- プロパティ：決まった名前以外を自分用に足す時は `my_` を付ける（例 `my_優先`）。皆で使うなら `config/registry.yml` の `properties` に登録する。顧客名はプロパティに書かず本文に（他人に配る要約に載るため）。詳しくは `docs/` の vault設計 5.4
- 新しいノートは Ctrl+N（テンプレートを選ぶ）。IDのないノートは push 時に notebase が id を付ける

## ライセンス

未定（試作）。
