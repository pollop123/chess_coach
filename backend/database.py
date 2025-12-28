from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 使用 SQLite，檔案會存在 backend/games.db
SQLALCHEMY_DATABASE_URL = "sqlite:///./games.db"

# 建立資料庫引擎
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 定義 "Game" 資料表
class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, default=datetime.utcnow)
    player_white = Column(String, default="Human")
    player_black = Column(String, default="AI")
    result = Column(String)  # 例如 "1-0", "0-1", "1/2-1/2"
    pgn = Column(Text)       # 完整的棋譜文字
    fen = Column(String)     # 最後局面的 FEN

# 自動建立資料表
Base.metadata.create_all(bind=engine)