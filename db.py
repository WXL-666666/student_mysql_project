from sqlalchemy import create_engine
from config import DB_CONFIG
import os


url = (
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    f"?charset=utf8mb4"
    )

echo = os.getenv("DB_ECHO", "false").lower() == "true"
engine = create_engine(
    url,
    echo=echo,                    # ← 想看 SQL 时在 .env 里写 DB_ECHO=true
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,            # ← 这个配得对，防 MySQL 掐掉空闲连接
)