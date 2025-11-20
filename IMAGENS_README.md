# Configuração de Imagens - URLs Públicas

## Resumo

As imagens geradas pela IA são salvas localmente no servidor e acessíveis via URLs públicas completas. **Não há integração com Google Drive ou serviços de nuvem**.

## Configuração Rápida

### 1. Configure o arquivo `.env`

Copie `.env.example` para `.env` e configure:

```bash
# URL base da aplicação (IMPORTANTE!)
BASE_URL=http://localhost:5000          # Desenvolvimento
# BASE_URL=https://seu-dominio.com      # Produção
```

### 2. Estrutura de Diretórios

```
aicentralv2/
└── static/
    └── uploads/
        └── audiencias/    ← Imagens salvas aqui
```

### 3. Como Funciona

1. **Geração**: IA cria imagem via OpenRouter
2. **Salvamento**: Arquivo salvo em `static/uploads/audiencias/gemini_TIMESTAMP_XXXX.png`
3. **URL Retornada**: `{BASE_URL}/static/uploads/audiencias/gemini_TIMESTAMP_XXXX.png`
4. **Banco de Dados**: URL completa salva em `cadu_audiencias.imagem_url`

### 4. Acesso Externo

Outros sistemas podem acessar diretamente:

```bash
# HTTP GET
curl https://seu-dominio.com/static/uploads/audiencias/gemini_20251120_103045_7891.png

# HTML
<img src="https://seu-dominio.com/static/uploads/audiencias/gemini_20251120_103045_7891.png">
```

## Deploy em Produção

```bash
# 1. Configure o .env com BASE_URL de produção
echo "BASE_URL=https://seu-dominio.com" >> .env

# 2. Execute o deploy
chmod +x deploy.sh
./deploy.sh
```

## Backup (Opcional)

Para fazer backup das imagens:

```bash
# Exemplo com rsync
rsync -avz aicentralv2/static/uploads/audiencias/ /backup/audiencias/
```

## Documentação Completa

Veja `URLS_IMAGENS.md` para detalhes completos sobre:
- Estrutura de URLs
- Configuração nginx
- Limpeza de imagens antigas
- Troubleshooting
- Migração futura para cloud storage

---

**Vantagens:**
- ✅ URLs públicas diretas
- ✅ Sem dependência de serviços terceiros
- ✅ Baixa latência
- ✅ Controle total
- ✅ Sem custos adicionais
