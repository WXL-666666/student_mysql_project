param([string]$task = "help")

$py = ".\.venv\Scripts\python.exe"

switch ($task) {
    "test"        { & $py -m pytest -q }
    "unit"        { & $py -m pytest -m unit -q }
    "integration" { & $py -m pytest -m integration -q }
    "e2e"         { & $py -m pytest -m e2e -q }
    "cov"         { & $py -m pytest -q --cov=api --cov=service --cov=repository --cov=cache --cov=models --cov=config --cov=db --cov=exceptions --cov=factories --cov-report=term-missing --cov-fail-under=90 }
    default       { Write-Host "用法: .\tasks.ps1 test|unit|integration|e2e|cov" }
}