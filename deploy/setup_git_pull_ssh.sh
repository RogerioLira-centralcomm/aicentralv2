#!/bin/bash
# Uso único no servidor: evita "Username for https://github.com" no git pull / deploy.sh
set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
KEY="${HOME}/.ssh/github_aicentralv2"
REMOTE_SSH="git@github.com:RogerioLira-centralcomm/aicentralv2.git"

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

if [[ ! -f "${KEY}" ]]; then
  echo "Gerando chave ${KEY} ..."
  ssh-keygen -t ed25519 -f "${KEY}" -N "" -C "srv-aicentralv2-deploy-key"
  echo ""
  echo "=== COLE ESTA CHAVE no GitHub ==="
  echo "Repo: aicentralv2 → Settings → Deploy keys → Add (Allow write access: OFF)"
  echo ""
  cat "${KEY}.pub"
  echo ""
  echo "Depois de salvar no GitHub, execute este script de novo."
  exit 0
fi

CFG="${HOME}/.ssh/config"
if ! grep -q "IdentityFile ${KEY}" "${CFG}" 2>/dev/null; then
  {
    echo ""
    echo "Host github.com"
    echo "  HostName github.com"
    echo "  User git"
    echo "  IdentityFile ${KEY}"
    echo "  IdentitiesOnly yes"
  } >> "${CFG}"
  chmod 600 "${CFG}"
fi

echo "Testando GitHub ..."
if ! GIT_SSH_COMMAND="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
    ssh -i "${KEY}" -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 | grep -qiE 'successfully authenticated|Hi '; then
  echo "Falha: chave ainda não autorizada no GitHub (deploy key) ou rede bloqueada."
  exit 1
fi

CURRENT="$(git remote get-url origin 2>/dev/null || true)"
if [[ "${CURRENT}" != "${REMOTE_SSH}" ]]; then
  echo "Alterando origin: ${CURRENT:-?} → ${REMOTE_SSH}"
  git remote set-url origin "${REMOTE_SSH}"
fi

echo "Fetch de teste ..."
git fetch origin main
echo "OK. Pode rodar: cd ${REPO_ROOT} && ./deploy.sh"