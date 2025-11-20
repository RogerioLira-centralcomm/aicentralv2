# Configuração de URLs de Imagens - AIcentral v2

## Visão Geral

As imagens geradas pela IA são salvas localmente no servidor e acessíveis via URLs públicas completas. Isso permite que outros sistemas acessem as imagens sem necessidade de autenticação ou integração com serviços de armazenamento em nuvem.

## Como Funciona

### 1. Geração e Armazenamento

Quando uma imagem é gerada:
1. A IA cria a imagem via OpenRouter API
2. A imagem é salva em: `aicentralv2/static/uploads/audiencias/`
3. Nome do arquivo: `gemini_YYYYMMDD_HHMMSS_XXXX.png`
4. URL completa é retornada: `{BASE_URL}/static/uploads/audiencias/gemini_YYYYMMDD_HHMMSS_XXXX.png`

### 2. Configuração da URL Base

No arquivo `.env`, configure a URL base da aplicação:

**Desenvolvimento:**
```bash
BASE_URL=http://localhost:5000
```

**Produção:**
```bash
BASE_URL=https://aicentral.centralcomm.media
```

### 3. Armazenamento no Banco

O campo `imagem_url` na tabela `cadu_audiencias` armazena a URL completa:
```
https://aicentral.centralcomm.media/static/uploads/audiencias/gemini_20251120_103045_7891.png
```

### 4. Acesso Externo

Outros sistemas podem acessar a imagem diretamente via HTTP GET:
```bash
curl https://aicentral.centralcomm.media/static/uploads/audiencias/gemini_20251120_103045_7891.png
```

Ou em HTML:
```html
<img src="https://aicentral.centralcomm.media/static/uploads/audiencias/gemini_20251120_103045_7891.png" alt="Audiência">
```

## Estrutura de Diretórios

```
aicentralv2/
├── static/
│   └── uploads/
│       └── audiencias/           ← Imagens geradas pela IA
│           ├── gemini_20251120_103045_7891.png
│           ├── gemini_20251120_104512_3456.png
│           └── ...
```

## Permissões e Segurança

### Servidor de Produção

Certifique-se de que:
1. O diretório `static/uploads/audiencias/` tem permissões de escrita para o usuário do Flask
2. O servidor web (nginx/apache) está configurado para servir arquivos estáticos
3. HTTPS está habilitado para segurança

### Exemplo nginx:

```nginx
location /static/ {
    alias /var/www/aicentralv2/aicentralv2/static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

## Backup e Manutenção

### Backup Automático

Para fazer backup das imagens, sincronize o diretório com um serviço de backup:

```bash
# Exemplo com rsync
rsync -avz /var/www/aicentralv2/aicentralv2/static/uploads/audiencias/ /backup/audiencias/
```

### Limpeza de Imagens Antigas

O sistema deleta automaticamente imagens antigas quando uma nova é salva para a mesma audiência.

Para limpar imagens órfãs (não referenciadas no banco):

```python
# Script de limpeza (exemplo)
import os
from pathlib import Path
from aicentralv2 import db

# Listar todas as URLs de imagens no banco
urls_no_banco = db.listar_todas_imagens_audiencias()
arquivos_no_banco = [url.split('/')[-1] for url in urls_no_banco]

# Listar arquivos no diretório
upload_dir = Path('aicentralv2/static/uploads/audiencias')
arquivos_no_disco = [f.name for f in upload_dir.glob('*.png')]

# Deletar órfãos
for arquivo in arquivos_no_disco:
    if arquivo not in arquivos_no_banco:
        (upload_dir / arquivo).unlink()
        print(f"Deletado: {arquivo}")
```

## Migração para Cloud Storage (Futuro)

Se futuramente precisar migrar para S3/Cloudinary/Google Cloud Storage:

1. Modificar `image_generation_service.py` para fazer upload direto
2. Atualizar URLs existentes no banco de dados
3. Manter estrutura de URLs públicas

## Troubleshooting

### Imagens não aparecem

1. Verifique se `BASE_URL` está correto no `.env`
2. Confirme que o servidor web serve arquivos de `/static/`
3. Verifique permissões do diretório `uploads/audiencias/`

### URL incorreta

Se a URL estiver com `localhost` em produção:
```bash
# Verifique o .env
grep BASE_URL .env

# Deve ser:
BASE_URL=https://aicentral.centralcomm.media
```

### Espaço em disco

Monitore o uso de espaço:
```bash
du -sh aicentralv2/static/uploads/audiencias/
```

Cada imagem PNG tem aproximadamente 1-3 MB.

---

**Vantagens desta Abordagem:**
- ✅ URLs públicas diretas
- ✅ Sem dependência de serviços terceiros
- ✅ Baixa latência (mesma máquina)
- ✅ Controle total sobre os arquivos
- ✅ Fácil integração com outros sistemas
- ✅ Sem custos adicionais

**Considerações:**
- ⚠️ Requer backup manual ou automatizado
- ⚠️ Espaço em disco limitado ao servidor
- ⚠️ CDN não incluído (pode adicionar nginx cache ou Cloudflare)
