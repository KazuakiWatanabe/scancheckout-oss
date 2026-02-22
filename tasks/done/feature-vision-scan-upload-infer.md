# `feature/vision-scan-upload-infer` 実装タスク

## 1. 目的

画像アップロードから候補提示までの最小ループを API 側で成立させる。

- `POST /scans` で画像を受け付ける
- `POST /scans/{scan_id}/infer` で TopK 候補を返す（ダミー推論）
- 既存の `/pos/checkout` へ接続可能な形で候補 SKU を返す

## 2. スコープ

1. `routes` に `health` と `scans` を追加
1. `vision` にダミー候補生成ロジックを追加
1. `models` にスキャン保存用の最小ストアを追加
1. `main.py` に新ルーターを登録
1. `requirements.txt` に `python-multipart` を追加

## 3. 非スコープ

- DB/MinIO 永続化
- 本番向け画像認識モデル
- UI 実装

## 4. 完了条件

1. `POST /scans` が `scan_id` を返す
1. `POST /scans/{scan_id}/infer` が候補リストを返す
1. 主要 Python ファイルの日本語 docstring を満たす
1. 構文チェックと API 疎通確認が通る
