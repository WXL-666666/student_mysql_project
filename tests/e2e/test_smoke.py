import pytest

pytestmark = pytest.mark.e2e


def test_health_endpoint(api):
    r = api.get("/")
    assert r.status_code == 200
    assert r.json() == {"msg": "ok"}