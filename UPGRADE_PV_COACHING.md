# 🎯 教練深度化升級：PV Line 整合

## 📋 改進概述

將引擎計算的 **PV Line (Principal Variation，預測變例)** 深度整合到 RAG 教練系統中，讓 AI 教練能夠針對具體的戰術路徑進行深度講解，而不是泛泛而談。

## ✨ 核心改進

### 1. **RAG 引擎升級** (`backend/rag.py`)

#### 新增參數：
```python
def get_advice(self, fen, move_history, user_question, pv_line=None, pv_score=None):
```

- `pv_line`: 引擎計算的最佳變例序列（UCI 格式列表）
- `pv_score`: 該變例的評分（厘兵單位）

#### 功能增強：
1. **PV Line 自動轉換**
   - 將 UCI 格式 (`e2e4`, `e7e5`) 自動轉換為人類可讀的標準代數記法 (SAN)
   - 例如：`4. Nxe5 Nxe5 5. d4 Bd6` 

2. **深度變例分析提示**
   - AI 教練現在會收到明確指令，要求解釋：
     - ✅ 為什麼這個序列對當前方有利？
     - ✅ 體現了什麼戰術/戰略思想？
     - ✅ 如果對手偏離路線會怎樣？
     - ✅ 關鍵轉折點在哪裡？

3. **防止空話分析**
   - 新增規則：要求 AI 進行具體的交換序列計算
   - 例如：「Nxc7 後，黑方回應 Qxc7，白方損失馬(3分)換得兵(1分)，淨虧2分」

### 2. **API 端點升級** (`backend/api.py`)

#### `/explain` 端點增強：

**新增參數：**
```python
class ExplainRequest(BaseModel):
    fen: str
    history: str = ""
    question: Optional[str] = None
    depth: int = 5  # 新增：引擎分析深度
```

**自動計算流程：**
```python
@app.post("/explain")
def explain_position(request: ExplainRequest):
    # 1. 計算引擎的預測變例
    best_move, score, pv = chess_engine.get_analysis(board, depth=request.depth)
    
    # 2. 將 PV Line 傳遞給 RAG 教練
    advice = rag_engine.get_advice(
        request.fen, 
        request.history, 
        user_question,
        pv_line=pv,      # 🔥 新增
        pv_score=score   # 🔥 新增
    )
```

## 📊 使用範例

### 前端呼叫方式：

```javascript
const response = await fetch('http://localhost:8000/explain', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    fen: 'r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4',
    history: '1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6',
    question: '請評估目前局勢並給出建議',
    depth: 5  // 可選，預設為 5
  })
});

const data = await response.json();
console.log(data.advice);
```

### AI 教練回覆範例：

**之前（泛泛而談）：**
> "現在應該考慮控制中心，建議走 d4 或 O-O。"

**之後（具體路徑分析）：**
> 📊 **引擎推薦變例**：`4. Ng5 d5 5. exd5 Na5 6. Bb5+ c6`
> 
> 🎯 **戰術解析**：
> 1. **Ng5** 施加雙重威脅：攻擊 f7 弱點 + 準備 d4 鞏固中心
> 2. 黑方被迫 **d5** 反擊，否則 Nxf7 形成強烈攻勢
> 3. **exd5** 後白方獲得空間優勢，黑方馬被迫跳到邊緣（Na5）
> 4. 如果黑方不走 Na5，例如走 **Nxd5**，則 **Nxf7** 叉王后，白方大優
> 
> 💡 **心法**：在開局階段，活躍子力的速度比保子更重要，這個變例犧牲中心兵換取主動權。

## 🎓 教學效果提升

### 改進前：
- ❌ AI 只能看到當前盤面，建議往往是通用原則
- ❌ 缺乏具體的變例計算，玩家不知道「為什麼」
- ❌ 容易產生幻覺，推薦不存在的走法

### 改進後：
- ✅ AI 能看到引擎計算的最佳路徑，有明確的分析目標
- ✅ 針對具體的變例進行逐步拆解，教學更有深度
- ✅ 結合合法走法列表 + PV Line，大幅降低幻覺
- ✅ 能解釋「如果對手不這樣走會怎樣」，教導玩家思考對手選項

## 🧪 測試方式

### 本地測試 PV Line 功能：
```bash
cd backend
python3 test_pv.py
```

### 完整系統測試：
```bash
# 啟動 Docker 容器
docker-compose up --build

# 前端測試 (開啟瀏覽器)
# 進入對局後點擊「AI 教練」按鈕
# 觀察回覆是否包含具體的變例分析
```

## 🚀 部署注意事項

1. **引擎計算深度**：
   - `depth=5` 適合實時互動（約 1-3 秒）
   - `depth=7` 適合賽後復盤（約 5-10 秒）
   - 可根據伺服器性能調整

2. **API 額度消耗**：
   - PV Line 會讓 Prompt 變長（約增加 100-200 tokens）
   - 建議搭配 Gemini Flash 系列模型使用

3. **快取優化**（可選）：
   - 可以考慮對相同 FEN + depth 的 PV 結果做快取
   - 減少重複計算，提升回應速度

## 📝 相關檔案

- `backend/rag.py` - RAG 引擎核心邏輯
- `backend/api.py` - API 端點定義
- `backend/chess_engine.py` - 引擎分析功能（已有 `get_analysis`）
- `backend/test_pv.py` - PV Line 測試腳本

## 🎯 未來擴展方向

1. **多變例對比**：
   - 不只分析最佳變例，也分析次佳選擇
   - 讓學生理解「為什麼 A 比 B 好」

2. **戰術圖案識別**：
   - 在 PV Line 中自動標註戰術類型（捉雙、牽制、閃擊等）
   - 幫助學生建立戰術模式庫

3. **互動式變例探索**：
   - 玩家可以問「如果我不走這步會怎樣？」
   - AI 即時計算並對比不同路線

---

## ✅ 總結

這次升級讓 Chess AI 從「會下棋的程式」進化為「真正的教練」。透過 PV Line 整合，AI 不再只是給建議，而是能夠：
- 💬 解釋**為什麼**這步棋好
- 🎯 展示**具體的**變例路徑
- 🧠 教導**戰術思維**而非單純的走法

讓學習西洋棋不再枯燥，每一步都有深度的背後邏輯！🚀
