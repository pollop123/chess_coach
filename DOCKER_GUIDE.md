# Docker 部署指南

本文件詳細說明如何使用 Docker 部署 Chess AI Coach 專案。

## 目錄

- [架構說明](#架構說明)
- [本地開發](#本地開發)
- [生產部署](#生產部署)
- [常見問題](#常見問題)
- [進階配置](#進階配置)

---

## 架構說明

本專案使用 **Docker Compose** 管理多容器應用：

```
┌─────────────────────────────────────┐
│          Docker Compose             │
├─────────────────┬───────────────────┤
│   Frontend      │     Backend       │
│   (Nginx)       │     (FastAPI)     │
│   Port: 80      │     Port: 8000    │
└─────────────────┴───────────────────┘
```

### 服務說明

| 服務 | 技術 | Port | 說明 |
|------|------|------|------|
| **frontend** | React + Nginx | 80 | 靜態網頁伺服器 |
| **backend** | FastAPI + Uvicorn | 8000 | REST API 服務 |

### Dockerfile 位置

```
chess_ai/
├── backend/Dockerfile       # 後端容器配置
├── frontend/dockerfile      # 前端容器配置
└── docker-compose.yml       # 多容器編排配置
```

---

## 本地開發

### 1. 準備環境變數

**根目錄 `.env`**（用於 Docker Compose）
```bash
# .env
GOOGLE_API_KEY=AIzaSy...你的金鑰
VITE_API_URL=http://localhost:8000
```

**後端 `backend/.env`**
```bash
# backend/.env
GOOGLE_API_KEY=AIzaSy...你的金鑰
LICHESS_API_TOKEN=lip_...  # 選填
```

### 2. 啟動服務

```bash
# 建置並啟動所有服務
docker-compose up --build

# 背景執行（不佔用終端）
docker-compose up -d --build
```

### 3. 訪問應用

| 服務 | URL | 說明 |
|------|-----|------|
| 前端 | http://localhost | 網頁界面 |
| API 文檔 | http://localhost:8000/docs | Swagger UI |
| 健康檢查 | http://localhost:8000 | 測試後端是否啟動 |

### 4. 查看日誌

```bash
# 查看所有服務日誌
docker-compose logs -f

# 只看後端日誌
docker-compose logs -f backend

# 只看前端日誌
docker-compose logs -f frontend
```

### 5. 停止服務

```bash
# 停止並移除容器
docker-compose down

# 同時移除映像檔和卷（完全清理）
docker-compose down --rmi all --volumes
```

---

## 生產部署

### 雲端平台部署（Zeabur / Render / Railway）

#### Step 1: 推送到 GitHub

```bash
git add .
git commit -m "準備部署"
git push origin main
```

#### Step 2: 連接平台

1. 登入 [Zeabur](https://zeabur.com) / [Render](https://render.com) / [Railway](https://railway.app)
2. 新增專案並連接 GitHub 倉庫
3. 平台會自動偵測 `docker-compose.yml`

#### Step 3: 設定環境變數

在平台的環境變數設定中添加：

| 變數名稱 | 值 | 說明 |
|---------|-----|------|
| `GOOGLE_API_KEY` | `AIzaSy...` | Google Gemini API Key |
| `VITE_API_URL` | `https://your-backend-url.com` | 後端公開網址 |
| `LICHESS_API_TOKEN` | `lip_...` | 選填，用於 Lichess Bot |

⚠️ **重要**：`VITE_API_URL` 必須填寫**後端的公開網址**，因為前端在**瀏覽器**執行。

#### Step 4: 部署

- 平台會自動建置和部署
- 建置時間：約 3-5 分鐘
- 完成後會獲得兩個網址：
  - 前端：`https://your-frontend.zeabur.app`
  - 後端：`https://your-backend.zeabur.app`

---

## 常見問題

### Q1: 前端無法連接到後端？

**原因**：`VITE_API_URL` 設定錯誤或未設定

**解決方案**：
```bash
# 檢查前端環境變數
docker-compose exec frontend sh
echo $VITE_API_URL

# 重新建置前端（確保變數打包進去）
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### Q2: 後端啟動失敗？

**可能原因**：
1. API Key 未設定
2. 依賴安裝失敗
3. Port 8000 被佔用

**除錯方法**：
```bash
# 查看後端日誌
docker-compose logs backend

# 進入後端容器檢查
docker-compose exec backend bash
python3 -c "import os; print(os.getenv('GOOGLE_API_KEY'))"

# 測試 API
curl http://localhost:8000
```

### Q3: 開局庫無法載入？

**原因**：`books/gm2001.bin` 檔案不存在

**解決方案**：
```bash
# 檢查檔案是否存在
docker-compose exec backend ls -la books/

# 如果缺少，請確保 Dockerfile 有正確複製
# backend/Dockerfile 第 14 行：COPY . .
```

### Q4: 前端顯示 502 Bad Gateway？

**原因**：Nginx 無法連接到後端

**解決方案**：
```bash
# 確保後端先啟動
docker-compose up -d backend
sleep 5
docker-compose up -d frontend

# 檢查網路連接
docker-compose exec frontend ping backend
```

### Q5: Docker 建置速度太慢？

**優化方法**：
```bash
# 使用 Docker BuildKit（更快的建置引擎）
export DOCKER_BUILDKIT=1
docker-compose build

# 清理未使用的映像檔
docker system prune -a
```

---

## 進階配置

### 自訂 Port

修改 `docker-compose.yml`：

```yaml
services:
  backend:
    ports:
      - "8080:8000"  # 改為 8080
  
  frontend:
    ports:
      - "3000:80"    # 改為 3000
```

### 開發模式熱重載

修改 `backend/Dockerfile`：

```dockerfile
# 開發模式：啟用熱重載
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

並掛載本地目錄：

```yaml
# docker-compose.yml
services:
  backend:
    volumes:
      - ./backend:/app  # 同步本地代碼
```

### 使用外部資料庫

```yaml
services:
  backend:
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/chess
    depends_on:
      - db
  
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: chess
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

### 效能監控

```bash
# 查看容器資源使用
docker stats

# 限制容器記憶體
docker-compose.yml:
  backend:
    mem_limit: 512m
    cpus: 0.5
```

### HTTPS 配置（使用 Nginx Proxy）

```yaml
services:
  nginx-proxy:
    image: jwilder/nginx-proxy
    ports:
      - "443:443"
    volumes:
      - /var/run/docker.sock:/tmp/docker.sock:ro
      - ./certs:/etc/nginx/certs

  frontend:
    environment:
      - VIRTUAL_HOST=yourdomain.com
      - LETSENCRYPT_HOST=yourdomain.com
```

---

## 檔案結構說明

```
chess_ai/
├── docker-compose.yml          # 多容器編排配置
├── .env                        # Docker Compose 環境變數
├── backend/
│   ├── Dockerfile             # 後端容器配置
│   ├── .env                   # 後端環境變數
│   ├── requirements.txt       # Python 依賴
│   ├── api.py                 # FastAPI 入口
│   └── books/                 # 開局庫
│       └── gm2001.bin
└── frontend/
    ├── dockerfile             # 前端容器配置
    ├── .env.local             # 前端本地環境變數（不提交）
    ├── .env.production        # 前端生產環境變數
    └── dist/                  # 建置產物（自動生成）
```

---

## 常用指令速查

| 操作 | 指令 |
|------|------|
| 啟動所有服務 | `docker-compose up -d --build` |
| 停止所有服務 | `docker-compose down` |
| 查看日誌 | `docker-compose logs -f` |
| 重啟服務 | `docker-compose restart backend` |
| 進入容器 | `docker-compose exec backend bash` |
| 查看容器狀態 | `docker-compose ps` |
| 重新建置 | `docker-compose build --no-cache` |
| 清理資源 | `docker system prune -a` |

---

## 支援

遇到問題？請查看：
- [主要 README](README.md)
- [GitHub Issues](https://github.com/pollop123/chess_coach/issues)
- [FastAPI 文檔](https://fastapi.tiangolo.com/)
- [Docker 官方文檔](https://docs.docker.com/)
