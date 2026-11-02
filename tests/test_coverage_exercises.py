r"""第七阶段练习：把覆盖率基线里 Missing 列指向、但还没测到的行补上。

运行（项目根，用项目自带 venv）：
    .venv\Scripts\python.exe -m pytest tests/test_coverage_exercises.py -v

这些练习专挑 pytest.ini 报告里 Missing 指向的行：
    - service.py:24   batch_register 成功路径的 return
    - api.py:40-48    get_session 生成器（正常提交 + 异常回滚）
    - api.py:52       get_service 工厂
    - api.py:58       get_cache 工厂（顺带覆盖 cache.py:21 make_redis_client）

⚠️ 这是【参考实现】。建议你先照着在 test_service.py / test_api.py 里手敲，
   跑通后再删除本文件（或保留也行——它本就是测试，不计入应用覆盖率）。
"""

import pytest
from sqlalchemy.orm import Session

from service import StudentService
from api import get_session, get_service, get_cache
from cache import StudentCache


# ── 练习 1：service.py:24 batch_register 成功路径 ─────────────
def test_batch_register_succeeds(service):
    """全部合法时 batch_register 真的把行写进去并返回 —— 覆盖 service.py:24。"""
    students = service.batch_register([("甲", 18, "A"), ("乙", 20, "B")])
    assert len(students) == 2
    assert students[0].name == "甲"
    assert students[1].age == 20


# ── 练习 2：直接调用 API 的依赖注入工厂 ─────────────────────
def test_get_service_returns_service():
    """get_service 工厂返回 StudentService —— 覆盖 api.py:52。"""
    svc = get_service()
    assert isinstance(svc, StudentService)


def test_get_cache_returns_cache():
    """get_cache 工厂返回 StudentCache；其内部 make_redis_client()（cache.py:21）也一并覆盖。

    注意：redis.Redis(**config) 是【惰性】的，构造时不连服务器，
    所以本测试不需要真的开 Memurai/Redis。
    """
    c = get_cache()
    assert isinstance(c, StudentCache)


# ── 练习 3（进阶）：直测 get_session 生成器 ──────────────────
def test_get_session_happy_path_commits():
    """请求正常结束 → commit + close —— 覆盖 api.py:40,42,43,48。"""
    gen = get_session()
    session = next(gen)            # 进入 yield（40 → 42）
    assert isinstance(session, Session)
    try:
        next(gen)                  # 请求正常结束 → commit(43) + finally close(48)
    except StopIteration:
        pass


def test_get_session_rolls_back_on_error():
    """请求中途抛异常 → rollback + 重新抛出 —— 覆盖 api.py:45,46。"""
    gen = get_session()
    session = next(gen)            # 进入 yield
    # 用 gen.throw 往生成器里注入异常，模拟"请求处理中途出错"
    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("boom"))
    # 异常被 except Exception 捕获：rollback(45) + raise(46)，finally(48) 仍会 close
