# ============================================================
# builder ステージ: 依存パッケージをインストールする
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# pip キャッシュを使わず、依存のみインストールして軽量化する。
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================================
# runtime ステージ: 実行環境（非 root ユーザー）
# ============================================================
FROM python:3.11-slim AS runtime

# builder でインストールしたパッケージをコピーする。
COPY --from=builder /install /usr/local

# 非 root ユーザーを作成し、セキュリティリスクを低減する。
RUN useradd --no-create-home --shell /bin/false appuser

WORKDIR /app

# アプリケーションコードをコピーする。
COPY . .

# appuser に実行権限を付与する。
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# --reload によりホストのコードマウント変更を即時反映する（開発用）。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
