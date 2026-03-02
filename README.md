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
  - 動態深度調整（殘局自動加深至 Depth 8）
  - 靜止搜索（Quiescence Search）防止水平線效應
  - 時限控制（確保 API 不超時）

- **效能表現**：
  - 快速走法：< 2 秒
  - 深度分析：< 5 秒
  - 節點搜尋：開局 ~15K, 殘局 ~5K

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
   VITE_API_URL=http://localhost:8000  # 本地測試
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
   
   ```bash
   # frontend/.env.local
   VITE_API_URL=http://localhost:8000
   ```

3. **啟動後端**
   ```bash
   cd backend
   pip install -r requirements.txt
   python3 main.py
   # 或使用 uvicorn api:app --reload
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

### 部署到雲端（Zeabur / Render / Railway）

1. **設定環境變數**
   - `GOOGLE_API_KEY`: 你的 Google Gemini API Key
   - `VITE_API_URL`: 你的後端公開網址（如 `https://your-backend.zeabur.app`）

2. **自動部署**
   - 平台會自動偵測 `docker-compose.yml` 並建置
   - 前端會在建置時將 `VITE_API_URL` 打包進去

3. **手動建置**
   ```bash
   # 後端
   cd backend
   docker build -t chess-backend .
   
   # 前端
   cd frontend
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
# 引擎功能測試
cd backend
python3 test_engine_upgrade.py

# API 端點測試
python3 test_api_endpoints.py
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