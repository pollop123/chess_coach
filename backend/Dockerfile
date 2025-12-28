FROM python:3.10-slim

WORKDIR /app

# 先複製 requirements 並安裝 (利用 Docker Cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY . .

# 告訴 Docker 我們會用 8000 port
EXPOSE 8000

# 啟動 FastAPI 伺服器
# --host 0.0.0.0 讓外部可以連線
# --reload 開發模式，改程式碼會自動重啟
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]