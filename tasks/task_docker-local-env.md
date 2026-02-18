# タスク：Docker ローカル環境構築

## 📚 前提ルール参照

作業開始前に以下を必ず読むこと：

- `CLAUDE.md`
- `AGENTS.md`

スコープ逸脱は禁止。

---

## 🌿 Step 1：ブランチ作成

```bash
git checkout main
git pull origin main
git checkout -b feature/docker-local-env
```

---

## 🎯 目的

以下の構成でローカル開発環境をDockerで起動できる状態にする：

- **FastAPI**（`services/api/`）
- **Odoo 19.0**（コンテナで起動）
- **PostgreSQL 16**（Odoo用DB）

---

## 📁 作成対象ファイル（これ以外は変更禁止）

| ファイル | 説明 |
| --------- | ------ |
| `docker-compose.yml` | プロジェクトルートに作成 |
| `services/api/Dockerfile` | FastAPI用 |
| `services/api/.dockerignore` | 不要ファイル除外 |
| `.env.example` | 環境変数テンプレート |
| `odoo/addons/.gitkeep` | アドオン置き場（空ファイル） |

---

## 🧩 Step 2：各ファイルの実装内容

### ① docker-compose.yml（プロジェクトルート）

以下の3サービスを定義する：

#### db（PostgreSQL 15）

- image: `postgres:16`
- container_name: `scancheckout-db`
- 環境変数: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- volume: `db-data:/var/lib/postgresql/data`
- network: `scancheckout-net`

#### odoo（Odoo 17.0）

- image: `odoo:19.0`
- container_name: `scancheckout-odoo`
- depends_on: `db`
- ports: `8069:8069`
- 環境変数: `HOST=db`, `USER`, `PASSWORD`
- volume: `odoo-data:/var/lib/odoo`, `./odoo/addons:/mnt/extra-addons`
- network: `scancheckout-net`

#### api（FastAPI）

- build: `./services/api`
- container_name: `scancheckout-api`
- ports: `8000:8000`
- volume: `./services/api:/app`（ホットリロード用）
- 環境変数:
  - `ODOO_URL=http://odoo:8069`（コンテナ内部名で解決）
  - `ODOO_DB`, `ODOO_USER`, `ODOO_PASSWORD`
- depends_on: `odoo`
- network: `scancheckout-net`

volumes: `db-data`, `odoo-data`
networks: `scancheckout-net`（bridge）

---

### ② services/api/Dockerfile

- ベースイメージ: `python:3.11-slim`
- マルチステージビルド（builder → runtime）
- `requirements.txt` から依存関係インストール
- 非rootユーザー（`appuser`）で実行
- 起動コマンド: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- EXPOSE: `8000`

---

### ③ services/api/.dockerignore

除外対象：

- `__pycache__/`, `*.pyc`, `*.pyo`
- `.env`, `.env.*`
- `.pytest_cache/`, `.mypy_cache/`
- `htmlcov/`, `.coverage`
- `dist/`, `build/`, `*.egg-info/`

---

### ④ .env.example（プロジェクトルート）

```dotenv
# PostgreSQL設定
POSTGRES_DB=odoo
POSTGRES_USER=odoo
POSTGRES_PASSWORD=odoo

# Odoo管理者アカウント
ODOO_USER=admin
ODOO_PASSWORD=admin

# API設定
API_ENV=development
```

---

### ⑤ odoo/addons/.gitkeep

空ファイルを作成するだけでよい。

---

## 🧪 Step 3：動作確認

以下のコマンドを順番に実行し、エラーがないことを確認する：

```bash
# .envを作成
cp .env.example .env

# ビルドして起動
docker-compose up --build -d

# コンテナ起動確認
docker-compose ps

# APIの疎通確認
curl http://localhost:8000/docs
```

`docker-compose ps` で3コンテナがすべて `Up` になっていることを確認すること。

---

## 📌 Step 4：完了報告（必須出力）

1. 作成ファイル一覧
2. `docker-compose ps` の出力結果
3. `curl http://localhost:8000/docs` の結果
4. CLAUDE.md 違反がないことの確認

---

## 🛑 禁止事項

- スコープ外ファイルの変更
- `.env` をGit管理に含める（`.gitignore` に追加すること）
- `localhost` をコンテナ間通信に使用（必ずサービス名を使う）
- Odooバージョンを勝手に変更しない（17.0固定）
