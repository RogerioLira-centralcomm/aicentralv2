# Como colar o script no terminal da Hostinger (passo a passo)

## Parte A — Abrir o terminal

1. Abra o navegador e vá em **https://hpanel.hostinger.com**
2. Faça **login** (e-mail e senha da Hostinger).
3. No menu à esquerda, clique em **VPS** (ou **Servidores**).
4. Clique no servidor cujo IP é **72.60.141.141** (ou o nome que vocês usam para o CentralX).
5. Procure um botão como:
   - **Terminal no navegador**, ou
   - **Browser terminal**, ou
   - **SSH** → **Abrir terminal**
6. Quando abrir a tela preta/verde, você deve ver algo como `root@srv...` ou um cursor piscando. **É aqui que cola.**

## Parte B — Copiar no seu Windows

No PowerShell (ou peça ao Cursor para rodar):

```powershell
Get-Content c:\Users\Dell\VSCodeTestes\aicentralv2\deploy\hostinger_paste_urgent_https.sh -Raw | Set-Clipboard
```

Mensagem de sucesso: o arquivo foi copiado (não aparece nada às vezes; só tente colar).

## Parte C — Colar no terminal Hostinger

1. Clique **dentro** da janela do terminal (um clique na área preta).
2. Cole com:
   - **Ctrl + V**, ou
   - **Ctrl + Shift + V** (alguns terminais no Chrome só aceitam este), ou
   - **Botão direito** → **Colar** / **Paste**
3. **Não** aperte Enter várias vezes antes do script inteiro aparecer. Espere as linhas surgirem.
4. Quando o texto parar de “subir”, aperte **Enter uma vez**.
5. Espere 2–5 minutos (vai instalar coisas e pedir certificado).

No final deve aparecer algo como: `OK — teste no browser: https://ai.centralcomm.media/`

## Se NÃO conseguir colar o script grande

Use os **3 blocos pequenos** abaixo, **na ordem**. Cole cada bloco, Enter, espere terminar (ou pelo menos o prompt `root@` voltar), depois o próximo.

### Bloco 1 — parar Easypanel e testar o app

```bash
for cid in $(docker ps -q 2>/dev/null); do
  docker inspect -f '{{json .HostConfig.PortBindings}}' "$cid" 2>/dev/null | grep -qE '"(80|443)/tcp"' && docker stop "$cid" && docker update --restart=no "$cid"
done
systemctl start gunicorn.service
curl -sS -o /dev/null -w "gunicorn: %{http_code}\n" http://127.0.0.1:8001/ -H "Host: ai.centralcomm.media"
```

Esperado: `gunicorn: 200` ou `302`. Se der `000`, avise antes do bloco 2.

### Bloco 2 — nginx

```bash
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y nginx certbot python3-certbot-nginx
systemctl enable --now nginx
test -f /var/www/aicentralv2/deploy/configure_nginx_upload.sh && bash /var/www/aicentralv2/deploy/configure_nginx_upload.sh
nginx -t && systemctl reload nginx
```

### Bloco 3 — certificado Let's Encrypt (só ai de início se falhar o SAN)

```bash
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email \
  --cert-name centralcomm-products --expand \
  -d ai.centralcomm.media \
  -d workspace.centralcomm.media \
  -d auth.centralcomm.media \
  -d planner.centralcomm.media \
  -d studio.centralcomm.media || \
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email -d ai.centralcomm.media
nginx -t && systemctl reload nginx
echo "FIM — abra https://ai.centralcomm.media/"
```

## Alternativa: subir o arquivo pelo Gerenciador de arquivos

1. No hPanel, na mesma VPS: **Gerenciador de arquivos** (ou SFTP).
2. Envie `hostinger_paste_urgent_https.sh` para `/root/` ou `/var/www/aicentralv2/deploy/`.
3. No terminal:

```bash
chmod +x /root/hostinger_paste_urgent_https.sh
bash /root/hostinger_paste_urgent_https.sh
```

## Teste no seu PC

```powershell
curl.exe -sI https://ai.centralcomm.media/
```

Sem erro de certificado; status **200** ou **302**.