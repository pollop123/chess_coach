import { useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import axios from "axios";
// 引入圖表套件
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine, ReferenceDot } from 'recharts';

// 自動判斷 API 網址
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

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

      const processedData = res.data.map(d => ({
        ...d,
        displayScore: (d.score_for !== undefined ? d.score_for : d.score)
      }));

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
      const response = await axios.post(`${API_URL}/analyze`, { fen: currentFen, depth: 3 });
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

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      minHeight: "100vh", fontFamily: "Arial, sans-serif", backgroundColor: "#f4f4f4", padding: "20px"
    }}>
      <h1 style={{ color: "#333", marginBottom: "20px" }}>♟️ 我的西洋棋 AI 平台</h1>

      <div style={{ display: "flex", gap: "30px", alignItems: "flex-start", flexWrap: "wrap", justifyContent: "center" }}>

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
                style={{ ...buttonStyle("white"), color: "#722ed1", padding: "5px 10px", fontSize: "0.8rem" }}
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
              backgroundColor: "white", padding: "10px", borderRadius: "10px", boxShadow: "0 2px 10px rgba(0,0,0,0.1)",
              height: "200px"
            }}>
              <h4 style={{ margin: "0 0 10px 0", color: "#666", textAlign: "center" }}>📊 局勢走勢</h4>
              <ResponsiveContainer width="100%" height="85%">
                <LineChart data={analysisData} onClick={(e) => { if (e && e.activePayload) setCurrentMoveIndex(e.activePayload[0].payload.move_number); }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="move_number" hide />
                  <YAxis hide domain={['auto', 'auto']} />
                  <Tooltip />
                  <ReferenceLine y={0} stroke="red" strokeDasharray="3 3" />
                  <Line type="monotone" dataKey="displayScore" stroke="#8884d8" dot={false} strokeWidth={2} />
                  {currentMoveIndex !== -1 && analysisData[currentMoveIndex] && (
                    <ReferenceDot x={analysisData[currentMoveIndex].move_number} y={analysisData[currentMoveIndex].displayScore} r={4} fill="red" stroke="none" />
                  )}
                </LineChart>
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