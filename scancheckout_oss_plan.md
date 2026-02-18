# BakeryScan OSS 版（仮称）実装計画（Phase1〜2 / Odoo連携まで）

目的：店舗内PC（Edge）で **撮影 → 候補提示 → 人が確定 → Odooへ明細作成** を最短で動かし、確定結果を学習データとして蓄積できる形にする。  
将来：精度向上（再学習）・セミセルフ・本部マスタ配信・LLM支援を安全に拡張できるよう、境界（Capture / Vision / UI / POS Adapter / Data）を分離する。

---

## 1. スコープ（まず作るもの）

### Phase 1（MVP-0：推論なしでも回る）

- 画像アップロード（撮影代替）→ スキャン登録
- 画面上で商品を手動選択して明細作成
- Odooに **注文下書き（sale.order）** または **POS注文（pos.order/create_from_ui）** を作成
- 画像・確定ラベル・環境メタ（店舗/端末）を保存（学習の種）

### Phase 2（MVP-1：候補提示）

- /infer が候補TopKと信頼度を返す（初期はダミーでも可）
- UIで信頼度色分け＋タップで候補切替
- 確定結果を decisions として保存し、Odooへ送信

> 重要：最初は「100%自動認識」ではなく **候補提示＋補正が速い** を中心にする（現場価値が出やすく、データも集まりやすい）。

---

## 2. リポジトリ構成

```text
bakeryscan-oss/
  docker-compose.yml
  .env.example
  README.md
  services/
    api/
      app/
        main.py
        settings.py
        db.py
        models.py
        schemas.py
        routes/
          health.py
          products.py
          scans.py
          decisions.py
          pos.py
        pos_adapters/
          odoo_jsonrpc.py
          dummy.py
        vision/
          infer.py
          preprocess.py
      Dockerfile
      requirements.txt
    ui/
      (React/Next/Vite いずれか)
  storage/
    models/
    images/
  scripts/
    seed_products.py
    export_dataset.py
  docs/
    api.md
    data_model.md
    security.md
```

---

## 3. Docker 構成（開発用）

- Postgres：業務データ（商品/スキャン/確定ログ）
- MinIO：画像保管（S3互換）
- API：FastAPI
- UI：Web（タッチUI）

※ 推論モデルは storage/models（volume）に置き、モデル切替・ロールバックができるようにする。

---

## 4. データモデル（最小）

- products：商品マスタ（sku, name, active, price任意）
- scans：撮影1回（image_uri, store_id, device_id）
- detections：検出領域（bbox, candidates）
- decisions：人が確定した結果（chosen_product_id, operator_id, sent_to_pos, pos_result）

---

## 5. API（最小）

- GET /health
- GET/POST /products（+ CSV import 任意）
- POST /scans（画像アップロード→MinIO保存→scans登録）
- POST /scans/{scan_id}/infer（候補生成→detections保存→返却）
- POST /decisions（確定保存）
- POST /pos/checkout（明細まとめて Odoo へ送信）

---

## 6. Odoo 連携設計（2案）

### 案A：注文下書き（sale.order）を作る（推奨：最初に堅い）

#### メリット

- Odoo標準の受注（見積）フローに載せやすい
- 必要フィールドが比較的少なく安定
- POSセッションなど “POS特有の状態” に依存しにくい

#### デメリット

- レジ（POS）としての体験に寄せるには追加実装が必要（販売＝POSの会計と一致しない可能性）

#### 想定モデル/メソッド

- `res.partner`（顧客：店内客を共通顧客にする等）
- `product.product` / `product.template`（SKU→product_id解決）
- `sale.order.create`（state='draft' の見積を作成）
- `sale.order.write`（追記・修正）
- `sale.order.action_confirm`（必要なら確定）

---

### 案B：POS注文（pos.order / create_from_ui）を作る（POSに近い）

#### メリット

- POSのオーダーとして登録でき、POS文脈に近い
- 将来的にセミセルフ/フルセルフへ拡張しやすい

#### デメリット（MVPでハマりやすい）

- OdooのPOSは **セッション（pos.session）** や設定、税/価格計算など依存が多い
- 版差分が出やすい（Odooのバージョン/導入モジュールで項目が変わる）

#### 想定モデル/メソッド（推奨ルート）

- `pos.order.create_from_ui(orders, draft=False)`  
  POSフロントが使う経路を流用するイメージ。  
  ※ orders の辞書フォーマットは Odoo 版で異なるため、最初は **POSフロントの通信を確認して合わせる** のが確実。

---

## 7. 実装タスク（チェックリスト）

### Step 1：雛形

- [ ] repo生成、compose、env、README
- [ ] FastAPI /health
- [ ] SQLAlchemy + Alembic

### Step 2：DB/API

- [ ] products/scans/detections/decisions
- [ ] /scans upload → MinIO保存
- [ ] /infer（ダミー候補でもOK）
- [ ] /decisions
- [ ] /pos/checkout（dummy adapter）

### Step 3：UI

- [ ] upload→infer→bbox+候補表示
- [ ] 確定→明細リスト→POS送信

### Step 4：Odoo adapter（案A→案Bの順が安全）

- [ ] JSON-RPC認証（/web/session/authenticate）
- [ ] /web/dataset/call_kw で call_kw 共通化
- [ ] SKU→product_id 解決（search_read）
- [ ] 案A：sale.order の draft 作成
- [ ] 案B：pos.order.create_from_ui で登録（必要なら）

---

## 8. セキュリティ/運用（最低限）

- APIは店内LAN限定、外部公開しない
- ログに個人情報を残さない（画像URIも扱い注意）
- モデルはバージョン管理し、更新はロールバック可能に
- LLM導入時は「画像を外に出さない」方針を基本とし、まずはメタ情報/テキストだけで支援する

---

## 9. 次の実装の当面ゴール

- 「画像アップロード→（候補表示）→確定→Odooに注文（下書き）を作る」まで一気通貫
- ここが通れば、認識精度は後から上げられる（データが溜まるため）

---

## 10. 付録：odoo_jsonrpc.py 実装スケルトン（注文下書き / POS注文）

> 目的：POS連携を差し替えられるよう、Adapter で統一I/Fを持ち、Odoo側のモデル/メソッド呼び出しを隠蔽する。

```python
# services/api/app/pos_adapters/odoo_jsonrpc.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple
import httpx


@dataclass(frozen=True)
class OdooConfig:
    base_url: str          # 例: http://odoo:8069
    db: str
    username: str
    password: str
    timeout_sec: float = 10.0


class OdooJsonRpcError(RuntimeError):
    pass


class OdooJsonRpcClient:
    """
    Odoo Web(JSON-RPC) 経由で /web/session/authenticate と /web/dataset/call_kw を叩くクライアント。
    - いわゆる XML-RPC ではなく、Webクライアントが使うJSON-RPCの薄いラッパ。
    - 認証後は cookie によりセッション維持される。
    """

    def __init__(self, cfg: OdooConfig) -> None:
        self.cfg = cfg
        self._client = httpx.Client(base_url=cfg.base_url, timeout=cfg.timeout_sec)
        self._uid: Optional[int] = None

    def close(self) -> None:
        self._client.close()

    def authenticate(self) -> int:
        """
        POST /web/session/authenticate
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": self.cfg.db,
                "login": self.cfg.username,
                "password": self.cfg.password,
            },
            "id": 1,
        }
        r = self._client.post("/web/session/authenticate", json=payload)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise OdooJsonRpcError(f"authenticate error: {data['error']}")
        result = data.get("result") or {}
        uid = result.get("uid")
        if not uid:
            raise OdooJsonRpcError(f"authenticate failed: {data}")
        self._uid = int(uid)
        return self._uid

    def call_kw(
        self,
        model: str,
        method: str,
        args: Sequence[Any] | None = None,
        kwargs: Dict[str, Any] | None = None,
    ) -> Any:
        """
        POST /web/dataset/call_kw
        """
        if self._uid is None:
            self.authenticate()

        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": model,
                "method": method,
                "args": list(args or []),
                "kwargs": kwargs or {},
            },
            "id": 2,
        }
        r = self._client.post("/web/dataset/call_kw", json=payload)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise OdooJsonRpcError(f"call_kw error: {data['error']}")
        return data.get("result")


# ----------------------------
# Adapter I/F（API側から使う）
# ----------------------------

@dataclass(frozen=True)
class CheckoutLine:
    sku: str
    qty: float
    # price_unit をAPI側で決めるか、Odoo側の価格表に任せるかで扱いが変わる
    price_unit: Optional[float] = None


class OdooPosAdapter:
    """
    /pos/checkout から呼ばれる Adapter。
    実装は「案A: sale.order（下書き）」をまず固め、必要に応じて「案B: pos.order（POS注文）」へ。
    """

    def __init__(self, cfg: OdooConfig) -> None:
        self.client = OdooJsonRpcClient(cfg)

    # ---- 共通ユーティリティ ----

    def resolve_product_ids_by_sku(self, skus: List[str]) -> Dict[str, int]:
        """
        SKU -> product.product.id を解決する。
        SKU の持ち方は運用次第（barcode / default_code など）。ここでは default_code 想定。
        """
        rows = self.client.call_kw(
            model="product.product",
            method="search_read",
            args=[
                [["default_code", "in", skus]],
                ["id", "default_code", "name", "barcode"],
            ],
            kwargs={"limit": len(skus)},
        ) or []
        out: Dict[str, int] = {}
        for r in rows:
            dc = r.get("default_code")
            if dc:
                out[str(dc)] = int(r["id"])
        return out

    # ----------------------------
    # 案A：注文下書き（sale.order）
    # ----------------------------

    def create_sale_order_draft(
        self,
        partner_id: int,
        lines: List[CheckoutLine],
        pricelist_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> int:
        """
        sale.order を draft（見積）で作成する。
        """
        sku_list = [l.sku for l in lines]
        sku_to_pid = self.resolve_product_ids_by_sku(sku_list)

        order_lines: List[Tuple[int, int, Dict[str, Any]]] = []
        for l in lines:
            pid = sku_to_pid.get(l.sku)
            if not pid:
                raise OdooJsonRpcError(f"Unknown SKU: {l.sku}")
            vals: Dict[str, Any] = {
                "product_id": pid,
                "product_uom_qty": l.qty,
            }
            # 価格を外部で固定したいなら price_unit 指定
            if l.price_unit is not None:
                vals["price_unit"] = l.price_unit
            order_lines.append((0, 0, vals))

        so_vals: Dict[str, Any] = {
            "partner_id": partner_id,
            "order_line": order_lines,
        }
        if pricelist_id is not None:
            so_vals["pricelist_id"] = pricelist_id
        if note:
            so_vals["note"] = note

        so_id = self.client.call_kw(
            model="sale.order",
            method="create",
            args=[so_vals],
        )
        return int(so_id)

    def confirm_sale_order(self, sale_order_id: int) -> Any:
        """
        必要なら確定（action_confirm）。
        """
        return self.client.call_kw(
            model="sale.order",
            method="action_confirm",
            args=[[sale_order_id]],
        )

    # ----------------------------
    # 案B：POS注文（pos.order.create_from_ui）
    # ----------------------------

    def create_pos_order_from_ui(
        self,
        session_id: int,
        lines: List[CheckoutLine],
        partner_id: Optional[int] = None,
        draft: bool = True,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        POSフロントが使う create_from_ui を呼ぶ想定のスケルトン。
        NOTE:
        - orders の辞書フォーマットは Odoo 版で変わるため、
          本番では「POSが送るpayloadをDevTools等で確認して合わせる」のが最短。
        - 税/値引き/丸め/金額計算の扱いも依存がある。
        """
        sku_list = [l.sku for l in lines]
        sku_to_pid = self.resolve_product_ids_by_sku(sku_list)

        # かなり簡略化した例（実際はposフロントのpayloadに合わせる）
        pos_lines = []
        for l in lines:
            pid = sku_to_pid.get(l.sku)
            if not pid:
                raise OdooJsonRpcError(f"Unknown SKU: {l.sku}")
            line_vals: Dict[str, Any] = {
                "product_id": pid,
                "qty": l.qty,
            }
            if l.price_unit is not None:
                line_vals["price_unit"] = l.price_unit
            pos_lines.append([0, 0, line_vals])

        order = {
            "data": {
                # ここはOdoo版差分がある（例: name/uid/sequence_number 等）
                "pos_session_id": session_id,  # フィールド名も版により異なる可能性あり
                "partner_id": partner_id or False,
                "lines": pos_lines,
            }
        }
        if extra:
            order["data"].update(extra)

        # create_from_ui: args=[ [order_dict], draft_bool ]
        # 版により signature が異なる可能性がある点に注意
        return self.client.call_kw(
            model="pos.order",
            method="create_from_ui",
            args=[[order], draft],
            kwargs={},
        )

```
