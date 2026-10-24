# 知見同期プログラム(notesync)

要件書 `docs/00_同期プログラム要件.md` の最初の部分です。

| できること | 要件 |
|---|---|
| id のないノートに id をつけ、`id_名前.md` に名前を変える | F-01〜03 |
| `[[名前]]` や別名のリンクを `[[id_名前\|名前]]` に直す(候補が1つのときだけ) | F-03 |
| 同じ名前のノートがあれば知らせる | F-04 |
| 個人vaultの `00_同期レポート.md` に結果を書く | F-21 |
| 試し運転(何も変えずにレポートだけ書く) | F-23 |
| 書き換える前に元のファイルを backup に残す(30日) | 安全策 |
| 機密フォルダのリンクは機密の中だけで直す | F-40 |
| 私.yaml とメンバー.csv の人コードが食い違えば止まる | F-44 |

まだのもの: 共有への集約と配布(F-05〜)、重い添付の移動(F-17b)、exe 化。

## 使い方

```
pip install pyyaml
copy config.example.yaml %APPDATA%\知見同期\config.yaml   (中身を自分用に直す)
python -m notesync once --dry-run      # 試し運転。00_同期レポート.md を見る
python -m notesync once                # 本番を1回
python -m notesync watch --interval 3  # 常駐(3秒ごと)
```

編集中のノート(最後の保存から `idle_seconds` 秒以内)には触りません。
`00_daily` などの日付ノート、`_templates` などの仕組みのフォルダ、配られた `90_共有` は対象外です。

## テスト

```
pip install -e .[dev]
pytest
```

`tests/sample_vault/` が試験用の vault です。
