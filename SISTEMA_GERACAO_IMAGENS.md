# Sistema de Geração de Imagens para Audiências

## ✅ Implementação Completa

### Componentes Criados

1. **Migration SQL**
   - ✅ Coluna `imagem_url` adicionada à tabela `cadu_audiencias`
   - Arquivo: `migrations/add_imagem_url_to_audiencias.py`

2. **Serviço de Geração de Imagens**
   - ✅ `services/image_generation_service.py`
   - Função: `preparar_prompt_imagem()` - Gemini 2.5 Flash
   - Função: `gerar_imagem_audiencia()` - GPT-5 Image
   - Função: `armazenar_imagem_local()` - Storage local

3. **Rotas da API**
   - ✅ `/api/preparar-prompt-imagem` (POST)
   - ✅ `/api/gerar-imagem-audiencia` (POST)
   - ✅ `/api/salvar-imagem-audiencia` (POST)

4. **Funções no db.py**
   - ✅ `atualizar_imagem_audiencia()` - Salvar URL no banco

5. **Interface**
   - ✅ Botão "Gerar Imagem" na listagem (desktop e mobile)
   - ✅ Modal responsivo com 2 colunas (prompt e preview)
   - ✅ JavaScript completo para gerenciamento do fluxo

6. **Diretório de Uploads**
   - ✅ `static/uploads/audiencias/` criado

### Como Usar

1. **Acesse a listagem de audiências**
   - URL: `/cadu-audiencias`

2. **Clique no botão de imagem** (ícone de foto) na coluna de ações

3. **O modal abrirá com**:
   - **Coluna 1**: Prompt editável gerado automaticamente pelo Gemini
   - **Coluna 2**: Preview da imagem (vazio inicialmente)

4. **Fluxo**:
   - ✅ Prompt é gerado automaticamente ao abrir
   - ✅ Você pode editar o prompt manualmente
   - ✅ Clique em "Gerar Novo Prompt" para regenerar
   - ✅ Clique em "Gerar Imagem" para criar a imagem
   - ✅ Aguarde 20-40 segundos (loading com feedback visual)
   - ✅ Preview aparece com a imagem gerada
   - ✅ Clique em "Confirmar e Salvar Imagem" para salvar no banco

5. **Imagem salva**:
   - URL é salva no campo `imagem_url` da audiência
   - Arquivo físico em `static/uploads/audiencias/`

### Modelos Utilizados

- **Preparação de Prompt**: `google/gemini-2.0-flash-exp:free` (OpenRouter)
- **Geração de Imagem**: `openai/gpt-4-vision-preview` (temporário)
  - ⚠️ **NOTA**: Quando o modelo `openai/gpt-5-image` estiver disponível no OpenRouter, atualizar em `image_generation_service.py` linha 128

### Configuração

A API Key do OpenRouter é carregada automaticamente do arquivo `.env`:
```python
# A aplicação lê automaticamente de .env
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
```

Certifique-se de que o arquivo `.env` contém sua chave (o arquivo não é commitado no git).

### Custos Estimados

- **Gemini 2.0 Flash**: Gratuito (modelo free)
- **GPT-4 Vision** (temporário): ~$0.01-0.04 por imagem
- **GPT-5 Image** (quando disponível): ~$0.04 por imagem

### Responsividade

- **Desktop**: Modal com 2 colunas lado a lado
- **Mobile**: Modal com 1 coluna (prompt acima, preview abaixo)
- **Preview**: Sempre mantém aspect ratio 16:9

### Tratamento de Erros

✅ Timeout de 30s para preparar prompt
✅ Timeout de 90s para gerar imagem
✅ Loading states com feedback visual
✅ Toasts para sucesso/erro
✅ Validação de prompt mínimo (50 caracteres)

### Próximos Passos (Opcional)

1. **Storage em Cloud** (S3/Cloudinary):
   - Substituir `armazenar_imagem_local()` por `armazenar_imagem_s3()` ou `armazenar_imagem_cloudinary()`
   - Código exemplo já incluído no plano original

2. **Exibir imagem na listagem**:
   - Adicionar coluna/badge mostrando miniatura da imagem
   - Indicador visual "Com imagem" quando houver URL

3. **Atualizar modelo quando disponível**:
   - Trocar `openai/gpt-4-vision-preview` por `openai/gpt-5-image`
   - Verificar documentação OpenRouter para estrutura correta da resposta

### Arquivos Modificados

```
✅ migrations/add_imagem_url_to_audiencias.py (NOVO)
✅ aicentralv2/services/image_generation_service.py (NOVO)
✅ aicentralv2/db.py (função adicionada)
✅ aicentralv2/routes.py (3 rotas adicionadas)
✅ aicentralv2/templates/cadu_audiencias.html (botão + modal + JS)
✅ aicentralv2/static/uploads/audiencias/ (diretório criado)
```

### Teste Rápido

1. Reinicie o servidor Flask
2. Acesse `/cadu-audiencias`
3. Clique no ícone de imagem em qualquer audiência
4. Modal deve abrir com prompt gerado
5. Clique em "Gerar Imagem"
6. Aguarde a geração
7. Confirme e salve

---

**Status**: ✅ IMPLEMENTAÇÃO COMPLETA
**Data**: 19/11/2025
