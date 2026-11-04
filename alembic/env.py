from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from config import DB_CONFIG
from models import Base  # ← 关键 1：把模型的元数据引过来，autogenerate 靠它比对

def get_url():
    """从 config 读连接串，避免在 alembic.ini 里硬编码密码。

    支持三种来源，优先级从高到低：
    1. 代码里注入的 `config.attributes["db_url"]`（测试用，conftest 走这条）
    2. 命令行 `alembic -x db_url=... upgrade head`
    3. 默认：.env 里的开发库（日常迁移用这条）

    这样同一套迁移既能建开发库、也能建测试库——**"迁移是唯一真相"**。
    """
    # 1) 程序内注入（pytest fixture 在内存里传参，不用拼字符串到命令行）
    if "db_url" in config.attributes:
        return config.attributes["db_url"]

    # 2) 命令行 -x 参数
    x_args = context.get_x_argument(as_dictionary=True)
    if "db_url" in x_args:
        return x_args["db_url"]

    # 3) 默认：开发库
    return (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        f"?charset=utf8mb4"
    )
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata  # ← 关键 2：让 Alembic 知道"模型长什么样"

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # 关键 3：离线模式也用我们自己的连接串，而不是 alembic.ini 里的占位符
    config.set_main_option("sqlalchemy.url", get_url())
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # 关键 4：在线模式把连接串塞进 config，覆盖 alembic.ini 的 sqlalchemy.url
    config.set_main_option("sqlalchemy.url", get_url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
