import pytest
import redis
from sqlalchemy import create_engine,delete
from sqlalchemy.orm import Session

from config import DB_CONFIG
from models import Base,Student
from repository import StudentRepository
from exceptions import StudentNotFoundError
from service import StudentService
TEST_DATABASE = "student_db_test"

TEST_URL = (
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}" 
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{TEST_DATABASE}"
    f"?charset=utf8mb4"
)

test_engine = create_engine(TEST_URL,echo=False)

@pytest.fixture(scope="session",autouse=True)
def prepare_database():
    # 在 conftest.py 的 prepare_database 里临时加一行，跑一次，然后删掉
    Base.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        session.execute(delete(Student))
        session.commit()
    yield

@pytest.fixture
def db_session():
    connection = test_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind = connection,
        join_transaction_mode = "create_savepoint"
    )
    yield session
    session.close()
    outer_transaction.rollback()
    connection.close()

@pytest.fixture
def student_repo(db_session):
    #"""fixture 依赖 fixture：db_session 先准备好，再包一层 Repository"""
    return StudentRepository(db_session)

class FakeStudentRepository:
    """假的 Repository：不连数据库，数据存在内存列表里"""

    def __init__(self):
        self.rows: list[Student] = []
        self._next_id = 1

    def add(self, name, age, grade):
        student = Student(id=self._next_id, name=name, age=age, grade=grade)
        self._next_id += 1
        self.rows.append(student)
        return student

    def get(self, student_id):
        for s in self.rows:
            if s.id == student_id:
                return s
        raise StudentNotFoundError(student_id)

    def list_all(self):
        return list(self.rows)

    def batch_add(self, rows):
        return [self.add(*row) for row in rows]

    def update_grade(self, student_id, new_grade):
        student = self.get(student_id)
        student.grade = new_grade
        return student

    def delete(self, student_id):
        self.rows.remove(self.get(student_id))


@pytest.fixture
def fake_repo():
    return FakeStudentRepository()


@pytest.fixture
def service(fake_repo):
    return StudentService(fake_repo)


# ── FastAPI 测试：TestClient + dependency_overrides ─────────
from fastapi.testclient import TestClient
from api import app, get_service, get_cache
from cache import StudentCache, make_fake_client


class BrokenRedisClient:
    """模拟 Redis 完全不可用：任何操作都抛连接错误。

    用来验证"缓存是加速手段，不是依赖"——Redis 挂了接口也该活着。
    """

    def get(self, key):
        raise redis.ConnectionError("redis is down")

    def set(self, *args, **kwargs):
        raise redis.ConnectionError("redis is down")

    def delete(self, *args, **kwargs):
        raise redis.ConnectionError("redis is down")


@pytest.fixture
def broken_cache():
    """一个永远连不上的缓存，用于验证降级路径"""
    return StudentCache(BrokenRedisClient())

@pytest.fixture
def client():
    """API 测试：override get_service 走测试库 + savepoint 回滚，跑完不留痕。
    同时把 get_cache override 成 fakeredis，所以 API 测试不需要真实 Redis 服务器。"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    fake_cache = StudentCache(make_fake_client())   # 测试用 fakeredis，无需服务器

    def override_get_service():
        return StudentService(StudentRepository(session))

    def override_get_cache():
        return fake_cache

    app.dependency_overrides[get_service] = override_get_service
    app.dependency_overrides[get_cache] = override_get_cache
    c = TestClient(app)
    c.app.state.test_cache = fake_cache   # 暴露给测试，方便断言缓存内部状态
    yield c
    app.dependency_overrides.clear()
    session.close()
    transaction.rollback()
    connection.close()