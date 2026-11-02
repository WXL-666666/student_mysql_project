import json
import os

from dotenv import load_dotenv

load_dotenv()  # 读 .env，让下面的 REDIS_CONFIG 能取到 REDIS_*（没配也能用默认值）

import redis  # 真实客户端（连 Redis 服务器时用）

# 和 config.py 同款风格：os.getenv 带默认值，没配也能跑
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "decode_responses": True,  # get 直接返回 str（不是 bytes），json.loads 更顺手
}


def make_redis_client():
    """运行时/本地用：连【真实 Redis 服务器】。"""
    return redis.Redis(**REDIS_CONFIG)


def make_fake_client():
    """测试用：纯内存模拟 Redis，不需要服务器。"""
    import fakeredis

    return fakeredis.FakeStrictRedis(decode_responses=True)


class StudentCache:
    def __init__(self, client):
        # 依赖注入：client 是谁都行（真服务器 or fakeredis），StudentCache 不关心
        self.r = client

    def _key(self, student_id):
        return f"student:{student_id}"

    def get(self, student_id):
        raw = self.r.get(self._key(student_id))
        if raw is None:
            return None  # 未命中
        return json.loads(raw)  # 命中：JSON 字符串还原成 dict

    def set(self, student, ttl=60):
        self.r.set(self._key(student["id"]), json.dumps(student), ex=ttl)

    def delete(self, student_id):
        self.r.delete(self._key(student_id))
