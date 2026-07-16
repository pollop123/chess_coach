# Chess AI 建議準確性稽核報告

日期：2026-07-14
範圍：走法推薦、教學分析、AI 教練文字、賽後課程推薦、訓練課程內容
狀態：已完成第一輪程式檢查與 Stockfish 18 實測

> **歷史快照說明（2026-07-15 更新）**
> 本文正文保留 2026-07-14 修正前的稽核結果，不能視為目前程式狀態。
> 下列問題已在後續修改中處理：非法／錯誤課程局面、候選手固定原始
> best move、推薦手與理由脫鉤、`Nxf7` 戰術誤標、非兵殘局套用兵殘局
> 心法，以及缺少獨立 Stockfish accuracy gate。評估函式亦已拆成獨立
> `backend/evaluation/` 模組，並保留舊評分行為作為後續改良基線。
>
> 修正後驗證：Backend 135 tests、reason benchmark 24/24、teaching
> structure benchmark 8/8、21 課程語義驗證與 14 課程 Stockfish 檢查均
> 通過。23 局面、50,000 nodes 的獨立 Stockfish benchmark 為 top-3
> 60.9%、最佳著 recall 78.3%；戰術 100%，但 positional top-3 20%、
> endgame top-3 40%，因此嚴格 `release_ready` 仍為 `false`。目前下一個
> 後續已新增兵型、子力活動、車活動與王活動元件；經獨立消融測試後，
> 預設搜尋只啟用不降低 top-3/recall 且改善殘局候選 MAE 的王活動，
> 其餘特徵保留為權重 0 的可校準元件。嚴格 `release_ready` 仍為 `false`，
> 不應把這次改良宣稱為已全面達成高準確性。

## 1. 執行摘要

目前系統的核心走法引擎，已足以支撐「中階陪練、走法大多合理」的產品定位；但整體教學建議的準確性仍不足，不能把所有候選手排序、棋理理由、警告與課程推薦都稱為「已驗證」。

主要結論如下：

- 中階與中階加強模式在現有 14 個固定測試局面上沒有出現 Stockfish 判定的 blunder，近最佳著率皆為 92.9%。
- 現有 teaching benchmark 雖然得到 8/8，卻會把預期答案直接注入為引擎最佳著，因此無法獨立證明答案正確。
- 教學分析會固定把原始 `best_move` 排在第一名，即使候選手重新搜尋的分數顯示其他走法更好。
- 棋理 `reason` 與 `theme` 規則過度寬鬆，可能把普通后車移動說成「避免大子損失」，或把攻擊對方國王說成「改善己方王安全」。
- 21 個訓練課程中，已確認至少兩個起始 FEN 不合法、一個課程答案會造成決定性劣勢，另有一個課程答案明顯低於同局面的最佳戰術著。
- 賽後課程推薦目前是依回合階段和掉分幅度做粗略標籤，適合當 MVP 導流，但不足以視為真正的弱點診斷。

因此建議把後續工作分成三個優先級：先修錯題與驗證漏洞，再修教學候選手與理由，最後擴充獨立準確性基準。

## 2. 稽核方法與限制

本次使用下列方式交叉檢查：

1. 執行完整 backend 單元測試。
2. 執行現有 teaching benchmark。
3. 使用本機 Stockfish 18、每次分析 12,000 nodes，重新評估既有 14 個 calibration 局面。
4. 對具爭議的課程題目使用 Stockfish 18、50,000 nodes 個別比較指定走法與最佳著。
5. 使用 `python-chess` 檢查自訂課程起始 FEN 的語義合法性。
6. 執行課程 validator、frontend lint 與 production build。

已通過的工程驗證：

- Backend：62 tests passed。
- Teaching benchmark：8/8 passed，但有效性有本報告第 4 節所述限制。
- Training lessons validator：21 lessons passed，但目前未檢查局面語義合法性。
- Frontend lint：passed。
- Frontend build：passed。

本次 Stockfish 樣本只有 14 個固定局面，其中包含簡單戰術、殘局和開局庫局面。因此數字只能證明這批固定樣本的表現，不能直接外推為所有實戰局面的準確率。

## 3. 核心走法推薦評估

### 3.1 Stockfish 18 實測結果

| 模式 | 測試局面 | ACPL | 中位掉分 | 近最佳著率 | Blunder rate | 漏殺 | 送大子 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 新手 | 14 | 120.5 | 6.0 | 57.1% | 35.7% | 0 | 0 |
| 初階 | 14 | 46.2 | 0.0 | 64.3% | 21.4% | 0 | 0 |
| 中階 | 14 | 5.5 | 0.0 | 92.9% | 0% | 0 | 0 |
| 中階加強 | 14 | 14.5 | 0.0 | 92.9% | 0% | 0 | 0 |

判讀：

- 中階與中階加強在目前固定樣本上可接受，符合「穩定陪練」而非高階棋力引擎的定位。
- 新手與初階模式刻意加入強度差異，不能拿它們的建議當作教學上的最佳答案。
- 教練分析端點不應沿用低難度 bot 實際選著作為「最佳建議」。目前 `/get_analysis` 使用獨立的深度分析，方向正確。
- 中階加強的 ACPL 高於中階，主要受單一升變題 centipawn 評估影響；該走法仍維持相同勝率期望。後續報告應同時保留 ACPL 與 WDL expectation loss，避免單一指標誤導。

### 3.2 目前可採用的產品說法

可以使用：

- 「適合中階陪練。」
- 「在固定測試局面中，大多能找到合理走法。」
- 「賽後分析優先使用 Stockfish 作為裁判。」

暫時不應使用：

- 「每一步都是最佳著。」
- 「教學理由均經引擎驗證。」
- 「能精準辨識玩家的棋力弱點。」

## 4. Teaching benchmark 的有效性問題

### 4.1 預期答案被直接注入

`backend/teaching_benchmark.py` 的 `_expected_base_move()` 會從 `expected_best_san` 取出走法，再把它放進：

```python
base_analysis = {
    "best_move": expected_move,
    "score": 0,
    "depth": position.depth,
}
```

而 `get_teaching_analysis()` 會優先加入並固定保留 `base_analysis["best_move"]`。因此 benchmark 的 `matched_best` 在相當程度上是在確認「注入的答案是否仍排第一」，不是確認引擎是否自行找到了正確答案。

### 4.2 驗收條件過度寬鬆

- 多數題目的 `expected_criticality` 預設同時接受 `normal`、`sharp`、`only_move`，等同沒有驗證 criticality。
- `expected_warnings` 只檢查預期集合是否為實際集合的子集合；多出錯誤 warning 仍會通過。
- benchmark 沒有使用 Stockfish、tablebase 或人工標註 PV 作為獨立 oracle。
- 測試只要求 `passed > 0`，沒有要求整體 pass rate、各主題最低通過率或禁止 false positive。

### 4.3 修正要求

新版 benchmark 應分成兩層：

1. **結構測試**：確認欄位、合法 SAN、不改動棋盤、timeout partial result。
2. **準確性測試**：從真實 FEN 執行完整 analysis，使用 Stockfish 或人工核准答案作為獨立 oracle。

禁止把 `expected_best_san` 注入被測函式。若要測 reason/theme，可明確標成 fixture test，不得把結果稱為 engine accuracy。

## 5. 候選手排序與分數一致性

### 5.1 問題

`backend/chess_engine.py` 目前會：

1. 找到與原始 `best_move` 相同的 candidate。
2. 只排序其他 candidates。
3. 把原始 candidate 強制放回第一名。
4. 以第一名分數計算所有 `loss_cp`。

這可能產生下列不一致：

- Rank 1 的重新評分低於 Rank 2。
- Rank 2 實際比 Rank 1 高分，卻因 `max(0, best - candidate)` 得到 0 loss。
- `only_move` 與 `sharp` 建立在錯誤基準上。
- RAG 收到的「已驗證候選手排序」其實不是按同一套分數排序。

### 5.2 修正方向

- 所有 candidates 必須使用相同深度、deadline 和評分視角。
- 完成評分後按 `perspective_score` 排序，不應固定原始 `best_move` 第一。
- 如果必須保留原始搜尋結果，應增加 `base_engine_choice: true`，而不是假裝它是 candidate rank 1。
- `loss_cp` 應以候選集合的最高有效分數計算。
- timeout 時應回傳 `analysis_complete: false` 或 candidate 個別的 `score_status`，避免把 partial result 宣稱為完整比較。
- mate score、tablebase 結果與普通 centipawn 必須分開處理。

### 5.3 驗收標準

- Rank 必須與 candidate score 的原始走棋方視角一致。
- Rank 1 的 `loss_cp` 必須為 0。
- 非 Rank 1 若同分可為 0，但需有 `near_equal` 或相同分數證據。
- 人工建立一個 `base_best_move` 故意錯誤的測試，確認系統會將更高分 candidate 排到第一。
- 黑方走棋局面也必須通過相同排序測試。

## 6. Reason、Theme 與 Warning 的準確性

### 6.1 已確認的過度推論

目前規則包含下列風險：

- 吃到價值 300 以上棋子就回傳 `wins_material`，沒有確認交換序列的淨物質結果。
- 任何未觸發 `hangs_major_piece` 的后或車移動，都可能回傳 `avoids_major_piece_loss`，即使該棋子原本沒有危險。
- `_move_attacks_king_zone()` 被映射為 `improves_king_safety`；攻擊敵王和改善己王安全是不同概念。
- 從中心格離開也會得到 `center_control`。
- 任何吃子、將軍或升變都得到 `tactics`，容易把一般交換誇大成戰術主題。
- 無后局面或小子少於等於兩枚就被視為教學殘局，可能誤標仍有多車與多兵的中局。
- `major_piece_loss_after_move` 的 warning 會額外人工扣 500cp，使 warning 規則反過來污染候選手排名與 criticality。

### 6.2 建議的證據分級

每個 reason/theme 應標記證據強度：

- `verified`：將死、合法升變、立即淨吃子、tablebase 結果等可直接證明的事實。
- `supported`：由 PV 和評估差支持，但仍是引擎判斷。
- `heuristic`：開局原則、中心控制、王安全等規則式解讀。

RAG 文案必須依證據強度調整：

- `verified` 可以使用肯定句。
- `supported` 使用「引擎變例顯示」。
- `heuristic` 使用「這步可能有助於」，不得標成已驗證事實。

### 6.3 Reason 規則修正原則

- `wins_material`：比較 PV 前後的 material balance，並至少搜尋對手一次合理吃回。
- `avoids_major_piece_loss`：必須證明走棋前大子正受到攻擊，且走棋後該直接威脅解除。
- `improves_king_safety`：檢查己方王區攻擊數、合法逃生格、是否完成易位或消除直接將軍威脅。
- 新增 `attacks_enemy_king`，不要和 `improves_king_safety` 混用。
- `controls_center`：確認移動後棋子新增或維持對 d4/e4/d5/e5 的有效控制。
- `wins_material`、`avoids_major_piece_loss`、`controls_center` 都需加入正反例測試。

## 7. AI 教練文字層風險

`backend/rag.py` 會把 reason code 轉換成肯定句，例如：

- `wins_material` →「能在已驗證的變例中取得物質優勢」
- `avoids_major_piece_loss` →「能避開后或車遭受攻擊的直接損失」
- `improves_king_safety` →「讓王更接近安全或關鍵位置」

當底層 reason 只是 heuristic 時，文字會放大錯誤的確定性。

### 修正要求

- Grounded formatter 必須優先使用程式生成的合法推薦手，現有做法應保留。
- 「對手最強回應」只能來自有效 PV；沒有 PV 時應明說尚未驗證。
- 「應避免」不能只取第一個有 warning 的 candidate，應選擇證據最強且與使用者問題相關的反例。
- 開局名稱、棋子移動事實和合法走法的現有 grounding 防護應保留。
- 若 candidate analysis timeout，教練文案不得使用「候選手已完整比較」。

## 8. 已確認的課程內容問題

### P0：`endgame-rook-activity` 答案錯誤

局面：

```text
8/5pk1/6p1/3R4/7P/6P1/5PK1/3r4 w - - 0 1
```

課程指定：`Rd7`
Stockfish 18 最佳：`Rxd1`

50,000-node 比較：

- `Rxd1`：約 +6.09。
- `Rd7`：約 -5.41。
- 評估差：約 1150cp。
- WDL expectation loss：1.000。

白車可以沿 d 線直接吃掉黑車，因此不能用此局面教授 `Rd7` 的活躍車概念。應更換 FEN，而不是只把答案改成 `Rxd1`，否則課程主題會消失。

### P0：`endgame-queen-mate-net` 起始局面不合法

```text
7k/6Q1/5K2/8/8/8/8/8 w - - 0 1
```

黑王在白方走棋前已經被白后將軍，局面卻標示白方走，因此不可能由合法棋局到達。`chess.js` 仍接受後續 `Kf7#`，但這不能證明 FEN 合法。

### P0：`endgame-lucena-bridge` 起始局面不合法

```text
4K3/4P3/8/8/8/8/4r3/4R1k1 w - - 0 1
```

黑王在 g1 已受到白車 e1 攻擊，卻標示白方走。指定的 `Rg1+` 在語義上實際會變成車移到黑王所在格；這不是合法西洋棋題目。

此外，該局面不是標準 Lucena 結構。建議使用可由 tablebase 驗證的標準 Lucena FEN，並以多步 PV 教授架橋，不要只放一個抽象的 `Rg1+`。

### P1：同局面兩個課程答案品質衝突

局面：

```text
r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6
```

- `middlegame-two-knights-fork` 指定 `Nxf7`，Stockfish 支持為最佳著。
- `middlegame-center-pressure` 指定 `Qf3`。
- 50,000-node 比較中，`Qf3` 約比 `Nxf7` 差 156cp，WDL expectation loss 約 0.368。

若要保留 `Qf3` 的教學概念，應換成沒有立即 `Nxf7` 戰術的局面；不能在已有強制戰術時把一般加壓手當主要答案。

### P2：可接受但不是最佳的課程答案

- `Qh3` 在指定送后警示題中仍維持明顯勝勢，但 Stockfish 偏好 `Qe5+`，兩者約差 380cp；WDL expectation loss 僅約 0.005。可保留為「安全走法」示例，但不應稱為最佳著。
- `e8=Q` 在升變題中仍為勝勢，但 Stockfish 偏好先走王；約差 194cp，WDL expectation loss 為 0。若課程只教直接升變，可接受，但應確認是否要教授最快或最精確的轉換。
- `Kf4` 在王兵題中與 `Kd4` 只差約 6cp，可視為近似等價，不需優先修改。

## 9. 課程 validator 的缺口

目前 `frontend/scripts/validate-training-lessons.mjs` 主要檢查：

- 課程數量、ID、階段、tag、欄位完整性。
- `chess.js` 是否能逐步執行 SAN。
- prerequisite 是否存在。

它沒有確認：

- FEN 是否為可由合法棋局到達的語義有效局面。
- 非走棋方是否已處於非法被將狀態。
- 是否存在相鄰雙王、缺王、過量棋子等問題。
- 推薦著是否接近最佳著。
- 課程文字是否和盤面事實一致。

### 修正要求

- 新增 Python validator，使用 `python-chess Board.is_valid()` 與 `status()` 檢查所有 `startFen`。
- 對 puzzle/guided/endgame 第一個指定走法，以 Stockfish 固定 nodes 或 Syzygy tablebase 驗證。
- 為課程設定容許值，例如：
  - puzzle：必須為唯一解、將殺或不超過 30cp。
  - guided：不超過 80cp，且不能改變勝負／和棋結果。
  - opening：允許多個主流走法，使用 opening book 或人工核准清單。
- 驗證 lesson ideas 中的直接盤面事實，例如是否真的將軍、吃子、牽制、升變或攻擊指定格。

## 10. 賽後課程推薦評估

目前推薦器依下列訊號建立 tag：

- 前 8 回合的錯誤 → `opening`、`development`。
- 掉分大於等於 150cp → `tactics`、`calculation`。
- mate threat → `king_safety`、`checkmate`。
- 殘局掉分大於等於 250cp → `promotion`。
- 中局掉分大於等於 50cp → `center`。

這套方法具備可解釋、穩定、無 LLM 幻覺的優點，但會把很多不同錯誤歸到同一類。例如中局漏掉底線殺、送后、錯誤交換和兵型決策，都可能被標成中心問題。

### 短期修正

- UI 文案由「根據這盤的失誤類型」改為「根據失誤階段與掉分幅度推測」。
- 沒有足夠證據時不要顯示三個具體弱點，只顯示一般複習建議。
- 課程推薦必須排除 validator 未通過的課程。

### 中期修正

在 Stockfish 賽後分析中增加可驗證特徵：

- 是否漏掉將殺或允許將殺。
- 是否直接送后、車或小子。
- 是否錯過明確吃子。
- 是否為升變或阻止升變問題。
- 是否涉及王安全、未完成發展或重複走子。
- 是否為殘局勝轉和、和轉敗。

推薦器再根據這些事實映射 lesson tags，而不是只依 cp loss 和回合數。

## 11. 建議修正順序

### 第一階段：阻止明確錯誤內容（P0）

1. 停用或修正三個問題課程：
   - `endgame-rook-activity`
   - `endgame-queen-mate-net`
   - `endgame-lucena-bridge`
2. 為所有 `startFen` 增加 `python-chess` 語義合法性驗證。
3. 修正 `Qf3` 與 `Nxf7` 共用局面的內容衝突。
4. 推薦器不得推薦未通過準確性驗證的課程。

完成定義：所有課程 FEN 有效，所有 puzzle/guided 第一手都通過外部引擎或 tablebase 門檻。

### 第二階段：修正候選手可信度（P1）

1. 移除固定 `base_best_move` 為 rank 1 的行為。
2. 使用一致評分重新排序 candidates。
3. 修正 `loss_cp`、`criticality` 和 timeout 狀態。
4. 將 teaching benchmark 分成結構與準確性兩套。
5. 加入黑方視角、錯誤 base move、同分走法與 mate score 測試。

完成定義：候選手 rank、score、loss 與外部 oracle 在核准測試集上保持一致，且沒有自我注入答案。

### 第三階段：收緊教學解說（P1）

1. 重寫 `wins_material`、`avoids_major_piece_loss`、`improves_king_safety`、`controls_center` 規則。
2. reason/theme 增加 `verified`、`supported`、`heuristic` 證據層級。
3. 讓 RAG 根據證據層級調整語氣。
4. 建立 false-positive benchmark，除了預期命中，也必須驗證不應出現的標籤。

完成定義：每個 reason 至少有正例、反例、黑白視角各一組；benchmark 對多餘 warning/theme 也會失敗。

### 第四階段：提升賽後推薦精度（P2）

1. 從 Stockfish review payload 增加具體錯誤事實。
2. 以具體錯誤事實映射課程 tag。
3. 建立推薦器 fixtures，驗證不同錯誤會導向正確課程類別。
4. 顯示推薦依據，例如「第 18 手漏掉底線防守，因此推薦底線殺題」。

完成定義：推薦理由可追溯到特定回合、特定可驗證錯誤與對應課程能力。

## 12. 建議新增的品質門檻

### 引擎走法

- 至少 100 個固定局面，分開統計 opening、middlegame、tactics、endgame。
- 中階模式：blunder rate 小於 5%，missed mate 為 0，major-piece hang 為 0。
- 中階加強：平均 WDL expectation loss 不高於中階；若 ACPL 受必勝局面影響，需另行說明。
- 每次修改搜尋、評估函式或 opening book 後都重跑。

### Teaching analysis

- Candidate top-1 與 Stockfish top-N 的一致率。
- Candidate set 對 Stockfish 最佳著的 recall。
- `only_move` precision 與 recall。
- Warning precision 優先於 recall，避免教練亂報送子或漏殺。
- Theme/reason 同時檢查 true positive 與 false positive。

### 課程內容

- 100% FEN semantic validity。
- 100% SAN legality。
- Puzzle 題 100% 經 Stockfish/tablebase 驗證。
- Guided 題不得造成勝負結果翻轉。
- 所有直接棋理敘述必須可由盤面或 PV 證明。

### 推薦器

- 每個 weakness tag 至少三個正例與兩個反例。
- 推薦理由可追溯到特定 review move。
- 無明確證據時回傳一般建議，不強行診斷。

## 13. 建議驗證命令

現有回歸：

```bash
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend -p 'test_*.py'
PYTHONPATH=backend .venv/bin/python backend/teaching_benchmark.py --json
PYTHONPATH=backend .venv/bin/python backend/stockfish_calibration.py \
  --stockfish /opt/homebrew/bin/stockfish \
  --nodes 12000 \
  --json

cd frontend
npm run validate:lessons
npm run lint
npm run build
```

後續應新增：

```bash
PYTHONPATH=backend .venv/bin/python backend/validate_training_lessons.py
PYTHONPATH=backend .venv/bin/python backend/teaching_accuracy_benchmark.py \
  --stockfish /opt/homebrew/bin/stockfish \
  --nodes 50000
```

第二組命令目前是建議介面，相關腳本尚未建立。

## 14. 最終判定

| 項目 | 目前判定 | 是否足夠 |
|---|---|---|
| 中階／中階加強走法 | 固定樣本表現良好 | 可作陪練，不能稱高精度引擎 |
| 候選手排名 | 受原始 best move 固定排序影響 | 不足 |
| 棋理 reason/theme | 有多個過度推論規則 | 不足 |
| AI 教練文字 | 合法走法 grounding 良好，但會放大錯誤 reason | 不足 |
| Stockfish 賽後評分 | 架構方向正確 | 基本足夠，仍需更多 nodes/coverage |
| 課程推薦 | 可解釋的粗略 MVP | 不足以稱精準診斷 |
| 課程內容 | 存在非法 FEN 與嚴重錯題 | 不足，應優先修正 |

短期發布前最低要求，是完成第一階段 P0 修正。若要對外主打「AI 教練」而不只是「可以對弈的棋力引擎」，則第二、第三階段也應完成後再宣稱教學分析具有可靠準確性。
