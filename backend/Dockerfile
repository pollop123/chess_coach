#
FROM python:3.10-slim

WORKDIR /app

# 安裝系統依賴與賽後分析用 Stockfish。遊戲走子仍使用專案自製引擎。
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

ENV STOCKFISH_PATH=/usr/games/stockfish \
    STOCKFISH_REVIEW_NODES=4000

# 先複製 requirements 並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🔥 關鍵：複製所有程式碼進入映像檔
COPY . .

# 告訴 Docker 我們會用 8000 port
EXPOSE 8000

# 🚀 生產環境啟動指令：使用平台提供的 PORT，沒有設定時預設 8000。
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
