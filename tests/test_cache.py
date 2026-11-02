import time

from cache import REDIS_CONFIG, StudentCache, make_fake_client


def test_miss_then_set_then_hit():
    cache = StudentCache(make_fake_client())

    # 🔮 预测：一开始没缓存 → get 返回 None（未命中）
    assert cache.get(1) is None

    cache.set({"id": 1, "name": "张三", "age": 18, "grade": "A"})

    # 🔮 预测：存入后再 get → 命中，且内容一致
    assert cache.get(1) == {"id": 1, "name": "张三", "age": 18, "grade": "A"}


def test_ttl_expiry():
    cache = StudentCache(make_fake_client())
    cache.set({"id": 2, "name": "李四", "age": 20, "grade": "B"}, ttl=1)

    # 🔮 预测：1 秒后 key 过期，get 又变 None
    time.sleep(1.1)
    assert cache.get(2) is None


# ── 降级：Redis 挂了，缓存层不该把异常抛给调用方 ──────────────
def test_get_degrades_to_miss_when_redis_down(broken_cache):
    """读缓存失败 → 返回 None（未命中），调用方自然回落查库"""
    assert broken_cache.get(1) is None


def test_set_and_delete_do_not_raise_when_redis_down(broken_cache):
    """写/删缓存失败 → 静默忽略，不能连累已经成功的业务操作"""
    broken_cache.set({"id": 1, "name": "张三", "age": 18, "grade": "A"})
    broken_cache.delete(1)


def test_corrupted_cache_value_treated_as_miss():
    """缓存里是脏数据（比如改过结构）→ 当成未命中，而不是 500"""
    client = make_fake_client()
    client.set("student:9", "这不是 JSON")
    assert StudentCache(client).get(9) is None


def test_redis_config_fails_fast():
    """Redis 连不上时必须"快速失败"，否则降级等于没降级。

    实测：不配超时 + 保留默认指数退避重试，一次失败要 26 秒；
    配 1s 超时并关掉退避重试后降到约 1 秒。
    """
    assert REDIS_CONFIG["socket_connect_timeout"] <= 2
    assert REDIS_CONFIG["socket_timeout"] <= 2
