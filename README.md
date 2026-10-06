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
  pm.py          工程管理：週報・計画変更の申請と承認・編集の反映・Excalidrawのガント図
  gantt.py       工程の集計（やることの数・見込み・遅れ）とガント図の描画
  pages.py ほか  Web閲覧のページ生成（render / access / pm_pages / core）
  pdf_out.py     PDF出力（日本語フォント埋め込み、ID・版・QRのフッター）
  site_template.html, editor.js   画面（素のHTML/CSS/JavaScript）
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
| `site/yamada.html` | 開発担当（山田） | 工程表の編集画面（ドラッグ・追加・削除・分割・段階に分解）、コメント |
| `site/staff.html` | 別チームの一般社員 | 公開された資料だけが見える。見えない資料は🔒と相談先 |

### よく使うコマンド

```bash
python3 tools/kv.py push vault-yamada "メッセージ"     # 検査 → コミット → サーバへ → 索引更新
python3 tools/view.py build boss index.html            # Web閲覧を作り直す（閲覧者ごと）
python3 tools/view.py pdf <ノートID> A4 boss            # PDF出力（A4〜A0）
python3 tools/pm.py gantt <工程表ID> m3                 # Excalidrawのガント図（書き込みは残して作り直す）
python3 tools/pm.py edit vault-yamada <工程表ID> ops.json <区分> <理由>   # 編集画面の申請を反映
python3 tools/pm.py decide <申請ID> approved boss "コメント"               # 承認
```

PDFの日本語フォントは自動で探します。見つからない時は環境変数 `RDNB_FONT` にTTF/TTCのパスを指定してください。

### 試作の割り切り

- Web閲覧は「閲覧者ごとに、見てよいものだけを入れた1枚のHTML」を事前に作る方式です
- 画面での承認・コメント・申請は、出てきた文字を手で反映します（画面から直接保存しない）。本番はサーバに送ります
- 工程表の履歴（計画変更の経緯）は、`setup_demo.py` で作り直すと最初の1件からになります

## Obsidian で使う（利用者の PC）

利用者が用意するのは **Git for Windows と Obsidian だけ**です。Python などは `notebase.cmd` が自動で用意します。

```
workspace/              好きな場所に作る空のフォルダ
├─ notebase.cmd         入口。ダブルクリックするだけ（client/notebase.cmd を配る）
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

### notebase.cmd がすること

| 処理 | 内容 |
|---|---|
| 本体の更新 | `.notebase` を `stable` ブランチに合わせる（開発者は `workspace/notebase.local.cmd` に `set "BRANCH=main"` を書くと main を使う） |
| vault の更新 | `client/vault.yml` に書いた範囲だけを `sample-vault/` に合わせる：テンプレート、プラグイン本体（版を固定・sha256 で照合）、システムが決める設定項目。**ノートには触らない**。更新の前に vault を自動でコミットするので戻せる |
| id の付与 | テンプレートを使わずに作ったノートに id を付け、名前を「作成日_タイトル_hash」に直す（vault 内のリンクも直す）。Templater の「新規作成時に実行」がオフの端末でも困らない |
| 検査 → push | `tools/kv.py` の検査（予約プロパティ、日付の書き方、顧客名、鍵など）を通ったものだけを push する。push はこれに一本化（Obsidian Git は使わない） |

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

### 新しいノート（Ctrl+N）

**Ctrl+N でテンプレートを選んで作ります**（Templater の「Create new note from template」に割り当て済み）。タイトルを聞かれ、ファイル名 `作成日_タイトル_hash`（例 `261004_X200中間報告_wfyzi.excalidraw.md`）とプロパティ `id`（例 `261004-wfyzi`）が付きます。ノートは全部 `10_notes` に入ります（フォルダ分けはしない）。

| テンプレート（90_templates/new） | 用途 |
|---|---|
| `01-base` | **基本（一番上に出る）**。検討・メモ・計算など何でも。文章と Excalidraw の図を1ファイルに（前半が文章、`%%` の後が図）。`type` は空＝未分類で、後で決める |
| `02-meeting` | 議事録。参加者・決まったこと・宿題（担当と期限付きのやること）＋ホワイトボード代わりの図 |
| `03-report` | 報告。要旨・スライド（各ノートの図のフレームを引用）・結論と依頼事項。PDF に出す |

デイリー・週ノート（`90_templates/periodic`）は Periodic Notes で作ると自動で当たるので、Ctrl+N の一覧には出ません。テンプレートを使わずに作ったノートにも、push 時に notebase が id を付けます。

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

### 書き方の約束

- やること：`- [ ] 内容 📅 2026-10-14 [task:: 工程表ID#T02]`（`task::` で工程タスクに紐づき、進捗＝完了数／総数になる）
- 図のフレームの引用：`![[作成日_タイトル_hash.excalidraw#F02]]`、版を固定する時は `#F02@コミット`
- 品番などの外部ID：`[[part:482015-BR1C]]`
- プロパティ：決まった名前以外を自分用に足す時は `my_` を付ける（例 `my_優先`）。皆で使うなら `config/registry.yml` の `properties` に登録する。顧客名はプロパティに書かず本文に（他人に配る要約に載るため）。詳しくは `docs/` の vault設計 5.4
- 新しいノートは Ctrl+N（テンプレートを選ぶ）。IDのないノートは push 時に notebase が id を付ける

## ライセンス

未定（試作）。
