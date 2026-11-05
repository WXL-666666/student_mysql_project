import os

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "student_db"),
    "port": int(os.getenv("DB_PORT", "3306")),
}


# ── 启动即校验：把「忘改密码」这类问题变成看得懂的报错 ──────────
# 背景：.env 是从 .env.example 复制来的，里面是占位符而不是真实密码。
# 如果不校验，问题会延迟到建连接时才爆，而且报的是完全不相干的错：
#   UnicodeEncodeError: 'latin-1' codec can't encode characters ...
# 新人看到这个根本想不到是「密码没改」。
_PLACEHOLDERS = {
    "",
    "改成你的密码",
    "<your-password>",
    "your_password",
    "your-password",
    "password",
}


def _validate_password(password: str | None) -> None:
    pwd = (password or "").strip()

    if pwd in _PLACEHOLDERS:
        raise RuntimeError(
            "\n"
            "❌ 数据库密码没有配置，或仍是 .env.example 里的占位符。\n"
            f"   当前 DB_PASSWORD = {password!r}\n"
            "\n"
            "   请打开项目根目录的 .env，把这一行改成你本机 MySQL 的真实密码：\n"
            "       DB_PASSWORD=你的密码\n"
            "\n"
            "   注意：.env 是从 .env.example 复制来的，占位符不会自动替换。\n"
        )

    # PyMySQL 在建立连接时会执行 password.encode("latin1")，
    # 因此密码里不能出现中文等非 ASCII 字符，否则报 UnicodeEncodeError。
    try:
        pwd.encode("latin1")
    except UnicodeEncodeError:
        bad = next((c for c in pwd if not c.isascii()), "?")
        raise RuntimeError(
            "\n"
            "❌ DB_PASSWORD 含有非 ASCII 字符，无法用于 MySQL 连接。\n"
            f"   第一个非法字符是：{bad!r}\n"
            "\n"
            "   PyMySQL 会用 latin1 编码密码，所以密码只能是数字、字母和常见符号，\n"
            "   不能包含中文。请换成一个纯英文/数字的密码。\n"
        ) from None


_validate_password(DB_CONFIG["password"])
