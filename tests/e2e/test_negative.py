import pytest
pytestmark = pytest.mark.e2e

@pytest.mark.parametrize("payload,expect_status,detail_keyword",[
    ({"name":"X","age":-1,"grade":"A"},422,"age"),
    ({"name":"X","age":151,"grade":"A"},422,"age"),
    ({"name":"","age":20,"grade":"A"},422,"name"),
    ({"name":"X","age":20,"grade":""},422,"grade"),
])
def test_invalid_payload(api,payload,expect_status,detail_keyword):
    r = api.post("/students", json=payload)
    assert r.status_code == expect_status
    assert detail_keyword in r.text,f"错误信息里应该提到{detail_keyword},实际是{r.text}"

def test_not_found_detail_is_helpful(api):
    r = api.get("/students/99999999")
    assert r.status_code == 404
    assert "99999999" in r.text,"错误信息里应该带上查的id，方便排查"

def test_blank_grade_returns_422_not_404(api):
    """回归用例：空白成绩曾是404(异常码语义错误)，已修为422"""
    created = api.post("/students", json={"name":"空白","age":20,"grade":"A"})
    sid = created.json()["id"]

    r = api.patch(f"/students/{sid}/grade", json={"new_grade":" "})
    assert r.status_code == 422
    assert "成绩" in r.text 
    
