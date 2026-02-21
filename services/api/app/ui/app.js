"use strict";

/**
 * ScanCheckout 操作用 UI スクリプト。
 *
 * 役割:
 * - カメラ起動と撮影（getUserMedia）
 * - /scans への画像アップロード
 * - /scans/{scan_id}/infer の実行
 * - 候補 SKU の確定と /pos/checkout(mode="sale") 実行
 */

/** UI 全体で共有する画面状態。 */
const state = {
  stream: null,
  scanId: null,
  candidates: [],
  selectedSku: "",
};

/** HTML 要素参照をまとめる。 */
const elements = {
  storeId: document.getElementById("storeId"),
  deviceId: document.getElementById("deviceId"),
  operatorId: document.getElementById("operatorId"),
  themeId: document.getElementById("themeId"),
  topK: document.getElementById("topK"),
  qty: document.getElementById("qty"),
  cameraPreview: document.getElementById("cameraPreview"),
  captureCanvas: document.getElementById("captureCanvas"),
  capturedImage: document.getElementById("capturedImage"),
  scanIdText: document.getElementById("scanIdText"),
  selectedSku: document.getElementById("selectedSku"),
  candidateList: document.getElementById("candidateList"),
  resultView: document.getElementById("resultView"),
  statusLine: document.getElementById("statusLine"),
  startCameraBtn: document.getElementById("startCameraBtn"),
  stopCameraBtn: document.getElementById("stopCameraBtn"),
  captureUploadBtn: document.getElementById("captureUploadBtn"),
  inferBtn: document.getElementById("inferBtn"),
  checkoutBtn: document.getElementById("checkoutBtn"),
};

/**
 * ステータス表示を更新する。
 * @param {"info" | "success" | "error"} level 表示レベル
 * @param {string} message 画面表示メッセージ
 */
function setStatus(level, message) {
  elements.statusLine.className = `status ${level}`;
  elements.statusLine.textContent = message;
}

/**
 * API レスポンス表示を更新する。
 * @param {unknown} payload 表示対象データ
 */
function setResult(payload) {
  elements.resultView.textContent = JSON.stringify(payload, null, 2);
}

/**
 * top_k の入力値を API 仕様（1-5）に丸める。
 * @returns {number} 正規化済み top_k
 */
function normalizeTopK() {
  const raw = Number(elements.topK.value);
  if (!Number.isFinite(raw)) {
    return 3;
  }
  return Math.min(5, Math.max(1, Math.trunc(raw)));
}

/**
 * fetch の共通ラッパ。
 * 失敗時は `HTTP <status>: <message>` 形式で例外化する。
 *
 * @param {string} url API パス
 * @param {RequestInit} options fetch オプション
 * @returns {Promise<unknown>} JSON または文字列レスポンス
 */
async function fetchApi(url, options = {}) {
  const response = await fetch(url, options);
  const rawBody = await response.text();

  let parsed = null;
  if (rawBody) {
    try {
      parsed = JSON.parse(rawBody);
    } catch (error) {
      parsed = rawBody;
    }
  }

  if (!response.ok) {
    const detail =
      (parsed && typeof parsed === "object" && parsed.detail) ||
      (parsed && typeof parsed === "object" && parsed.message) ||
      String(parsed || "unknown error");
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }

  return parsed;
}

/**
 * カメラを開始する。
 *
 * Note:
 * - HTTPS または localhost 以外ではブラウザ制約で失敗する場合がある。
 */
async function startCamera() {
  if (state.stream) {
    return;
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "environment" },
    audio: false,
  });
  state.stream = stream;
  elements.cameraPreview.srcObject = stream;
  setStatus("success", "カメラを開始しました。");
}

/** カメラを停止する。 */
function stopCamera() {
  if (!state.stream) {
    return;
  }
  state.stream.getTracks().forEach((track) => track.stop());
  state.stream = null;
  elements.cameraPreview.srcObject = null;
  setStatus("info", "カメラを停止しました。");
}

/**
 * video 要素から現在フレームを JPEG Blob として抽出する。
 * @returns {Promise<Blob>} 抽出した画像
 */
function captureFrameAsBlob() {
  return new Promise((resolve, reject) => {
    const video = elements.cameraPreview;
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
      reject(new Error("カメラ映像が未取得です。先にカメラ開始してください。"));
      return;
    }

    const canvas = elements.captureCanvas;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      reject(new Error("canvas コンテキスト取得に失敗しました。"));
      return;
    }

    ctx.drawImage(video, 0, 0, width, height);
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error("画像 Blob の作成に失敗しました。"));
          return;
        }
        resolve(blob);
      },
      "image/jpeg",
      0.9,
    );
  });
}

/** 候補リストを再描画する。 */
function renderCandidates() {
  elements.candidateList.innerHTML = "";
  if (!state.candidates.length) {
    const item = document.createElement("li");
    item.className = "candidate-empty";
    item.textContent = "候補がありません。";
    elements.candidateList.appendChild(item);
    return;
  }

  state.candidates.forEach((candidate, index) => {
    const item = document.createElement("li");
    item.className = "candidate-item";

    const label = document.createElement("label");
    label.className = "candidate-label";

    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "candidateSku";
    radio.value = candidate.sku;
    radio.checked = index === 0;
    radio.addEventListener("change", () => {
      state.selectedSku = candidate.sku;
      elements.selectedSku.value = candidate.sku;
    });

    const text = document.createElement("span");
    text.textContent = `${candidate.sku} / ${candidate.name} (score: ${candidate.score})`;

    label.appendChild(radio);
    label.appendChild(text);
    item.appendChild(label);
    elements.candidateList.appendChild(item);
  });

  state.selectedSku = state.candidates[0].sku;
  elements.selectedSku.value = state.selectedSku;
}

/** 撮影して /scans へ送信する。 */
async function captureAndUploadScan() {
  const imageBlob = await captureFrameAsBlob();
  elements.capturedImage.src = URL.createObjectURL(imageBlob);

  const storeId = elements.storeId.value.trim();
  const deviceId = elements.deviceId.value.trim();
  if (!storeId) {
    throw new Error("store_id は必須です。");
  }

  const formData = new FormData();
  formData.append("image", imageBlob, `capture-${Date.now()}.jpg`);
  formData.append("store_id", storeId);
  if (deviceId) {
    formData.append("device_id", deviceId);
  }

  const payload = await fetchApi("/scans", {
    method: "POST",
    body: formData,
  });

  state.scanId = payload.scan_id;
  elements.scanIdText.textContent = state.scanId;
  setResult(payload);
  setStatus("success", `scan を作成しました: ${state.scanId}`);
}

/** /scans/{scan_id}/infer を実行する。 */
async function runInfer() {
  if (!state.scanId) {
    throw new Error("先に撮影して /scans を実行してください。");
  }

  const topK = normalizeTopK();
  elements.topK.value = String(topK);
  const themeValue = elements.themeId.value.trim();

  const payload = await fetchApi(`/scans/${state.scanId}/infer`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      top_k: topK,
      theme_id: themeValue || null,
    }),
  });

  const detections = Array.isArray(payload.detections) ? payload.detections : [];
  const first = detections.length > 0 ? detections[0] : null;
  state.candidates = Array.isArray(first?.candidates) ? first.candidates : [];

  renderCandidates();
  setResult(payload);
  setStatus("success", `infer 完了: 候補 ${state.candidates.length} 件`);
}

/** /pos/checkout(mode=sale) を実行する。 */
async function checkoutSaleOrder() {
  const storeId = elements.storeId.value.trim();
  const operatorId = elements.operatorId.value.trim();
  const sku = elements.selectedSku.value.trim() || state.selectedSku;
  const qty = Number(elements.qty.value);

  if (!storeId) {
    throw new Error("store_id は必須です。");
  }
  if (!sku) {
    throw new Error("確定SKUを入力してください。");
  }
  if (!Number.isFinite(qty) || qty <= 0) {
    throw new Error("qty は 0 より大きい値を指定してください。");
  }

  const payload = await fetchApi("/pos/checkout", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      store_id: storeId,
      operator_id: operatorId || null,
      mode: "sale",
      lines: [
        {
          sku: sku,
          qty: qty,
        },
      ],
    }),
  });

  setResult(payload);
  setStatus("success", "checkout を実行しました。結果を確認してください。");
}

/**
 * ボタン押下時の共通エラーハンドラ。
 * @param {() => Promise<void>} action 実行関数
 */
async function runWithErrorBoundary(action) {
  try {
    await action();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setStatus("error", message);
  }
}

/** 画面イベントを初期化する。 */
function bindEvents() {
  elements.startCameraBtn.addEventListener("click", () =>
    runWithErrorBoundary(startCamera),
  );
  elements.stopCameraBtn.addEventListener("click", () => stopCamera());
  elements.captureUploadBtn.addEventListener("click", () =>
    runWithErrorBoundary(captureAndUploadScan),
  );
  elements.inferBtn.addEventListener("click", () => runWithErrorBoundary(runInfer));
  elements.checkoutBtn.addEventListener("click", () =>
    runWithErrorBoundary(checkoutSaleOrder),
  );
}

bindEvents();
