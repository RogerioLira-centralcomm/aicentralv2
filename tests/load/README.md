# Teste de carga inicial — Cadu Conversations

Este ensaio abre **40 conversas novas e independentes ao mesmo tempo** e acompanha o SSE até o evento terminal. Ele mede TTFB, primeiro token, duração total, códigos HTTP, erros e taxa de conclusão.

O script inicia em `dry-run`. Sem `--execute` e a frase de confirmação exata, nenhuma chamada é enviada.

## Preparação

Use uma conta exclusiva de homologação com créditos suficientes. Entre normalmente no Cadu e obtenha, pela aba Network do navegador:

- o valor completo do cabeçalho `Cookie` de uma chamada autenticada;
- o valor de `X-CSRF-Token` da mesma sessão.

Não salve esses valores no repositório ou no histórico do terminal. Exporte-os somente na sessão que executará o teste:

```bash
export CADU_LOAD_BASE_URL="https://workspace.centralcomm.media"
export CADU_LOAD_COOKIE="<cookie da sessão de teste>"
export CADU_LOAD_CSRF="<csrf da sessão de teste>"
```

## Conferência sem tráfego

Este comando apenas mostra o plano e é seguro para preparar agora:

```bash
.venv/bin/python scripts/load_test_conversations.py
```

## Execução posterior com 40 conexões

```bash
.venv/bin/python scripts/load_test_conversations.py \
  --connections 40 \
  --execution-mode fast \
  --execute \
  --confirm RODAR-CARGA-CADU-40 \
  --output /tmp/cadu-load-40.json
```

O limite desta primeira versão é 40 conexões. O script não contém credenciais no relatório.

## Critérios iniciais

- 40 eventos terminais recebidos;
- nenhuma resposta `5xx`;
- nenhuma conversa termina sem evento terminal;
- taxa de sucesso de 100%;
- registrar p50/p95/p99 de TTFB, primeiro token e duração total;
- verificar no servidor saturação de CPU, memória, conexões PostgreSQL, fila e erros do provedor durante a mesma janela.

O resultado desta rodada deve orientar o próximo degrau. Não aumente a concorrência enquanto houver `5xx`, streams sem encerramento, conflito de conversa ou crescimento não recuperado de conexões ao banco.
