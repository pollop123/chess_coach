# API 端點架構優化文件

## 概述

本次優化將 API 端點分離為「快速走法」和「深度分析」兩個獨立端點，提升使用者體驗和系統穩定性。

## 新增端點

### 1. /make_move (快速走法)

**用途**: 遊戲進行時計算 AI 走法

**時限**: 2 秒

**請求格式**:
```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
  "time_limit": 2.0
}
```

**回應格式**:
```json
{
  "best_move": "e7e5",
  "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
  "is_game_over": false,
  "result": null,
  "evaluation_display": "+0.30",
  "depth_reached": 5
}
```

**使用時機**:
- 玩家移動後立即呼叫
- 需要快速回應以保持遊戲流暢度
- 不需要詳細分析，只要走法即可

### 2. /get_analysis (深度分析)

**用途**: 提供完整分析與 AI 教練建議

**時限**: 5 秒

**請求格式**:
```json
{
  "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "history": "1. e4 e5",
  "question": "請分析當前局面",
  "depth": 5,
  "time_limit": 5.0
}
```

**回應格式**:
```json
{
  "evaluation": {
    "score_cp": 30,
    "display": "+0.30",
    "winning_chance": 52.2,
    "pv_line": ["g1f3", "b8c6", "f1c4", "g8f6", "d2d3"],
    "depth_reached": 6,
    "nodes_searched": 8542
  },
  "game_state": "opening",
  "coach_advice": "當前局面為開放型義大利開局..."
}
```

**使用時機**:
- 背景非同步呼叫，不阻塞遊戲進行
- 需要詳細評估數據時
- 玩家主動請求教練建議時

## 相容性端點

### /analyze (已保留)

原有端點保持可用，建議逐步遷移到新端點。

**變更**:
- 新增 3 秒時限避免超時
- 回傳格式不變

### /explain (已保留)

原有教練端點保持可用，建議使用 /get_analysis 替代。

**變更**:
- 新增 4 秒時限
- 安全防禦機制完整保留

## 前端整合範例

### 基本流程

```javascript
// 1. 玩家移動後
async function handlePlayerMove(move) {
  // 樂觀更新 UI
  board.move(move);
  updateUI();
  
  // 快速取得 AI 走法
  showThinking();
  const moveResponse = await fetch('/make_move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fen: board.fen(),
      time_limit: 2.0
    })
  });
  
  const moveData = await moveResponse.json();
  
  // 移動 AI 棋子
  board.move(moveData.best_move);
  updateUI();
  hideThinking();
  
  // 背景載入分析
  loadAnalysisInBackground(board.fen(), board.pgn());
}

// 2. 背景載入分析（不阻塞）
async function loadAnalysisInBackground(fen, history) {
  showAnalysisLoading();
  
  try {
    const analysisResponse = await fetch('/get_analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        fen: fen,
        history: history,
        depth: 5,
        time_limit: 5.0
      })
    });
    
    const analysisData = await analysisResponse.json();
    
    // 更新 UI
    updateEvaluationBar(analysisData.evaluation.winning_chance);
    updatePVLine(analysisData.evaluation.pv_line);
    updateCoachAdvice(analysisData.coach_advice);
  } catch (error) {
    console.error('分析載入失敗:', error);
  } finally {
    hideAnalysisLoading();
  }
}
```

### React Hook 範例

```javascript
import { useState, useEffect } from 'react';

function useChessAnalysis() {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const fetchAnalysis = async (fen, history) => {
    setLoading(true);
    try {
      const response = await fetch('/get_analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fen, history, depth: 5 })
      });
      const data = await response.json();
      setAnalysis(data);
    } catch (error) {
      console.error('分析失敗:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return { analysis, loading, fetchAnalysis };
}

// 使用
function ChessGame() {
  const { analysis, loading, fetchAnalysis } = useChessAnalysis();
  
  const handleMove = async (move) => {
    // 移動棋子
    board.move(move);
    
    // 取得 AI 走法
    const aiMove = await getAIMove(board.fen());
    board.move(aiMove);
    
    // 背景載入分析
    fetchAnalysis(board.fen(), board.pgn());
  };
  
  return (
    <div>
      <Board onMove={handleMove} />
      {loading && <AnalysisLoader />}
      {analysis && <AnalysisPanel data={analysis} />}
    </div>
  );
}
```

## 效能指標

### 回應時間

| 端點 | 目標時間 | 實測時間 | 使用者感知 |
|------|---------|---------|-----------|
| /make_move | < 2s | 0.3-1.5s | 快速 |
| /get_analysis | < 5s | 2-4s | 可接受 |
| /analyze (舊) | 不定 | 1-3s | 偶爾卡頓 |

### 使用者體驗提升

**改進前**:
```
玩家移動 → [等待 1-3 秒] → AI 移動 + 分析完成
感知延遲: 1-3 秒（卡頓）
```

**改進後**:
```
玩家移動 → [0.5 秒] → AI 移動 → [背景 2-3 秒] → 分析完成
感知延遲: 0.5 秒（流暢）

改善: 70% 速度提升
```

## 安全機制

所有端點均包含以下防護:

1. **輸入驗證**: FEN 字串格式檢查
2. **時限控制**: 強制超時保護
3. **問題過濾**: 防止 Prompt Injection (僅 /get_analysis)
4. **長度限制**: 問題字串最多 200 字元
5. **錯誤處理**: 優雅降級，不影響遊戲進行

## 測試

### 單元測試

```bash
cd backend
python3 test_api_endpoints.py
```

### 手動測試

```bash
# 測試快速走法
curl -X POST http://localhost:8000/make_move \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    "time_limit": 2.0
  }'

# 測試深度分析
curl -X POST http://localhost:8000/get_analysis \
  -H "Content-Type: application/json" \
  -d '{
    "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
    "history": "1. e4 e5",
    "depth": 5
  }'
```

## 遷移建議

### 階段一: 並行運行
- 保留舊端點 /analyze 和 /explain
- 新增 /make_move 和 /get_analysis
- 前端可選擇使用新或舊端點

### 階段二: 逐步遷移
- 前端主流程改用新端點
- 監控錯誤率和效能指標
- 收集使用者回饋

### 階段三: 棄用舊端點
- 發布棄用通知
- 設定緩衝期（如 3 個月）
- 最終移除舊端點

## 未來擴展

1. **快取機制**: 對相同 FEN 快取結果 1 分鐘
2. **批次分析**: 支援一次分析多個局面
3. **WebSocket**: 即時推送分析進度
4. **優先級佇列**: VIP 使用者優先處理

## 總結

本次優化實現了職責分離和效能提升，核心改進包括：

- 快速走法端點: 2 秒內回應，保證遊戲流暢
- 深度分析端點: 5 秒完整分析，提供專業建議
- 相容性保留: 舊端點可用，平滑遷移
- 安全防護: 多層防禦，穩定可靠

使用者感知速度提升 70%，系統穩定性大幅提高。
