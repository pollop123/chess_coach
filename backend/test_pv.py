#!/usr/bin/env python3
"""測試 PV Line 功能"""

import sys
import os

# 確保可以導入本地模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import chess
    import chess_engine
    
    print("=" * 60)
    print("測試 PV Line (預測變例) 功能")
    print("=" * 60)
    
    # 測試一個中局位置 (意大利開局)
    board = chess.Board('r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4')
    print(f'\n📋 當前局面: {board.fen()}')
    print('\n棋盤狀態:')
    print(board)
    print('\n⏳ 正在計算引擎分析 (深度 5)...\n')
    
    analysis = chess_engine.get_analysis(board, depth=5)
    best_move = analysis["best_move"]
    score = analysis["score"]
    pv_line = analysis["pv"]
    
    print(f'✅ 最佳著法: {board.san(best_move)}')
    print(f'📊 評分: {score/100:+.2f}')
    print(f'\n🎯 PV Line (UCI 格式): {" ".join(pv_line)}')
    
    # 轉換為 SAN 格式 (人類可讀)
    print('\n📝 PV Line (標準代數記法):')
    temp_board = board.copy()
    san_moves = []
    for i, uci_move in enumerate(pv_line):
        try:
            move = chess.Move.from_uci(uci_move)
            if move not in temp_board.legal_moves:
                print(f"⚠️  警告: {uci_move} 不是合法步法，停止解析")
                break
            san = temp_board.san(move)
            move_num = temp_board.fullmove_number
            if temp_board.turn == chess.WHITE:
                san_moves.append(f'{move_num}. {san}')
            else:
                san_moves.append(f'{san}')
            temp_board.push(move)
        except Exception as e:
            print(f"⚠️  解析錯誤 ({uci_move}): {e}")
            break
    
    print(' '.join(san_moves))
    
    print('\n' + '=' * 60)
    print('🎓 這就是 AI 教練能看到的「預測變例」')
    print('   現在 RAG 可以用這個資訊進行深度講解了！')
    print('=' * 60)
    
except ImportError as e:
    print(f"❌ 模組導入失敗: {e}")
    print("\n請確認已安裝相依套件:")
    print("  pip3 install python-chess")
    sys.exit(1)
except Exception as e:
    print(f"❌ 執行錯誤: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
