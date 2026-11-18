# PI — pastas de arquivos (dev × produção)

## Regra única

| O quê | Onde fica |
|-------|-----------|
| **Arquivos** | Só no **disco Linux** do servidor (`PI_UPLOAD_ROOT`) |
| **Acesso da equipe** | **URL logada** `/cadu_pi/<id>/arquivos/<secao>` (nunca pasta no Windows) |
| **PC de desenvolvimento** | **Não grava** pastas de PI (`PI_FILES_SERVER_ONLY=true`) |

Se tentar usar `C:\...\instance\uploads\pi`, caminho Linux mapeado no Windows ou SSH do app para gravar no servidor, **não é o fluxo suportado**.

---

## `.env` no dev (Windows)

Arquivo de referência: [`pi-arquivos.env.dev.example`](pi-arquivos.env.dev.example)

```env
PI_PASTAS_BACKEND=local
PI_FILES_SERVER_ONLY=true
PI_MAKE_INVITES_ENABLED=false
PI_MAKE_CONFIGURACAO_ENABLED=false
PI_MAKE_ANDAMENTO_ENABLED=false
```

**Não coloque** `PI_UPLOAD_ROOT`, `PI_UPLOAD_REMOTE_SSH`, `PI_STORAGE_SSH_DEV`.

No Windows, `PI_FILES_SERVER_ONLY` fica **ativo por padrão** mesmo se a linha faltar — só desliga com `PI_FILES_SERVER_ONLY=false` (não recomendado).

---

## `.env` em produção (Linux / gunicorn)

Arquivo de referência: [`pi-arquivos.env.production.example`](pi-arquivos.env.production.example)

```env
PI_PASTAS_BACKEND=local
PI_FILES_SERVER_ONLY=false
PI_UPLOAD_ROOT=/var/www/aicentralv2/instance/uploads/pi
PI_MAKE_INVITES_ENABLED=false
PI_MAKE_CONFIGURACAO_ENABLED=false
PI_MAKE_ANDAMENTO_ENABLED=false
BASE_URL=https://ai.centralcomm.media
```

Após alterar o `.env` no servidor: reiniciar o gunicorn.

---

## Fluxo operacional

1. Deploy no servidor com o bloco de **produção** acima.
2. No site (logado): PI → **Gerar pastas** → abrir links Principal / Financeiro / etc.
3. Upload e download só pela interface web.

Smoke a partir do PC:

```powershell
$env:PI_VERIFY_BASE_URL="https://ai.centralcomm.media"
$env:PI_VERIFY_EMAIL="..."
$env:PI_VERIFY_PASSWORD="..."
$env:PI_VERIFY_ID_PI="..."
python scripts/verify_pi_storage.py --remote
```

---

## Teste com o 1º PI da lista (antes do deploy)

```powershell
python scripts/test_pi_primeiro_lista.py
set PI_VERIFY_SERVER_SSH=usuario@servidor
python scripts/test_pi_primeiro_lista.py --servidor
```

Com código novo já publicado (login na URL):

```powershell
set PI_VERIFY_EMAIL=...
set PI_VERIFY_PASSWORD=...
python scripts/test_pi_primeiro_lista.py --remoto
```

---

## Checklist rápido

| Variável | Dev (Windows) | Produção (Linux) |
|----------|---------------|------------------|
| `PI_PASTAS_BACKEND` | `local` / `padrão` | `local` |
| `PI_FILES_SERVER_ONLY` | `true` (padrão) | `false` |
| `PI_UPLOAD_ROOT` | **ausente** | `/var/www/aicentralv2/instance/uploads/pi` |
| `PI_UPLOAD_REMOTE_SSH` | **ausente** | **ausente** |
| Acesso aos arquivos | URL publicada + `--remote` | URL do site (login) |