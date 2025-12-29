import os
import berserk
import chess
import chess_engine
import threading
import time

# 取得 Token
API_TOKEN = os.getenv("LICHESS_API_TOKEN")

if not API_TOKEN:
    print("❌ 錯誤：未設定 LICHESS_API_TOKEN")
    print("請在 .env 檔案中設定 LICHESS_API_TOKEN=你的Token")
    exit(1)

# 連線到 Lichess
session = berserk.TokenSession(API_TOKEN)
client = berserk.Client(session=session)

def play_game(game_id):
    """處理單一局遊戲的邏輯"""
    print(f"🎮 開始對局: {game_id}")
    
    # 建立棋盤
    board = chess.Board()
    
    # 訂閱遊戲狀態串流
    stream = client.bots.stream_game_state(game_id)
    
    for event in stream:
        if event['type'] == 'gameFull':
            # 初始化棋盤狀態
            state = event['state']
            moves = state['moves']
            if moves:
                board = chess.Board()
                for move in moves.split():
                    board.push_uci(move)
            
            # 判斷是否輪到我們 (White or Black)
            white_id = event['white'].get('id')
            my_id = client.account.get()['id']
            is_white = (white_id == my_id)
            
            print(f"我是 {'白棋' if is_white else '黑棋'}")
            
            # 如果輪到我，思考並走棋
            if board.turn == (chess.WHITE if is_white else chess.BLACK):
                make_move(game_id, board)

        elif event['type'] == 'gameState':
            # 更新棋盤
            moves = event['moves']
            board = chess.Board()
            if moves:
                for move in moves.split():
                    board.push_uci(move)
            
            # 檢查遊戲是否結束
            if event['status'] != 'started':
                print(f"🏁 遊戲結束: {event['status']}")
                break
            
            # 判斷是否輪到我們
            # 注意：這裡要再確認一次，因為 gameState 事件包含對手的走棋
            # 我們需要知道我是白還是黑，但 gameState 沒給這個資訊
            # 所以我們通常在 gameFull 存下來，或者簡單判斷：
            # 如果 board.turn == 我的顏色，就走棋
            # 這裡簡單點：每次 gameState 更新後，檢查是否輪到「我」
            # 但我怎麼知道我是誰？
            # 比較好的做法是傳入 my_color
            pass 
            
            # 重新判斷輪次 (需要知道我是誰)
            # 由於 stream loop 比較難傳遞變數，我們重新抓一次 user profile 比較保險，或是用 closure
            # 為了效能，我們假設在 gameFull 已經知道顏色
            # 這裡簡化邏輯：如果 board.turn == my_color (需全域或閉包)
            # 讓我們用一個更簡單的邏輯：
            # 每次收到 gameState，我們檢查最後一步是誰走的。
            # 如果最後一步是對手走的，那就輪到我。
            
            # 更好的方法：
            # 我們在 gameFull 已經知道 is_white
            # 這裡直接用
            is_my_turn = board.turn == (chess.WHITE if is_white else chess.BLACK)
            if is_my_turn:
                make_move(game_id, board)

def make_move(game_id, board):
    """思考並走棋"""
    print("🤔 思考中...")
    # 使用我們的引擎算出最佳步
    # 這裡可以設定深度，例如 3 或 4
    best_move = chess_engine.get_best_move(board, depth=3)
    
    if best_move:
        print(f"🚀 下出: {best_move.uci()}")
        # 增加重試機制 (Retry Logic)
        for attempt in range(3):
            try:
                client.bots.make_move(game_id, best_move.uci())
                return # 成功就離開
            except Exception as e:
                print(f"⚠️ 走棋失敗 (嘗試 {attempt+1}/3): {e}")
                time.sleep(1) # 等一秒再試
        print("❌ 放棄走棋 (重試 3 次失敗)")
    else:
        print("❌ 算不出棋步 (可能被將死了或 Bug)")

def main():
    print("🤖 Lichess Bot 啟動中...")
    try:
        profile = client.account.get()
        print(f"✅ 登入成功: {profile['username']} (ID: {profile['id']})")
    except Exception as e:
        print(f"❌ 登入失敗: {e}")
        return

    # 監聽事件 (挑戰、遊戲開始)
    print("👂 正在監聽挑戰...")
    for event in client.bots.stream_incoming_events():
        if event['type'] == 'challenge':
            challenge = event['challenge']
            print(f"⚔️ 收到挑戰: {challenge['challenger']['name']} ({challenge['speed']})")
            
            # 自動接受挑戰 (你可以加條件，例如只接 Blitz/Rapid)
            try:
                client.bots.accept_challenge(challenge['id'])
                print("✅ 已接受挑戰！")
            except Exception as e:
                print(f"❌ 接受失敗: {e}")
        
        elif event['type'] == 'gameStart':
            game_id = event['game']['gameId']
            # 開一個新執行緒去處理這局遊戲 (支援多開)
            t = threading.Thread(target=play_game, args=(game_id,))
            t.start()

if __name__ == "__main__":
    main()
