import os
import chromadb
from google import genai
from google.genai import types
import chess
import chess.pgn
import io
import time # 用來做延遲重試

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

        # --- A. 搜尋相似規則 ---
        rule_results = self.rule_collection.query(query_texts=["General chess strategy"], n_results=1)
        rule_text = rule_results['documents'][0][0] if (rule_results['documents'] and rule_results['documents'][0]) else ""

        # --- B. 搜尋相似棋譜 ---
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

        # --- C. 決定語氣 (合併式 Prompt，更適合 Gemma) ---
        
        role_play = "你是一位專業的西洋棋教練。"
        if source_type == "lichess":
            role_play = """
            你是一位親切的西洋棋 YouTuber。
            你發現這局面曾出現在 Eric Rosen 等高手的對局中。
            請用「分享冷知識」的口吻，解釋高手的意圖。
            **重要**：如果這是正常開局 (如 Nf6)，請解釋其戰略價值，不要為了戲劇效果把它說成是陷阱或壞棋。
            """
        elif source_type == "master":
            role_play = "你是一位特級大師，請引用歷史名局進行深度戰略分析。"

        final_prompt = f"""
        {role_play}
        
        [任務目標]:
        你必須根據 [當前盤面] 提供準確的分析。
        
        [當前盤面 (FEN)]: {fen}
        
        [資料庫檢索結果 (僅供參考)]: 
        {similar_game_info}
        
        [通用原則]: {rule_text}
        
        [玩家問題]: {user_question}
        
        [🔥 重要指令 - 絕對遵守]:
        1. **FEN 是唯一的真理**：請先仔細閱讀 FEN 字串確認兵與棋子的實際位置。
        2. **糾正幻覺**：如果 [資料庫檢索結果] 提到的開局（例如西西里防禦 c5）與當前 FEN 不符（例如 FEN 顯示 c 兵在 c7），**請直接忽略檢索結果**，並依據 FEN 判斷正確的開局名稱（例如 Alekhine's Defense）。
        3. **不要瞎掰**：不要分析盤面上不存在的棋步（例如不要說「黑方走了 c5」如果 c 兵根本沒動）。
        4. **不要編造粉絲名稱**。
        
        請開始分析：
        """

        return self.call_gemini_with_fallback(final_prompt)

rag_engine = ChessRAG()