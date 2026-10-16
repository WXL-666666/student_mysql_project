"""FastAPI 接口测试。用 TestClient，不启真服务器。
依赖 conftest 的 client fixture：get_service 被 override 成测试库 + savepoint 回滚，
所以这些测试不碰开发库 student_db，跑完不留痕。
"""


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
