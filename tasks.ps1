# 测试命令矩阵 —— 改完代码该跑哪条，这里定义
# 用法：.\tasks.ps1 test | unit | integration | e2e | cov | help
#
# 为什么写成脚本而不是背命令：
#   cov 那条有 9 个 --cov，记不住；而脚本本身也是文档，打开就知道有哪些常用操作。
# 为什么不用 .bat：批处理对中文路径和编码支持很差（这台机器历史上就吃过编码的亏）。

param([string]$task = "help")

$py = ".\.venv\Scripts\python.exe"

switch ($task) {
    "test" {
        # 日常全量：不带覆盖率，快
        & $py -m pytest -q
    }
    "unit" {
        # 秒级反馈：不连 MySQL、不连 Redis
        & $py -m pytest -m unit -q
    }
    "integration" {
        # 需要 MySQL（会自动用 alembic 重建测试库）
        & $py -m pytest -m integration -q
    }
    "e2e" {
        # 需要真实启动 uvicorn（M4 才会有用例）
        & $py -m pytest -m e2e -q
    }
    "cov" {
        # 全量 + 覆盖率 + 90% 阈值（低于就退出码 1）
        & $py -m pytest -q --cov=api --cov=service --cov=repository --cov=cache --cov=models --cov=config --cov=db --cov=exceptions --cov=factories --cov-report=term-missing --cov-fail-under=90
    }
    default {
        Write-Host @"
用法: .\tasks.ps1 test|unit|integration|e2e|cov
  test          全量测试（无覆盖率）
  unit          只跑不依赖外部服务的用例
  integration   只跑需要 MySQL 的用例
  e2e           只跑需要真实 HTTP 服务的用例
  cov           全量 + 覆盖率报告 + 90% 阈值
"@
    }
}
