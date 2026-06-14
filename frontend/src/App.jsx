import { useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import axios from "axios";
// 引入圖表套件
import { ComposedChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, ReferenceDot, ReferenceArea, Area, Scatter } from 'recharts';

// 預設走同網域 /api，由 Vite/Nginx 代理到後端；分離部署時可用 VITE_API_URL 覆蓋。
const API_URL = import.meta.env.VITE_API_URL || "/api";

const BOT_DIFFICULTIES = [
  { id: "newbie", label: "新手", description: "不用開局庫，低深度" },
  { id: "beginner", label: "初階", description: "基本合理，仍會漏招" },
  { id: "intermediate", label: "中階", description: "穩定陪練" },
  { id: "advanced", label: "中階加強", description: "開局與殘局更完整，但不是高階引擎" }
];

const BOT_STYLES = [
  { id: "balanced", label: "穩健", description: "優先選客觀穩定的走法" },
  { id: "trickster", label: "陷阱", description: "偏好將軍、攻王與壓縮回應，用來練防守警覺" }
];

const TRAINING_PHASES = [
  { id: "opening", label: "開局" },
  { id: "middlegame", label: "中局" },
  { id: "endgame", label: "殘局" }
];

const TRAINING_LESSONS = [
  {
    id: "italian-giuoco-piano",
    phase: "opening",
    opening: "義大利開局",
    variation: "Giuoco Piano",
    goal: "快速發展子力，主教瞄準 f7，穩定完成短易位。",
    moves: ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d3", "d6", "O-O"],
    ideas: [
      "e4 先占中心，打開后與主教的路線。",
      "Nf3 發展騎士並攻擊 e5 兵，是義大利開局的核心節奏。",
      "Bc4 瞄準 f7 弱點，同時完成王翼子力發展。",
      "c3 支援後續 d4，也讓白方保留穩健中心。",
      "O-O 把國王帶到安全位置，接著才談中局計畫。"
    ]
  },
  {
    id: "italian-two-knights",
    phase: "opening",
    opening: "義大利開局",
    variation: "Two Knights Defense",
    goal: "面對 ...Nf6 時保持中心壓力，理解黑方反擊 e4 的節奏。",
    moves: ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "d3", "Bc5", "c3", "d6", "O-O"],
    ideas: [
      "黑方 ...Nf6 直接攻擊 e4，白方要注意中心兵的保護。",
      "d3 是穩健選擇，先保住 e4 並準備短易位。",
      "c3 讓白方之後有 d4 的中心突破想法。",
      "不要急著連續移動同一隻棋子，先完成發展比較重要。"
    ]
  },
  {
    id: "italian-evans-gambit",
    phase: "opening",
    opening: "義大利開局",
    variation: "Evans Gambit",
    goal: "用 b4 犧牲側翼兵搶節奏，換取中心與子力活動。",
    moves: ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4", "Bxb4", "c3", "Ba5", "d4"],
    ideas: [
      "b4 是 Evans Gambit 的關鍵，目標是趕走黑方主教。",
      "白方犧牲 b 兵換取 c3、d4 的中心推進速度。",
      "這條線比較進攻型，適合練習用節奏補償物質。",
      "如果沒有跟上 c3、d4，棄兵就容易只剩虧損。"
    ]
  },
  {
    id: "middlegame-scholar-mate",
    phase: "middlegame",
    opening: "中局戰術",
    variation: "弱點攻擊：f7 將殺",
    goal: "辨識王旁弱點，抓住對方防守不足時的直接將殺。",
    startFen: "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
    moves: ["Qxf7#"],
    ideas: [
      "f7 是黑方開局最脆弱的點，通常只有國王保護。",
      "當后與主教同時瞄準 f7，對方又沒完成防守時，要先檢查是否有將殺。",
      "中局戰術題先找王的安全，再找強迫手：將軍、吃子、威脅。"
    ]
  },
  {
    id: "middlegame-center-pressure",
    phase: "middlegame",
    opening: "中局判斷",
    variation: "中心壓力：發展后支援攻擊",
    goal: "在戰術還沒直接成立時，找能增加壓力又不丟子的發展手。",
    startFen: "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
    moves: ["Qf3"],
    ideas: [
      "Qf3 支援 f7 壓力，也連結騎士與主教的攻擊方向。",
      "中局不一定每步都是將殺；有時候好棋是把更多子力帶進同一個目標。",
      "如果攻擊還沒成熟，不要只靠一隻棋子衝進去。"
    ]
  },
  {
    id: "endgame-queen-mate-net",
    phase: "endgame",
    opening: "殘局訓練",
    variation: "后王配合：縮小國王空間",
    goal: "用國王支援后的控制，讓對方國王沒有逃生格。",
    startFen: "7k/6Q1/5K2/8/8/8/8/8 w - - 0 1",
    moves: ["Kf7#"],
    ideas: [
      "后很強，但殘局將殺通常需要國王一起控制逃生格。",
      "Kf7# 不是單純追王，而是用國王封住黑王周圍格子。",
      "后王殺王的核心是縮小空間，不是一直無目的將軍。"
    ]
  },
  {
    id: "endgame-pawn-promotion",
    phase: "endgame",
    opening: "殘局訓練",
    variation: "通路兵升變",
    goal: "辨識能直接升變的通路兵，優先把優勢轉成后。",
    startFen: "8/4P3/4K3/8/8/8/8/4k3 w - - 0 1",
    moves: ["e8=Q"],
    ideas: [
      "通路兵到第七排時，升變通常比其他慢手更重要。",
      "升變成后能把兵的優勢轉成決定性火力。",
      "殘局先算升變格是否安全，再決定王要不要支援。"
    ]
  }
];

function App() {
  const [game, setGame] = useState(new Chess());
  const [appMode, setAppMode] = useState("play");
  const [trainingPhase, setTrainingPhase] = useState("opening");
  const [trainingGame, setTrainingGame] = useState(() => createTrainingGame(TRAINING_LESSONS[0]));
  const [selectedLessonId, setSelectedLessonId] = useState(TRAINING_LESSONS[0].id);
  const [trainingFeedback, setTrainingFeedback] = useState({
    tone: "neutral",
    text: "選擇一條變體，照棋盤提示走白方主線。黑方會自動走出該變體的回應。"
  });
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [status, setStatus] = useState("準備開始新棋局");
  const [isResigned, setIsResigned] = useState(false);
  const [history, setHistory] = useState([]);

  // --- 新增/修改狀態 ---
  // chatHistory: 儲存對話紀錄 { role: 'user' | 'model', text: string }
  const [chatHistory, setChatHistory] = useState([
    { role: "model", text: "我是你的 AI 教練。你可以讓我分析目前盤面，或直接提出局面問題。" }
  ]);
  const [userInput, setUserInput] = useState(""); // 玩家輸入的問題
  const [isCoachThinking, setIsCoachThinking] = useState(false); // 教練思考中狀態

  const [analysisData, setAnalysisData] = useState([]);
  const [currentMoveIndex, setCurrentMoveIndex] = useState(-1);
  const [humanColor, setHumanColor] = useState("white");
  const [botDifficulty, setBotDifficulty] = useState("intermediate");
  const [botStyle, setBotStyle] = useState("balanced");

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
    if (appMode !== "play" || game.isGameOver() || isResigned || analysisData.length > 0) return;
    const result = humanColor === "white" ? "0-1" : "1-0";
    setIsResigned(true);
    setStatus(`你已投降，遊戲結束：${result === "1-0" ? "白勝" : "黑勝"}`);
    saveGameToDB(result);
  }

  function loadGame(pgn) {
    try {
      const newGame = new Chess();
      newGame.loadPgn(pgn);
      setGame(newGame);
      setStatus("已載入歷史賽局 (復盤模式)");
      setAnalysisData([]);
      setCurrentMoveIndex(-1);
      setIsResigned(false);
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
        const isMate = d.is_checkmate || d.mate_threat || Math.abs(rawScore) > 15000;
        // 將死局面必須貼到圖表頂端/底端，一般局面才以 centipawn 截斷。
        const chartScore = isMate
          ? (rawScore >= 0 ? 1000 : -1000)
          : Math.max(-900, Math.min(900, rawScore));
        return {
          ...d,
          displayScore: chartScore,
          rawScore: rawScore, // 白方視角，供局勢走勢圖使用
          playerScore: playerScore, // 玩家視角，供側邊評估條使用
          evalLabel: formatChartScore(rawScore, isMate)
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
  const phaseLessons = TRAINING_LESSONS.filter((lesson) => lesson.phase === trainingPhase);
  const selectedLesson = TRAINING_LESSONS.find((lesson) => lesson.id === selectedLessonId) || phaseLessons[0] || TRAINING_LESSONS[0];
  const trainingHistory = trainingGame.history();
  const expectedTrainingMove = selectedLesson.moves[trainingHistory.length];
  const trainingComplete = trainingHistory.length >= selectedLesson.moves.length;
  const boardFen = appMode === "training" ? trainingGame.fen() : displayFen;
  const boardOrientation = appMode === "training" ? "white" : humanColor;
  const selectedDifficulty = BOT_DIFFICULTIES.find((difficulty) => difficulty.id === botDifficulty) || BOT_DIFFICULTIES[2];
  const selectedStyle = BOT_STYLES.find((style) => style.id === botStyle) || BOT_STYLES[0];

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

  function cloneChess(chessInstance) {
    const update = new Chess();
    const pgn = chessInstance.pgn();
    if (pgn) update.loadPgn(pgn);
    return update;
  }

  function createTrainingGame(lesson) {
    return lesson?.startFen ? new Chess(lesson.startFen) : new Chess();
  }

  function resetTraining(nextLessonId = selectedLessonId) {
    const lesson = TRAINING_LESSONS.find((item) => item.id === nextLessonId) || TRAINING_LESSONS[0];
    setTrainingPhase(lesson.phase);
    setSelectedLessonId(lesson.id);
    setTrainingGame(createTrainingGame(lesson));
    setSelectedSquare(null);
    setTrainingFeedback({
      tone: "neutral",
      text: `${lesson.opening}：${lesson.variation}。先走 ${lesson.moves[0]}，目標是：${lesson.goal}`
    });
  }

  function selectTrainingPhase(nextPhase) {
    const firstLesson = TRAINING_LESSONS.find((lesson) => lesson.phase === nextPhase) || TRAINING_LESSONS[0];
    resetTraining(firstLesson.id);
  }

  function playTrainingMove(sourceSquare, targetSquare) {
    if (trainingComplete) {
      setTrainingFeedback({ tone: "neutral", text: "這條變體已完成。可以重練，或切換其他變體。" });
      return false;
    }
    if (trainingGame.turn() !== "w") return false;

    const nextGame = cloneChess(trainingGame);
    let move = null;
    try {
      move = nextGame.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
    } catch {
      return false;
    }
    if (!move) return false;

    const expectedMove = selectedLesson.moves[trainingHistory.length];
    if (move.san !== expectedMove) {
      setTrainingFeedback({
        tone: "warn",
        text: `這步 ${move.san} 是合法棋，但本變體這裡要練的是 ${expectedMove}。先照主線走，重點是建立「中心、出子、保王」的節奏。`
      });
      return false;
    }

    const ideaIndex = Math.min(Math.floor(trainingHistory.length / 2), selectedLesson.ideas.length - 1);
    const reply = selectedLesson.moves[nextGame.history().length];
    if (reply) {
      try {
        nextGame.move(reply);
      } catch {
        setTrainingFeedback({
          tone: "warn",
          text: `主線資料在 ${reply} 這步無法套用，請檢查變體設定。`
        });
        return true;
      }
    }

    const remaining = selectedLesson.moves.length - nextGame.history().length;
    setTrainingGame(nextGame);
    setTrainingFeedback({
      tone: remaining <= 0 ? "success" : "success",
      text: remaining <= 0
        ? `完成 ${selectedLesson.variation}。重點：${selectedLesson.goal}`
        : `正確：${move.san}。${selectedLesson.ideas[ideaIndex]} 下一步白方要找 ${selectedLesson.moves[nextGame.history().length]}。`
    });
    return true;
  }

  function onDrop(sourceSquare, targetSquare) {
    setSelectedSquare(null);
    if (appMode === "training") {
      return playTrainingMove(sourceSquare, targetSquare);
    }

    if (isResigned) return false;

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
    } catch { return false; }
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

  function handleSquareClick(square) {
    if ((analysisData.length > 0 || isResigned) && appMode === "play") return;

    if (!selectedSquare) {
      const activeGame = appMode === "training" ? trainingGame : game;
      const piece = activeGame.get(square);
      if (!piece) return;
      if (appMode === "training" && piece.color !== "w") return;
      if (appMode === "play" && piece.color !== (humanColor === "white" ? "w" : "b")) return;
      setSelectedSquare(square);
      return;
    }

    if (selectedSquare === square) {
      setSelectedSquare(null);
      return;
    }

    const moved = onDrop(selectedSquare, square);
    if (!moved) {
      const activeGame = appMode === "training" ? trainingGame : game;
      const piece = activeGame.get(square);
      if (piece && (appMode === "training" ? piece.color === "w" : piece.color === (humanColor === "white" ? "w" : "b"))) {
        setSelectedSquare(square);
      } else {
        setSelectedSquare(null);
      }
    }
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
        time_limit: 1.5,
        difficulty: botDifficulty,
        bot_style: botStyle
      });
      
      const bestMoveUci = response.data.best_move;
      
      if (bestMoveUci) {
        const from = bestMoveUci.substring(0, 2);
        const to = bestMoveUci.substring(2, 4);
        const promotion = bestMoveUci.length > 4 ? bestMoveUci[4] : undefined;
        safeGameMutate((g) => {
          g.move({ from, to, promotion });
          if (g.isGameOver()) handleGameOver(g);
          else if (response.data.bot_style === "trickster" && response.data.style_bonus > 0) {
            setStatus(`輪到你了。陷阱型 AI 剛製造了威脅，先檢查將軍、吃子和被攻擊的子。`);
          } else {
            setStatus(`輪到你了（${response.data.difficulty_label || selectedDifficulty.label}／${selectedStyle.label}）`);
          }
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

  function formatChartScore(score, isMate = Math.abs(score) > 15000) {
    if (isMate) {
      return score >= 0 ? "白方將死勝勢" : "黑方將死勝勢";
    }
    return `白方評分：${(score / 100).toFixed(2)}`;
  }

  function renderEvalTooltip({ active, payload, label }) {
    if (!active || !payload || payload.length === 0) return null;
    const point = payload[0].payload;
    return (
      <div style={{
        backgroundColor: "rgba(255,255,255,0.96)",
        border: "1px solid #cfc8bf",
        borderRadius: "6px",
        boxShadow: "0 8px 20px rgba(0,0,0,0.16)",
        color: "#111827",
        padding: "7px 9px",
        fontSize: "0.78rem",
        lineHeight: 1.35,
        minWidth: "112px"
      }}>
        <div style={{ color: "#6b6258", fontWeight: 700 }}>第 {label} 步</div>
        <div style={{ fontWeight: 800 }}>{point.evalLabel}</div>
      </div>
    );
  }

  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      minHeight: "100vh",
      fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      background: "linear-gradient(180deg, #eef0ed 0%, #f8f6f1 46%, #ebe7de 100%)",
      padding: "28px 20px",
      color: "#1f2933"
    }}>
      <header style={{
        width: "100%",
        maxWidth: "980px",
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: "18px",
        marginBottom: "22px"
      }}>
        <div>
          <div style={{
            color: "#6b5d43",
            fontSize: "0.76rem",
            fontWeight: 800,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            marginBottom: "4px"
          }}>
            棋局分析工作台
          </div>
          <h1 style={{
            color: "#111827",
            margin: 0,
            fontSize: "2.1rem",
            lineHeight: 1.05,
            fontWeight: 850,
            letterSpacing: 0
          }}>
            Chess Coach AI
          </h1>
        </div>
        <div style={{
          padding: "8px 12px",
          borderRadius: "999px",
          backgroundColor: "rgba(17,24,39,0.08)",
          color: "#374151",
          fontSize: "0.85rem",
          fontWeight: 700,
          border: "1px solid rgba(17,24,39,0.10)"
        }}>
          訪客模式
        </div>
      </header>

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
            marginBottom: "18px"
          }}>
            <div style={{
            height: "480px",
            boxShadow: "0 18px 42px rgba(17,24,39,0.18)",
            position: "relative",
            border: "1px solid rgba(17,24,39,0.12)"
          }}>
            <Chessboard
              position={boardFen}
              onPieceDrop={onDrop}
              onSquareClick={handleSquareClick}
              boardOrientation={boardOrientation}
              customSquareStyles={selectedSquare ? {
                [selectedSquare]: { boxShadow: "inset 0 0 0 4px rgba(47,111,78,0.85)" }
              } : {}}
            />
            </div>

            {/* 導航按鈕 */}
            {analysisData.length > 0 && (
              <div style={{
                minHeight: "38px",
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                gap: "10px",
                marginTop: "10px"
              }}>
                <button onClick={() => navigateMove(-1)} style={navButtonStyle}>上一步</button>
                <span style={{ fontWeight: 800, alignSelf: "center", color: "#374151", minWidth: "68px", textAlign: "center" }}>{currentMoveIndex === -1 ? "最終局" : `第 ${currentMoveIndex} 步`}</span>
                <button onClick={() => navigateMove(1)} style={navButtonStyle}>下一步</button>
              </div>
            )}
          </div>

          <div style={{
            padding: "14px 16px",
            backgroundColor: "#ffffff",
            borderRadius: "8px",
            marginBottom: "18px",
            boxShadow: "0 8px 24px rgba(17,24,39,0.08)",
            fontWeight: 750,
            color: "#374151",
            textAlign: "center",
            border: "1px solid #e5e0d8"
          }}>
            {appMode === "training" ? "訓練模式：照提示走白方，黑方會自動回應" : status}
          </div>

          {/* 控制按鈕 */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center" }}>
            <button onClick={() => setAppMode("play")} style={buttonStyle(appMode === "play" ? "#111827" : "#9ca3af")}>對局</button>
            <button onClick={() => { setAppMode("training"); resetTraining(selectedLessonId); }} style={buttonStyle(appMode === "training" ? "#2f6f4e" : "#9ca3af")}>訓練模式</button>
            <button onClick={() => { const ng = new Chess(); setGame(ng); setStatus("新局開始"); setAnalysisData([]); setCurrentMoveIndex(-1); setIsResigned(false); setChatHistory([]); if (humanColor === "black") makeAIMove(ng.fen()); }} style={buttonStyle("#111827")}>新局</button>
            {appMode === "play" && (
              <button
                onClick={resignGame}
                disabled={game.isGameOver() || isResigned || analysisData.length > 0}
                style={buttonStyle(game.isGameOver() || isResigned || analysisData.length > 0 ? "#c7c2b9" : "#9f3a38")}
              >
                投降
              </button>
            )}
            <button onClick={analyzeGame} style={buttonStyle("#2f6f4e")}>賽後分析</button>
            <button onClick={downloadPGN} style={buttonStyle("#6b5d43")}>匯出 PGN</button>
            <div style={{ display: "flex", gap: "2px" }}>
              <button onClick={() => setHumanColor("white")} style={buttonStyle(humanColor === "white" ? "#333" : "#ccc")}>白</button>
              <button onClick={() => setHumanColor("black")} style={buttonStyle(humanColor === "black" ? "#333" : "#ccc")}>黑</button>
            </div>
          </div>

          {appMode === "play" && (
            <div style={{
              marginTop: "10px",
              padding: "10px",
              borderRadius: "8px",
              backgroundColor: "#ffffff",
              border: "1px solid #e5e0d8",
              boxShadow: "0 8px 24px rgba(17,24,39,0.06)"
            }}>
              <div style={{ fontSize: "0.78rem", color: "#6b6258", fontWeight: 800, marginBottom: "7px" }}>
                機器人難度
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "6px" }}>
                {BOT_DIFFICULTIES.map((difficulty) => (
                  <button
                    key={difficulty.id}
                    onClick={() => setBotDifficulty(difficulty.id)}
                    disabled={game.history().length > 0 || isResigned || analysisData.length > 0}
                    title={difficulty.description}
                    style={{
                      ...buttonStyle(botDifficulty === difficulty.id ? "#2f6f4e" : "#e5e0d8"),
                      color: botDifficulty === difficulty.id ? "#ffffff" : "#374151",
                      padding: "7px 6px",
                      fontSize: "0.78rem"
                    }}
                  >
                    {difficulty.label}
                  </button>
                ))}
              </div>
              <div style={{ color: "#6b6258", fontSize: "0.76rem", lineHeight: 1.45, marginTop: "6px" }}>
                {selectedDifficulty.description}
              </div>
              <div style={{ fontSize: "0.78rem", color: "#6b6258", fontWeight: 800, margin: "10px 0 7px" }}>
                機器人風格
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "6px" }}>
                {BOT_STYLES.map((style) => (
                  <button
                    key={style.id}
                    onClick={() => setBotStyle(style.id)}
                    disabled={game.history().length > 0 || isResigned || analysisData.length > 0}
                    title={style.description}
                    style={{
                      ...buttonStyle(botStyle === style.id ? "#6b5d43" : "#e5e0d8"),
                      color: botStyle === style.id ? "#ffffff" : "#374151",
                      padding: "7px 6px",
                      fontSize: "0.78rem"
                    }}
                  >
                    {style.label}
                  </button>
                ))}
              </div>
              <div style={{ color: "#6b6258", fontSize: "0.76rem", lineHeight: 1.45, marginTop: "6px" }}>
                {selectedStyle.description}
              </div>
            </div>
          )}
        </div>

        {/* 右側：聊天室 & 分析圖表 */}
        <div style={{ width: "400px", display: "flex", flexDirection: "column", gap: "20px" }}>

          {appMode === "training" ? (
            <OpeningTrainingPanel
              phases={TRAINING_PHASES}
              trainingPhase={trainingPhase}
              onSelectPhase={selectTrainingPhase}
              lessons={phaseLessons}
              selectedLesson={selectedLesson}
              selectedLessonId={selectedLessonId}
              onSelectLesson={resetTraining}
              feedback={trainingFeedback}
              history={trainingHistory}
              expectedMove={expectedTrainingMove}
              complete={trainingComplete}
              onReset={() => resetTraining(selectedLessonId)}
            />
          ) : (
          <>
            {/* 💬 AI 戰術聊天室 */}
            <div style={{
            backgroundColor: "#ffffff",
            borderRadius: "8px",
            boxShadow: "0 16px 38px rgba(17,24,39,0.10)",
            display: "flex", flexDirection: "column", height: "500px", overflow: "hidden"
          }}>
            <div style={{ padding: "14px 16px", backgroundColor: "#111827", color: "#f8f5ee", fontWeight: "bold", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span>AI 教練</span>
              <button
                onClick={() => askCoach()}
                disabled={isCoachThinking}
                style={{ ...buttonStyle("#f8f5ee"), color: "#111827", padding: "5px 10px", fontSize: "0.8rem", border: "1px solid rgba(255,255,255,0.65)" }}
              >
                分析目前局面
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
                  教練正在思考...
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
                style={{ ...buttonStyle("#111827"), borderRadius: "50%", width: "40px", height: "40px", padding: 0, display: "flex", alignItems: "center", justifyContent: "center" }}
              >
                ➤
              </button>
            </div>
          </div>
          </>
          )}

          {/* 📊 分析圖表 (如果有數據) */}
          {appMode === "play" && analysisData.length > 0 && (
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
                    content={renderEvalTooltip}
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

          {/* 歷史戰績 */}
          {appMode === "play" && (
          <div style={{
            width: "100%",
            maxWidth: "600px",
            backgroundColor: "#ffffff",
            borderRadius: "8px",
            padding: "18px",
            boxShadow: "0 12px 30px rgba(17,24,39,0.08)",
            border: "1px solid #e5e0d8"
          }}>
            <h3 style={{ borderBottom: "2px solid #eee", paddingBottom: "10px", marginTop: 0, color: "#333" }}>
              最近棋局
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
          )}

        </div>
      </div>
    </div>
  );
}

function OpeningTrainingPanel({
  phases,
  trainingPhase,
  onSelectPhase,
  lessons,
  selectedLesson,
  selectedLessonId,
  onSelectLesson,
  feedback,
  history,
  expectedMove,
  complete,
  onReset
}) {
  const progress = Math.round((history.length / selectedLesson.moves.length) * 100);
  const feedbackColor = feedback.tone === "success" ? "#2f6f4e" : feedback.tone === "warn" ? "#a15c18" : "#374151";
  const feedbackBg = feedback.tone === "success" ? "#edf7f0" : feedback.tone === "warn" ? "#fff4e6" : "#f5f6f4";

  return (
    <div style={{
      backgroundColor: "#ffffff",
      borderRadius: "8px",
      boxShadow: "0 16px 38px rgba(17,24,39,0.10)",
      border: "1px solid #e5e0d8",
      overflow: "hidden"
    }}>
      <div style={{ padding: "16px", backgroundColor: "#111827", color: "#f8f5ee" }}>
        <div style={{ fontSize: "0.82rem", opacity: 0.78, fontWeight: 750 }}>訓練模式</div>
        <div style={{ fontSize: "1.2rem", fontWeight: 850, marginTop: "2px" }}>{selectedLesson.opening}</div>
        <div style={{ fontSize: "0.88rem", opacity: 0.88 }}>{selectedLesson.variation}</div>
      </div>

      <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "14px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px" }}>
          {phases.map((phase) => (
            <button
              key={phase.id}
              onClick={() => onSelectPhase(phase.id)}
              style={{
                ...buttonStyle(trainingPhase === phase.id ? "#2f6f4e" : "#e5e0d8"),
                color: trainingPhase === phase.id ? "#ffffff" : "#374151",
                padding: "7px 8px"
              }}
            >
              {phase.label}
            </button>
          ))}
        </div>

        <div>
          <label style={{ display: "block", fontSize: "0.78rem", color: "#6b6258", fontWeight: 800, marginBottom: "6px" }}>
            選擇題目
          </label>
          <select
            value={selectedLessonId}
            onChange={(event) => onSelectLesson(event.target.value)}
            style={{
              width: "100%",
              border: "1px solid #d8d2c8",
              borderRadius: "6px",
              padding: "9px 10px",
              color: "#1f2933",
              backgroundColor: "#fff",
              fontWeight: 700
            }}
          >
            {lessons.map((lesson) => (
              <option key={lesson.id} value={lesson.id}>
                {lesson.variation}
              </option>
            ))}
          </select>
        </div>

        <div style={{
          padding: "12px",
          borderRadius: "8px",
          backgroundColor: "#f7f6f3",
          border: "1px solid #e5e0d8"
        }}>
          <div style={{ fontSize: "0.78rem", color: "#6b6258", fontWeight: 800, marginBottom: "4px" }}>本變體目標</div>
          <div style={{ color: "#263238", fontWeight: 650, lineHeight: 1.45 }}>{selectedLesson.goal}</div>
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "10px"
        }}>
          <div style={trainingMetricStyle}>
            <span style={metricLabelStyle}>下一步白方</span>
            <strong>{complete ? "完成" : expectedMove}</strong>
          </div>
          <div style={trainingMetricStyle}>
            <span style={metricLabelStyle}>進度</span>
            <strong>{progress}%</strong>
          </div>
        </div>

        <div style={{
          height: "8px",
          backgroundColor: "#e5e0d8",
          borderRadius: "999px",
          overflow: "hidden"
        }}>
          <div style={{
            width: `${progress}%`,
            height: "100%",
            backgroundColor: "#2f6f4e",
            transition: "width 0.2s ease"
          }} />
        </div>

        <div style={{
          padding: "12px",
          borderRadius: "8px",
          color: feedbackColor,
          backgroundColor: feedbackBg,
          border: `1px solid ${feedback.tone === "warn" ? "#f2c48d" : "#d8d2c8"}`,
          fontWeight: 650,
          lineHeight: 1.5
        }}>
          {feedback.text}
        </div>

        <div>
          <div style={{ fontSize: "0.78rem", color: "#6b6258", fontWeight: 800, marginBottom: "6px" }}>目前棋譜</div>
          <div style={{
            minHeight: "42px",
            padding: "10px",
            borderRadius: "6px",
            backgroundColor: "#fbfaf7",
            border: "1px solid #e5e0d8",
            color: "#374151",
            fontSize: "0.9rem",
            lineHeight: 1.5
          }}>
            {history.length ? history.join(" ") : "尚未開始"}
          </div>
        </div>

        <div>
          <div style={{ fontSize: "0.78rem", color: "#6b6258", fontWeight: 800, marginBottom: "6px" }}>學習重點</div>
          <ul style={{ margin: 0, paddingLeft: "18px", color: "#374151", lineHeight: 1.55 }}>
            {selectedLesson.ideas.map((idea) => (
              <li key={idea}>{idea}</li>
            ))}
          </ul>
        </div>

        <button onClick={onReset} style={buttonStyle("#111827")}>重練這條變體</button>
      </div>
    </div>
  );
}

// 通用按鈕樣式
function buttonStyle(bgColor) {
  return {
    padding: "8px 12px", cursor: "pointer", backgroundColor: bgColor, color: "white",
    border: "1px solid rgba(17,24,39,0.10)", borderRadius: "6px", fontSize: "0.88rem", fontWeight: 750, transition: "all 0.2s"
  };
}

const navButtonStyle = {
  padding: "4px 10px", cursor: "pointer", backgroundColor: "#555", color: "white",
  border: "none", borderRadius: "4px", fontSize: "0.8rem"
};

const trainingMetricStyle = {
  padding: "10px",
  borderRadius: "8px",
  backgroundColor: "#f7f6f3",
  border: "1px solid #e5e0d8",
  display: "flex",
  flexDirection: "column",
  gap: "2px"
};

const metricLabelStyle = {
  color: "#6b6258",
  fontSize: "0.75rem",
  fontWeight: 800
};

export default App;
