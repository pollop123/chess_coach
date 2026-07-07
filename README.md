# Chess AI Coach - 專業級西洋棋分析系統

一個不只會下棋，還會**深度教學**的專業 AI 系統。

本專案結合了優化的 Minimax 引擎、RAG (檢索增強生成) 技術與專業級評估體系，提供即時分析、深度講解與智能建議。

## 核心特色

### AI 教練系統
- **PV Line 深度講解**：解析引擎計算的最佳變例，逐步拆解戰術意圖
- **具體路徑分析**：不只說「這步好」，更說明「為什麼好」與「對手偏離會怎樣」
- **戰術識別**：自動識別叉王、牽制、棄子攻擊等戰術主題
- **心法提煉**：將複雜戰術總結為可學習的關鍵觀念

### 專業引擎功能
- **評估體系**：
  - Centipawn 格式化顯示（如 +1.50）
  - Sigmoid 勝率計算（0-100%）
  - 將死檢測（顯示 M3 等步數）
  
- **搜尋優化**：
  - 迭代加深搜尋（Iterative Deepening）
  - 具有 `EXACT / LOWER / UPPER` 邊界的 Zobrist 置換表，可跨深度與重複分析重用
  - 動態深度調整（殘局自動加深至 Depth 8）
  - 靜止搜索（Quiescence Search）防止水平線效應
  - 時限控制（確保 API 不超時）

- **可校準的四級難度**：
  - 新手、初階、中階使用不同的安全失誤帶，同一局面會穩定重現同一走法
  - 中階加強使用自製引擎在當前時間與深度下的最佳手
  - 所有難度都會淘汰會立即淨送后或車的風格候選手

- **效能表現**：
  - 快速走法：透過時限搜尋控制回應時間
  - 深度分析：依局面複雜度與設定深度調整
  - 開局階段優先使用 Polyglot 開局庫，沒有書步時回落到引擎搜尋

### API 架構
- **職責分離設計**：
  - `/make_move`：快速走法計算（2秒時限）
  - `/get_analysis`：深度分析與教練建議（5秒時限）
  - 錯誤隔離：Gemini 故障不影響下棋
  
- **安全防護**：
  - 輸入驗證與長度限制
  - Prompt Injection 防禦
  - System Instruction 隔離

### 整合功能
- **Lichess Bot**：可部署為 Lichess 機器人，自動接受挑戰
- **歷史棋譜分析**：完整賽局復盤，標註好壞棋
- **互動式網頁**：React 介面，即時評估圖表與教練對話

## 技術堆疊

- **Backend**: Python, FastAPI, python-chess
- **AI/RAG**: Google Gemini API, ChromaDB (向量資料庫)
- **Frontend**: React, Vite, chess.js, react-chessboard
- **Infrastructure**: Docker, Docker Compose
- **演算法**: Minimax + Alpha-Beta Pruning, Quiescence Search

## 快速開始

### 前置需求

- Docker & Docker Compose
- [Google Gemini API Key](https://aistudio.google.com/)
- [Lichess API Token](https://lichess.org/account/oauth/token)（選填）

### 方式一：使用 Docker（推薦用於生產環境）

1. **Clone 專案**
   ```bash
   git clone https://github.com/pollop123/chess_coach.git
   cd chess_coach
   ```

2. **設定環境變數**
   
   在專案根目錄建立 `.env` 檔案（用於 Docker Compose）：
   ```bash
   # .env
   GOOGLE_API_KEY=你的_google_api_key
   ```
   
   同時在 `backend/` 目錄下也建立 `.env` 檔案：
   ```bash
   # backend/.env
   GOOGLE_API_KEY=你的_google_api_key
   LICHESS_API_TOKEN=你的_lichess_token  # 選填
   ```

3. **使用 Docker Compose 啟動**
   ```bash
   # 啟動所有服務（前端 + 後端）
   docker-compose up --build
   
   # 背景執行
   docker-compose up -d --build
   
   # 查看日誌
   docker-compose logs -f
   
   # 停止服務
   docker-compose down
   ```

4. **訪問服務**
   - **前端介面**: http://localhost
   - **後端 API 文檔**: http://localhost:8000/docs
   - **後端健康檢查**: http://localhost:8000

### 方式二：本地開發環境

1. **Clone 專案**
   ```bash
   git clone https://github.com/pollop123/chess_coach.git
   cd chess_coach
   ```

2. **設定環境變數**
   ```bash
   # backend/.env
   GOOGLE_API_KEY=你的_google_api_key
   LICHESS_API_TOKEN=你的_lichess_token  # 選填
   ```
   
   前端本地開發預設呼叫 `/api`，Vite 會代理到 `http://localhost:8000`，通常不需要額外設定 `frontend/.env.local`。

3. **啟動後端**
   ```bash
   cd backend
   pip install -r requirements.txt
   python3 main.py
   # 或使用 uvicorn api:app --reload
   # uvicorn main:app --reload 也會載入同一個 api:app
   ```

4. **啟動前端**（另開終端）
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **快速啟動腳本**
   ```bash
   # 在專案根目錄執行
   ./start_local.sh
   ```

### 用 Stockfish 校準機器人強度

Stockfish 只擔任裁判，實戰走棋仍由本專案的 Minimax 引擎負責。

```bash
brew install stockfish
PYTHONPATH=backend .venv/bin/python backend/stockfish_calibration.py --nodes 12000
```

也可以用 `STOCKFISH_PATH` 指定其他 UCI 執行檔。報告包含：

- `ACPL`：與 Stockfish 最佳手的平均百分兵損失
- `WPL`：平均預期得分損失，在已勝或已敗局面比 ACPL 穩定
- `near-best`：與 Stockfish 評分差不超過 15cp 的比例
- `blunders`：單手造成至少 20% 預期得分損失的比例
- `hangs` 與 `missed_mates`：送大子與漏將死次數

這些是固定局面的走法品質指標，不是 Elo。要估計 Elo，還需要使用固定時制進行大量對局。

### 檢查教學分析品質

教學分析基準會檢查 `teaching_analysis` 的結構化輸出，包含候選手排序、局面主題、criticality 與錯誤警告。它用來追蹤「教學能不能講到重點」，不是 Stockfish 走棋強度或 Elo 測試。

```bash
PYTHONPATH=backend .venv/bin/python backend/teaching_benchmark.py
PYTHONPATH=backend .venv/bin/python backend/teaching_benchmark.py --json
```

目前基準涵蓋開局、戰術、殘局與失誤警告。若調整 `get_teaching_analysis` 或引擎評估，先跑這個基準確認教學輸出沒有退步，再用 Stockfish 校準檢查實戰走棋品質。

### Docker 相關指令

```bash
# 重新建置映像檔
docker-compose build

# 只啟動後端
docker-compose up backend

# 只啟動前端
docker-compose up frontend

# 進入容器內部
docker-compose exec backend bash
docker-compose exec frontend sh

# 查看容器狀態
docker-compose ps

# 清除所有容器與映像
docker-compose down --rmi all --volumes
```

### 免費部署建議（Vercel + Render + Neon）

這個專案建議使用三個免費服務分工部署：

- **Neon**：Postgres 資料庫，提供 `DATABASE_URL`
- **Render**：FastAPI 後端，使用 `render.yaml`
- **Vercel**：Vite React 前端，使用 `frontend/` 作為專案根目錄

1. **建立 Neon 資料庫**
   - 建立一個 Neon Free Postgres 專案
   - 複製 pooled 或 direct connection string
   - 將 connection string 作為 Render 的 `DATABASE_URL`

2. **部署 Render 後端**
   - 在 Render 建立 Blueprint 或 Web Service，連到 GitHub repo
   - 如果使用 Blueprint，Render 會讀取根目錄的 `render.yaml`
   - 必填環境變數：
     - `GOOGLE_API_KEY`: 你的 Google Gemini API Key
     - `DATABASE_URL`: Neon 提供的 Postgres 連線字串
   - 選填環境變數：
     - `LICHESS_API_TOKEN`: Lichess Bot 需要時再填
   - 部署完成後取得後端網址，例如 `https://chess-coach-api.onrender.com`

3. **部署 Vercel 前端**
   - Import GitHub repo
   - Root Directory 設為 `frontend`
   - Build Command 使用 `npm run build`
   - Output Directory 使用 `dist`
   - 必填環境變數：
     - `VITE_API_URL`: Render 後端公開網址，例如 `https://chess-coach-api.onrender.com`

4. **檢查部署**
   - 開啟 Render 後端根路徑，應該看到健康檢查回應
   - 開啟 Vercel 前端，下一步棋與 AI 教練應該會呼叫 Render API
   - Render Free 服務閒置後會 sleep，第一次請求可能需要約一分鐘喚醒

### Docker 手動建置

   ```bash
   # 後端
   cd backend
   docker build -t chess-backend .
   
   # 前端
   cd frontend
   docker build -t chess-frontend .
   
   # 如果前後端分離部署，才需要指定 API URL
   docker build -t chess-frontend --build-arg VITE_API_URL=https://your-backend-url .
   ```

## API 使用範例

### 快速走法
```bash
curl -X POST http://localhost:8000/make_move \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "time_limit": 2.0
  }'
```

### 深度分析
```bash
curl -X POST http://localhost:8000/get_analysis \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "history": "1. e4 e5",
    "question": "請分析當前局面",
    "depth": 5
  }'
```

回應範例：
```json
{
  "evaluation": {
    "score_cp": 30,
    "display": "+0.30",
    "winning_chance": 52.2,
    "pv_line": ["g1f3", "b8c6", "f1c4"],
    "depth_reached": 6
  },
  "game_state": "opening",
  "coach_advice": "當前局面為義大利開局..."
}
```

## 使用指南

### 網頁對弈
1. 打開 http://localhost
2. 與 AI 對弈或擺出特定局面分析
3. 點擊「AI 教練」獲得深度建議

### Lichess 機器人
1. 確保 `.env` 設定好 `LICHESS_API_TOKEN`
2. 執行 Bot：
   ```bash
   docker-compose exec backend python lichess_bot.py
   ```
3. 到 Lichess 挑戰你的 Bot

### 測試
```bash
# 後端回歸測試
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend -p 'test_*.py'

# 教學分析基準
PYTHONPATH=backend .venv/bin/python backend/teaching_benchmark.py

# 前端檢查
cd frontend
npm run lint
npm run build
```

## 專案結構

```
.
├── backend/
│   ├── chess_engine.py      # Minimax 引擎與評估系統
│   ├── rag.py               # RAG 教練邏輯
│   ├── api.py               # FastAPI 端點
│   ├── lichess_bot.py       # Lichess Bot 客戶端
│   ├── database.py          # SQLite 資料庫
│   └── test_*.py            # 測試腳本
├── frontend/
│   └── src/                 # React 前端
├── docs/
│   ├── ENGINE_UPGRADE_SPEC.md    # 引擎升級技術文件
│   ├── API_OPTIMIZATION.md       # API 架構文件
│   └── UPGRADE_PV_COACHING.md    # PV Line 整合文件
├── docker-compose.yml
└── README.md
```

## 效能指標

| 指標 | 數值 |
|------|------|
| 快速走法回應時間 | 0.3-1.5s |
| 深度分析回應時間 | 2-4s |
| 開局搜尋深度 | 5 層 |
| 殘局搜尋深度 | 8 層 |
| 勝率計算精度 | Sigmoid 函數 |
| API 穩定性 | 時限保護 + 錯誤隔離 |

## 技術亮點

1. **迭代加深搜尋**：時間內算越深越好，保證 API 不超時
2. **動態深度調整**：殘局自動加深，精準算出殺棋
3. **PV Line 教學**：將引擎思路轉化為人類可理解的講解
4. **System Instruction 隔離**：防止 Prompt Injection 攻擊
5. **職責分離架構**：快速走法與深度分析解耦，提升 70% 體驗

## 文件

- [引擎升級技術規格](ENGINE_UPGRADE_SPEC.md)
- [API 架構優化文件](API_OPTIMIZATION.md)
- [PV Line 整合說明](UPGRADE_PV_COACHING.md)

## 授權

[MIT](https://choosealicense.com/licenses/mit/)

## 致謝

本專案使用以下開源技術：
- python-chess：西洋棋邏輯庫
- Google Gemini：AI 教練後端
- ChromaDB：向量資料庫
- FastAPI：高效能 Web 框架
