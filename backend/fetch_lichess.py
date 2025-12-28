import berserk
import chess.pgn
import io
import chromadb
import time

# ---------------------------------------------------------
# 1. 設定
# ---------------------------------------------------------
client = berserk.Client()
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="chess_games")

def ingest_games_from_user(username, max_games=20, perf_type='rapid'):
    """(這個函數保持不變，負責抓單一使用者的棋)"""
    print(f"  📥 正在分析 {username} ({perf_type})...")
    
    try:
        # 設定抓取參數
        games_gen = client.games.export_by_player(
            username, 
            max=max_games, 
            perf_type=perf_type, 
            rated=True, 
            evals=True
        )
        games = list(games_gen)
    except Exception as e:
        print(f"  ⚠️ 跳過 {username}: {e}")
        return 0

    if not games: return 0

    count = 0
    for game_data in games:
        # 只存贏棋 (避免學到輸家的走法)
        winner = game_data.get('winner')
        try:
            white = game_data['players']['white']['user']['name']
            black = game_data['players']['black']['user']['name']
        except: continue

        user_color = 'white' if white.lower() == username.lower() else 'black'
        if winner != user_color: continue 

        pgn_text = game_data.get('moves', '')
        if not pgn_text: continue

        full_pgn = f'[Event "Lichess {perf_type}"]\n[White "{white}"]\n[Black "{black}"]\n[Result "1-0"]\n\n{pgn_text} 1-0'
        
        pgn_io = io.StringIO(full_pgn)
        game_obj = chess.pgn.read_game(pgn_io)
        if not game_obj: continue
            
        board = game_obj.board()
        docs, ids, metas = [], [], []
        move_cnt = 0
        
        for move in game_obj.mainline_moves():
            board.push(move)
            move_cnt += 1
            if move_cnt > 40: break 
            
            docs.append(board.fen())
            ids.append(f"rank_{perf_type}_{game_data['id']}_{move_cnt}")
            metas.append({
                "white": white, "black": black, "result": "1-0",
                "last_move": move.uci(), "source": f"leaderboard_{perf_type}"
            })
            
        if docs:
            try:
                collection.add(documents=docs, ids=ids, metadatas=metas)
                count += 1
            except: pass

    print(f"  ✅ {username} 入庫: {count} 場")
    return count

def fetch_top_players(perf_type='rapid', count=10):
    """
    🔥 自動去抓排行榜前 N 名的玩家 ID
    """
    print(f"\n🏆 正在查詢 Lichess {perf_type.upper()} 排行榜前 {count} 名...")
    try:
        # 抓取排行榜
        leaderboard = client.users.get_leaderboard(perf_type, count)
        # 提取使用者名稱
        top_users = [user['username'] for user in leaderboard]
        print(f"✨ 捕獲高手名單: {', '.join(top_users)}")
        return top_users
    except Exception as e:
        print(f"❌ 查詢排行榜失敗: {e}")
        return []

if __name__ == "__main__":
    print("🚀 啟動「全自動高手收割機」...")
    
    # 設定：你想抓哪種排行榜？抓多少人？
    # 建議：Rapid (快棋) 品質較好，Blitz (超快棋) 數量較多
    target_modes = [
        {'type': 'rapid', 'top_n': 20, 'games_per_person': 10}, 
        # {'type': 'blitz', 'top_n': 10, 'games_per_person': 5} # 也可以把這行打開
    ]

    for mode in target_modes:
        perf = mode['type']
        
        # 1. 自動去抓排行榜名單
        top_players = fetch_top_players(perf_type=perf, count=mode['top_n'])
        
        # 2. 遍歷名單，一個一個抓
        for player in top_players:
            ingest_games_from_user(player, max_games=mode['games_per_person'], perf_type=perf)
            # 禮貌性暫停，避免被 API 封鎖
            time.sleep(1)

    print("\n🏁 收割完成！你的資料庫現在充滿了分數最高的人類智慧！")