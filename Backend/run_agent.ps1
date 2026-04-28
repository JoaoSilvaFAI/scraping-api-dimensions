# Script para rodar o Agent Scraper CLI
$env:TMP="d:\FAI\tmp"
$env:TEMP="d:\FAI\tmp"
$env:UV_PYTHON_INSTALL_DIR="d:\FAI\uv_python"
$env:UV_CACHE_DIR="d:\FAI\uv_cache"
$env:PLAYWRIGHT_BROWSERS_PATH="d:\FAI\pw-browsers"

Write-Host "Iniciando Agent CLI..." -ForegroundColor Green
uv run python agent_scraper.py
