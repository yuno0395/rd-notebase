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
  setup_demo.py  サンプルデータから試作環境を作る
  dev/           サンプルデータを作った時の台本（参考）
sample-vault/    Obsidian vault の雛形（フォルダ・テンプレート・初期設定・LFS設定）。notebase が利用者の vault に配る
client/          利用者の PC で動く部分（notebase.cmd・run.py・配るものの一覧 vault.yml）
sample-data/     サンプルデータ（山田・上司・一般社員の vault、案件 P00001 の工程表）
config/          タグ台帳・利用者・案件・休日（registry.yml）
docs/            要件書（基本方針・非機能要件・ID体系・vault設計・工程管理・要件整理）とレビュー記録
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
| `site/yamada.html` | 開発担当（山田） | 工程・週報の経過、コメント |
| `site/staff.html` | 別チームの一般社員 | 公開された資料だけが見える。見えない資料は🔒と相談先 |

### よく使うコマンド

```bash
python3 tools/kv.py push vault-yamada "メッセージ"     # 検査 → コミット → サーバへ → 索引更新
python3 tools/kv.py refs vault-yamada vault-suzuki     # 購読：見てよい他人のノートのスタブを _refs/ に作る
python3 tools/view.py build boss index.html            # Web閲覧を作り直す（閲覧者ごと）
python3 tools/view.py pdf <ノートID> A4 boss            # PDF出力（A4〜A0）
python3 tools/pm.py gantt <工程表ID> m3                 # Excalidrawのガント図（書き込みは残して作り直す）
python3 tools/pm.py sync proj-P00001                    # dotpm の変更を工程表へ（承認が要るものは申請。サーバの受け取り処理）
python3 tools/pm.py decide <申請ID> approved boss "コメント"               # 承認
```

PDFの日本語フォントは自動で探します。見つからない時は環境変数 `RDNB_FONT` にTTF/TTCのパスを指定してください。

### 試作の割り切り

- Web閲覧は「閲覧者ごとに、見てよいものだけを入れた1枚のHTML」を事前に作る方式です
- 画面での承認・コメント・申請は、出てきた文字を手で反映します（画面から直接保存しない）。本番はサーバに送ります
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
│   ├─ 40_attachments/  添付（中身は Git LFS）と付属ノート
│   ├─ 90_templates/    テンプレート（notebase が配る。直接編集しない）
│   └─ .rdnb/           自分のID・正本の場所（config.yml）、構成の版
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

### notebase.cmd がすること

| 処理 | 内容 |
|---|---|
| 本体の更新 | `.notebase` を `stable` ブランチに合わせる（開発者は `workspace/notebase.local.cmd` に `set "BRANCH=main"` を書くと main を使う） |
| vault の更新 | `client/vault.yml` に書いた範囲だけを `sample-vault/` に合わせる：テンプレート、プラグイン本体（版を固定・sha256 で照合）、システムが決める設定項目。**ノートには触らない**。更新の前に vault を自動でコミットするので戻せる |
| id の付与 | テンプレートを使わずに作ったノートに id を付ける（名前はそのまま）。以前の名前「作成日_タイトル_hash(.excalidraw).md」は、末尾の乱数と `.excalidraw` を一度だけ外す（vault 内のリンクも直す） |
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

デイリー・週ノート（`90_templates/periodic`）は Periodic Notes で作ると自動で当たるので、Ctrl+N の一覧には出ません。ファイル一覧の「新規ノート」やコマンドパレットで作った空のノートには、Templater が 01-base を入れます（フォルダテンプレート `/`）。Excalidraw の新規作成も 01-base から作ります（図のテンプレートに指定。実機では未確認）。それでも id のないノートには、push 時に notebase が id を付けます。

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

### 工程（Project Planner、まずは自分のセルフマネジメント）

工程は Obsidian の **Project Planner**（Dataview が必要。どちらも版を固定して配る）で見ます。専用のファイルは作らず、**やることの行（Obsidian Tasks の書き方）に依存と期間を足す**だけで、ガント・依存の図（クリティカルパス）・カンバンになります。

```markdown
- [ ] 案A 試作設計 🆔 x200-design 🛫 2026-10-05 📅 2026-11-06
- [ ] 治具の手配 🆔 x200-jig ⛔ x200-design 📅 2026-11-13
- [ ] 評価試験 🆔 x200-test ⛔ x200-make,x200-jig
```

- `🆔` はそのタスクの名前（vault の中で重ならない英数字。ノートの `id` とは別）、`⛔` は前のタスク、`🛫` 開始日、`📅` 期限。日付のないタスクは依存から位置を推定して点線で描く（「Apply suggested dates」で書き込む）
- ガントで棒をドラッグすると、その行の日付が書き換わる。土日を除いた稼働日で数え、クリティカルパスを表示する（配る設定）
- やることは、今までどおり発生したノート（検討・議事録など）に書く。デイリーノートの未完了一覧（Tasks）と同じデータ
- 節目（マイルストーン）はプラグインの設定に保存される（ノートには書かれない）。残したい節目はタスクの行として書く
- やること1件ごとにノートを作る機能（companion notes）はオフ
- 案件の承認付き工程表（取りまとめ役・計画変更の承認）は、使ってみて書き方が固まってから Project Planner の行の形に作り直す。それまで `20_工程/` の同期と `pm.py sync`（dotpm の形）は使わない。dotpm は配布をやめた（入っていれば notebase が外す。作ったファイルは残る）

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
