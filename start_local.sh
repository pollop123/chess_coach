#!/bin/bash

# 本地測試啟動腳本
echo "🚀 啟動 Chess AI 本地測試環境..."

# 檢查是否在正確的目錄
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ 請在專案根目錄執行此腳本"
    exit 1
fi

# 啟動後端
echo "📦 啟動後端服務 (http://localhost:8000)..."
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
elif [ -f "backend/.env" ]; then
    set -a
    source backend/.env
    set +a
fi

cd backend
if [ -x "../.venv/bin/python" ]; then
    ../.venv/bin/python main.py &
else
    python3 main.py &
fi
BACKEND_PID=$!
cd ..

# 等待後端啟動
sleep 3

# 啟動前端
echo "🎨 啟動前端服務 (http://localhost:5173)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ 服務已啟動！"
echo "   前端: http://localhost:5173"
echo "   後端: http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止所有服務"

# 等待中斷信號
trap "echo '🛑 停止服務...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
