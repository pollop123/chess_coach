import os
import chromadb
from google import genai
from google.genai import types
import chess
import chess.pgn
import io
import time # 用來做延遲重試
import chess_engine # 匯入我們剛拆分出來的引擎

# 取得 API Key
api_key = os.getenv("GOOGLE_API_KEY")

class ChessRAG:
    def __init__(self):
        # 初始化 ChromaDB
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.rule_collection = self.chroma_client.get_or_create_collection(name="chess_knowledge")
        self.game_collection = self.chroma_client.get_or_create_collection(name="chess_games")
        
        self.client = None
        
        # 🔥 軍火庫設定：優先使用高額度模型
        self.backup_models = [
            "gemma-3-27b-it",         # 👑 主力：根據你的截圖，這隻額度最高 (RPM 30)
            "gemini-2.0-flash",       # 備用：速度快但額度少 (RPM 5)
            "gemini-2.0-flash-lite-preview-02-05", # 備用：Lite版通常比較省
            "gemini-1.5-flash"        # 嘗試抓抓看這隻經典款
        ]
        
        if api_key:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception as e:
                print(f"RAG Init Error: {e}")
        
        # 初始化資料庫 (如果空的才跑)
        if self.rule_collection.count() == 0:
            self.add_knowledge()
        if self.game_collection.count() == 0:
            self.seed_master_games()

    def add_knowledge(self):
        """補回戰術規則庫"""
        print("📚 正在初始化戰術規則庫...")
        documents = [
            "西西里防禦 (Sicilian Defense): 黑方利用 c 兵控制 d4 中心，創造不對稱局面。",
            "法蘭西防禦 (French Defense): 結構堅固但黑方白格主教容易被兵鍊擋住。",
            "開局原則: 控制中心 (e4, d4, e5, d5)，盡早出動騎士與主教，不要重複走同一隻棋子。",
            "捉雙 (Fork): 一個棋子同時攻擊對手兩個目標，通常由騎士或兵發動。",
            "牽制 (Pin): 利用遠程棋子限制對手棋子移動，因為移動後會暴露後方更有價值的目標。",
            "底線弱點 (Back Rank Weakness): 當國王前的兵沒有移動過，且被車在底線將軍時，會形成悶殺。",
            "孤兵 (Isolated Pawn): 沒有鄰兵保護的兵是弱點，但可能控制關鍵格子。"
        ]
        ids = [f"rule_{i}" for i in range(len(documents))]
        self.rule_collection.add(documents=documents, ids=ids)

    def seed_master_games(self):
        # 簡化版種子
        print("🌱 初始化種子棋譜...")
        sample_pgn = """
        [Event "The Immortal Game"]
        [Site "London"]
        [White "Adolf Anderssen"]
        [Black "Lionel Kieseritzky"]
        [Result "1-0"]
        1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5 8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8 15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6 21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0
        """
        pgn = io.StringIO(sample_pgn)
        game = chess.pgn.read_game(pgn)
        board = game.board()
        docs, ids, metas = [], [], []
        for i, move in enumerate(game.mainline_moves()):
            board.push(move)
            docs.append(board.fen())
            ids.append(f"immortal_{i}")
            metas.append({"white": "Anderssen", "black": "Kieseritzky", "result": "1-0", "last_move": move.uci(), "source": "master"})
        self.game_collection.add(documents=docs, ids=ids, metadatas=metas)

    # 🔥 帶有重試與備援機制的呼叫函式
    def call_gemini_with_fallback(self, prompt):
        for model in self.backup_models:
            try:
                # print(f"🤖 嘗試呼叫模型: {model} ...") 
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return response.text
            except Exception as e:
                error_msg = str(e)
                # 判斷是否為額度不足 (429 Resource Exhausted) 或 模型找不到 (404 Not Found)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    print(f"⚠️ 模型 {model} 額度已滿 (喝咖啡中)，切換下一個...")
                    time.sleep(1) 
                    continue 
                elif "404" in error_msg or "NOT_FOUND" in error_msg:
                    print(f"⚠️ 找不到模型 {model} (可能名稱有誤)，跳過...")
                    continue
                else:
                    return f"發生未預期錯誤 ({model}): {error_msg}"
        
        return "❌ 所有 AI 教練都去喝咖啡了 (Quota Exceeded)。請稍後再試。"

    def get_advice(self, fen, move_history, user_question):
        if not self.client: return "錯誤：API Key 未設定"

        # --- 0. 解析歷史紀錄 (Context Awareness) ---
        pgn_text = "無 (開局)"
        if move_history:
            pgn_text = move_history # 直接使用完整的 PGN

        # --- A. 動態檢索規則 (Dynamic Retrieval) ---
        # 如果使用者有問具體問題，就用問題去搜；否則搜通用策略
        search_query = user_question if (user_question and len(user_question) > 3) else "General chess strategy"
        print(f"🔍 RAG 檢索關鍵字: {search_query}")
        
        rule_results = self.rule_collection.query(query_texts=[search_query], n_results=1)
        rule_text = rule_results['documents'][0][0] if (rule_results['documents'] and rule_results['documents'][0]) else "無相關規則"

        # --- B. 搜尋相似棋譜 ---
        # 檢索還是得用 FEN，因為我們要找的是「相似的局面」
        # 如果用 PGN 搜，必須要完全一樣的走法才能搜到，這樣命中率太低
        game_results = self.game_collection.query(query_texts=[fen], n_results=1)
        
        similar_game_info = "無相似歷史對局。"
        source_type = "general" 

        if game_results['documents'] and game_results['documents'][0]:
            dist = game_results['distances'][0][0]
            meta = game_results['metadatas'][0][0]
            
            # 放寬距離讓它容易聯想
            if dist < 0.6:
                white = meta.get('white', '?')
                black = meta.get('black', '?')
                move = meta.get('last_move', '?')
                source = meta.get('source', 'master')
                
                if "lichess" in source:
                    source_type = "lichess"
                    similar_game_info = f"[Lichess 相似局] {white} vs {black}, 高手走了 {move}"
                else:
                    source_type = "master"
                    similar_game_info = f"[歷史名局] {white} vs {black}, 大師走了 {move}"

        # --- C. 決定語氣 ---
        role_play = "你是一位專業的西洋棋教練。"
        if source_type == "lichess":
            role_play = """
            你是一位專業的西洋棋教練。
            你發現這局面曾出現在 Lichess 高手的對局中。
            請用「教學」的口吻，解釋高手的意圖，並指導學生如何學習這個走法。
            """
        elif source_type == "master":
            role_play = "你是一位特級大師，請引用歷史名局進行深度戰略分析。"

        # --- D. 計算合法走法與戰術風險 (防止幻覺與送子) ---
        legal_moves_text = "無"
        risky_moves_text = "無"
        engine_best_move_text = "無"
        
        try:
            board = chess.Board(fen)
            legal_moves = []
            risky_moves = []
            
            # 簡單的子力價值表
            piece_values = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

            for move in board.legal_moves:
                san = board.san(move)
                legal_moves.append(san)
                
                # 檢查是否為送子 (Risky Capture)
                # 邏輯：如果目標格有對手防守，且我方攻擊子力價值 > 被吃掉的子力價值 (虧本交易)
                if board.is_capture(move):
                    target_square = move.to_square
                    attacker_piece = board.piece_at(move.from_square)
                    attacker_value = piece_values.get(attacker_piece.piece_type, 0)
                    
                    # 取得被吃掉的棋子價值 (處理 En Passant)
                    if board.is_en_passant(move):
                        captured_value = 1
                    else:
                        captured_p = board.piece_at(target_square)
                        captured_value = piece_values.get(captured_p.piece_type, 0) if captured_p else 0

                    # 檢查對手是否有防守該格
                    defenders = board.attackers(not board.turn, target_square)
                    if defenders:
                        # 如果我方價值 > 被吃子力價值，且有防守，視為高風險
                        # 例如：馬(3) 吃 兵(1)，有防守 -> 虧 2 分 -> 警告
                        if attacker_value > captured_value:
                            risky_moves.append(f"{san} (丟子風險: 損失 {attacker_value} vs 獲利 {captured_value})")

            legal_moves_text = ", ".join(legal_moves)
            if risky_moves:
                risky_moves_text = ", ".join(risky_moves)
            
            # 🔥 計算引擎最佳步 (Depth=3, 快速計算)
            best_move = chess_engine.get_best_move(board, depth=3)
            if best_move:
                engine_best_move_text = board.san(best_move)
                
        except Exception as e:
            print(f"Tactical Analysis Error: {e}")

        final_prompt = f"""
        {role_play}
        
        [任務目標]:
        你必須根據 [完整棋譜 (PGN)] 與 [當前盤面] 提供準確的分析。
        請特別關注雙方的開局選擇與中局計畫。
        
        [當前盤面 (FEN)]: {fen}
        
        [合法走法列表 (Legal Moves)]: 
        {legal_moves_text}
        (⚠️ 請注意：你建議的任何走法，都必須在這個列表內，否則就是違規！)

        [高風險走法 (Risky Moves - 慎選)]:
        {risky_moves_text}
        (⚠️ 這些走法可能會導致丟子，除非你有明確的戰術理由，否則請避免建議這些步法。)
        
        [引擎推薦 (Engine Suggestion)]:
        {engine_best_move_text}
        (💡 這是電腦計算出的最佳步，請優先考慮分析這一步的優點。)
        
        [完整棋譜 (PGN)]: 
        {pgn_text}
        
        [資料庫檢索結果 (僅供參考)]: 
        {similar_game_info}
        
        [相關戰術規則 ({search_query})]: 
        {rule_text}
        
        [玩家問題]: {user_question}
        
        [🔥 重要指令 - 絕對遵守]:
        1. **合法性檢查**：在建議任何一步棋之前，請先檢查它是否在 [合法走法列表] 中。如果不在，絕對不要建議。
        2. **雙重驗證**：判斷「開局名稱」與「歷史走法」請以 [PGN] 為準；判斷「當前棋子位置」與「戰術威脅」請以 [FEN] 為準。
        3. **戰術優先**：在分析戰略前，先檢查是否有立即的戰術威脅（如：將軍、捉雙、抽后、無根子）。如果有，請優先警告玩家。
        4. **戰術交換檢查**：在建議吃子之前，務必檢查目標格是否有對手防守。若我方子力價值較高（如馬吃兵）且有防守，這是送子 (Blunder)，絕對不要建議。
        5. **具體計算 (Exchange Sequence)**：如果你提到某步棋是「高風險」或「壞棋」，你必須列出具體的交換序列來證明（例如：「白方走 Nxc7，黑方回應 Qxc7，白方損失馬(3分) 換得兵(1分)，淨虧 2 分」）。不要只說「暴露弱點」這種空話。
        6. **糾正幻覺**：如果 [資料庫檢索結果] 與當前盤面衝突，請**直接忽略並保持沉默**，不要在回答中提到「因為不符所以忽略」或「資料庫說...」。
        7. **誠實回答**：如果不確定某個術語或開局，請直說「我不確定」，不要編造不存在的棋理。
        
        請開始分析：
        """

        return self.call_gemini_with_fallback(final_prompt)

rag_engine = ChessRAG()