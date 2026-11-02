"""FastAPI 接口测试。用 TestClient，不启真服务器。
依赖 conftest 的 client fixture：get_service 被 override 成测试库 + savepoint 回滚，
所以这些测试不碰开发库 student_db，跑完不留痕。
"""

from api import app, get_cache


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
    assert "成绩" in r.json()["detail"]


def test_not_found_still_returns_404(client):
    """确认改完异常映射后，"找不到"仍然是 404，没被误伤"""
    assert client.get("/students/99999999").status_code == 404
    assert client.patch("/students/99999999/grade",
                        json={"new_grade": "B"}).status_code == 404
