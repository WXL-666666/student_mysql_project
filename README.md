# 学生管理服务（FastAPI + MySQL + Redis）

一个用于练习「分层架构 + 自动化测试」的学生信息增删改查服务。业务很简单，重点在**测试体系怎么搭**。

## 技术栈

| 层 | 选型 |
|---|---|
| Web 框架 | FastAPI 0.162 + Uvicorn |
| ORM | SQLAlchemy 2.1（Declarative + Mapped） |
| 数据库 | MySQL 8.4（InnoDB / utf8mb4） |
| 缓存 | Redis 5.0 + redis-py 8.1（cache-aside） |
| 数据库迁移 | Alembic 1.20 |
| 测试 | pytest 9.2 + pytest-cov + factory_boy + fakeredis |
| CI | GitHub Actions（启动 MySQL 容器跑全量回归） |

## 接口

| 方法 | 路径 | 说明 | 成功码 |
|---|---|---|---|
| GET | `/` | 健康检查 | 200 |
| GET | `/students` | 学生列表 | 200 |
| POST | `/students` | 新增学生 | 201 |
| GET | `/students/{id}` | 单个学生（走缓存） | 200 |
| PATCH | `/students/{id}/grade` | 修改成绩 | 200 |
| DELETE | `/students/{id}` | 删除学生 | 204 |

错误语义：资源不存在 → `404`；输入不合法（含业务规则）→ `422`。

## 快速开始

前置：Python 3.14+、MySQL 8.4+、Redis 5+（Redis 仅运行服务时需要，跑测试不需要）

```powershell
# 1. 创建虚拟环境并安装依赖（用 lock 文件保证版本可复现）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock

# 2. 准备配置（复制模板后【必须】改 DB_PASSWORD）
Copy-Item .env.example .env
notepad .env
#    把 DB_PASSWORD=改成你的密码 换成你本机 MySQL 的真实密码（只能用数字/字母/符号）

# 3. 创建数据库（两个：开发库 + 测试库）
#    ⚠️ 下面的 mysql 命令需要 mysql 客户端在 PATH 里。
#    如果你的 MySQL 是免安装版（解压即用），mysql 不在 PATH，命令会报
#    「无法将"mysql"项识别为 cmdlet...」，把命令换成完整路径即可，例如：
#    & "D:\DevTools\MySQL-8.4.13\bin\mysql.exe" -u root -p -e "CREATE DATABASE ..."
mysql -u root -p -e "CREATE DATABASE student_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
mysql -u root -p -e "CREATE DATABASE student_db_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"

# 4. 建表（用迁移，不要手工建表）
.\.venv\Scripts\alembic.exe upgrade head

# 5. 跑测试
.\.venv\Scripts\python.exe -m pytest -q
# 预期：59 passed

# 6. 启动服务
.\.venv\Scripts\python.exe api.py
# 打开 http://127.0.0.1:8000/docs
```

> 每一步都不要跳。第 3 步建的是**两个**库，测试库漏了会在跑测试时报 `Unknown database 'student_db_test'`。

## 测试体系

**59 个用例 / 行覆盖率 99%（branch 模式，231 条可执行语句）**

```
TOTAL   231   2   99%
```

剩下未覆盖的 2 行是 `api.py` 的 `__main__` 入口守卫，合理不测。

### 分层：按「运行依赖」分，不按「测什么」分

| 文件 | 层 | 依赖 |
|---|---|---|
| `test_service.py` | 业务规则（单元） | **零依赖**，用假 Repository |
| `test_student_model.py` / `test_crud.py` / `test_transaction.py` | 数据存取（集成） | 真实 MySQL |
| `test_repository_constraint.py` | 数据库约束（集成） | 真实 MySQL |
| `test_api.py` | HTTP 接口（集成） | TestClient + 真实 MySQL |
| `test_cache.py` | 缓存行为（单元） | fakeredis |

Service 层用 `FakeStudentRepository` 替身，**不连数据库**，因此可以在没有 MySQL 的机器上跑，速度是微秒级。

### 隔离：savepoint 事务回滚

测试用「外层真实事务 + 内层 SAVEPOINT」，跑完整体回滚：

```python
connection = test_engine.connect()
outer = connection.begin()
session = Session(bind=connection, join_transaction_mode="create_savepoint")
yield session
outer.rollback()
```

好处是**业务代码里的 `commit()` 不需要为测试做任何妥协**，数据库仍然零残留。

### 缓存：既能测命中，也能测故障

- 正常路径用 `fakeredis`，CI 不需要 Redis 服务
- 故障路径用 `BrokenRedisClient`（任何操作都抛连接错误），验证 **Redis 挂掉时接口仍返回 200**
- 缓存层配置了 0.5s 超时 + 关闭退避重试，避免故障时把请求拖死

### 迁移：可重放是硬要求

```powershell
.\.venv\Scripts\alembic.exe downgrade base   # 删表
.\.venv\Scripts\alembic.exe upgrade head     # 从零重建
```

基线迁移是从零 `create_table` 的，所以上面两条命令可以在任何空库上完整重放，不依赖历史表状态。

> 测试库的表结构目前由 SQLAlchemy `create_all` 初始化，迁移的可重放性靠上面这两条命令手工验证。计划改为测试库直接走 `alembic upgrade head`，让每次跑测试都顺带验证迁移。

### CI

`.github/workflows/ci.yml`：push 触发 → 启动 MySQL 8 容器 → 装依赖 → 跑全量测试。

## 项目结构

```
student_mysql_project/
├── api.py              FastAPI 应用（路由 + 依赖注入 + 异常映射）
├── service.py          业务规则层
├── repository.py       数据存取层（无业务判断）
├── models.py           SQLAlchemy 模型（含 CHECK 约束）
├── cache.py            Redis 缓存封装（含降级）
├── exceptions.py       业务异常体系（自带 HTTP 状态码）
├── db.py / config.py   引擎与配置
├── factories.py        测试数据工厂（factory_boy）
├── alembic/            数据库迁移
├── tests/              测试（conftest 提供 db_session / client / broken_cache 等 fixture）
└── .github/workflows/  CI
```

依赖方向是单向的：

```
api.py → service.py → repository.py → models.py
                   ↘ exceptions.py ↗
```

## 已知限制

诚实地列出来，方便评估这个项目的边界：

- **列表接口无分页**，`GET /students` 全表返回，数据量大时会有内存与超时风险
- **测试库用 `create_all` 建表**，迁移脚本未纳入自动化测试（计划改为 `alembic upgrade head`）
- **`name` 无唯一约束**，可以创建重名学生
- **无鉴权**，任何请求都可读写
- **缓存降级是实例级的**：若将来把缓存客户端改为全局单例复用，`_degraded` 标记会退化成永久熔断，需要换成带冷却时间的熔断器
- **无速率限制**，无请求级日志与链路追踪
- 单实例部署，未考虑多副本下的一致性

## 常见问题

**`UnicodeEncodeError: 'latin-1' codec can't encode characters in position 0-5`**

`.env` 里的 `DB_PASSWORD` 还是占位符 `改成你的密码`，或者你填了中文密码。PyMySQL 建连接时会用 latin1 编码密码，非 ASCII 字符必然失败。改成真实密码，且只用数字/字母/常见符号。

**`mysql : 无法将"mysql"项识别为 cmdlet、函数、脚本文件或可运行程序的名称`**

mysql 客户端不在 PATH（免安装版常见）。用完整路径调用，见「快速开始」第 3 步的说明。

**`(1050, "Table 'students' already exists")`**

目标库里已有一张结构不符的旧表。删掉后重跑迁移：

```powershell
& "D:\DevTools\MySQL-8.4.13\bin\mysql.exe" -u root -p -e "DROP TABLE student_db.students"
.\.venv\Scripts\alembic.exe upgrade head
```

**`Unknown database 'student_db_test'`**

测试库没建。回到「快速开始」第 3 步，那里要建**两个**库。

## 常用命令

```powershell
# 测试
.\.venv\Scripts\python.exe -m pytest -q                    # 全量
.\.venv\Scripts\python.exe -m pytest tests\test_service.py  # 只跑不连库的那层

# 迁移
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe downgrade -1

# 起服务
.\.venv\Scripts\python.exe api.py
```
