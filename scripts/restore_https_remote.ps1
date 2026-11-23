# Envia e executa deploy/restore_https_products.sh na VPS (requer chave SSH).
# Uso:
#   .\scripts\restore_https_remote.ps1
#   .\scripts\restore_https_remote.ps1 -SshTarget root@72.60.141.141

param(
    [string]$SshTarget = "root@ai.centralcomm.media"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$script = Join-Path $repo "deploy\restore_https_products.sh"
if (-not (Test-Path $script)) {
    throw "Não encontrei deploy/restore_https_products.sh em $repo"
}

Write-Host "Enviando restauração HTTPS para $SshTarget ..."
Write-Host "(Easypanel: para containers Docker em 80/443 antes do certbot)"
Get-Content $script -Raw | ssh $SshTarget "RESTORE_HTTPS_STOP_DOCKER_80_443=1 bash -s"