import time

from cache import StudentCache, make_fake_client


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
