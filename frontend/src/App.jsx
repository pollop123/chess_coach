import { useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import axios from "axios";
// 引入圖表套件
import { ComposedChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceDot, ReferenceArea, Area, Scatter } from 'recharts';

// 預設走同網域 /api，由 Vite/Nginx 代理到後端；分離部署時可用 VITE_API_URL 覆蓋。
const API_URL = import.meta.env.VITE_API_URL || "/api";

function App() {
  const [game, setGame] = useState(new Chess());
  const [status, setStatus] = useState("歡迎來到西洋棋 AI 平台！");
  const [history, setHistory] = useState([]);

  // --- 新增/修改狀態 ---
  // chatHistory: 儲存對話紀錄 { role: 'user' | 'model', text: string }
  const [chatHistory, setChatHistory] = useState([
    { role: "model", text: "👋 你好！我是你的 AI 教練。按「AI 教練解說」讓我分析盤面，或者在下方直接問我問題！" }
  ]);
  const [userInput, setUserInput] = useState(""); // 玩家輸入的問題
  const [isCoachThinking, setIsCoachThinking] = useState(false); // 教練思考中狀態

  const [analysisData, setAnalysisData] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [humanColor, setHumanColor] = useState("white");

  // 用來自動捲動聊天室
  const chatEndRef = useRef(null);

  // 1. 初始化載入歷史
  useEffect(() => {
    fetchHistory();
  }, []);

  // 聊天室自動捲動到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  async function fetchHistory() {
    try {
      const res = await axios.get(`${API_URL}/games`);
      setHistory(res.data);
    } catch (err) {
      console.error("無法讀取歷史紀錄", err);
    }
  }

  async function saveGameToDB(result) {
    try {
      await axios.post(`${API_URL}/games`, {
        pgn: game.pgn(),
        result: result,
        fen: game.fen()
      });
      fetchHistory();
    } catch (err) {
      console.error("存檔失敗", err);
    }
  }

  function resignGame() {
    if (game.isGameOver()) return;
    setStatus("你投降了！遊戲結束 (0-1)");
    saveGameToDB("0-1");
  }

  function loadGame(pgn) {
    try {
      const newGame = new Chess();
      newGame.loadPgn(pgn);
      setGame(newGame);
      setStatus("已載入歷史賽局 (復盤模式)");
      setAnalysisData([]);
      setCurrentMoveIndex(-1);
      // 載入新局時，重置聊天室，但保留歡迎訊息
      setChatHistory([{ role: "model", text: "已切換賽局，請隨時問我問題！" }]);
    } catch (e) {
      console.error("PGN 載入失敗", e);
    }
  }

  async function analyzeGame() {
    if (game.pgn() === "") return;
    setStatus("📊 正在進行全盤深度分析...");
    try {
      const res = await axios.post(`${API_URL}/analyze_full`, {
        pgn: game.pgn(),
        perspective: humanColor,
        depth: 2
      });

      const processedData = res.data.map(d => {
        const rawScore = d.score ?? 0;
        const playerScore = d.score_for ?? rawScore;
        // 限制分數範圍在圖表內，避免將死分數把點擠到邊界。
        const clampedScore = Math.max(-900, Math.min(900, rawScore));
        return {
          ...d,
          displayScore: clampedScore,
          rawScore: rawScore, // 白方視角，供局勢走勢圖使用
          playerScore: playerScore // 玩家視角，供側邊評估條使用
        };
      });

      setAnalysisData(processedData);
      setStatus("✅ 分析完成！");
    } catch (err) {
      console.error("分析失敗", err);
      setStatus("❌ 分析失敗");
    }
  }

  function navigateMove(direction) {
    if (analysisData.length === 0) return;
    let newIndex = currentMoveIndex;
    if (newIndex === -1) newIndex = analysisData.length - 1;
    newIndex += direction;
    if (newIndex < 0) newIndex = 0;
    if (newIndex >= analysisData.length) newIndex = analysisData.length - 1;
    setCurrentMoveIndex(newIndex);
  }

  const displayFen = (currentMoveIndex !== -1 && analysisData.length > 0)
    ? analysisData[currentMoveIndex].fen
    : game.fen();

  // 🔥 核心修改：發送訊息給 AI 教練
  // manualQuestion: 如果有的話，代表是玩家手動打字；如果沒有，代表是按「分析按鈕」
  async function askCoach(manualQuestion = null) {
    if (isCoachThinking) return;

    // 1. 決定顯示在聊天室的文字
    const questionText = manualQuestion || "請幫我分析目前的盤面局勢與優劣。";

    // 2. 更新聊天室 (顯示玩家訊息)
    setChatHistory(prev => [...prev, { role: "user", text: questionText }]);
    setIsCoachThinking(true);
    setUserInput(""); // 清空輸入框

    try {
      // 3. 呼叫後端
      const res = await axios.post(`${API_URL}/explain`, {
        fen: displayFen, // 針對目前顯示的盤面 (支援復盤)
        history: game.pgn(),
        question: manualQuestion // 如果是 null，後端會用預設 Prompt
      });

      // 4. 顯示教練回應
      setChatHistory(prev => [...prev, { role: "model", text: res.data.advice }]);
    } catch (err) {
      console.error(err);
      setChatHistory(prev => [...prev, { role: "model", text: "❌ 教練連線失敗，請檢查後端 API。" }]);
    } finally {
      setIsCoachThinking(false);
    }
  }

  // 處理按下 Enter 發送
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (userInput.trim()) {
        askCoach(userInput);
      }
    }
  };

  function safeGameMutate(modify) {
    setGame((g) => {
      const update = new Chess();
      update.loadPgn(g.pgn());
      modify(update);
      return update;
    });
  }

  function onDrop(sourceSquare, targetSquare) {
    if (analysisData.length > 0) {
      setStatus("⚠️ 復盤模式下無法移動");
      return false;
    }

    let move = null;
    const tempGame = new Chess();
    tempGame.loadPgn(game.pgn());
    const expectedTurn = humanColor === "white" ? "w" : "b";
    if (tempGame.turn() !== expectedTurn) return false;

    try {
      move = tempGame.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
    } catch (error) { return false; }
    if (move === null) return false;

    safeGameMutate((g) => {
      g.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
    });
    setStatus("AI 思考中...");

    // 玩家走子後，不用自動清空聊天紀錄，保留上下文
    // 但可以加一行分隔線或提示
    // setChatHistory(prev => [...prev, { role: "system", text: "--- 棋局已更新 ---" }]); 

    if (tempGame.isGameOver()) {
      handleGameOver(tempGame);
    } else {
      makeAIMove(tempGame.fen());
    }
    return true;
  }

  function handleGameOver(chessInstance) {
    let result = "Draw";
    if (chessInstance.isCheckmate()) {
      result = chessInstance.turn() === 'w' ? "0-1" : "1-0";
      setStatus(`遊戲結束：${result === "1-0" ? "白勝" : "黑勝"} (Checkmate)`);
    } else if (chessInstance.isDraw()) {
      result = "1/2-1/2";
      setStatus("遊戲結束：和局");
    }
    saveGameToDB(result);
  }

  async function makeAIMove(currentFen) {
    try {
      const response = await axios.post(`${API_URL}/make_move`, { 
        fen: currentFen, 
        time_limit: 1.5
      });
      
      const bestMoveUci = response.data.best_move;
      
      if (bestMoveUci) {
        const from = bestMoveUci.substring(0, 2);
        const to = bestMoveUci.substring(2, 4);
        const promotion = bestMoveUci.length > 4 ? bestMoveUci[4] : undefined;
        safeGameMutate((g) => {
          g.move({ from, to, promotion });
          if (g.isGameOver()) handleGameOver(g);
          else setStatus("輪到你了");
        });
      }
    } catch (error) {
      console.error("Backend Error:", error);
      setStatus("連線錯誤");
    }
  }

  function downloadPGN() {
    const element = document.createElement("a");
    const file = new Blob([game.pgn()], { type: "text/plain" });
    element.href = URL.createObjectURL(file);
    element.download = `chess_game_${new Date().getTime()}.pgn`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  }

  // 勝率條組件
  function EvaluationBar({ winningChance, evalDisplay }) {
    const whiteHeight = winningChance;
    const blackHeight = 100 - winningChance;

    return (
      <div style={{ 
        display: "flex", 
        flexDirection: "column", 
        alignItems: "center",
        width: "40px"
      }}>
        <div style={{
          width: "100%",
          height: "480px",
          backgroundColor: "#ddd",
          borderRadius: "5px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column-reverse",
          position: "relative",
          boxShadow: "0 2px 5px rgba(0,0,0,0.2)"
        }}>
          {/* 白方區域 */}
          <div style={{
            height: `${whiteHeight}%`,
            backgroundColor: "#f0f0f0",
            transition: "height 0.3s ease",
            display: "flex",
            alignItems: "center",
            justifyContent: "center"
          }}>
          </div>
          
          {/* 黑方區域 */}
          <div style={{
            height: `${blackHeight}%`,
            backgroundColor: "#333",
            transition: "height 0.3s ease"
          }}>
          </div>

          {/* 中間線 */}
          <div style={{
            position: "absolute",
            top: "50%",
            left: "0",
            right: "0",
            height: "2px",
            backgroundColor: "#999",
            transform: "translateY(-50%)"
          }}></div>
        </div>

        {/* 評分顯示 */}
        <div style={{
          marginTop: "10px",
          fontSize: "14px",
          fontWeight: "bold",
          color: evalDisplay.startsWith("+") ? "#52c41a" : evalDisplay.startsWith("-") ? "#ff4d4f" : "#666",
          textAlign: "center"
        }}>
          {evalDisplay}
        </div>
        
        <div style={{
          fontSize: "12px",
          color: "#999",
          marginTop: "5px"
        }}>
          {winningChance.toFixed(1)}%
        </div>
      </div>
    );
  }

  function getMoveDotColor(classification) {
    if (classification === "blunder") return "#ef4444";
    if (classification === "mistake") return "#ff7f50";
    if (classification === "inaccuracy") return "#f4a259";
    return null;
  }

  function renderEvalDot({ cx, cy, payload }) {
    const color = getMoveDotColor(payload?.classification);
    if (!payload?.move || !color) return null;
    return (
      <circle
        cx={cx}
        cy={cy}
        r={payload.classification === "blunder" ? 7 : 6}
        fill={color}
        stroke="#ffffff"
        strokeWidth={payload.classification === "blunder" ? 2 : 1}
      />
    );
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", fontFamily: "Arial, sans-serif", backgroundColor: "#f4f4f4", padding: "20px"
    }}>
      <h1 style={{ color: "#333", marginBottom: "20px" }}>♟️ 我的西洋棋 AI 平台</h1>

      <div style={{ display: "flex", gap: "30px", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "center" }}>

        {/* 勝率條 - 只在賽後分析時顯示 */}
        {analysisData.length > 0 && (
          <EvaluationBar 
            winningChance={
              currentMoveIndex >= 0 && analysisData[currentMoveIndex]
                ? (analysisData[currentMoveIndex].playerScore > 0 
                    ? 50 + Math.min(analysisData[currentMoveIndex].playerScore / 50, 50) 
                    : 50 + Math.max(analysisData[currentMoveIndex].playerScore / 50, -50))
                : 50
            }
            evalDisplay={
              currentMoveIndex >= 0 && analysisData[currentMoveIndex]
                ? (analysisData[currentMoveIndex].playerScore > 0 ? "+" : "") + (analysisData[currentMoveIndex].playerScore / 100).toFixed(2)
                : "+0.00"
            }
          />
        )}

        {/* 左側：棋盤區 */}
        <div style={{ width: "480px" }}>
          <div style={{
            height: "480px", marginBottom: "20px",
            boxShadow: "0 4px 10px rgba(0,0,0,0.2)", position: "relative"
          }}>
            <Chessboard position={displayFen} onPieceDrop={onDrop} boardOrientation={humanColor} />

            {/* 導航按鈕 */}
            {analysisData.length > 0 && (
              <div style={{
                position: "absolute", bottom: "-40px", left: "0", width: "100%",
                display: "flex", justifyContent: "center", gap: "10px"
              }}>
                <button onClick={() => navigateMove(-1)} style={navButtonStyle}>⬅️ 上一步</button>
                <span style={{ fontWeight: "bold", alignSelf: "center" }}>{currentMoveIndex === -1 ? "最終局" : `第 ${currentMoveIndex} 步`}</span>
                <button onClick={() => navigateMove(1)} style={navButtonStyle}>下一步 ➡️</button>
              </div>
            )}
          </div>

          <div style={{
            padding: "15px", backgroundColor: "white", borderRadius: "8px",
            marginBottom: "20px", boxShadow: "0 2px 5px rgba(0,0,0,0.1)", fontWeight: "bold", color: "#555", textAlign: "center"
          }}>
            {status}
          </div>

          {/* 控制按鈕 */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center" }}>
            <button onClick={() => { const ng = new Chess(); setGame(ng); setStatus("新局開始"); setAnalysisData([]); setChatHistory([]); if (humanColor === "black") makeAIMove(ng.fen()); }} style={buttonStyle("#ff4d4f")}>🔄 新局</button>
            <button onClick={analyzeGame} style={buttonStyle("#52c41a")}>📈 賽後分析</button>
            <button onClick={downloadPGN} style={buttonStyle("#1890ff")}>📥 PGN</button>
            <div style={{ display: "flex", gap: "2px" }}>
              <button onClick={() => setHumanColor("white")} style={buttonStyle(humanColor === "white" ? "#333" : "#ccc")}>白</button>
              <button onClick={() => setHumanColor("black")} style={buttonStyle(humanColor === "black" ? "#333" : "#ccc")}>黑</button>
            </div>
          </div>
        </div>

        {/* 右側：聊天室 & 分析圖表 */}
        <div style={{ width: "400px", display: "flex", flexDirection: "column", gap: "20px" }}>

          {/* 💬 AI 戰術聊天室 */}
          <div style={{
            backgroundColor: "white", borderRadius: "10px", boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
            display: "flex", flexDirection: "column", height: "500px", overflow: "hidden"
          }}>
            <div style={{ padding: "15px", backgroundColor: "#722ed1", color: "white", fontWeight: "bold", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>🤖 AI 戰術教練</span>
              <button
                onClick={() => askCoach()}
                disabled={isCoachThinking}
                style={{ ...buttonStyle("#ffffff"), color: "#4c1d95", padding: "5px 10px", fontSize: "0.8rem", border: "1px solid rgba(255,255,255,0.65)" }}
              >
                ⚡ 一鍵分析
              </button>
            </div>

            {/* 訊息列表 */}
            <div style={{ flex: 1, padding: "15px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px", backgroundColor: "#f9f9f9" }}>
              {chatHistory.map((msg, idx) => (
                <div key={idx} style={{
                  alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                  backgroundColor: msg.role === "user" ? "#722ed1" : "white",
                  color: msg.role === "user" ? "white" : "#333",
                  padding: "10px 14px",
                  borderRadius: "12px",
                  maxWidth: "85%",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                  whiteSpace: "pre-line", // 支援換行
                  fontSize: "0.95rem",
                  borderBottomRightRadius: msg.role === "user" ? "2px" : "12px",
                  borderTopLeftRadius: msg.role === "model" ? "2px" : "12px"
                }}>
                  {msg.text}
                </div>
              ))}
              {isCoachThinking && (
                <div style={{ alignSelf: "flex-start", color: "#888", fontSize: "0.8rem", paddingLeft: "10px" }}>
                  教練正在思考... 💭
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* 輸入框 */}
            <div style={{ padding: "10px", borderTop: "1px solid #eee", display: "flex", gap: "5px", backgroundColor: "white" }}>
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="問教練問題 (例如：為什麼這步不好？)"
                disabled={isCoachThinking}
                style={{ flex: 1, padding: "10px", borderRadius: "20px", border: "1px solid #ddd", outline: "none" }}
              />
              <button
                onClick={() => { if (userInput.trim()) askCoach(userInput); }}
                disabled={isCoachThinking || !userInput.trim()}
                style={{ ...buttonStyle("#722ed1"), borderRadius: "50%", width: "40px", height: "40px", padding: 0, display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                ➤
              </button>
            </div>
          </div>

          {/* 📊 分析圖表 (如果有數據) */}
          {analysisData.length > 0 && (
            <div style={{
              backgroundColor: "#f7f6f3",
              borderRadius: "8px",
              boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
              height: "170px",
              overflow: "hidden",
              border: "1px solid #e6e1dc"
            }}>
              <div style={{
                height: "28px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0 12px",
                color: "#282622",
                fontSize: "0.78rem",
                fontWeight: 700
              }}>
                <span>局勢走勢（白方視角）</span>
                <span style={{ color: "#5f5a52", fontWeight: 600 }}>0 線</span>
              </div>
              <ResponsiveContainer width="100%" height={142}>
                <ComposedChart
                  data={analysisData}
                  margin={{ top: 8, right: 10, bottom: 8, left: 10 }}
                  onClick={(e) => { if (e && e.activePayload) setCurrentMoveIndex(e.activePayload[0].payload.move_number); }}
                >
                  <defs>
                    <linearGradient id="blackAdvantageArea" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#33312d" stopOpacity={1}/>
                      <stop offset="100%" stopColor="#4a4741" stopOpacity={0.96}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="move_number" hide />
                  <YAxis hide domain={[-1000, 1000]} />
                  <Tooltip 
                    cursor={{ stroke: "#8f8a83", strokeWidth: 1 }}
                    contentStyle={{
                      backgroundColor: "#ffffff",
                      border: "1px solid #cfc8bf",
                      borderRadius: "6px",
                      boxShadow: "0 6px 18px rgba(0,0,0,0.12)"
                    }}
                    labelFormatter={(label) => `第 ${label} 步`}
                    formatter={(value, name, item) => {
                      const score = item?.payload?.rawScore ?? value;
                      return [(score / 100).toFixed(2), "白方評分"];
                    }}
                  />
                  
                  <ReferenceArea y1={-1000} y2={1000} fill="#3a3833" fillOpacity={1} />

                  {/* 中線 (0分線) */}
                  <ReferenceLine y={0} stroke="#beb9b1" strokeWidth={3} />
                  
                  <Area 
                    type="monotone" 
                    dataKey="displayScore" 
                    baseValue={-1000}
                    stroke="#f7f6f3"
                    strokeWidth={5}
                    fill="#f7f6f3"
                    fillOpacity={1}
                    isAnimationActive={false}
                  />
                  
                  <Line 
                    type="monotone" 
                    dataKey="displayScore" 
                    stroke="#f7f6f3"
                    dot={false} 
                    strokeWidth={5}
                    isAnimationActive={false}
                    activeDot={{ r: 7, fill: "#ffffff", stroke: "#4a4741", strokeWidth: 2 }}
                  />

                  <Scatter
                    data={analysisData.filter((d) => d.move && d.classification !== "good")}
                    dataKey="displayScore"
                    shape={renderEvalDot}
                    isAnimationActive={false}
                  />
                  
                  {/* 當前位置標記 */}
                  {currentMoveIndex !== -1 && analysisData[currentMoveIndex] && (
                    <ReferenceDot 
                      x={analysisData[currentMoveIndex].move_number} 
                      y={analysisData[currentMoveIndex].displayScore} 
                      r={8} 
                      fill="transparent" 
                      stroke="#ffffff"
                      strokeWidth={3}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 📜 歷史戰績 (修正版) */}
          <div style={{
            width: "100%", maxWidth: "600px", backgroundColor: "white",
            borderRadius: "10px", padding: "20px", boxShadow: "0 2px 10px rgba(0,0,0,0.1)"
          }}>
            <h3 style={{ borderBottom: "2px solid #eee", paddingBottom: "10px", marginTop: 0, color: "#333" }}>
              📜 歷史戰績
            </h3>
            {history.length === 0 ? (
              <p style={{ textAlign: "center", color: "#999" }}>尚無紀錄</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, maxHeight: "200px", overflowY: "auto" }}>
                {history.map((h) => (
                  <li key={h.id} onClick={() => loadGame(h.pgn)}
                    style={{
                      borderBottom: "1px solid #eee",
                      padding: "10px",
                      cursor: "pointer",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      color: "#333" // 🔥 強制設定文字顏色為深灰，防止變成白色
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = "#f9f9f9"}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = "transparent"}
                  >
                    <div style={{ display: "flex", flexDirection: "column" }}>
                      {/* 🔥 確保 ID 和 日期 都有顏色，並且處理日期格式 */}
                      <span style={{ fontWeight: "bold", fontSize: "0.95rem", color: "#333" }}>
                        #{h.id ? h.id : "?"}
                      </span>
                      <span style={{ fontSize: "0.85rem", color: "#888" }}>
                        {h.date ? new Date(h.date).toLocaleString("zh-TW") : "無日期"}
                      </span>
                    </div>

                    <span style={{
                      color: h.result === "1-0" ? "green" : (h.result === "0-1" ? "red" : "#faad14"),
                      fontWeight: "bold",
                      backgroundColor: "#f0f0f0",
                      padding: "4px 8px",
                      borderRadius: "4px",
                      minWidth: "40px",
                      textAlign: "center"
                    }}>
                      {h.result}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}

// 通用按鈕樣式
function buttonStyle(bgColor) {
  return {
    padding: "8px 12px", cursor: "pointer", backgroundColor: bgColor, color: "white",
    border: "none", borderRadius: "6px", fontSize: "0.9rem", fontWeight: "bold", transition: "all 0.2s"
  };
}

const navButtonStyle = {
  padding: "4px 10px", cursor: "pointer", backgroundColor: "#555", color: "white",
  border: "none", borderRadius: "4px", fontSize: "0.8rem"
};

export default App;
