#
FROM python:3.10-slim

WORKDIR /app

# 安裝系統依賴 (有些 Python 套件需要編譯)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# 先複製 requirements 並安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🔥 關鍵：複製所有程式碼進入映像檔
COPY . .

# 告訴 Docker 我們會用 8000 port
EXPOSE 8000

# 🚀 生產環境啟動指令：
# 1. 移除 --reload (生產環境不需要熱重載，且會消耗效能)
# 2. 確保 app 入口點正確 (你原本寫 api:app)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]