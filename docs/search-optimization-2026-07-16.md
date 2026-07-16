# 低運算量搜尋優化記錄

日期：2026-07-16

目標是保留自製 Minimax/alpha-beta 引擎，以教學平台可控的運算量為優先，並用 Stockfish 作為獨立準確性裁判，而不是取代自製引擎。

## 過往方法與本輪選擇

- Stockfish 在迭代加深上使用 aspiration window，搜尋中也結合 LMR、futility pruning、null-move pruning 等方法。
- Ethereal 的搜尋程式同樣對後段走法使用 LMR，並在縮減搜尋顯示可能改善邊界時重搜。
- Sunfish 證明小型 Python 引擎也能透過傳統 alpha-beta 搜尋技巧保持簡潔，不需要全盤複刻 Stockfish 架構。

參考原始程式：

- [Stockfish search.cpp](https://github.com/official-stockfish/Stockfish/blob/master/src/search.cpp)
- [Ethereal search.c](https://raw.githubusercontent.com/AndyGrant/Ethereal/master/src/search.c)
- [Sunfish sunfish.py](https://raw.githubusercontent.com/thomasahle/sunfish/master/sunfish.py)

## 實驗結果

### Aspiration window：不保留

100cp 初始視窗在 5 個代表局面的結果與完整視窗一致，但深度 4 節點只從 35,803 降到 35,699（-0.3%）。30cp 和 60cp 反而因重搜增加節點，所以已撤除實作。

### Quiescence delta pruning：不保留

代表局面約 51.1% 的搜尋節點來自 quiescence，因此曾實驗只略過「非被將、非升變、非將軍著」且在子力上不可能跨過 alpha/beta 的吃子。200cp 緩衝在 5 個固定深度局面保持走法與分數，但只少 2.9% 節點；14 局面時限校準中只少 1.2% 節點。Stockfish ACPL 雖維持 14.5，但收益不足以抵銷剪枝風險與維護成本，實作已撤除。

### 單次搜尋靜態評估快取：不保留

以 Zobrist hash 快取同一搜尋內的靜態評估時，10,908 次評估中有 3,192 次命中（約 29%），但總時間從 3.035 秒變成 3.039–3.047 秒。在目前 Python 實作中，計算 hash 與查表的成本抵銷了評估命中，所以不加入引擎。

### 保守型 LMR：保留

目前只對以下走法嘗試少搜一層：

- 當前搜尋深度至少 4。
- 排序後第 5 手以後的走法。
- 非將軍、非吃子、非升變，且當前不在被將軍狀態。
- 不縮減即將升變的兵。
- 縮減搜尋若顯示該手可能突破 alpha/beta 邊界，立即恢復完整深度重搜。

5 個代表局面、深度 4：

| 模式 | 總節點 | 總時間 | 走法／分數 |
|---|---:|---:|---|
| LMR 關閉 | 35,803 | 5,753 ms | 基準 |
| LMR 開啟 | 17,070 | 2,302 ms | 4 題完全一致；1 題同分走法改變 |

固定深度代表局面節點約減少 52%，時間約減少 60%。在 1.5 秒時間限制下，14 局面 Stockfish 校準的 ACPL 仍為 14.5、平均勝率期望損失仍為 0.0018，平均完成深度從 2.50 增加到 2.86。

23 局面、50,000 Stockfish nodes 的 teaching accuracy 結果維持 top-3 60.9%、最佳著 recall 78.3%，與評估模組分支的基準相同。因此 LMR 沒有降低目前獨立準確性，但嚴格 `release_ready` 仍為 `false`；下一個品質瓶頸是評估函數與候選排序，不是搜尋速度。

## 驗證

- Backend：137 tests passed
- Reason benchmark：24/24
- Teaching structure benchmark：8/8
- `git diff --check`：passed

## 後續邊界

Null-move pruning 在 zugzwang 與兵殘局容易出問題，futility pruning 與更激進的 LMR 也可能漏看延遲戰術。在教學平台中，它們都應繼續作為可關閉的 A/B 實驗，並且必須先通過戰術與殘局分類閨門，不應直接當成預設功能。
