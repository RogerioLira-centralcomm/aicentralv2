#!/usr/bin/env bash
# Cria pasta de teste no disco do servidor (pode apagar depois).
# Rode NO LINUX (SSH no servidor): bash deploy/criar_pasta_teste_pi9999.sh
set -euo pipefail
ROOT="${PI_UPLOAD_ROOT:-/var/www/aicentralv2/instance/uploads/pi}"
BASE="${ROOT}/PI9999__9999"
for s in principal financeiro pecas assinados; do
  mkdir -p "${BASE}/${s}"
  printf '%s\n' "TESTE PI 9999 — seção ${s}. Pode apagar esta pasta inteira: ${BASE}" > "${BASE}/${s}/APAGAR_ME.txt"
done
printf '%s\n' "PASTA DE TESTE — apague: rm -rf ${BASE}" > "${BASE}/LEIA-ME_APAGAR.txt"
chmod -R a+rX "${BASE}" 2>/dev/null || true
echo "OK — criado: ${BASE}"
ls -la "${BASE}"
ls -la "${BASE}/principal"