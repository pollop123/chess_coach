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
    tags: ["opening", "development", "king_safety"],
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
    tags: ["opening", "development", "calculation"],
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
    tags: ["opening", "initiative", "center"],
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
    tags: ["tactics", "king_safety", "checkmate"],
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
    tags: ["middlegame", "tactics", "calculation", "center"],
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
    tags: ["endgame", "checkmate", "king_safety"],
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
    tags: ["endgame", "promotion", "conversion"],
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

const WEAKNESS_LABELS = {
  opening: "開局節奏",
  development: "子力發展",
  king_safety: "王安全",
  tactics: "戰術警覺",
  calculation: "計算精準度",
  endgame: "殘局轉換",
  promotion: "通路兵升變",
  center: "中心控制",
  conversion: "優勢轉換"
};

function countPiecesFromFen(fen) {
  const placement = (fen || "").split(" ")[0] || "";
  return placement.replace(/[1-8/]/g, "").length;
}

function getMovePhase(item) {
  if (item.move_number <= 8) return "opening";
  if (countPiecesFromFen(item.fen) <= 10 || item.move_number >= 28) return "endgame";
  return "middlegame";
}

function tagsForReviewMove(item) {
  const tags = new Set();
  const phase = getMovePhase(item);
  const cpLoss = item.cp_loss || 0;

  if (phase === "opening") {
    tags.add("opening");
    tags.add("development");
  }
  if (phase === "endgame") {
    tags.add("endgame");
    tags.add("conversion");
  }
  if (cpLoss >= 150) {
    tags.add("tactics");
    tags.add("calculation");
  }
  if (item.mate_threat || item.is_checkmate) {
    tags.add("king_safety");
    tags.add("checkmate");
  }
  if (phase === "endgame" && cpLoss >= 250) {
    tags.add("promotion");
  }
  if (phase === "middlegame" && cpLoss >= 50) {
    tags.add("center");
  }

  return [...tags];
}

function getPracticeRecommendations(analysisData, humanColor, lessons) {
  const humanSide = humanColor === "black" ? "black" : "white";
  const reviewMoves = analysisData
    .filter((item) => item.move && item.side_to_move === humanSide)
    .filter((item) => ["inaccuracy", "mistake", "blunder"].includes(item.classification));

  const tagWeights = new Map();
  for (const item of reviewMoves) {
    const severity = item.classification === "blunder" ? 3 : item.classification === "mistake" ? 2 : 1;
    for (const tag of tagsForReviewMove(item)) {
      tagWeights.set(tag, (tagWeights.get(tag) || 0) + severity);
    }
  }

  if (tagWeights.size === 0) {
    return {
      weaknesses: [],
      recommendations: [lessons.find((lesson) => lesson.id === "italian-giuoco-piano") || lessons[0]].filter(Boolean)
    };
  }

  const rankedLessons = lessons
    .map((lesson) => {
      const score = (lesson.tags || []).reduce((sum, tag) => sum + (tagWeights.get(tag) || 0), 0)
        + (tagWeights.get(lesson.phase) || 0);
      return { lesson, score };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score || a.lesson.id.localeCompare(b.lesson.id));

  const weaknesses = [...tagWeights.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([tag]) => tag);

  return {
    weaknesses,
    recommendations: rankedLessons.length
      ? rankedLessons.slice(0, 2).map((item) => item.lesson)
      : [lessons.find((lesson) => lesson.id === "middlegame-center-pressure") || lessons[0]].filter(Boolean)
  };
}

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
  const [isAnalyzing, setIsAnalyzing] = useState(false);

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
    if (game.pgn() === "" || isAnalyzing) return;
    setIsAnalyzing(true);
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
    } finally {
      setIsAnalyzing(false);
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
  const practiceRecommendations = getPracticeRecommendations(analysisData, humanColor, TRAINING_LESSONS);

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

  function startRecommendedLesson(lessonId) {
    resetTraining(lessonId);
    setAppMode("training");
    setStatus("已切換到推薦練習");
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
      <div className="eval-bar">
        <div className="eval-bar__track">
          {/* 白方區域 */}
          <div className="eval-bar__white" style={{ height: `${whiteHeight}%`, flexBasis: `${whiteHeight}%` }}>
          </div>
          
          {/* 黑方區域 */}
          <div className="eval-bar__black" style={{ height: `${blackHeight}%`, flexBasis: `${blackHeight}%` }}>
          </div>

          {/* 中間線 */}
          <div className="eval-bar__midline"></div>
        </div>

        {/* 評分顯示 */}
        <div className={`eval-bar__score ${evalDisplay.startsWith("+") ? "is-positive" : evalDisplay.startsWith("-") ? "is-negative" : ""}`}>
          {evalDisplay}
        </div>
        
        <div className="eval-bar__chance">
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
      <div className="chart-tooltip">
        <div className="chart-tooltip__label">第 {label} 步</div>
        <div className="chart-tooltip__value">{point.evalLabel}</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <div className="app-header__eyebrow">棋局分析工作台</div>
          <h1>Chess Coach AI</h1>
          <p>對局、訓練、復盤與教練問答集中在同一個棋盤旁。</p>
        </div>
        <div className="session-card">
          <span>目前模式</span>
          <strong>{appMode === "training" ? "訓練" : analysisData.length > 0 ? "復盤" : "對局"}</strong>
        </div>
      </header>

      <main className={`coach-workspace ${analysisData.length > 0 ? "has-evaluation" : ""}`}>

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
        <section className="board-panel" aria-label="棋盤與對局控制">
          <div className="board-console">
            <div className="board-console__topline">
              <div>
                <span>你執</span>
                <strong>{boardOrientation === "white" ? "白方" : "黑方"}</strong>
              </div>
              <div>
                <span>難度</span>
                <strong>{appMode === "training" ? selectedLesson.phase : selectedDifficulty.label}</strong>
              </div>
              <div>
                <span>風格</span>
                <strong>{appMode === "training" ? selectedLesson.variation : selectedStyle.label}</strong>
              </div>
            </div>
            <div className="board-frame">
              <Chessboard
                position={boardFen}
                onPieceDrop={onDrop}
                onSquareClick={handleSquareClick}
                boardOrientation={boardOrientation}
                customLightSquareStyle={{ backgroundColor: "#dce7d0" }}
                customDarkSquareStyle={{ backgroundColor: "#4f7f69" }}
                customBoardStyle={{ borderRadius: "6px" }}
                customSquareStyles={selectedSquare ? {
                  [selectedSquare]: { boxShadow: "inset 0 0 0 4px rgba(255,209,102,0.92)" }
                } : {}}
              />
            </div>
          </div>

          {analysisData.length > 0 && (
            <div className="review-nav">
              <button className="btn btn-ghost btn-sm" onClick={() => navigateMove(-1)}>上一步</button>
              <span>{currentMoveIndex === -1 ? "最終局" : `第 ${currentMoveIndex} 步`}</span>
              <button className="btn btn-ghost btn-sm" onClick={() => navigateMove(1)}>下一步</button>
            </div>
          )}

          <div className="status-strip" aria-live="polite">
            {appMode === "training" ? "訓練模式：照提示走白方，黑方會自動回應" : status}
          </div>

          <div className="control-bar">
            <button className={`btn ${appMode === "play" ? "btn-primary" : "btn-muted"}`} onClick={() => setAppMode("play")}>對局</button>
            <button className={`btn ${appMode === "training" ? "btn-success" : "btn-muted"}`} onClick={() => { setAppMode("training"); resetTraining(selectedLessonId); }}>訓練模式</button>
            <button className="btn btn-primary" onClick={() => { const ng = new Chess(); setGame(ng); setStatus("新局開始"); setAnalysisData([]); setCurrentMoveIndex(-1); setIsResigned(false); setChatHistory([]); if (humanColor === "black") makeAIMove(ng.fen()); }}>新局</button>
            {appMode === "play" && (
              <button
                className="btn btn-danger"
                onClick={resignGame}
                disabled={game.isGameOver() || isResigned || analysisData.length > 0}
              >
                投降
              </button>
            )}
            <button className="btn btn-success" onClick={analyzeGame} disabled={isAnalyzing || game.pgn() === ""}>
              {isAnalyzing ? "分析中..." : "賽後分析"}
            </button>
            <button className="btn btn-secondary" onClick={downloadPGN}>匯出 PGN</button>
            <div className="segmented-control" aria-label="選擇玩家顏色">
              <button className={humanColor === "white" ? "is-active" : ""} onClick={() => setHumanColor("white")}>白</button>
              <button className={humanColor === "black" ? "is-active" : ""} onClick={() => setHumanColor("black")}>黑</button>
            </div>
          </div>

          {appMode === "play" && (
            <div className="bot-settings">
              <div className="setting-label">機器人難度</div>
              <div className="option-grid option-grid-four">
                {BOT_DIFFICULTIES.map((difficulty) => (
                  <button
                    key={difficulty.id}
                    className={`option-tile ${botDifficulty === difficulty.id ? "is-selected" : ""}`}
                    onClick={() => setBotDifficulty(difficulty.id)}
                    disabled={game.history().length > 0 || isResigned || analysisData.length > 0}
                    title={difficulty.description}
                  >
                    {difficulty.label}
                  </button>
                ))}
              </div>
              <div className="setting-help">{selectedDifficulty.description}</div>
              <div className="setting-label">機器人風格</div>
              <div className="option-grid option-grid-two">
                {BOT_STYLES.map((style) => (
                  <button
                    key={style.id}
                    className={`option-tile ${botStyle === style.id ? "is-selected is-earth" : ""}`}
                    onClick={() => setBotStyle(style.id)}
                    disabled={game.history().length > 0 || isResigned || analysisData.length > 0}
                    title={style.description}
                  >
                    {style.label}
                  </button>
                ))}
              </div>
              <div className="setting-help">{selectedStyle.description}</div>
            </div>
          )}
        </section>

        {/* 右側：聊天室 & 分析圖表 */}
        <aside className="side-panel" aria-label="教練、訓練與分析">

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
            <div className="coach-card">
            <div className="panel-header">
              <span>AI 教練</span>
              <button
                className="btn btn-inverse btn-sm"
                onClick={() => askCoach()}
                disabled={isCoachThinking}
              >
                分析目前局面
              </button>
            </div>

            {/* 訊息列表 */}
            <div className="chat-feed">
              {chatHistory.map((msg, idx) => (
                <div key={idx} className={`chat-bubble ${msg.role === "user" ? "is-user" : "is-model"}`}>
                  {msg.text}
                </div>
              ))}
              {isCoachThinking && (
                <div className="thinking-line">
                  教練正在思考...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* 輸入框 */}
            <div className="chat-composer">
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="問教練問題 (例如：為什麼這步不好？)"
                disabled={isCoachThinking}
              />
              <button
                className="send-button"
                onClick={() => { if (userInput.trim()) askCoach(userInput); }}
                disabled={isCoachThinking || !userInput.trim()}
                aria-label="送出問題"
              >
                ➤
              </button>
            </div>
          </div>
          </>
          )}

          {/* 📊 分析圖表 (如果有數據) */}
          {appMode === "play" && analysisData.length > 0 && (
            <div className="analysis-card">
              <div className="chart-header">
                <span>局勢走勢（白方視角）</span>
                <span>0 線</span>
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

          {appMode === "play" && analysisData.length > 0 && (
            <div className="practice-card">
              <div className="practice-card__header">
                <div>
                  <div className="panel-kicker">推薦練習</div>
                  <h3>下一步訓練</h3>
                </div>
                <span>
                  {practiceRecommendations.weaknesses.length
                    ? practiceRecommendations.weaknesses.map((tag) => WEAKNESS_LABELS[tag] || tag).join(" / ")
                    : "穩定復盤"}
                </span>
              </div>

              <p className="practice-summary">
                {practiceRecommendations.weaknesses.length
                  ? "根據這盤的失誤類型，先補最常出現的弱點。"
                  : "這盤沒有明顯反覆失誤，建議用基礎開局題維持節奏。"}
              </p>

              <div className="practice-list">
                {practiceRecommendations.recommendations.map((lesson) => (
                  <div className="practice-item" key={lesson.id}>
                    <div>
                      <strong>{lesson.variation}</strong>
                      <small>{lesson.opening} · {TRAINING_PHASES.find((phase) => phase.id === lesson.phase)?.label || lesson.phase}</small>
                      <p>{lesson.goal}</p>
                    </div>
                    <button className="btn btn-primary" onClick={() => startRecommendedLesson(lesson.id)}>
                      開始練
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 歷史戰績 */}
          {appMode === "play" && (
          <div className="history-card">
            <h3>
              最近棋局
            </h3>
            {history.length === 0 ? (
              <p className="empty-state">尚無紀錄</p>
            ) : (
              <ul className="history-list">
                {history.map((h) => (
                  <li key={h.id} onClick={() => loadGame(h.pgn)}
                  >
                    <div className="history-meta">
                      <span>
                        #{h.id ? h.id : "?"}
                      </span>
                      <small>
                        {h.date ? new Date(h.date).toLocaleString("zh-TW") : "無日期"}
                      </small>
                    </div>

                    <span className={`result-badge ${h.result === "1-0" ? "is-win" : h.result === "0-1" ? "is-loss" : "is-draw"}`}>
                      {h.result}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          )}

        </aside>
      </main>
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

  return (
    <div className="training-card">
      <div className="training-card__header">
        <div className="panel-kicker">訓練模式</div>
        <div className="training-title">{selectedLesson.opening}</div>
        <div className="training-subtitle">{selectedLesson.variation}</div>
      </div>

      <div className="training-card__body">
        <div className="phase-tabs">
          {phases.map((phase) => (
            <button
              key={phase.id}
              className={trainingPhase === phase.id ? "is-active" : ""}
              onClick={() => onSelectPhase(phase.id)}
            >
              {phase.label}
            </button>
          ))}
        </div>

        <div>
          <label className="setting-label">
            選擇題目
          </label>
          <select
            className="lesson-select"
            value={selectedLessonId}
            onChange={(event) => onSelectLesson(event.target.value)}
          >
            {lessons.map((lesson) => (
              <option key={lesson.id} value={lesson.id}>
                {lesson.variation}
              </option>
            ))}
          </select>
        </div>

        <div className="goal-box">
          <div className="setting-label">本變體目標</div>
          <div>{selectedLesson.goal}</div>
        </div>

        <div className="training-metrics">
          <div className="metric-card">
            <span>下一步白方</span>
            <strong>{complete ? "完成" : expectedMove}</strong>
          </div>
          <div className="metric-card">
            <span>進度</span>
            <strong>{progress}%</strong>
          </div>
        </div>

        <div className="progress-track">
          <div style={{ width: `${progress}%` }} />
        </div>

        <div className={`feedback-box tone-${feedback.tone}`}>
          {feedback.text}
        </div>

        <div>
          <div className="setting-label">目前棋譜</div>
          <div className="move-line">
            {history.length ? history.join(" ") : "尚未開始"}
          </div>
        </div>

        <div>
          <div className="setting-label">學習重點</div>
          <ul className="idea-list">
            {selectedLesson.ideas.map((idea) => (
              <li key={idea}>{idea}</li>
            ))}
          </ul>
        </div>

        <button className="btn btn-primary" onClick={onReset}>重練這條變體</button>
      </div>
    </div>
  );
}

export default App;
