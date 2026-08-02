import { lazy, Suspense, useMemo, useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import axios from "axios";
import { TRAINING_LESSONS, TRAINING_PHASES } from "./trainingLessons";
import { LearningDashboard } from "./LearningDashboard";
import {
  buildLessonChallenges,
  findAcceptedMove,
  scoreLessonAttempt
} from "./lessonEngine";
import {
  buildLearningPlan,
  getLearningStats,
  getLessonLockReason,
  getLessonProgress,
  getNextLesson,
  isLessonUnlocked,
  loadLearningProgress,
  recordLessonResult,
  saveLearningProgress
} from "./learningProgress";

const EvaluationChart = lazy(() => import("./EvaluationChart"));

// 預設走同網域 /api，由 Vite/Nginx 代理到後端；分離部署時可用 VITE_API_URL 覆蓋。
const API_URL = import.meta.env.VITE_API_URL || "/api";
const MATE_SCORE_THRESHOLD = 15000;

function calculateEvaluationBarShare(score) {
  if (Math.abs(score) > MATE_SCORE_THRESHOLD) return score > 0 ? 100 : 0;
  return Math.round((1000 / (1 + Math.exp(-0.00368 * score)))) / 10;
}

function formatEvaluationScore(score) {
  if (Math.abs(score) > MATE_SCORE_THRESHOLD) return score > 0 ? "白方將死" : "黑方將死";
  return `${score > 0 ? "+" : ""}${(score / 100).toFixed(2)}`;
}

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

const LESSON_TYPE_LABELS = {
  opening: "主線課",
  puzzle: "局面題",
  guided: "引導課",
  endgame: "殘局課"
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

function getPracticeRecommendations(analysisData, humanColor, lessons, progress) {
  const eligibleLessons = lessons.filter(
    (lesson) => lesson.recommendationVerified && isLessonUnlocked(lesson, lessons, progress)
  );
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
      recommendations: [eligibleLessons.find((lesson) => lesson.id === "italian-giuoco-piano") || eligibleLessons[0]].filter(Boolean)
    };
  }

  const rankedLessons = eligibleLessons
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
      : [eligibleLessons.find((lesson) => lesson.id === "middlegame-center-pressure") || eligibleLessons[0]].filter(Boolean)
  };
}

function createTrainingGame(challenges, challengeIndex = 0, fallbackFen) {
  const challenge = challenges[challengeIndex] || challenges[0];
  return new Chess(challenge?.fen || fallbackFen);
}

function App() {
  const [game, setGame] = useState(new Chess());
  const [appMode, setAppMode] = useState("play");
  const [trainingPhase, setTrainingPhase] = useState("opening");
  const [trainingGame, setTrainingGame] = useState(() => createTrainingGame(
    buildLessonChallenges(TRAINING_LESSONS[0]),
    0,
    TRAINING_LESSONS[0].startFen
  ));
  const [selectedLessonId, setSelectedLessonId] = useState(TRAINING_LESSONS[0].id);
  const [trainingStepOrder, setTrainingStepOrder] = useState(() => (
    buildLessonChallenges(TRAINING_LESSONS[0]).map((challenge) => challenge.index)
  ));
  const [trainingStepCursor, setTrainingStepCursor] = useState(0);
  const [trainingStepSolved, setTrainingStepSolved] = useState(false);
  const [trainingMissedSteps, setTrainingMissedSteps] = useState([]);
  const [trainingRetryDrill, setTrainingRetryDrill] = useState(false);
  const [trainingFeedback, setTrainingFeedback] = useState({
    tone: "neutral",
    text: "先觀察局面再走棋；需要時可逐步開啟提示。"
  });
  const [learningProgress, setLearningProgress] = useState(() => loadLearningProgress());
  const [trainingMistakes, setTrainingMistakes] = useState(0);
  const [trainingHints, setTrainingHints] = useState(0);
  const [hintLevel, setHintLevel] = useState(0);
  const [trainingResultRecorded, setTrainingResultRecorded] = useState(false);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [status, setStatus] = useState("準備開始新棋局");
  const [isResigned, setIsResigned] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyStatus, setHistoryStatus] = useState("loading");

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

  // 只捲動聊天室本身，避免 scrollIntoView 帶著整個頁面跳到底部。
  const chatFeedRef = useRef(null);

  // 1. 初始化載入歷史
  useEffect(() => {
    const controller = new AbortController();
    fetchHistory(controller.signal);
    return () => controller.abort();
  }, []);

  // 聊天室自動捲動到底部
  useEffect(() => {
    const chatFeed = chatFeedRef.current;
    if (!chatFeed) return;
    chatFeed.scrollTo({ top: chatFeed.scrollHeight, behavior: "smooth" });
  }, [chatHistory]);

  useEffect(() => {
    saveLearningProgress(learningProgress);
  }, [learningProgress]);

  async function fetchHistory(signal) {
    try {
      const res = await axios.get(`${API_URL}/games`, { signal });
      setHistory(res.data);
      setHistoryStatus("ready");
    } catch (err) {
      if (axios.isCancel(err) || err?.code === "ERR_CANCELED") return;
      setHistory([]);
      setHistoryStatus("unavailable");
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
      setCurrentMoveIndex(processedData.length > 0 ? processedData.length - 1 : -1);
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
  const selectedReviewIndex = currentMoveIndex >= 0 ? currentMoveIndex : analysisData.length - 1;
  const selectedReviewPoint = selectedReviewIndex >= 0 ? analysisData[selectedReviewIndex] : null;
  const selectedWhiteScore = selectedReviewPoint?.rawScore ?? 0;
  const selectedWdl = selectedReviewPoint?.wdl ?? null;
  const selectedEvaluationShare = selectedWdl?.expected_score ?? calculateEvaluationBarShare(selectedWhiteScore);
  const phaseLessons = TRAINING_LESSONS.filter((lesson) => lesson.phase === trainingPhase);
  const selectedLesson = TRAINING_LESSONS.find((lesson) => lesson.id === selectedLessonId) || phaseLessons[0] || TRAINING_LESSONS[0];
  const trainingChallenges = useMemo(() => buildLessonChallenges(selectedLesson), [selectedLesson]);
  const activeTrainingStepIndex = trainingStepOrder[trainingStepCursor] ?? 0;
  const currentTrainingChallenge = trainingChallenges[activeTrainingStepIndex] || trainingChallenges[0];
  const trainingHistory = trainingGame.history();
  const expectedTrainingMove = currentTrainingChallenge?.primaryMove;
  const trainingComplete = Boolean(
    currentTrainingChallenge
    && trainingStepSolved
    && trainingStepCursor >= trainingStepOrder.length - 1
  );
  const trainingAttemptResult = scoreLessonAttempt({
    totalSteps: trainingStepOrder.length,
    mistakes: trainingMistakes,
    hintsUsed: trainingHints,
    passScore: selectedLesson.passScore || 70
  });
  const trainingProgressPercent = trainingStepOrder.length
    ? Math.round(((trainingStepCursor + (trainingStepSolved ? 1 : 0)) / trainingStepOrder.length) * 100)
    : 0;
  const boardFen = appMode === "training" ? trainingGame.fen() : displayFen;
  const boardOrientation = appMode === "training" ? selectedLesson.side : humanColor;
  const selectedDifficulty = BOT_DIFFICULTIES.find((difficulty) => difficulty.id === botDifficulty) || BOT_DIFFICULTIES[2];
  const selectedStyle = BOT_STYLES.find((style) => style.id === botStyle) || BOT_STYLES[0];
  const practiceRecommendations = getPracticeRecommendations(
    analysisData,
    humanColor,
    TRAINING_LESSONS,
    learningProgress
  );
  const learningStats = getLearningStats(learningProgress, TRAINING_LESSONS);
  const learningPlan = buildLearningPlan(
    TRAINING_LESSONS,
    learningProgress,
    analysisData.length > 0 ? practiceRecommendations.recommendations : []
  );
  const nextLesson = getNextLesson(TRAINING_LESSONS, selectedLesson.id, learningProgress);

  useEffect(() => {
    if (appMode !== "training" || !trainingComplete || trainingResultRecorded) return;
    setLearningProgress((current) => recordLessonResult(current, selectedLesson.id, {
      completed: trainingAttemptResult.passed,
      mistakes: trainingMistakes,
      hintsUsed: trainingHints,
      score: trainingAttemptResult.score,
      missedSteps: trainingMissedSteps,
      partial: trainingRetryDrill
    }));
    setTrainingResultRecorded(true);
  }, [
    appMode,
    selectedLesson.id,
    trainingComplete,
    trainingHints,
    trainingMistakes,
    trainingMissedSteps,
    trainingRetryDrill,
    trainingAttemptResult.passed,
    trainingAttemptResult.score,
    trainingResultRecorded
  ]);

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
    return new Chess(chessInstance.fen());
  }

  function resetTraining(nextLessonId = selectedLessonId, retryStepIndexes = null) {
    const lesson = TRAINING_LESSONS.find((item) => item.id === nextLessonId) || TRAINING_LESSONS[0];
    const lockReason = getLessonLockReason(lesson, TRAINING_LESSONS, learningProgress);
    if (lockReason) {
      setStatus(lockReason);
      setAppMode("learning");
      return false;
    }
    const challenges = buildLessonChallenges(lesson);
    const allStepIndexes = challenges.map((challenge) => challenge.index);
    const requestedSteps = Array.isArray(retryStepIndexes)
      ? [...new Set(retryStepIndexes)].filter((index) => allStepIndexes.includes(index))
      : [];
    const stepOrder = requestedSteps.length ? requestedSteps : allStepIndexes;
    if (!stepOrder.length) return false;

    setTrainingPhase(lesson.phase);
    setSelectedLessonId(lesson.id);
    setTrainingStepOrder(stepOrder);
    setTrainingRetryDrill(stepOrder.length < allStepIndexes.length);
    setTrainingStepCursor(0);
    setTrainingStepSolved(false);
    setTrainingMissedSteps([]);
    setTrainingGame(createTrainingGame(challenges, stepOrder[0], lesson.startFen));
    setSelectedSquare(null);
    setTrainingMistakes(0);
    setTrainingHints(0);
    setHintLevel(0);
    setTrainingResultRecorded(false);
    setTrainingFeedback({
      tone: "neutral",
      text: challenges[stepOrder[0]]?.prompt || `${lesson.opening}：${lesson.variation}。目標：${lesson.goal}`
    });
    return true;
  }

  function startRecommendedLesson(lessonId) {
    if (!resetTraining(lessonId)) return;
    setAppMode("training");
    setStatus("已切換到推薦練習");
  }

  function selectTrainingPhase(nextPhase) {
    const firstUnlocked = TRAINING_LESSONS.find(
      (lesson) => lesson.phase === nextPhase && isLessonUnlocked(lesson, TRAINING_LESSONS, learningProgress)
    );
    // 沒有可上的課時留在原階段，否則會靜默跳到別的階段。
    if (!firstUnlocked) {
      setTrainingFeedback({
        tone: "warn",
        text: "這個階段的課程都還沒解鎖，請先完成對應的先修課程。"
      });
      return;
    }
    resetTraining(firstUnlocked.id);
  }

  function openLearningArea() {
    setSelectedSquare(null);
    setAppMode("learning");
  }

  function revealTrainingHint() {
    if (trainingStepSolved || !currentTrainingChallenge) return;
    const nextLevel = Math.min(2, hintLevel + 1);
    setHintLevel(nextLevel);
    setTrainingHints((count) => count + 1);
    setTrainingFeedback({
      tone: "neutral",
      text: nextLevel === 1
        ? `觀念提示：${currentTrainingChallenge.hints[0]}`
        : `走法提示：${currentTrainingChallenge.hints[1]}`
    });
  }

  function advanceTrainingStep() {
    if (!trainingStepSolved || trainingComplete) return;
    const nextCursor = trainingStepCursor + 1;
    const nextStepIndex = trainingStepOrder[nextCursor];
    const nextChallenge = trainingChallenges[nextStepIndex];
    if (!nextChallenge) return;
    setTrainingStepCursor(nextCursor);
    setTrainingStepSolved(false);
    setHintLevel(0);
    setSelectedSquare(null);
    setTrainingGame(createTrainingGame(trainingChallenges, nextStepIndex, selectedLesson.startFen));
    setTrainingFeedback({ tone: "neutral", text: nextChallenge.prompt });
  }

  function retryMissedTrainingSteps() {
    resetTraining(selectedLesson.id, trainingMissedSteps);
  }

  function playTrainingMove(sourceSquare, targetSquare) {
    if (trainingStepSolved || !currentTrainingChallenge) {
      setTrainingFeedback({ tone: "neutral", text: trainingComplete ? "本次課程已完成。" : "這一步已完成，請前往下一題。" });
      return false;
    }
    const learnerTurn = selectedLesson.side === "black" ? "b" : "w";
    if (trainingGame.turn() !== learnerTurn) return false;

    const nextGame = cloneChess(trainingGame);
    let move = null;
    try {
      move = nextGame.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
    } catch {
      return false;
    }
    if (!move) return false;

    const acceptedMove = findAcceptedMove(currentTrainingChallenge, move.san);
    if (!acceptedMove) {
      const nextMistakeCount = trainingMistakes + 1;
      setTrainingMistakes(nextMistakeCount);
      setTrainingMissedSteps((current) => (
        current.includes(activeTrainingStepIndex) ? current : [...current, activeTrainingStepIndex]
      ));
      setTrainingFeedback({
        tone: "warn",
        text: nextMistakeCount >= 2
          ? `這步 ${move.san} 合法，但沒有命中本題重點；可以開啟第二層提示。`
          : `再想一次：${currentTrainingChallenge.hints[0]}`
      });
      return false;
    }

    setTrainingGame(nextGame);
    setTrainingStepSolved(true);
    setTrainingFeedback({
      tone: "success",
      text: `好棋：${move.san}。${acceptedMove.explanation}`
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
      if (appMode === "training" && piece.color !== (selectedLesson.side === "black" ? "b" : "w")) return;
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
      if (piece && (appMode === "training"
        ? piece.color === (selectedLesson.side === "black" ? "b" : "w")
        : piece.color === (humanColor === "white" ? "w" : "b"))) {
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

  // 局勢條：Stockfish 可用時顯示 WDL，否則只以評分做視覺比例，不宣稱勝率。
  function EvaluationBar({ whiteShare, evalDisplay, wdl, analysisSource }) {
    const whiteHeight = Math.max(0, Math.min(100, whiteShare));
    const blackHeight = 100 - whiteHeight;
    const ariaDescription = wdl
      ? `白勝 ${wdl.white_win.toFixed(1)}%，和棋 ${wdl.draw.toFixed(1)}%，黑勝 ${wdl.black_win.toFixed(1)}%`
      : "目前僅提供局面評分，未提供勝和負機率";

    return (
      <div
        className="eval-bar"
        role="img"
        aria-label={`白方局勢評估 ${evalDisplay}，${ariaDescription}`}
      >
        <div className="eval-bar__track">
          {/* 白方區域 */}
          <div className="eval-bar__white" style={{ height: `${whiteHeight}%`, flexBasis: `${whiteHeight}%` }}>
          </div>
          
          {/* 黑方區域 */}
          <div className="eval-bar__black" style={{ height: `${blackHeight}%`, flexBasis: `${blackHeight}%` }}>
          </div>

          {/* 中間線 */}
          <div className="eval-bar__midline"></div>
          <span className="eval-bar__side is-black" aria-hidden="true">黑</span>
          <span className="eval-bar__side is-white" aria-hidden="true">白</span>
        </div>

        {/* 評分顯示 */}
        <div className={`eval-bar__score ${evalDisplay.startsWith("+") ? "is-positive" : evalDisplay.startsWith("-") ? "is-negative" : ""}`}>
          {evalDisplay}
        </div>
        
        {wdl ? (
          <div className="eval-bar__wdl" title="Stockfish UCI_ShowWDL">
            <span>白勝 {wdl.white_win.toFixed(1)}%</span>
            <span>和棋 {wdl.draw.toFixed(1)}%</span>
            <span>黑勝 {wdl.black_win.toFixed(1)}%</span>
          </div>
        ) : (
          <div className="eval-bar__chance" title={analysisSource === "custom" ? "自製引擎評分" : undefined}>
            僅評分
          </div>
        )}
      </div>
    );
  }

  function formatChartScore(score, isMate = Math.abs(score) > 15000) {
    if (isMate) {
      return score >= 0 ? "白方將死勝勢" : "黑方將死勝勢";
    }
    return `白方評分：${(score / 100).toFixed(2)}`;
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
          <strong>{appMode === "learning" ? "學習專區" : appMode === "training" ? "課程練習" : analysisData.length > 0 ? "復盤" : "對局"}</strong>
        </div>
      </header>

      {appMode === "learning" ? (
        <LearningDashboard
          phases={TRAINING_PHASES}
          lessons={TRAINING_LESSONS}
          progress={learningProgress}
          stats={learningStats}
          plan={learningPlan}
          onStartLesson={startRecommendedLesson}
          onReturnToGame={() => setAppMode("play")}
        />
      ) : (
      <main className={`coach-workspace ${analysisData.length > 0 ? "has-evaluation" : ""}`}>

        {/* 勝率條 - 只在賽後分析時顯示 */}
        {analysisData.length > 0 && (
          <EvaluationBar 
            whiteShare={selectedEvaluationShare}
            evalDisplay={formatEvaluationScore(selectedWhiteScore)}
            wdl={selectedWdl}
            analysisSource={selectedReviewPoint?.analysis_source}
          />
        )}

        {/* 左側：棋盤區 */}
        <section className="board-panel" aria-label="棋盤與對局控制">
          <div className="board-console">
            <div className="board-console__topline">
              <div>
                <span>{appMode === "training" ? "練習方" : "你執"}</span>
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
            {appMode === "training" ? `課程練習：你執${selectedLesson.side === "black" ? "黑方" : "白方"}，先思考再使用提示` : status}
          </div>

          <div className="control-bar">
            <button className={`btn ${appMode === "play" ? "btn-primary" : "btn-muted"}`} onClick={() => setAppMode("play")}>對局</button>
            <button className="btn btn-success" onClick={openLearningArea}>學習專區</button>
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
              allLessons={TRAINING_LESSONS}
              learningProgress={learningProgress}
              selectedLesson={selectedLesson}
              selectedLessonId={selectedLessonId}
              onSelectLesson={resetTraining}
              feedback={trainingFeedback}
              history={trainingHistory}
              expectedMove={expectedTrainingMove}
              challenge={currentTrainingChallenge}
              stepNumber={trainingStepCursor + 1}
              totalSteps={trainingStepOrder.length}
              stepSolved={trainingStepSolved}
              progressPercentage={trainingProgressPercent}
              complete={trainingComplete}
              mistakes={trainingMistakes}
              hints={trainingHints}
              hintLevel={hintLevel}
              lessonProgress={getLessonProgress(learningProgress, selectedLesson.id)}
              attemptResult={trainingAttemptResult}
              missedStepsCount={trainingMissedSteps.length}
              isRetryDrill={trainingRetryDrill}
              nextLesson={nextLesson}
              onHint={revealTrainingHint}
              onReset={() => resetTraining(selectedLessonId)}
              onAdvance={advanceTrainingStep}
              onRetryMissed={retryMissedTrainingSteps}
              onNext={() => nextLesson && resetTraining(nextLesson.id)}
              onBack={openLearningArea}
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
            <div className="chat-feed" ref={chatFeedRef}>
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
            <Suspense fallback={<div className="analysis-card chart-loading" role="status">正在載入局勢圖表…</div>}>
              <EvaluationChart
                analysisData={analysisData}
                currentMoveIndex={currentMoveIndex}
                onMoveSelect={setCurrentMoveIndex}
              />
            </Suspense>
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
                  ? "根據這盤的失誤階段與掉分幅度推測，先補最可能相關的主題。"
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
            {historyStatus !== "ready" || history.length === 0 ? (
              <p className="empty-state" aria-live="polite">
                {historyStatus === "loading"
                  ? "讀取紀錄中…"
                  : historyStatus === "unavailable"
                    ? "後端未連線，歷史紀錄暫不可用"
                    : "尚無紀錄"}
              </p>
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
      )}
    </div>
  );
}

export function OpeningTrainingPanel({
  phases,
  trainingPhase,
  onSelectPhase,
  lessons,
  allLessons,
  learningProgress,
  selectedLesson,
  selectedLessonId,
  onSelectLesson,
  feedback,
  history,
  expectedMove,
  challenge,
  stepNumber,
  totalSteps,
  stepSolved,
  progressPercentage,
  complete,
  mistakes,
  hints,
  hintLevel,
  lessonProgress,
  attemptResult,
  missedStepsCount,
  isRetryDrill,
  nextLesson,
  onHint,
  onReset,
  onAdvance,
  onRetryMissed,
  onNext,
  onBack
}) {
  const acceptedMoveLabel = challenge?.acceptedMoves?.map((candidate) => candidate.san).join("、") || expectedMove;

  return (
    <div className="training-card">
      <div className="training-card__header">
        <div className="training-header-row">
          <div className="panel-kicker">課程練習</div>
          <button className="text-button" onClick={onBack}>返回學習專區</button>
        </div>
        <div className="training-title">{selectedLesson.opening}</div>
        <div className="training-subtitle">{selectedLesson.variation}</div>
        <div className="lesson-chip-row">
          <span>{LESSON_TYPE_LABELS[selectedLesson.type] || "課程"}</span>
          <span>{selectedLesson.side === "black" ? "執黑" : "執白"}</span>
          <span>難度 {selectedLesson.difficulty}</span>
        </div>
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
            {lessons.map((lesson) => {
              const lockReason = getLessonLockReason(lesson, allLessons, learningProgress);
              return (
                <option key={lesson.id} value={lesson.id} disabled={Boolean(lockReason)}>
                  {lesson.variation}{lockReason ? "（需先修）" : ""}
                </option>
              );
            })}
          </select>
        </div>

        <div className="goal-box">
          <div className="setting-label">本變體目標</div>
          <div>{selectedLesson.goal}</div>
        </div>

        <div className="training-metrics">
          <div className="metric-card">
            <span>
              {complete
                ? (isRetryDrill ? "錯題重練結果" : "結業結果")
                : `${isRetryDrill ? "錯題" : "挑戰"} ${stepNumber}/${totalSteps}`}
            </span>
            <strong>
              {complete
                ? attemptResult.grade
                : stepSolved
                  ? "本題完成"
                  : hintLevel >= 2
                    ? acceptedMoveLabel
                    : challenge?.prompt || (selectedLesson.type === "puzzle" ? "找出最佳手" : "運用本課觀念")}
            </strong>
          </div>
          <div className="metric-card">
            <span>進度</span>
            <strong>{progressPercentage}%</strong>
          </div>
        </div>

        <div className="progress-track">
          <div style={{ width: `${progressPercentage}%` }} />
        </div>

        <div className={`feedback-box tone-${feedback.tone}`}>
          {feedback.text}
        </div>

        {!complete && !stepSolved && (
          <button className="btn btn-secondary hint-button" onClick={onHint} disabled={hintLevel >= 2}>
            {hintLevel === 0 ? "給我觀念提示" : hintLevel === 1 ? "顯示走法提示" : "提示已全部開啟"}
          </button>
        )}

        <div className="attempt-summary" aria-label="本次練習統計">
          <span>錯誤 {mistakes}</span>
          <span>提示 {hints}</span>
          <span>熟練度 {lessonProgress.mastery}/5</span>
          <span>目前分數 {attemptResult.score}</span>
        </div>

        {complete && isRetryDrill && (
          <section className="lesson-result is-retry" aria-label="錯題重練結果">
            <div>
              <span>錯題重練</span>
              <strong>{attemptResult.score}</strong>
            </div>
            <p>
              這次只重練了 {totalSteps} 題錯題，不會計入結業成績或熟練度。
              {attemptResult.passed ? " 這幾題已經掌握，回頭重練整堂就能結業。" : " 建議再看一次學習重點後重練。"}
            </p>
            <small>歷史最高 {lessonProgress.bestScore || 0} 分</small>
          </section>
        )}

        {complete && !isRetryDrill && (
          <section className={`lesson-result ${attemptResult.passed ? "is-passed" : "is-retry"}`} aria-label="課程結業成績">
            <div>
              <span>本次成績</span>
              <strong>{attemptResult.score}</strong>
            </div>
            <p>
              正確率 {attemptResult.accuracy}% · 及格標準 {attemptResult.passScore} 分 ·
              {attemptResult.passed ? " 已通過，可以前往下一課。" : " 尚未通過，建議重練錯題。"}
            </p>
            <small>歷史最高 {lessonProgress.bestScore || attemptResult.score} 分</small>
          </section>
        )}

        <div>
          <div className="setting-label">本題走法</div>
          <div className="move-line">
            {history.length ? history.join(" ") : "尚未開始"}
          </div>
        </div>

        <div>
          <div className="setting-label">學習重點</div>
          {complete ? (
            <ul className="idea-list">
              {selectedLesson.ideas.map((idea) => (
                <li key={idea}>{idea}</li>
              ))}
            </ul>
          ) : (
            <p className="locked-learning-copy">完成課程後會整理完整學習重點；作答前先依目標判斷。</p>
          )}
        </div>

        <div className="training-actions">
          <button className="btn btn-secondary" onClick={onReset}>重練整堂</button>
          {stepSolved && !complete && (
            <button className="btn btn-primary" onClick={onAdvance}>下一個挑戰</button>
          )}
          {complete && missedStepsCount > 0 && (
            <button className="btn btn-secondary" onClick={onRetryMissed}>只重練錯題（{missedStepsCount}）</button>
          )}
          {complete && attemptResult.passed && !isRetryDrill && nextLesson && (
            <button className="btn btn-primary" onClick={onNext}>下一課：{nextLesson.variation}</button>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
