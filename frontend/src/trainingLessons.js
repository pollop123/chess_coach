export const TRAINING_PHASES = [
  { id: "basics", label: "基礎規則" },
  { id: "opening", label: "開局" },
  { id: "middlegame", label: "中局" },
  { id: "endgame", label: "殘局" }
];

const LESSON_CATALOG = [
  // 基礎規則課：教棋子怎麼走與基本規則，不是教最佳手，所以不走引擎正確性閘門。
  {
    id: "rules-rook-bishop-queen",
    phase: "basics",
    type: "rules",
    tags: ["rules", "piece_movement"],
    opening: "基礎規則",
    variation: "車、象、后怎麼走",
    goal: "認識三種走長距離的棋子：車走直線橫線，象走斜線，后兩種都可以。",
    startFen: "7k/8/8/8/8/8/8/R1BQK3 w - - 0 1",
    moves: ["Ra7", "Kg8", "Bf4", "Kf8", "Qd3", "Ke8"],
    challengeSteps: {
      0: {
        prompt: "車沿著直線或橫線走，一次可以走好幾格。把 a1 的車往上走到 a7。",
        hints: ["車只能沿著同一條直線或同一條橫線移動，中間不能有棋子擋住。", "把車從 a1 一路往上推，停在 a7。"],
        acceptedMoves: [{ san: "Ra7", explanation: "車沿著 a 直線走了六格。只要中間沒有棋子，車可以一次走很遠。" }]
      },
      1: {
        prompt: "象只能走斜線。把 c1 的象斜著走到 f4。",
        hints: ["象永遠斜著走，所以它會一直停在同一種顏色的格子上。", "從 c1 往右上斜走：d2、e3，停在 f4。"],
        acceptedMoves: [{ san: "Bf4", explanation: "象沿著斜線走了三格。c1 是黑格，f4 也是黑格：象永遠待在同一種顏色。" }]
      },
      2: {
        prompt: "后最靈活：可以像車走直線，也可以像象走斜線。把 d1 的后往上走到 d3。",
        hints: ["后結合了車和象的走法，任何直線、橫線、斜線都可以走。", "讓后沿著 d 直線往上走兩格，停在 d3。"],
        acceptedMoves: [{ san: "Qd3", explanation: "后這次像車一樣走直線。下一次它也可以改走斜線。" }]
      }
    },
    ideas: [
      "車：直線、橫線，任意格數。",
      "象：斜線，任意格數，永遠停在同色格。",
      "后：直線、橫線、斜線都可以，是最強的棋子。",
      "這三種棋子都不能跳過其他棋子。"
    ]
  },
  {
    id: "rules-knight",
    phase: "basics",
    type: "rules",
    tags: ["rules", "piece_movement"],
    opening: "基礎規則",
    variation: "騎士（馬）怎麼走",
    goal: "學會騎士的「日」字走法，以及它是唯一能跳過其他棋子的棋子。",
    startFen: "7k/8/8/8/8/8/PPP5/1N2K3 w - - 0 1",
    moves: ["Nc3", "Kg8", "Nd5", "Kf8", "Nf6", "Kg7"],
    challengeSteps: {
      0: {
        prompt: "騎士走「日」字：先直走兩格，再往旁邊一格。它可以跳過前面的兵。把 b1 的騎士跳到 c3。",
        hints: ["騎士的落點和起點會形成一個「日」字（2 格 × 1 格）。前面有兵擋著也沒關係，騎士會跳過去。", "從 b1 往上兩格、往右一格，就是 c3。"],
        acceptedMoves: [{ san: "Nc3", explanation: "騎士跳過了 b2 的兵，落在 c3。只有騎士能這樣跳。" }]
      },
      1: {
        prompt: "再跳一次，把騎士跳到 d5。",
        hints: ["每次跳躍一樣是「兩格加一格」，方向可以任意。", "從 c3 往上兩格、往右一格，就是 d5。"],
        acceptedMoves: [{ san: "Nd5", explanation: "又是一個「日」字：兩格往上、一格往右。" }]
      },
      2: {
        prompt: "最後把騎士跳到 f6。",
        hints: ["也可以先橫走兩格、再直走一格，一樣是「日」字。", "從 d5 往右兩格、往上一格，就是 f6。"],
        acceptedMoves: [{ san: "Nf6", explanation: "這次是橫走兩格、再往上一格。騎士每跳一次，格子顏色都會換一次。" }]
      }
    },
    ideas: [
      "騎士走「日」字：兩格加一格，方向不限。",
      "騎士是唯一可以跳過其他棋子的棋子。",
      "騎士每跳一次都會換到另一種顏色的格子。"
    ]
  },
  {
    id: "rules-pawn",
    phase: "basics",
    type: "rules",
    tags: ["rules", "piece_movement", "promotion"],
    opening: "基礎規則",
    variation: "兵怎麼走、怎麼吃、升變",
    goal: "兵往前走、斜著吃；走到最後一排可以升變成更強的棋子。",
    startFen: "8/1P5k/8/3p4/8/8/4P3/4K3 w - - 0 1",
    moves: ["e4", "Kg6", "exd5", "Kf5", "b8=Q"],
    challengeSteps: {
      0: {
        prompt: "兵只能往前走一格，但還沒走過的兵可以一次走兩格。把 e2 的兵走兩格到 e4。",
        hints: ["兵只能往前，不能後退，也不能橫走。第一次走的時候可以選擇走一格或兩格。", "把 e2 的兵往前推兩格，停在 e4。"],
        acceptedMoves: [
          { san: "e4", explanation: "兵第一次移動可以走兩格，很快就能佔到中間。" },
          { san: "e3", explanation: "走一格也是合法的；只是第一次移動時，兵可以選擇直接走兩格。" }
        ]
      },
      1: {
        prompt: "兵吃子的方式和走路不同：它只能吃斜前方一格的棋子。吃掉 d5 的黑兵。",
        hints: ["兵往前走，但吃子時要斜著吃。正前方有棋子的話，兵反而會被擋住。", "你的兵在 e4，斜前方的 d5 有黑兵，可以吃它。"],
        acceptedMoves: [{ san: "exd5", explanation: "兵斜著吃掉了 d5 的黑兵。記住：兵直走、斜吃。" }]
      },
      2: {
        prompt: "兵走到對方的最後一排時會「升變」，可以變成后、車、象或騎士，通常選后。把 b7 的兵走到 b8 升變成后。",
        hints: ["兵到達最後一排一定要升變，選最強的后最常見。", "把 b7 的兵往前走一格到 b8，升變成后。"],
        acceptedMoves: [{ san: "b8=Q", explanation: "兵升變成后，一下子從最弱的棋子變成最強的棋子。" }]
      }
    },
    ideas: [
      "兵只能往前走一格，第一次可以走兩格。",
      "兵斜著吃子，正前方有棋子時會被擋住。",
      "兵走到最後一排要升變，通常變成后。"
    ]
  },
  {
    id: "rules-check",
    phase: "basics",
    type: "rules",
    tags: ["rules", "check", "king_safety"],
    opening: "基礎規則",
    variation: "王與將軍",
    goal: "王一次走一格；被將軍時一定要馬上解除，可以把王移開，或用其他棋子擋住。",
    startFen: "4r2k/8/8/8/R7/8/8/4K3 w - - 0 1",
    moves: ["Kd2", "Rd8+", "Rd4"],
    challengeSteps: {
      0: {
        prompt: "黑車沿著 e 直線攻擊你的王，這叫「將軍」。被將軍時一定要先解除。把王移到安全的格子。",
        hints: ["王一次只能往任何方向走一格，而且不能走到還會被攻擊的格子。", "把王往左或往右移一格，離開 e 直線（例如 d2）。"],
        acceptedMoves: [
          { san: "Kd2", explanation: "王離開了 e 直線，不再被黑車攻擊。" },
          { san: "Kd1", explanation: "王往左移一格，離開了 e 直線。" },
          { san: "Kf1", explanation: "王往右移一格，離開了 e 直線。" },
          { san: "Kf2", explanation: "王往右上移一格，離開了 e 直線。" },
          { san: "Re4", explanation: "你沒有移動王，而是用車擋在中間。這也是解除將軍的方法！" }
        ]
      },
      1: {
        prompt: "黑車換到 d 直線，又將軍了。這次試試看另一種方法：用你的車擋在中間。",
        hints: ["解除將軍有三種方法：移動王、擋住攻擊的線、吃掉攻擊的棋子。", "你的車在 a4，可以橫走到 d4，擋在黑車和你的王中間。"],
        acceptedMoves: [
          { san: "Rd4", explanation: "車擋在 d4，黑車就攻擊不到你的王了。" },
          { san: "Kc2", explanation: "移動王也能解除將軍。下次也可以試試用車擋住（Rd4）。" },
          { san: "Kc1", explanation: "移動王也能解除將軍。下次也可以試試用車擋住（Rd4）。" },
          { san: "Kc3", explanation: "移動王也能解除將軍。下次也可以試試用車擋住（Rd4）。" },
          { san: "Ke1", explanation: "移動王也能解除將軍。下次也可以試試用車擋住（Rd4）。" },
          { san: "Ke2", explanation: "移動王也能解除將軍。下次也可以試試用車擋住（Rd4）。" },
          { san: "Ke3", explanation: "移動王也能解除將軍。下次也可以試試用車擋住（Rd4）。" }
        ]
      }
    },
    ideas: [
      "王一次走一格，不能走到會被攻擊的格子。",
      "被將軍時一定要解除：移動王、擋住攻擊線，或吃掉攻擊的棋子。",
      "不能走一步讓自己的王被將軍。"
    ]
  },
  {
    id: "rules-mate-stalemate",
    phase: "basics",
    type: "rules",
    tags: ["rules", "checkmate"],
    opening: "基礎規則",
    variation: "將死與逼和",
    goal: "將死才會贏；對手沒被將軍又無路可走是逼和，算和棋。",
    startFen: "7k/8/5K2/8/8/8/8/6Q1 w - - 0 1",
    moves: ["Qg7#"],
    challengeSteps: {
      0: {
        prompt: "找出將死黑王的一步。小心：如果黑王沒被將軍、卻哪裡都不能走，那是「逼和」，會變成和棋。",
        hints: ["將死要同時做到兩件事：正在將軍，而且黑王逃不掉、也吃不掉攻擊它的棋子。", "把后走到 g7，貼著黑王將軍；你的王在 f6 保護著后，黑王吃不掉它。"],
        acceptedMoves: [{ san: "Qg7#", explanation: "后在 g7 將軍，你的王保護著后，黑王沒有地方可逃：將死！如果走 Qg6，黑王沒被將軍又不能動，就會變成逼和。" }]
      }
    },
    ideas: [
      "將死：正在被將軍，而且沒有任何方法解除。",
      "逼和：沒有被將軍，但輪到走的一方沒有任何合法棋步，算和棋。",
      "快贏的時候要特別小心別走成逼和。"
    ]
  },
  {
    id: "rules-special-moves",
    phase: "basics",
    type: "rules",
    tags: ["rules", "castling", "en_passant"],
    opening: "基礎規則",
    variation: "王車易位與吃過路兵",
    goal: "認識兩個特殊規則：王車易位能保護王，吃過路兵是兵的特別吃法。",
    startFen: "4k3/3p4/8/4P3/8/8/5PPP/4K2R w K - 0 1",
    moves: ["O-O", "d5", "exd6"],
    challengeSteps: {
      0: {
        prompt: "王車易位：王往車的方向走兩格，車跳到王的另一邊。條件是王和車都還沒動過、中間沒有棋子、王沒有被將軍，也不會經過被攻擊的格子。現在來易位！",
        hints: ["易位是唯一一次可以同時移動兩個棋子的走法，常用來讓王躲到角落更安全。", "把王從 e1 往右走兩格到 g1，車會自動跳到 f1。"],
        acceptedMoves: [{ san: "O-O", explanation: "王到了 g1、車到了 f1。王躲在兵後面，比留在中間安全。" }]
      },
      1: {
        prompt: "黑兵從 d7 一次走兩格到 d5，剛好停在你的 e5 兵旁邊。這時你可以「吃過路兵」：把它當成只走了一格那樣斜吃掉。",
        hints: ["吃過路兵只能在對方的兵剛走兩格、停在你的兵旁邊時的下一步使用，錯過就不能吃了。", "把你的 e5 兵斜走到 d6，就能吃掉 d5 的黑兵。"],
        acceptedMoves: [{ san: "exd6", explanation: "你的兵走到 d6，d5 的黑兵被吃掉了。這就是吃過路兵。" }]
      }
    },
    ideas: [
      "王車易位：王走兩格，車跳到另一邊；王和車都不能動過。",
      "王被將軍、或要經過被攻擊的格子時，不能易位。",
      "吃過路兵：對方的兵走兩格停在你的兵旁邊，下一步可以斜吃它。"
    ]
  },
  {
    id: "italian-giuoco-piano",
    phase: "opening",
    tags: ["opening", "development", "king_safety"],
    opening: "義大利開局",
    variation: "Giuoco Piano",
    goal: "快速發展子力，主教瞄準 f7，穩定完成短易位。",
    moves: ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d3", "d6", "O-O"],
    challengeSteps: {
      3: {
        prompt: "黑方主教已站到 c5。選一個兼顧發展與王安全的穩健計畫。",
        hints: [
          "不用急著攻擊；先找能準備中心突破或完成王安全的走法。",
          "c3、d3 與 O-O 都符合目前的開局原則。"
        ],
        acceptedMoves: [
          { san: "c3", explanation: "c3 準備 d4，建立義大利開局常見的中心突破。" },
          { san: "d3", explanation: "d3 穩固 e4，讓白方可以安全完成短易位。" },
          { san: "O-O", explanation: "O-O 先處理王安全，再回頭準備 c3、d4。" }
        ]
      }
    },
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
    prerequisites: ["italian-giuoco-piano"],
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
    tags: ["middlegame", "center", "development", "activity"],
    opening: "中局判斷",
    variation: "中心壓力：Re1 支援突破",
    goal: "在完成王翼發展後，用車支援中心兵，為後續突破做準備。",
    startFen: "r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w kq - 0 6",
    moves: ["Re1"],
    challengeSteps: {
      0: {
        prompt: "沒有立即戰術時，找一個能改善中心控制的穩健走法。",
        hints: [
          "先檢查 e4 的支援，以及 c3、d4 的突破準備。",
          "Re1、c3、Nbd2 都能讓更多子力參與中心。"
        ],
        acceptedMoves: [
          { san: "Re1", explanation: "Re1 直接支援 e4，讓後續中心突破更可靠。" },
          { san: "c3", explanation: "c3 為 d4 做準備，建立完整的中心計畫。" },
          { san: "Nbd2", explanation: "Nbd2 完成后翼發展，也能支援 e4 與未來的中心行動。" }
        ]
      }
    },
    ideas: [
      "Re1 先保護 e4，讓白方之後更有餘裕準備 c3、d4。",
      "中局不一定每步都是戰術；先讓子力共同支援中心，通常比單子冒進可靠。",
      "這個局面有多個近似等價的穩健走法，Re1 是可接受的計畫手，不是唯一解。"
    ]
  },
  {
    id: "middlegame-two-knights-fork",
    phase: "middlegame",
    prerequisites: ["middlegame-scholar-mate"],
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
    moves: ["Qe5+"],
    ideas: [
      "后很強，但一旦站到容易被追打的位置，攻擊就會變成送子。",
      "Qe5+ 把后轉到中央，同時用將軍取得節奏並保留攻勢。",
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
    startFen: "7k/8/5KQ1/8/8/8/8/8 w - - 0 1",
    moves: ["Qg7#"],
    ideas: [
      "后很強，但殘局將殺通常需要國王一起控制逃生格。",
      "Qg7# 利用白王控制 g7 周圍的關鍵格，讓黑王無法吃后或逃走。",
      "后王殺王的核心是縮小空間，不是一直無目的將軍。"
    ]
  },
  {
    id: "endgame-pawn-promotion",
    phase: "endgame",
    type: "guided",
    engineMaxCpLoss: 250,
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
    startFen: "8/5pk1/6p1/3R4/7P/6P1/5PK1/r7 w - - 0 1",
    moves: ["Rd7"],
    challengeSteps: {
      0: {
        prompt: "這個車兵殘局沒有強迫戰術。找一個能讓車或兵更主動的走法。",
        hints: [
          "主動車、限制黑王，以及製造通路兵都是合理方向。",
          "Rd7、Rd3、Rd6、h5 都能維持局面並提出具體問題。"
        ],
        acceptedMoves: [
          { san: "Rd7", explanation: "Rd7 進入第七排，攻擊 f7 並限制黑王。" },
          { san: "Rd3", explanation: "Rd3 保持橫向機動，準備從側面攻擊黑兵。" },
          { san: "Rd6", explanation: "Rd6 把車放到主動橫線，同時盯住 g6 與 f7。" },
          { san: "h5", explanation: "h5 固定王翼兵型並爭取製造遠方通路兵。" }
        ]
      }
    },
    ideas: [
      "車兵殘局裡，主動車通常比被動守兵更重要。",
      "Rd7 讓白車進入第七排，同時攻擊 f7 兵並限制黑王。這是近似等價的主動走法，不是唯一解。",
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
    prerequisites: ["endgame-rook-activity"],
    tags: ["endgame", "promotion", "conversion"],
    opening: "殘局訓練",
    variation: "車兵升變：架橋概念",
    goal: "在車兵殘局中用車遮擋將軍，幫通路兵完成升變。",
    startFen: "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 4 1",
    moves: ["Rd1+", "Ke7", "Rd4", "Ke6", "Kc7", "Rc2+", "Kb6", "Rh2", "Rb4"],
    ideas: [
      "Rd1+ 先把防守方國王趕離升變區，再讓自己的王離開兵前方。",
      "Rd4 把車預先放到第四橫線；黑車側面將軍時，白王便能逐步靠近。",
      "最後 Rb4 用車擋住側面將軍，這就是 Lucena 的『架橋』，接著 b 兵可以升變。"
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

// Only unchanged, independently reviewed lesson lines may be used by the postgame recommender.
// Opening lines are manually reviewed; non-opening lines were checked with Stockfish 18 at 50k nodes.
const VERIFIED_LESSON_LINES = {
  "italian-giuoco-piano": "opening|start|e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O|v2:3=c3,d3,O-O",
  "italian-two-knights": "opening|start|e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Bc5 c3 d6 O-O",
  "italian-evans-gambit": "opening|start|e4 e5 Nf3 Nc6 Bc4 Bc5 b4 Bxb4 c3 Ba5 d4",
  "london-system-development": "opening|start|d4 d5 Nf3 Nf6 Bf4 e6 e3 c5 c3 Nc6 Nbd2",
  "sicilian-alapin-center": "opening|start|e4 c5 c3 Nf6 e5 Nd5 d4 cxd4 Nf3 Nc6 cxd4",
  "middlegame-scholar-mate": "puzzle|r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4|Qxf7#",
  "middlegame-center-pressure": "guided|r1bqk2r/ppp2ppp/2np1n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQ1RK1 w kq - 0 6|Re1|v2:0=Re1,c3,Nbd2",
  "middlegame-two-knights-fork": "puzzle|r1bqkb1r/ppp2ppp/2n5/3np1N1/2B5/8/PPPP1PPP/RNBQK2R w KQkq - 0 6|Nxf7",
  "middlegame-hanging-queen": "guided|7r/4k2p/8/7Q/8/8/8/4K3 w - - 0 1|Qe5+",
  "middlegame-back-rank-mate": "puzzle|6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1|Ra8#",
  "middlegame-center-break": "guided|r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2P2N2/PP1P1PPP/RNBQ1RK1 w kq - 4 5|d4",
  "middlegame-pin-pressure": "guided|r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq - 2 3|Bb5",
  "endgame-queen-mate-net": "puzzle|7k/8/5KQ1/8/8/8/8/8 w - - 0 1|Qg7#",
  "endgame-pawn-promotion": "guided|8/4P3/4K3/8/8/8/8/4k3 w - - 0 1|e8=Q",
  "endgame-rook-activity": "guided|8/5pk1/6p1/3R4/7P/6P1/5PK1/r7 w - - 0 1|Rd7|v2:0=Rd7,Rd3,Rd6,h5",
  "endgame-king-opposition": "guided|8/8/4k3/8/4P3/4K3/8/8 w - - 0 1|Kf4",
  "endgame-king-activation": "guided|8/8/5k2/8/4P3/4K3/8/8 w - - 0 1|Kd4",
  "endgame-lucena-bridge": "guided|1K1k4/1P6/8/8/8/8/r7/2R5 w - - 4 1|Rd1+ Ke7 Rd4 Ke6 Kc7 Rc2+ Kb6 Rh2 Rb4",
  "sicilian-black-setup": "opening|start|e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6",
  "caro-kann-black-center": "opening|start|e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5",
  "black-back-rank-mate": "puzzle|r5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 0 1|Ra1#"
};

function lessonLineSignature(lesson) {
  const challengeSignature = Object.entries(lesson.challengeSteps || {})
    .sort(([left], [right]) => Number(left) - Number(right))
    .map(([stepIndex, step]) => (
      // rejectsMainline 會改變引擎閘門覆蓋的走法，翻動它必須重新驗證正確性。
      `${stepIndex}${step.rejectsMainline ? "!" : ""}=${(step.acceptedMoves || []).map((candidate) => candidate.san || candidate).join(",")}`
    ))
    .join(";");
  const base = `${lesson.type}|${lesson.startFen || "start"}|${lesson.moves.join(" ")}`;
  return challengeSignature ? `${base}|v2:${challengeSignature}` : base;
}

export const TRAINING_LESSONS = LESSON_CATALOG.map((lesson) => ({
  type: lesson.phase === "opening" ? "opening" : "puzzle",
  difficulty: lesson.phase === "endgame" ? 2 : 1,
  side: "white",
  prerequisites: [],
  ...lesson,
  recommendationVerified: VERIFIED_LESSON_LINES[lesson.id] === lessonLineSignature({
    type: lesson.type || (lesson.phase === "opening" ? "opening" : "puzzle"),
    startFen: lesson.startFen,
    moves: lesson.moves,
    challengeSteps: lesson.challengeSteps
  })
}));
