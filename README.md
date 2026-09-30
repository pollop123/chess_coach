# Chess AI Coach - 專業級西洋棋分析系統

一個不只會下棋，還會**深度教學**的專業 AI 系統。

本專案結合了優化的 Minimax 引擎、RAG (檢索增強生成) 技術與專業級評估體系，提供即時分析、深度講解與智能建議。

## 核心特色

### AI 教練系統
- **依問題調整的 RAG 問答**：檢索相關棋理，讓 Gemini 自然解釋、比較或給提示，支援同盤面的追問
- **引用與語意核對**：檢查來源、棋步與數值，再核對回答是否有依據及切題；來源原文可展開查看
- **無 Key 也可使用**：未設定 Gemini、模型逾時或引用不合格時，提供基礎分析與相關棋理
- **PV Line 深度講解**：解析引擎計算的最佳變例，逐步拆解戰術意圖
- **具體路徑分析**：不只說「這步好」，更說明「為什麼好」與「對手偏離會怎樣」
- **戰術識別**：自動識別叉王、牽制、棄子攻擊等戰術主題
- **心法提煉**：將複雜戰術總結為可學習的關鍵觀念

### 專業引擎功能
- **評估體系**：
  - Centipawn 格式化顯示（如 +1.50）
  - Sigmoid 勝率計算（0-100%）
  - 將死檢測（顯示 M3 等步數）
  - 可插拔的兵型、子力活動、車活動與王活動 evaluator
  - 以 phase units 平滑控制中後盤權重，權重為 0 的實驗特徵不進入搜尋成本
  - Stockfish gate 目前只啟用有淨收益的王活動；其餘特徵保留供後續校準
  
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

### 學習循環與課程引擎 V2
- **21 堂開局、中局與殘局課程**：支援白方與黑方視角
- **多解挑戰**：同一局面可接受多個經驗證的合理走法，並顯示對應解釋
- **結業門檻**：依正確率與提示使用量計分，通過先修課後才解鎖後續課程
- **錯題重練**：可只重做本次失誤的挑戰，錯題清單會存進進度，重整頁面後仍能接續重練；重練錯題屬於練習，不計入結業成績、熟練度與最佳分數
- **陷阱課支援**：課程主線預設一定是可接受答案；要把它教成錯誤走法時必須宣告 `rejectsMainline`，該手也會被排除在 Stockfish 閘門外
- **進度相容**：舊版 localStorage 記錄會自動升級到 V2，保留完成數與熟練度
- **內容驗證**：每個可接受走法都要通過 SAN／FEN 語義檢查，主線與 `challengeSteps` 不同步會直接驗證失敗；Stockfish gate 目前覆蓋 22 個非開局第一手或 V2 候選手案例

## 技術堆疊

- **Backend**: Python, FastAPI, python-chess
- **AI/RAG**: Google Gemini API, ChromaDB (向量資料庫)
- **Frontend**: React, Vite, chess.js, react-chessboard
- **Infrastructure**: Docker, Docker Compose
- **演算法**: Minimax + Alpha-Beta Pruning, Quiescence Search

## 快速開始

### 匯入 Chess.com 對局

在棋盤旁的「匯入 Chess.com 對局」輸入使用者名稱，選月份及一局棋譜，按「匯入此局」。
系統會自動選擇該帳號執白或執黑的視角，並將棋盤鎖定為復盤用途；按「新局」可回到對局。
接著按「分析這局」，完成後會選取玩家評分損失較大的一步之前的局面，可按「請教練講解這個局面」
或自行切換步數提問。講解沿用 RAG 的證據核對與無 Key 回退，不會自動分析整個帳號的所有棋局。

- 不需要 Chess.com 登入或 API Key；使用 [官方公開 API](https://www.chess.com/news/view/published-data-api)，輸入名稱不代表驗證帳號所有權。
- 最近 10 筆匯入棋譜保存在此瀏覽器的 localStorage，重複匯入會更新紀錄，可個別開啟或清除全部。清除網站資料、更換瀏覽器或裝置後不會同步；儲存失敗時會提示。
- 匯入紀錄不寫入伺服器的共用 `games` 資料表。分析時棋譜仍會送至後端；使用 Gemini 講解時，問題、相關對話與整理後的證據會送至模型。
- 僅支援公開、已完成、合法的標準西洋棋，最多 400 個半回合；每頁 20 局，不支援的棋譜會略過。
- 後端 `GET /imports/chesscom/{username}/archives` 取得月份，`GET /imports/chesscom/{username}/{year}/{month}?page=0` 取得棋局。固定連線至官方主機、不跟隨重新導向，各程序依序請求，最多暫存 4 份公開回應、每份 5 分鐘；來源資料也可能有更新延遲。
- 支援找不到帳號、限流、逾時、空棋局與錯誤資料的提示，可重新查詢。

### 教練問答與 RAG 模式

賽後分析走 `POST /review_game`，以 NDJSON 回傳進度：全局先以每次搜尋 50,000 節點初評，
再對掉分至少 50cp、接近分類邊界或涉及將殺的步數加深至 500,000 節點，最多複核 12 步。
候選過多時優先複核將殺及掉分較大的步數；畫面會標示複核數量及所選局面的初評／複核狀態。
每次搜尋另有 8 秒上限，整局預算預設 180 秒；節點是上限，不保證每次都達到。
可取消分析，服務會在當次搜尋返回後停止；中斷、逾時或缺少 Stockfish 會顯示錯誤，不發布部分結果。

圖表局面評分與教練的推薦手、實際手及變例沿用同一份伺服器 Stockfish 證據。
實際手與找到的候選手在同一局面以 MultiPV 比較；將殺分數保留獨立型別，不當成一般 cp 掉分。
`/explain` 使用 `review_id`、`review_ply` 與 FEN 核對證據，不會在賽後講解時改用自製引擎重算。
有限搜尋與目前的 cp 分類門檻仍可能誤判，這些調整不代表已驗證整體準確率。

分析證據只暫存於單一後端程序記憶體（最多 8 局、30 分鐘），不寫入資料庫。
重啟、過期或被新紀錄擠出後須重新分析；目前部署需使用單一 worker／實例，之後擴充多實例時需共用暫存。
可用 `STOCKFISH_REVIEW_QUICK_NODES`、`STOCKFISH_REVIEW_DEEP_NODES`、
`STOCKFISH_REVIEW_MAX_REFINEMENTS`、`STOCKFISH_REVIEW_TIMEOUT_SECONDS` 調整預算。
舊 `/analyze_full` 保留供相容用途，`STOCKFISH_REVIEW_NODES` 只控制舊路徑。

目前採用**有證據約束的自然回答**：模型可以改寫、解釋與摘要，每段附上來源 ID。
程式先檢查 JSON、引用來源、棋步與數值，再以第二次模型呼叫檢查支持性、切題程度、
不確定性與回答模式。只有通過核對的文字才顯示；語意審核仍可能出錯，並非正確性保證。
引擎負責推薦手，模型不得自行替換；證據不足時會明說無法確認。

一般規則、局面問答、候選比較、提示與完整分析採不同回答方式。一般規則不需等待
引擎搜尋；只有「分析目前局面」預設要求完整分析，平常問答不再附固定六段報告。
提示模式會移除推薦手、變例與含座標的來源，限制回答不洩漏具體走法。
前端傳入同一盤面最近最多 8 則訊息（每則最多 1,500 字），用於「再講簡單一點」等追問；
舊訊息不能作為棋理證據。盤面改變或開新局時取消尚未完成的教練請求。
來源原文收在「查看依據」中，可按需展開。

來源分為「一般棋理」與「本局分析」：前者來自 `backend/coach_evidence.py` 的
19 條版本控制知識，後者來自引擎分析、候選手比較、合法走法與 ECO 比對，以及直接由盤面計算的「上一手檢查」（是否送出一步殺、留下無保護棋子或錯過免費吃子）與「目前威脅檢查」。
一般棋理不代表目前局面已經出現該戰術；未完成候選比較時不提供確定的排名／掉分結論。
歷史棋局的 FEN 文字相似度尚未作為可引用證據。

- 預設使用本機關鍵字檢索，玩家問題的明確關鍵字優先於局面階段。
- 設定 `GOOGLE_API_KEY` 後啟用 Gemini 自然問答；成功回答通常需要生成、審核共兩次模型呼叫，會增加免費額度用量。未設定時仍可取得基礎分析與相關棋理。
- 選填 `ENABLE_CHROMA_RAG=1` 加入向量檢索。向量庫只負責排序，引用文字仍以本機審核過的知識為準；初始化會同步同一份知識，檢索失敗時回退本機檢索。
- 選填 `RAG_TIMEOUT_SECONDS=20` 設定生成與審核共用的時間預算（20–30 秒，較小設定自動提升至 20 秒）。單次請求與備援模型僅在剩餘預算至少 10 秒時啟動，沒有 SDK 自動重試。逾時或核對失敗時回退基礎回覆；此時間不包含引擎分析或向量庫初始化。
- 回答保留原有 `/explain` 的 `advice` 與 `/get_analysis` 的 `coach_advice` 字串介面，另附 `sources`、`mode`、`status`（後者加上 `coach_` 前綴）；請求可傳 `conversation` 與 `mode`（`auto`、`overview`、`hint`）。

回答品質可用真實模型抽查：`make coach-eval PYTHON=.venv/bin/python` 會把
`backend/coach_eval_cases.json` 的初學者問題各跑兩次，統計是否先下結論、提到關鍵走法、
給出下次的檢查習慣、視角是否正確與保留語氣次數。這會把局面與問題送到 Gemini 並使用 Key 的額度；
分數是比較調整前後的粗略指標，仍需閱讀回答本身。

離線回歸測試不需要 Key，也不會呼叫外部模型：

```bash
PYTHONPATH=backend .venv/bin/python -m unittest \
  backend/test_rag_grounding.py backend/test_rag_answers.py
```

### 前置需求

- Docker & Docker Compose
- [Google Gemini API Key](https://aistudio.google.com/)（啟用依問題選取證據的問答時需要；基礎分析選填）
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

3. **建立／升級資料庫並啟動**
   ```bash
   # 第一次使用全新 volume
   docker compose build
   docker compose run --rm backend python scripts/upgrade_database.py
   docker compose up
   
   # 背景執行
   docker compose up -d
   
   # 查看日誌
   docker compose logs -f
   
   # 停止服務
   docker compose down
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
   python3 -m venv .venv
   .venv/bin/pip install -r backend/requirements.txt

   # 全新資料庫先升級到最新版 schema
   make PYTHON=.venv/bin/python db-upgrade

   cd backend
   ../.venv/bin/python main.py
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

### 資料庫 migration

應用程式啟動時不再隱式執行 `create_all`；schema 只由 Alembic 管理。
本地啟動腳本、Docker 與 Render 都會先執行安全升級工具：全新或已由
Alembic 管理的資料庫會冪等升級；舊版或未知 schema 會在任何 Alembic
寫入前停止並提示人工接管。

全新資料庫：

```bash
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python db-current
```

若資料庫是舊版程式建立、已有 `games` 表但還沒有 `alembic_version`，
先備份，再執行嚴格的 baseline 接管與升級：

```bash
# 只驗證既有 schema 並 stamp 0001，不會執行 migration
DATABASE_URL=sqlite:///backend/games.db \
  make PYTHON=.venv/bin/python db-adopt

# 確認接管成功後才建立背景復盤資料表
DATABASE_URL=sqlite:///backend/games.db \
  make PYTHON=.venv/bin/python db-upgrade
```

接管工具遇到額外資料表、欄位、索引或不相容型別會直接拒絕，不會猜測或
修改資料。這兩步不會自動套用到目前的 `backend/games.db`。

部署至 Neon 時，應用程式可讓 `DATABASE_URL` 使用 pooled 連線；另將
direct（非 `-pooler`）連線設為 `MIGRATION_DATABASE_URL`，讓 Alembic
只透過 direct 連線更新 schema。連線字串只放環境變數，不要提交到版本庫。

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

候選手準確性另有兩種 Stockfish benchmark profile：

```bash
# 日常修改：8 個代表局面、depth 2、最多 3 個候選手，不啟用殘局自動加深
PYTHONPATH=backend .venv/bin/python backend/teaching_accuracy_benchmark.py --profile smoke

# 只檢查目前修改的主題；例如 positional 會跑全部 5 個局面棋題
PYTHONPATH=backend .venv/bin/python backend/teaching_accuracy_benchmark.py \
  --profile smoke --topic positional

# commit／merge 前：完整 23 局面與 50,000 Stockfish nodes
PYTHONPATH=backend .venv/bin/python backend/teaching_accuracy_benchmark.py \
  --profile release

# 對外宣稱高準確性前才強制正式門檻；目前尚未達標，會以非零狀態退出
PYTHONPATH=backend .venv/bin/python backend/teaching_accuracy_benchmark.py \
  --profile release --require-release-ready
```

也可從 `frontend/` 執行 `npm run validate:teaching-smoke`；額外參數可用
`npm run validate:teaching-smoke -- --topic positional` 傳入。

Stockfish oracle 會依引擎版本、nodes、FEN、MultiPV 與候選走法快取在
`backend/.cache/teaching_accuracy_stockfish.json`。修改自製引擎不需要清除
這份快取；更換 Stockfish 或 nodes 時會自動失效。需要強制重算可加
`--refresh-cache`，完全停用則使用 `--no-cache`。Smoke profile 只供快速方向
檢查，不能取代完整 release corpus。

### 提交前驗證

在專案根目錄執行：

```bash
# Backend 單元測試、Frontend lint 與 production build
make PYTHON=.venv/bin/python verify

# Stockfish smoke benchmark 與回歸門檻
make PYTHON=.venv/bin/python teaching-smoke
```

CI 會執行相同命令，並保存 smoke JSON 報告。Smoke gate 只防止已知品質
退步；正式對外宣稱準確性前仍須執行完整 release benchmark。

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
   - 複製 pooled connection string 作為 Render 的 `DATABASE_URL`
   - 另複製 direct connection string 作為 `MIGRATION_DATABASE_URL`

2. **部署 Render 後端**
   - 在 Render 建立 Blueprint 或 Web Service，連到 GitHub repo
   - 如果使用 Blueprint，Render 會讀取根目錄的 `render.yaml`
   - 必填環境變數：
     - `DATABASE_URL`: Neon 提供的 pooled Postgres 連線字串
     - `MIGRATION_DATABASE_URL`: Neon 提供的 direct Postgres 連線字串
     - `CORS_ORIGINS`: Vercel 前端網址；多個網址以逗號分隔
   - 選填環境變數：
     - `GOOGLE_API_KEY`: 啟用 Gemini 問答時設定；未設定仍提供基礎分析
     - `LICHESS_API_TOKEN`: Lichess Bot 需要時再填
     - `ENGINE_QUEUE_TIMEOUT_SECONDS`: 引擎忙碌時最多排隊秒數，預設 `2.0`
   - 每次服務啟動都會以 `MIGRATION_DATABASE_URL` 執行
     `python scripts/upgrade_database.py`；全新或已管理資料庫會安全升級
   - 若接管舊資料庫，先備份並執行
     `python scripts/adopt_alembic_baseline.py`，成功後再執行安全升級工具
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
npm test
npm run lint
npm run build
```

## 專案結構

```
.
├── backend/
│   ├── chess_engine.py      # Minimax 引擎與評估系統
│   ├── evaluation/          # 可組合、可校準的局面評估元件
│   │   ├── evaluator.py      # 加總、phase taper 與特徵權重 gate
│   │   ├── pawn_structure.py # 疊兵、孤兵、通路兵與連結兵
│   │   ├── piece_activity.py # mobility、象對與騎士前哨
│   │   ├── rook_activity.py  # 開放線、七橫線與雙車連結
│   │   └── king_activity.py  # 殘局王接近與對王
│   ├── rag.py               # RAG 教練邏輯
│   ├── api.py               # FastAPI 端點
│   ├── lichess_bot.py       # Lichess Bot 客戶端
│   ├── database.py          # SQLite／Postgres ORM 與復盤 job model
│   ├── migrations/          # Alembic schema revisions
│   ├── scripts/             # 安全 migration 與舊資料庫接管工具
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
