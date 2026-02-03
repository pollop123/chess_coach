#!/usr/bin/env python3
"""測試引擎升級功能"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import chess
    import chess_engine
    
    print("=" * 70)
    print("🚀 測試引擎升級功能")
    print("=" * 70)
    
    # 測試案例 1: 開局局面
    print("\n📋 測試案例 1: 開局局面")
    print("-" * 70)
    board = chess.Board()
    board.push_san("e4")
    board.push_san("e5")
    board.push_san("Nf3")
    
    print(f"FEN: {board.fen()}")
    print(f"棋盤:\n{board}\n")
    
    print("⏳ 計算分析...")
    analysis = chess_engine.get_analysis(board, depth=5)
    
    print(f"\n✅ 分析結果:")
    print(f"  最佳走法: {analysis['best_move'].uci() if analysis['best_move'] else 'None'}")
    print(f"  分數 (cp): {analysis['score']}")
    print(f"  顯示分數: {analysis['eval_display']}")
    print(f"  勝率: {analysis['winning_chance']}%")
    print(f"  搜尋深度: {analysis['depth']}")
    print(f"  節點數: {analysis['nodes']}")
    print(f"  PV Line: {' '.join(analysis['pv'][:5])}")
    
    # 測試案例 2: 殘局局面（應該搜尋更深）
    print("\n" + "=" * 70)
    print("📋 測試案例 2: 殘局局面（測試動態深度）")
    print("-" * 70)
    
    # K+Q vs K
    board_endgame = chess.Board("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1")
    print(f"FEN: {board_endgame.fen()}")
    print(f"棋盤:\n{board_endgame}\n")
    
    print("⏳ 計算分析...")
    analysis_endgame = chess_engine.get_analysis(board_endgame, depth=5)
    
    print(f"\n✅ 分析結果:")
    print(f"  最佳走法: {analysis_endgame['best_move'].uci()}")
    print(f"  分數 (cp): {analysis_endgame['score']}")
    print(f"  顯示分數: {analysis_endgame['eval_display']}")
    print(f"  勝率: {analysis_endgame['winning_chance']}%")
    print(f"  搜尋深度: {analysis_endgame['depth']} (應該比開局更深)")
    print(f"  節點數: {analysis_endgame['nodes']}")
    
    # 測試案例 3: 將死局面
    print("\n" + "=" * 70)
    print("📋 測試案例 3: 將死局面")
    print("-" * 70)
    
    # Back rank mate in 1
    board_mate = chess.Board("6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
    print(f"FEN: {board_mate.fen()}")
    print(f"棋盤:\n{board_mate}\n")
    
    print("⏳ 計算分析...")
    analysis_mate = chess_engine.get_analysis(board_mate, depth=5)
    
    print(f"\n✅ 分析結果:")
    print(f"  最佳走法: {analysis_mate['best_move'].uci()}")
    print(f"  分數 (cp): {analysis_mate['score']}")
    print(f"  顯示分數: {analysis_mate['eval_display']} (應該顯示 M1 或 M2)")
    print(f"  勝率: {analysis_mate['winning_chance']}%")
    
    # 測試格式化函數
    print("\n" + "=" * 70)
    print("🧪 測試評估格式化函數")
    print("-" * 70)
    
    test_scores = [150, -80, 20000, -19995, 500, -1000]
    for score in test_scores:
        display = chess_engine.format_evaluation(score)
        win_chance = chess_engine.calculate_winning_chance(score)
        print(f"  Score {score:6d} cp -> Display: {display:>6s} | Win: {win_chance:5.1f}%")
    
    # 測試遊戲階段檢測
    print("\n" + "=" * 70)
    print("🎮 測試遊戲階段檢測")
    print("-" * 70)
    
    phases = [
        (chess.Board(), "開局"),
        (chess.Board("4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1"), "殘局"),
        (chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"), "中局")
    ]
    
    for board, expected in phases:
        phase = chess_engine.detect_game_phase(board)
        print(f"  子力數: {len(board.piece_map()):2d} -> 階段: {phase:11s} (預期: {expected})")
    
    print("\n" + "=" * 70)
    print("✅ 所有測試完成！")
    print("=" * 70)
    
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
