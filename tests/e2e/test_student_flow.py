import pytest

pytestmark = pytest.mark.e2e

def test_full_crud_flow(api):
    """一条用例走完 增 → 查 → 改 → 删，每步都断言"""
    # 增
    created = api.post("/students", json={"name": "e2e学生", "age": 20, "grade": "A"})
    assert created.status_code == 201
    sid = created.json()["id"]

    # 查（真实 HTTP GET，会走 Redis 缓存）
    got = api.get(f"/students/{sid}")
    assert got.status_code == 200
    assert got.json()["name"] == "e2e学生"

    # 改（没有 PUT，只有 PATCH /students/{id}/grade，body 是 new_grade）
    updated = api.patch(f"/students/{sid}/grade", json={"new_grade": "A+"})
    assert updated.status_code == 200
    assert updated.json()["grade"] == "A+"

    # 改完必须能读到新值（验证缓存失效有没有生效）
    again = api.get(f"/students/{sid}")
    assert again.json()["grade"] == "A+"

    # 删
    assert api.delete(f"/students/{sid}").status_code == 204
    assert api.get(f"/students/{sid}").status_code == 404

