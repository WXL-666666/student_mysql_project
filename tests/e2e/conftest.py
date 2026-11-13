"""e2e 层的公共基建：真起一个 uvicorn，打完真端口再关掉。"""
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

HOST = "127.0.0.1"
PROJECT_ROOT = Path(__file__).resolve().parents[2]      # tests/e2e/conftest.py → 项目根


def free_port() -> int:
    """让系统分配一个空闲端口。端口写 0 = 内核随便挑一个空闲的。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def wait_until_ready(base_url: str, proc: subprocess.Popen, timeout: float = 20.0) -> None:
    """轮询 GET /，直到返回 200。

    ⚠️ 三个反面写法：
    - time.sleep(3)：机器慢就 flaky，机器快就白等
    - socket.connect 判就绪：端口能连上只说明"有人监听"，不代表应用能处理请求
    - 只等 HTTP 不看子进程：app 名写错时进程秒退，却要白等满 20 秒
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            # 子进程已经退出（典型原因：模块名/变量名写错），别等了，交给上层去打日志
            raise RuntimeError("服务进程启动后立即退出")
        try:
            if httpx.get(base_url + "/", timeout=0.5).status_code == 200:
                return
        except Exception:
            pass                      # 服务还没起来时连不上，属于预期内，继续等
        time.sleep(0.1)
    raise RuntimeError(f"服务在 {timeout}s 内没就绪：{base_url}")


@pytest.fixture(scope="session")
def live_server():
    """session 级：整个 e2e 会话只起一次服务（启动是固定成本）。"""
    port = free_port()
    base_url = f"http://{HOST}:{port}"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app",
         "--host", HOST, "--port", str(port), "--log-level", "warning"],
        cwd=PROJECT_ROOT,             # 关键：换个目录跑 pytest 也不会 ImportError
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,     # 合并，失败时能一次看到 uvicorn 的原始输出
        text=True,                    # 否则读到的是 bytes，打印出来全是转义
    )
    try:
        wait_until_ready(base_url, proc)
        yield base_url
    except Exception:
        # 起不来时把子进程的原始输出带出来，否则只会看到"没就绪"，等 20 秒毫无线索
        proc.terminate()
        out = proc.communicate(timeout=10)[0]
        raise RuntimeError(f"服务启动失败，子进程输出：\n{out}")
    finally:
        if proc.poll() is None:       # 还活着才杀，避免对已退出进程再发信号
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()           # Windows 上 terminate 偶尔不彻底


@pytest.fixture
def api(live_server):
    """每条用例一个 client；用例结束后清理它创建的数据"""
    created_ids: list[int] = []

    class TrackingClient(httpx.Client):
        """记录所有创建出来的 id，结束时统一删"""
        def post(self, *args, **kwargs):
            r = super().post(*args, **kwargs)
            if r.status_code == 201 and "id" in r.json():
                created_ids.append(r.json()["id"])
            return r

    with TrackingClient(base_url=live_server, timeout=10.0) as client:
        yield client

        # 注意缩进：清理必须还在 with 里面，否则 client 已关闭，
        # delete 会抛异常再被 except 吞掉 —— 看起来跑了，实际一条都没删。
        for sid in created_ids:
            try:
                client.delete(f"/students/{sid}")
            except Exception:
                pass          # 已经被用例自己删掉了，忽略