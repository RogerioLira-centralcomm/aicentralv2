# Instala Node.js LTS via winget (se disponível), instala deps npm e gera o CSS de produção
# Execute no PowerShell:  .\scripts\setup_frontend.ps1

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERRO] $msg" -ForegroundColor Red }

Write-Info "Verificando winget..."
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
  Write-Warn "winget não encontrado. Instale Node.js LTS manualmente por https://nodejs.org e reexecute este script."
} else {
  Write-Info "Instalando Node.js LTS (pode demorar)..."
  winget install OpenJS.NodeJS.LTS -e --silent | Out-Null
}

Write-Info "Verificando npm..."
$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
  Write-Err "npm não encontrado. Após instalar Node.js, feche e reabra o VS Code/PowerShell e rode novamente."
  exit 1
}

Write-Info "Instalando dependências do frontend (npm install)..."
npm install

Write-Info "Gerando CSS de produção (npm run build)..."
npm run build

Write-Info "Finalizado. O arquivo CSS deve estar em aicentralv2/static/css/tailwind/output.css"
