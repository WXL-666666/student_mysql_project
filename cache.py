import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # 读 .env，让下面的 REDIS_CONFIG 能取到 REDIS_*（没配也能用默认值）

import redis  # 真实客户端（连 Redis 服务器时用）
from redis.backoff import NoBackoff
from redis.retry import Retry

logger = logging.getLogger(__name__)

# 和 config.py 同款风格：os.getenv 带默认值，没配也能跑
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "127.0.0.1"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "db": int(os.getenv("REDIS_DB", "0")),
    "decode_responses": True,  # get 直接返回 str（不是 bytes），json.loads 更顺手
    # 强制 RESP2 握手。redis-py 8.x 默认走 RESP3（连接时先发 `HELLO 3`），
    # 而 HELLO 是 Redis 6.0 才有的命令 —— 本机装的 Redis 5.0.14 不支持，
    # 会直接抛 ResponseError: unknown command `HELLO`。
    # RESP2 在 Redis 5/6/7/8 上全兼容，所以显式指定更稳。
    "protocol": 2,
    # ── 超时与重试：缓存必须"快速失败" ──────────────────────
    # redis-py 8 默认「无连接超时 + 指数退避重试」，Redis 连不上时要 26s 才报错，
    # 会把整个请求拖死（降级了但降得太慢 = 等于没降级）。
    # 实测：关掉退避重试 + 0.5s 超时后，单次失败耗时从 26.2s 降到约 1s。
    # 本地 Redis 连接是毫秒级，0.5s 已经非常宽松；连远程可调大环境变量。
    "socket_connect_timeout": float(os.getenv("REDIS_CONNECT_TIMEOUT", "0.5")),
    "socket_timeout": float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.5")),
    "retry": Retry(NoBackoff(), 0),
}


def make_redis_client():
    """运行时/本地用：连【真实 Redis 服务器】。"""
    return redis.Redis(**REDIS_CONFIG)


def make_fake_client():
    """测试用：纯内存模拟 Redis，不需要服务器。"""
    import fakeredis

    return fakeredis.FakeStrictRedis(decode_responses=True)


class StudentCache:
    """缓存层。

    设计原则：**缓存是加速手段，不是依赖**。
    Redis 挂掉、超时、返回脏数据时，这里一律降级成"未命中"，
    让调用方回落查库 —— 接口因此不会因为缓存故障而 500。
    """

    def __init__(self, client):
        # 依赖注入：client 是谁都行（真服务器 or fakeredis），StudentCache 不关心
        self.r = client
        # 同一请求内一旦缓存失败过，后续操作直接跳过。
        # 否则一次 GET 会付「读超时 + 写超时」两倍代价。
        # 实例是每请求新建的，所以 Redis 恢复后下一个请求会自动重试。
        self._degraded = False

    def _key(self, student_id):
        return f"student:{student_id}"

    def get(self, student_id):
        try:
            raw = self.r.get(self._key(student_id))
        except redis.RedisError as exc:
            logger.warning("缓存读取失败，降级为直接查库：%s", exc)
            self._degraded = True  # 本请求后续不再碰缓存
            return None  # 降级：当作未命中
        if raw is None:
            return None  # 未命中
        try:
            return json.loads(raw)  # 命中：JSON 字符串还原成 dict
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("缓存内容无法解析，视为未命中：%s", exc)
            return None

    def set(self, student, ttl=60):
        if self._degraded:
            return  # 已经确认缓存不可用，别再花时间
        try:
            self.r.set(self._key(student["id"]), json.dumps(student), ex=ttl)
        except redis.RedisError as exc:
            # 写缓存失败不影响已经成功的业务操作，忽略即可
            self._degraded = True
            logger.warning("缓存写入失败，已忽略：%s", exc)

    def delete(self, student_id):
        if self._degraded:
            return
        try:
            self.r.delete(self._key(student_id))
        except redis.RedisError as exc:
            # 删不掉会留下旧值，但不应让删除接口失败（旧值还会受 TTL 约束）
            self._degraded = True
            logger.warning("缓存删除失败，已忽略：%s", exc)
