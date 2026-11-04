"""分页：先写测试，再实现。这一步的测试应该先红后绿。"""

import pytest

# client fixture 连真测试库 → integration
pytestmark = pytest.mark.integration


def test_list_returns_default_page_size(client):
    """默认只返回 20 条，不是全表"""
    for i in range(25):
        client.post("/students", json={"name": f"学生{i}", "age": 20, "grade": "A"})

    r = client.get("/students")
    assert r.status_code == 200
    assert len(r.json()) == 20          # ← 现在会失败：返回了 25 条


def test_list_respects_offset(client):
    """limit + offset 能翻页，且两页不重叠"""
    for i in range(5):
        client.post("/students", json={"name": f"分页{i}", "age": 20, "grade": "A"})

    page1 = client.get("/students?limit=2&offset=0").json()
    page2 = client.get("/students?limit=2&offset=2").json()

    assert len(page1) == 2 and len(page2) == 2
    assert {s["id"] for s in page1}.isdisjoint({s["id"] for s in page2})


def test_negative_offset_rejected(client):
    """边界值：offset 不能是负数"""
    assert client.get("/students?offset=-1").status_code == 422


def test_limit_over_max_rejected(client):
    """边界值：limit 上限 100，防止有人一次拉全表"""
    assert client.get("/students?limit=101").status_code == 422