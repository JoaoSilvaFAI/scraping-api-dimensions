# Script para rodar o backend redirecionando o cache para o Disco D
$env:TMP="d:\FAI\tmp"
$env:TEMP="d:\FAI\tmp"
$env:UV_PYTHON_INSTALL_DIR="d:\FAI\uv_python"
$env:UV_CACHE_DIR="d:\FAI\uv_cache"
$env:PLAYWRIGHT_BROWSERS_PATH="d:\FAI\pw-browsers"

Write-Host "Iniciando FastAPI na porta 8000..." -ForegroundColor Cyan
uv run uvicorn main:app --host 0.0.0.0 --port 8000
