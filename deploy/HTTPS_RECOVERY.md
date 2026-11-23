# Recuperação HTTPS (ai.centralcomm.media e família)

## Sintoma

- Browser: conexão não é privada / certificado inválido
- Certificado: **CN=Easypanel** (autoassinado)
- `http://` → **308** para `https://`
- `https://` → **502 Bad Gateway**

Causa: outro processo (geralmente **Easypanel** ou Traefik em Docker) ocupa as portas **80/443** na VPS `72.60.141.141`, em vez do **Nginx + Let's Encrypt** (`centralcomm-products`).

## Urgente — terminal Hostinger (sem git pull)

No PC, copie o script para a área de transferência:

```powershell
Get-Content c:\Users\Dell\VSCodeTestes\aicentralv2\deploy\hostinger_paste_urgent_https.sh -Raw | Set-Clipboard
```

No terminal web Hostinger (como **root**), cole tudo e Enter. Arquivo: [`deploy/hostinger_paste_urgent_https.sh`](hostinger_paste_urgent_https.sh).

## Correção rápida (no servidor, com git)

```bash
cd /var/www/aicentralv2
git pull origin main   # para ter deploy/restore_https_products.sh
sudo bash deploy/restore_https_products.sh
```

## Correção a partir do Windows (quem tem chave SSH em `root@ai.centralcomm.media`)

```powershell
cd c:\Users\Dell\VSCodeTestes\aicentralv2
$env:RESTORE_HTTPS_STOP_DOCKER_80_443 = "1"
Get-Content deploy\restore_https_products.sh -Raw | ssh root@ai.centralcomm.media "RESTORE_HTTPS_STOP_DOCKER_80_443=1 bash -s"
```

Adicione a chave em `%USERPROFILE%\.ssh\` ou use o console web da Hostinger (VPS → Terminal).

## Depois de corrigir

```powershell
curl.exe -sI https://ai.centralcomm.media/
```

Deve retornar **200** ou **302** sem erro de certificado.

## Prevenção

- Não instalar Easypanel/Caddy na mesma VPS sem alinhar com o time.
- O `deploy.sh` não reemite certificado; se `configure_nginx_upload.sh` falhar com aviso de SSL, rode o script de restauração antes de outro deploy.