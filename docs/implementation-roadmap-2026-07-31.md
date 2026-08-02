# Chess AI Coach 實作路線圖

日期：2026-07-31

## 目標

把專案從功能完整的單機作品，推進成準確性可量測、公開部署可承受、
且能持續迭代的教學產品。排序原則是先守住正確性與服務穩定，再增加功能。

## Phase 1：工程與安全基線（已完成）

- API 對 FEN、PGN、depth、time limit、history 與 pagination 設定上限。
- 完整賽局分析限制為 400 plies。
- API 每個請求建立獨立 `EngineSession`，並以可設定的 bounded slots 控制 CPU；
  忙碌逾時回傳可重試的 HTTP 503。
- CORS 改由 `CORS_ORIGINS` 設定，不再預設允許所有來源。
- Python runtime dependencies 固定版本，新增 dev requirements。
- 新增 `make verify`、`make teaching-smoke` 與 GitHub Actions。
- Smoke benchmark 加入可版本控制的 regression gate。
- 候選著先通過「可立即吃回的低證據棄子」screen，再進行完整比較；
  已驗證 fork 不會被延後。

本階段驗收基線：

- Backend：209 tests。
- Frontend：13 tests、ESLint 與 production build 通過。
- Teaching smoke：Top-3 50%、最佳著召回 75%、排序反轉 20.8%。
- 相較修改前，最佳著召回由 62.5% 提升至 75%，排序反轉由 25% 降至
  20.8%，平均候選損失誤差由 91.8cp 降至 73.6cp。
- 在另一組 game-grouped validation slice（每主題 4 題、共 16 題）中，
  Top-3 維持 81.2%，最佳著召回由 62.5% 升至 68.8%，平均候選損失誤差
  由 153.5cp 降至 144.7cp；排序反轉由 6.7% 小幅變為 7.1%。因此保留
  此候選篩選，但不把小樣本結果外推為完整 validation 結論。

## Phase 2：服務架構（進行中）

- [x] 將 TT、generation、deadline、stats 與 evaluator 移入
  `EngineSession`；API 與 Lichess 多局不再共享可變搜尋狀態。
- [x] 建立 `review_jobs`／`review_moves` durable schema，預留 idempotency、
  lease、progress、cancel 與逐步結果欄位。
- [x] 導入 Alembic、移除 import-time `create_all`，並提供 fail-closed legacy
  adoption 與安全啟動升級工具。
- [ ] 將 `/analyze_full` 接到獨立 worker，提供建立、狀態、取消、結果與前端
  polling；目前只完成資料層，不宣稱背景執行已完成。
- [ ] 將 `api.py` 拆成 schemas、analysis routes、game routes 與 services。
- [ ] 公開多人使用前，替 `/games` 與 review jobs 加入使用者歸屬與存取控制。

驗收條件：

- 兩個並行分析不共享 deadline、stats 或 generation（已驗證）。
- 使用者中止復盤後不再消耗 Stockfish／自製引擎資源（待 worker 實作驗證）。
- migration 可在空資料庫與精準匹配的既有資料庫部署，且資料不遺失
  （已以 tempfile 驗證）。
- Session refactor 的固定深度中位時間差為 positional +1.3%、rook endgame
  +4.8%，節點數完全一致；固定時間首輪完成深度與節點數也一致。

## Phase 3：棋力與教學準確性

1. 只使用 train split 調整 evaluator，在 validation split 決策。
2. 針對未通過局面建立錯誤類型：horizon、candidate miss、ranking error、
   evaluation semantic gap。
3. 優先解決 positional 與 rook endgame，不以增加固定時間掩蓋問題。
4. 候選池實驗必須同時報告 recall、Top-3、inversion、loss MAE 與 latency。
5. 候選方案通過 validation gate 後，才對 untouched test split跑一次。

驗收條件：

- Smoke 不低於目前 regression gate。
- Validation 的 positional Top-3、WDL loss 與 blunder rate 同時改善。
- Test split 不因單一主題改善而出現整體退步。

## Phase 4：產品學習循環

- [x] 將復盤中的錯誤主題連到課程推薦，並排除未驗證或尚未解鎖課程。
- [x] 記錄完成、錯誤、提示、分數、連續通過、錯題步驟與下次複習時間；
  V1 進度可無痛移轉到 V2。
- [x] 完成課程引擎 V2 縱向切片：獨立挑戰局面、多個可接受答案、
  逐手解釋、結業分數、先修解鎖與只重練錯題。
- [x] 擴充 Vitest／React Testing Library，覆蓋學習排程、V1→V2 移轉、
  多解判定、分數、先修鎖定、結業與錯題重練介面。
- [ ] 補上棋盤 drag／click 全流程、AI 回應與復盤 polling 的互動回歸。
- [ ] 追蹤 p50/p95 latency、timeout、完成深度、RAG fallback 與課程完成率。

驗收條件：

- 同一弱點再次出現時會提高對應課程優先級。
- 核心學習狀態與結業介面可在 CI 無瀏覽器人工操作下回歸驗證；
  棋盤完整操作流程尚待補齊。
- 使用者看得到分析進度、失敗原因與安全的重試入口。
