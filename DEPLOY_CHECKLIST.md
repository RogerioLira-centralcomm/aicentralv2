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
