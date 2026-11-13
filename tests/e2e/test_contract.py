"""M4-3：用 Pydantic 契约断言真实响应。"""
import pytest

from api import StudentOut          # ← 从 api 导入，不是 from conftest

pytestmark = pytest.mark.e2e


def test_response_matches_schema(api):
    """响应必须能被 StudentOut 完整解析——字段缺失/改名/类型不符都会失败"""
    created = api.post("/students", json={"name": "契约", "age": 20, "grade": "A"})
    sid = created.json()["id"]
    try:
        parsed = StudentOut.model_validate(api.get(f"/students/{sid}").json())
        assert parsed.id == sid
        assert parsed.name == "契约"
    finally:
        api.delete(f"/students/{sid}")        # 不收尾就留垃圾（M4-4 会用 fixture 统一做）


def test_response_has_no_extra_fields(api):
    """防止后端把内部字段（密码、软删除标记）暴露出去"""
    created = api.post("/students", json={"name": "字段", "age": 20, "grade": "A"})
    sid = created.json()["id"]
    try:
        body = api.get(f"/students/{sid}").json()
        assert set(body.keys()) == {"id", "name", "age", "grade"}
    finally:
        api.delete(f"/students/{sid}")
