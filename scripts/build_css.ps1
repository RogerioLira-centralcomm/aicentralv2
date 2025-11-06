# Gera o CSS local (produção) assumindo que Node/npm já estão instalados
# Execute no PowerShell:  .\scripts\build_css.ps1

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Err($msg) { Write-Host "[ERRO] $msg" -ForegroundColor Red }

Write-Info "Verificando npm..."
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
  Write-Err "npm não encontrado. Instale Node.js LTS: https://nodejs.org"
  exit 1
}

Write-Info "Instalando dependências (npm ci se lockfile existir, senão npm install)..."
if (Test-Path package-lock.json) {
  npm ci
} else {
  npm install
}

Write-Info "Executando build (npm run build)..."
npm run build

Write-Info "Build concluído. CSS em aicentralv2/static/css/tailwind/output.css"
