export const TRAINING_PHASES = [
  { id: "opening", label: "開局" },
  { id: "middlegame", label: "中局" },
  { id: "endgame", label: "殘局" }
];

const LESSON_CATALOG = [
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
    id: "london-system-development",
    phase: "opening",
    tags: ["opening", "development", "center"],
    opening: "倫敦系統",
    variation: "基本出子結構",
    goal: "用穩定兵型和早出主教建立可重複的開局節奏。",
    moves: ["d4", "d5", "Nf3", "Nf6", "Bf4", "e6", "e3", "c5", "c3", "Nc6", "Nbd2"],
    ideas: [
      "倫敦系統的重點是先把子力放到自然格，而不是背大量變體。",
      "Bf4 讓主教在兵鍊外面活動，避免被自己的 e3 關住。",
      "c3 和 e3 形成穩固中心，接著才考慮 Bd3、O-O 與 Ne5。",
      "這題適合開局常常忘記出子順序的玩家。"
    ]
  },
  {
    id: "sicilian-alapin-center",
    phase: "opening",
    tags: ["opening", "center", "development"],
    opening: "西西里防禦",
    variation: "Alapin 中心建立",
    goal: "面對 ...c5 時用 c3、d4 建立白方中心，而不是急著單子進攻。",
    moves: ["e4", "c5", "c3", "Nf6", "e5", "Nd5", "d4", "cxd4", "Nf3", "Nc6", "cxd4"],
    ideas: [
      "Alapin 的核心是 c3 支援 d4，爭取完整中心。",
      "e5 趕走黑方騎士，但後續一定要接 d4 才有意義。",
      "Nf3 先補發展，再用 cxd4 保住中心兵型。",
      "如果復盤常出現開局中心被打散，這題很適合重練。"
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
    type: "guided",
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
    id: "middlegame-two-knights-fork",
    phase: "middlegame",
    tags: ["tactics", "calculation", "king_safety"],
    opening: "中局戰術",
    variation: "騎士叉擊：Nxf7",
    goal: "看見能把黑王引出來的騎士戰術，並評估後續攻擊補償。",
    startFen: "r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6",
    moves: ["Nxf7"],
    ideas: [
      "Nxf7 不是單純貪兵，而是同時攻擊后翼車與暴露黑王。",
      "這種戰術要先算對方是否能吃回，以及吃回後王是否安全。",
      "如果復盤常漏掉強迫手，先從將軍、吃子、威脅三類候選找起。"
    ]
  },
  {
    id: "middlegame-hanging-queen",
    phase: "middlegame",
    type: "guided",
    tags: ["tactics", "calculation", "king_safety"],
    opening: "中局判斷",
    variation: "后的位置安全",
    goal: "在攻擊前先確認大子不會被低價子或王翼子力追掉。",
    startFen: "7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1",
    moves: ["Qh3"],
    ideas: [
      "后很強，但一旦站到容易被追打的位置，攻擊就會變成送子。",
      "Qh3 先把后帶回安全格，保留後續將軍與側翼壓力。",
      "復盤出現大幅掉分時，先問自己：我的后、車是否被直接攻擊？"
    ]
  },
  {
    id: "middlegame-back-rank-mate",
    phase: "middlegame",
    tags: ["tactics", "checkmate", "king_safety"],
    opening: "中局戰術",
    variation: "底線將殺",
    goal: "辨識國王被自己兵擋住時，車能直接切入底線的將殺。",
    startFen: "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
    moves: ["Ra8#"],
    ideas: [
      "底線將殺常來自國王沒有逃生格，而不是攻擊子很多。",
      "車到第八排時，要確認對方是否能吃車或墊子。",
      "看到對方三個兵把國王關住時，先檢查底線將軍。"
    ]
  },
  {
    id: "middlegame-center-break",
    phase: "middlegame",
    type: "guided",
    tags: ["middlegame", "center", "calculation"],
    opening: "中局判斷",
    variation: "中心突破：d4",
    goal: "在完成基本發展後，用中心突破打開子力活動空間。",
    startFen: "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 w kq - 4 5",
    moves: ["d4"],
    ideas: [
      "中心突破通常要在王安全、子力基本就位後才有效。",
      "d4 會打開 c1 主教與后翼子力，讓白方不只停在防守。",
      "如果攻擊停滯，先檢查中心是否有可安全推進的兵。"
    ]
  },
  {
    id: "middlegame-pin-pressure",
    phase: "middlegame",
    type: "guided",
    tags: ["tactics", "calculation", "king_safety"],
    opening: "中局戰術",
    variation: "牽制壓力：Bb5",
    goal: "用主教牽制騎士，讓對方王和后之間產生戰術壓力。",
    startFen: "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 2 3",
    moves: ["Bb5"],
    ideas: [
      "Bb5 牽制 c6 騎士，因為它後面連著黑王。",
      "牽制不一定馬上贏子，但會限制對方可選回應。",
      "復盤常漏戰術時，要留意自己的長線子是否能製造牽制。"
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
  },
  {
    id: "endgame-rook-activity",
    phase: "endgame",
    type: "guided",
    tags: ["endgame", "conversion", "activity"],
    opening: "殘局訓練",
    variation: "車的活躍性",
    goal: "在車兵殘局中把車放到主動位置，限制對方王與兵。",
    startFen: "8/5pk1/6p1/3R4/7P/6P1/5PK1/3r4 w - - 0 1",
    moves: ["Rd7"],
    ideas: [
      "車兵殘局裡，主動車通常比被動守兵更重要。",
      "Rd7 讓白車進入第七排，攻擊兵並限制黑王。",
      "如果復盤殘局常慢慢丟優勢，先練車的活躍位置。"
    ]
  },
  {
    id: "endgame-king-opposition",
    phase: "endgame",
    type: "guided",
    tags: ["endgame", "conversion", "king_safety"],
    opening: "殘局訓練",
    variation: "王兵殘局：靠近中心",
    goal: "用國王靠近中心支援通路兵，避免只推兵造成失控。",
    startFen: "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1",
    moves: ["Kf4"],
    ideas: [
      "王兵殘局裡，國王的位置通常比多走一步兵更重要。",
      "Kf4 讓白王靠近中心，支援 e 兵前進。",
      "殘局不要只看能不能推兵，也要看王能不能站到關鍵格。"
    ]
  },
  {
    id: "endgame-king-activation",
    phase: "endgame",
    type: "guided",
    tags: ["endgame", "conversion", "activity"],
    opening: "殘局訓練",
    variation: "王的活躍化",
    goal: "在簡化後讓國王走向中心，主動參與攻防。",
    startFen: "8/8/5k2/8/4P3/4K3/8/8 w - - 0 1",
    moves: ["Kd4"],
    ideas: [
      "殘局的王是強子，不應該一直留在後方。",
      "Kd4 讓白王搶中心，支援自己的兵並限制黑王。",
      "如果復盤殘局常無計畫移動，先練王的中心化。"
    ]
  },
  {
    id: "endgame-lucena-bridge",
    phase: "endgame",
    type: "guided",
    tags: ["endgame", "promotion", "conversion"],
    opening: "殘局訓練",
    variation: "車兵升變：架橋概念",
    goal: "在車兵殘局中用車遮擋將軍，幫通路兵完成升變。",
    startFen: "4K3/4P3/8/8/8/8/4r3/4R1k1 w - - 0 1",
    moves: ["Rg1+"],
    ideas: [
      "車兵升變常需要先處理對方車的將軍騷擾。",
      "Rg1+ 把車放到能遮擋與反將的位置，準備讓兵前進。",
      "這題不是背完整理論，而是理解車要幫兵擋住檢查線。"
    ]
  },
  {
    id: "sicilian-black-setup",
    phase: "opening",
    type: "opening",
    difficulty: 2,
    side: "black",
    tags: ["opening", "development", "center"],
    opening: "西西里防禦",
    variation: "黑方基本發展",
    goal: "用 ...c5 從側翼反擊中心，再以 ...d6、...Nf6 完成穩健發展。",
    moves: ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6"],
    ideas: [
      "...c5 不直接占據中心，而是立刻向 d4 施壓。",
      "...d6 支援中心並替后翼主教保留發展選擇。",
      "交換 d4 兵後用 ...Nf6 攻擊 e4，黑方要靠子力活動平衡空間。"
    ]
  },
  {
    id: "caro-kann-black-center",
    phase: "opening",
    type: "opening",
    difficulty: 2,
    side: "black",
    prerequisites: ["sicilian-black-setup"],
    tags: ["opening", "development", "center"],
    opening: "卡羅康防禦",
    variation: "中心交換與主教出子",
    goal: "用 ...c6、...d5 建立中心，交換後讓后翼主教在兵鏈外發展。",
    moves: ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5"],
    ideas: [
      "...c6 的目的不是被動防守，而是準備以 ...d5 挑戰白方中心。",
      "...dxe4 後要接續發展，不能只顧著守住多出來的兵。",
      "...Bf5 先把主教放到兵鏈外，是卡羅康常見的發展重點。"
    ]
  },
  {
    id: "black-back-rank-mate",
    phase: "middlegame",
    type: "puzzle",
    difficulty: 1,
    side: "black",
    tags: ["tactics", "checkmate", "king_safety"],
    opening: "黑方戰術",
    variation: "底線將殺：Ra1",
    goal: "從黑方視角辨識白王被自己的兵封住時，車可以直接切入底線。",
    startFen: "r5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1",
    moves: ["Ra1#"],
    ideas: [
      "先檢查白王是否有逃生格，再確認車進入底線不會被吃。",
      "從黑方視角練題，可以避免只習慣替白方尋找戰術。",
      "強迫手的順序仍然是將軍、吃子、威脅。"
    ]
  }
];

export const TRAINING_LESSONS = LESSON_CATALOG.map((lesson) => ({
  type: lesson.phase === "opening" ? "opening" : "puzzle",
  difficulty: lesson.phase === "endgame" ? 2 : 1,
  side: "white",
  prerequisites: [],
  ...lesson
}));
