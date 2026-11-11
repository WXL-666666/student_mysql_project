"""FastAPI 接口测试。用 TestClient，不启真服务器。
依赖 conftest 的 client fixture：get_service 被 override 成测试库 + savepoint 回滚，
所以这些测试不碰开发库 student_db，跑完不留痕。
"""

from api import app, get_cache
import pytest
pytestmark = pytest.mark.integration
def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"msg": "ok"}


def test_list_students(client):
    r = client.get("/students")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_and_get(client):
    r = client.post("/students", json={"name": "赵六", "age": 21, "grade": "A"})
    assert r.status_code == 201
    sid = r.json()["id"]
    got = client.get(f"/students/{sid}")
    assert got.status_code == 200
    assert got.json()["name"] == "赵六"


def test_age_negative_rejected_at_boundary(client):
    # Pydantic 在请求边界就拦，根本没到 service
    r = client.post("/students", json={"name": "X", "age": -1, "grade": "A"})
    assert r.status_code == 422


def test_age_over_150_rejected(client):
    r = client.post("/students", json={"name": "X", "age": 200, "grade": "A"})
    assert r.status_code == 422


def test_empty_grade_rejected(client):
    r = client.post("/students", json={"name": "X", "age": 18, "grade": ""})
    assert r.status_code == 422


def test_not_found_returns_404(client):
    r = client.get("/students/999999999")
    assert r.status_code == 404


def test_change_grade(client):
    r = client.post("/students", json={"name": "钱七", "age": 22, "grade": "C"})
    sid = r.json()["id"]
    g = client.patch(f"/students/{sid}/grade", json={"new_grade": "A"})
    assert g.status_code == 200
    assert g.json()["grade"] == "A"


def test_delete_then_not_found(client):
    r = client.post("/students", json={"name": "孙八", "age": 23, "grade": "B"})
    sid = r.json()["id"]
    d = client.delete(f"/students/{sid}")
    assert d.status_code == 204
    assert client.get(f"/students/{sid}").status_code == 404


def test_get_populates_cache(client):
    # cache-aside：第一次 GET 未命中 → 查库并回填；之后缓存里应有该 key
    r = client.post("/students", json={"name": "缓存测试", "age": 20, "grade": "A"})
    assert r.status_code == 201
    sid = r.json()["id"]

    got = client.get(f"/students/{sid}")
    assert got.status_code == 200
    assert got.json()["name"] == "缓存测试"

    # 第一次 GET 后，fakeredis 缓存里应已有 student:{sid}（无需真实服务器）
    assert client.app.state.test_cache.get(sid) is not None


def test_delete_invalidates_cache(client):
    r = client.post("/students", json={"name": "失效测试", "age": 21, "grade": "C"})
    sid = r.json()["id"]
    client.get(f"/students/{sid}")                       # 触达 → 回填缓存
    assert client.app.state.test_cache.get(sid) is not None

    client.delete(f"/students/{sid}")                    # 删除 → 让缓存失效
    assert client.app.state.test_cache.get(sid) is None  # 缓存已被删


def test_patch_invalidates_cache(client):
    """回归用例：PATCH 改分后必须删缓存，否则 60 秒内都读到旧值"""
    r = client.post("/students", json={"name": "改分失效", "age": 21, "grade": "B"})
    sid = r.json()["id"]

    assert client.get(f"/students/{sid}").json()["grade"] == "B"   # 触达 → 回填缓存
    assert client.app.state.test_cache.get(sid) is not None

    client.patch(f"/students/{sid}/grade", json={"new_grade": "A"})
    assert client.app.state.test_cache.get(sid) is None            # 缓存已被删

    # 再读必须拿到新值；如果 PATCH 漏了 cache.delete，这里会拿到旧值 'B'
    assert client.get(f"/students/{sid}").json()["grade"] == "A"


def test_get_returns_cache_on_second_request(client):
    # 第一次 GET：未命中 → 查库并回填缓存
    r = client.post("/students", json={"name": "缓存命中", "age": 25, "grade": "A"})
    assert r.status_code == 201
    sid = r.json()["id"]

    first = client.get(f"/students/{sid}")
    assert first.status_code == 200

    # 第二次 GET：缓存命中，直接返回（覆盖 api.py 的 `return hit` 分支）
    second = client.get(f"/students/{sid}")
    assert second.status_code == 200
    assert second.json() == first.json()
    # 缓存里确有该 key，证明第二次是从缓存返回、没有再打 DB
    assert client.app.state.test_cache.get(sid) is not None


# ── 降级：Redis 不可用时接口仍然可用 ─────────────────────────
def test_get_student_survives_when_redis_is_down(client, broken_cache):
    """缓存连不上 → 降级查库，返回 200，而不是 500。

    对应真实故障：Redis 服务停掉后，详情接口不该跟着挂。
    """
    app.dependency_overrides[get_cache] = lambda: broken_cache

    r = client.post("/students", json={"name": "降级验证", "age": 20, "grade": "A"})
    assert r.status_code == 201
    sid = r.json()["id"]

    got = client.get(f"/students/{sid}")
    assert got.status_code == 200
    assert got.json()["name"] == "降级验证"


def test_delete_survives_when_redis_is_down(client, broken_cache):
    """缓存删不掉也不该让 DELETE 失败（旧值还有 TTL 兜底）"""
    app.dependency_overrides[get_cache] = lambda: broken_cache

    r = client.post("/students", json={"name": "降级删除", "age": 21, "grade": "B"})
    sid = r.json()["id"]

    assert client.delete(f"/students/{sid}").status_code == 204


# ── 异常状态码语义 ────────────────────────────────────────────
def test_blank_grade_returns_422_not_404(client):
    """空白成绩是"输入不合法"→ 422，不是"学生不存在"→ 404。

    "   " 能绕过 Pydantic 的 min_length=1，落到 service 层才被拦下。
    """
    r = client.post("/students", json={"name": "张八", "age": 22, "grade": "A"})
    sid = r.json()["id"]

    r = client.patch(f"/students/{sid}/grade", json={"new_grade": "   "})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list)                 # 已统一成字段级数组
    assert detail[0]["loc"] == ["body", "grade"]    # 指向哪个字段
    assert "成绩" in detail[0]["msg"]               # 人看得懂的原因


def test_create_blank_grade_returns_422(client):
    """创建入口也要拦空白成绩。

    以前 register 只校验 age，POST grade=" " 会返回 201，空格成绩直接进库；
    而改分时同样的值被拒。一条规则两个入口不一致 —— 这条用例守住创建端。
    """
    r = client.post("/students", json={"name": "空格", "age": 20, "grade": " "})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["loc"] == ["body", "grade"]


def test_422_detail_shape_is_consistent(client):
    """契约一致性：同一个 422，无论谁拦的，body 结构必须一样。

    以前 Pydantic 拦的返回 detail=[{...}]，service 拦的返回 detail="...",
    客户端得写两套解析。现在统一成数组，这条用例防止哪天又分叉。
    """
    pydantic_422 = client.post("/students", json={"name": "X", "age": -1, "grade": "A"})
    sid = client.post("/students", json={"name": "X", "age": 20, "grade": "A"}).json()["id"]
    service_422 = client.patch(f"/students/{sid}/grade", json={"new_grade": "  "})

    for tag, r in (("Pydantic", pydantic_422), ("service", service_422)):
        assert r.status_code == 422, tag
        detail = r.json()["detail"]
        assert isinstance(detail, list), f"{tag} 的 detail 应是数组，实际 {type(detail)}"
        assert {"loc", "msg"} <= set(detail[0]), f"{tag} 的 detail 缺少字段：{detail[0]}"


def test_not_found_still_returns_404(client):
    """确认改完异常映射后，"找不到"仍然是 404，没被误伤"""
    assert client.get("/students/99999999").status_code == 404
    assert client.patch("/students/99999999/grade",
                        json={"new_grade": "B"}).status_code == 404

def test_commit_failed_returns_500_not_201(client):
    """commit 失败时，客户端绝不能拿到「假装成功的 201」。

    验证的是 M2-3 修的时序问题：commit 被移到了路由内、return 之前。
    如果哪天有人把 bundle.session.commit() 删掉（commit 又回到响应之后），
    这条测试会立刻变红——因为 commit 根本不会被调用，异常也不会被抛出来。

    注意：用 pytest.raises 而不是 assert r.status_code >= 500。
    原因是 TestClient 默认 raise_server_exceptions=True——未处理的
    RuntimeError 会「穿透」成测试异常，而不是转成 500 响应。
    （真服务器才会返回 500；TestClient 把异常重新抛出来。）
    """

    session = client.app.state.test_session
    original_commit = session.commit

    # 让这次请求的 commit 抛异常，模拟"提交时数据库出问题"（死锁/连接断开等）
    def boom():
        raise RuntimeError("commit 炸了")

    session.commit = boom
    try:
        with pytest.raises(RuntimeError, match="commit 炸了"):
            client.post("/students", json={"name": "时序", "age": 20, "grade": "A"})
    finally:
        session.commit = original_commit
