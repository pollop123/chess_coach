# Chess AI Coach ♟️🤖

一個不只會下棋，還會**教學**的強大 AI。

本專案結合了自製的 Minimax 引擎與 **RAG (檢索增強生成)** 技術，這位 AI 教練能用自然語言解釋它的每一步棋，提煉出關鍵的西洋棋心法，並引用歷史名局來幫助你進步。

## ✨ 功能特色

*   **🧠 RAG AI 教練**:
    *   **深度解說**：使用 Google Gemini API 解釋「為什麼」這步棋是好棋（或壞棋）。
    *   **心法提煉**：將複雜的戰術總結為一句話「心法」（例如：「控制中心」、「騎士前哨站」）。
    *   **引擎思維**：公開引擎內部的計算數據（評分、預測變例 PV），讓你看懂電腦的思考路徑。
    *   **情境感知**：自動判斷當前輪次與視角，提供最精準的建議。

*   **⚡ 強力西洋棋引擎**:
    *   **Minimax 演算法**：搭配 Alpha-Beta 剪枝。
    *   **靜止搜索 (Quiescence Search)**：防止「水平線效應」，在戰術交換時算得更深。
    *   **動態殘局深度**：在殘局階段自動加深搜索（最高 Depth 8），精準算出殺棋。
    *   **開局庫**：內建 `gm2001.bin`，開局走法多變且專業。

*   **🤖 Lichess 機器人整合**:
    *   可連接至 Lichess.org 作為 Bot 帳號運作。
    *   自動接受挑戰並使用引擎對弈。
    *   內建斷線重連與重試機制，穩定性高。

*   **📊 互動式網頁介面**:
    *   基於 React 的現代化棋盤介面。
    *   即時局勢評分圖表 (CP Loss)。
    *   AI 教練對話視窗，隨時提問。

## 🛠️ 技術堆疊

*   **Backend**: Python, FastAPI, python-chess, SQLAlchemy
*   **AI/RAG**: Google Gemini API, ChromaDB (向量資料庫)
*   **Frontend**: React, Vite, chess.js, react-chessboard, Recharts
*   **Infrastructure**: Docker, Docker Compose

## 🚀 快速開始

### 前置需求

*   Docker & Docker Compose
*   [Google Gemini API Key](https://aistudio.google.com/) (用於 RAG 教練)
*   [Lichess API Token](https://lichess.org/account/oauth/token) (選填，用於 Bot)

### 安裝步驟

1.  **Clone 專案**
    ```bash
    git clone https://github.com/pollop123/chess_coach.git
    cd chess_coach
    ```

2.  **設定環境變數**
    在 `backend/` 目錄下建立 `.env` 檔案：
    ```bash
    # backend/.env
    GOOGLE_API_KEY=你的_google_api_key
    LICHESS_API_TOKEN=你的_lichess_token (選填)
    ```

3.  **使用 Docker Compose 啟動**
    ```bash
    docker-compose up --build
    ```

    啟動後即可訪問：
    *   **前端介面**: http://localhost:5173
    *   **後端 API**: http://localhost:8000/docs

## 🎮 使用指南

### 網頁對弈與分析
1.  打開 http://localhost:5173。
2.  你可以直接跟 AI 下棋，或是擺出特定局面進行分析。
3.  點擊 **"Ask AI Coach"**，AI 會詳細解釋當前局面的優劣與策略。

### 執行 Lichess 機器人
如果你想讓 Bot 在 Lichess 上線：

1.  確保 `.env` 裡已經設定好 `LICHESS_API_TOKEN`。
2.  在容器內執行 Bot 腳本：
    ```bash
    docker-compose exec backend python lichess_bot.py
    ```
3.  現在你可以去 Lichess 挑戰你的 Bot 了！

*(注意：如果你的帳號還不是 Bot 帳號，請先執行 `docker-compose exec backend python upgrade_bot.py` 進行升級。)*

## 📂 專案結構

```
.
├── backend/
│   ├── chess_engine.py  # 核心 Minimax 引擎與評估邏輯
│   ├── rag.py           # RAG 邏輯 (Gemini + ChromaDB)
│   ├── lichess_bot.py   # Lichess Bot 客戶端
│   ├── api.py           # FastAPI 端點
│   └── ...
├── frontend/
│   ├── src/             # React 原始碼
│   └── ...
├── docker-compose.yml
└── README.md
```

## 📄 授權

[MIT](https://choosealicense.com/licenses/mit/)