# Verificação do hub Cadu Media Studio

Execute na raiz do projeto:

```sh
node --test tests/frontend/mc-studio-library.test.cjs
node tests/frontend/mc-studio-browser.cjs
```

O teste de navegador requer Python com Jinja2, Playwright e Chromium. `PLAYWRIGHT_MODULE` aceita o caminho do módulo Playwright instalado; `CHROME_PATH` permite usar um executável Chrome existente; `PYTHON` seleciona o interpretador.

O teste renderiza o template de produção com um layout-base mínimo e intercepta as APIs com fixtures locais. Não inicia o backend, não autentica, não envia dados externos e não testa os motores de geração. Artefatos ficam em `tmp/studio-check/`.

Cobre deduplicação inicial, biblioteca acima de 12 itens, busca, links com marca, crédito atrasado, filtros e recuperação de falhas. Verifica ausência de overflow em 1024/768/390px e captura desktop de 1440px. Os testes de estado também cobrem respostas fora de ordem, cancelamento e payload inválido.
