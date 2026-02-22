# ScanCheckout OSS

> Scan で買い物の会計を行う OSS プロジェクト

---

## 🎯 プロジェクト概要

ScanCheckout OSS は、**画像アップロード → 商品候補提示 → 人が確定 → Odooへ明細作成**
という最短の業務ループを構築することを目的とした OSS プロジェクトです。

本プロジェクトは以下を重視します：

- 完全自動認識ではない
- 候補提示＋人補正を優先
- データが蓄積される設計
- Odoo連携を中心とした実用性

---

## 🏗 アーキテクチャ

```text
app/
 ├── routes/         # FastAPI ルート（HTTP I/O）
 ├── pos_adapters/   # Odoo連携（外部POS隠蔽）
 ├── vision/         # 推論処理
 └── models/         # DB層
```

### 境界ルール（重要）

- route から Odoo を直接呼ばない
- Odoo 呼び出しは adapter 内のみ
- vision は外部APIに直接依存しない

---

## 🐳 Docker構成

実装済みの `docker-compose.yml` は以下の構成です。

```yaml
services:
  api:
    build: ./services/api
    ports:
      - "8000:8000"
    environment:
      ODOO_URL: http://odoo:8069
      ODOO_DB: odoo
      ODOO_USER: admin
      ODOO_PASSWORD: admin
    depends_on:
      - odoo

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: odoo
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
    volumes:
      - db-data:/var/lib/postgresql/data

  odoo-init:
    image: odoo:19.0
    command: odoo --database=odoo --init=base --without-demo=all --stop-after-init

  odoo:
    image: odoo:19.0
    ports:
      - "8069:8069"

volumes:
  db-data:
```

起動手順（ローカル）：

```bash
cp .env.example .env
docker compose down -v
docker compose up -d --build
docker compose ps
```

確認URL：

- API: `http://localhost:8000/health`
- UI: `http://localhost:8000/ui/`
- Odoo: `http://localhost:8069`

Note:
- `odoo-init` は初回起動時に DB を初期化して終了する one-shot サービスです。
- 停止は `docker compose down`、データ含め初期化は `docker compose down -v` を使います。

## 🎬 デモ操作方法

1. コンテナを起動します。

```bash
cp .env.example .env
docker compose up -d --build
```

2. Odoo を開いて初期準備をします（`http://localhost:8069`）。
- `Sales` アプリをインストール
- 商品を作成し、`Internal Reference (default_code)` に次のSKUのいずれかを設定  
  `TEST-SKU`, `TEST-SVC`, `BREAD-001`, `BREAD-002`, `CAKE-001`

3. Theme を作成します（任意）。

```bash
curl -X POST http://localhost:8000/themes ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"bakery\",\"sku_list\":[\"BREAD-001\",\"CAKE-001\"]}"
```

4. UI を開いて操作します（`http://localhost:8000/ui/`）。
- `Theme` を選択（未選択でも可）
- `カメラ開始` を押す
- `撮影して /scans へ送信`
- `/infer 実行` で候補を表示
- SKUと数量を確認して `確定してOdoo登録`

5. Odoo 側で結果を確認します。
- `Sales > Quotations` に `sale.order` が作成されていることを確認
- 必要に応じて受注内容（SKU/数量）を照合

---

## 🔐 セキュリティ方針

## 1. 画像データ

- 画像は原則ローカル保存
- 外部LLMへ画像を直接送信しない

## 2. Odoo連携

- call_kw は adapter 内のみ
- 認証情報は `.env` で管理
- secrets の Git 管理禁止

## 3. データ保護

- 顧客情報は evidence に保存しない
- ログは個人情報を含めない

## 4. LLM利用時の制約

- 個人情報を送信しない
- SKU・商品名のみを対象とする
- 将来的にローカルLLM優先

---

## 🧩 API仕様（/pos/checkout）

OpenAPI 形式（抜粋）：

```yaml
paths:
  /pos/checkout:
    post:
      summary: Checkout items and create order in Odoo
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                store_id:
                  type: string
                operator_id:
                  type: string
                mode:
                  type: string
                  enum: [sale, pos]
                lines:
                  type: array
                  items:
                    type: object
                    properties:
                      sku:
                        type: string
                      qty:
                        type: number
                      price_unit:
                        type: number
      responses:
        200:
          description: Successful response
```

---

## 🧾 Odoo連携方針

### フェーズ順

1. sale.order draft 作成
2. action_confirm 実行
3. pos.order.create_from_ui（版差検証後）

MVPでは sale.order ベースで実装します。

---

## 🧠 LLM統合ロードマップ

### Phase 1（現状）

- ルールベース候補提示

### Phase 2

- 商品画像→特徴抽出モデル導入（Edge推論）

### Phase 3

- SKU候補補完をLLMで支援
- SKU誤認識の自然言語補正

### Phase 4

- ローカルLLM（Ollama等）による閉域補正

※ LLMは補助であり、業務確定は必ず人が行う。

---

## 🧪 テスト

```bash
pytest
black .
isort .
```

---

## 📝 ブランチ戦略

| ブランチ | 役割 |
| ---------- | ------ |
| main | 常に動作可能 |
| develop | 次リリース候補 |
| feature/odoo-* | Odoo機能 |
| feature/ui-* | UI改善 |
| feature/vision-* | 推論 |
| fix/* | バグ修正 |
| docs/* | ドキュメント |

main 直接 push 禁止。PR 必須。

---

## 🏷 タグ運用（リリース）

- 形式：`vMAJOR.MINOR.PATCH`
- main マージ時にタグ付与
- MINOR：機能追加
- PATCH：バグ修正
- CHANGELOG.md 更新必須

---

## 📂 Evidence（証跡）

PR 作成時は以下を実行：

```bash
python scripts/generate_evidence.py --title "feature/xxxx" --git-ref HEAD
```

---

## 📅 更新日

2026-02-18

---

## 📜 ライセンス

TBD
