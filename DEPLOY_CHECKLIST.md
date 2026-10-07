# Checklist de Deploy - Painel Admin

## ✅ Pré-requisitos
- [x] Banco de produção já possui todas as tabelas necessárias
- [x] Usuários já estão configurados como admin
- [x] `psycopg[binary]` adicionado ao requirements.txt
- [ ] Código testado localmente
- [ ] Commit e push para repositório

## 🚀 Deploy (Servidor)

### 1. Fazer backup (opcional, por segurança)
```bash
pg_dump -U seu_usuario -d aicentral_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. Executar deploy
```bash
./deploy.sh
```

### 3. Verificar logs
```bash
sudo journalctl -u aicentralv2 -f
```

### 4. Testar painel admin
- [ ] Acessar http://seu-dominio.com/admin/
- [ ] Login funciona
- [ ] Dashboard carrega com estatísticas
- [ ] Navegação entre seções funciona

## ⚠️ Rollback (Se necessário)

```bash
git reset --hard HEAD~1
sudo systemctl restart aicentralv2
```

## Migrações

- A ordem do deploy está em `migrations/ORDER.txt` (`?` opcional, `~` histórico do Reports pré-v2).
- SQL que o deploy não executa fica em `migrations/NOT_IN_DEPLOY.txt`, com categoria e motivo.
- Antes de promover um item `auditar` para o `ORDER.txt`, rode no servidor, somente leitura:
  `venv/bin/python migrations/audit_unlisted.py` (APLICADA, JA-EXISTE, PARCIAL, AUSENTE, SEM-OBJETOS).
- Um `.sql` novo precisa estar no `ORDER.txt`, ser chamado por um `run_*.py` ou constar em `NOT_IN_DEPLOY.txt`.

## Deploy lento: onde olhar

- Ao final (e também quando falha), o `deploy.sh` mostra o tempo de cada etapa, maiores primeiro. O histórico fica em `logs/deploy-timings.log` (uma linha de total e uma por etapa, por deploy, com a revisão).
- O serviço só para para trocar bibliotecas se `pip install --dry-run` disser que algum pacote vai mudar (`Would install ...`). Mudou `requirements.txt` sem pacote novo? O deploy registra o arquivo e segue sem parar o site.
- O `pip` não usa mais `--upgrade`: pacotes sem versão fixa (`torch`, `numpy`...) ficam como estão. Para atualizar de propósito: `PIP_UPGRADE=1 ./deploy.sh`.
- `requirements.txt` aponta o índice de `torch` só para CPU: instalações novas baixam centenas de MB, não GB. Ambientes que já têm `torch` não mudam.
- Para um trace detalhado de uma execução: `PS4='+ $(date +%T) ' bash -x ./deploy.sh 2> logs/deploy-trace.log` e procure os maiores intervalos.
