# Cadu — modelo financeiro e experiência de produto

Implementação local de 15/09/2026. Não há cobrança, chamadas a provedores, OAuth, MCP ou mudança de autenticação. Os estudos anteriores e os editores existentes foram preservados.

## Entradas

- [Produtos e contratação](cadu-platform.html): cinco homes, navegação, contexto, planos, créditos, Skills privadas e fontes conectadas fictícias.
- [Apresentação de 12 slides](cadu-commercial-model.html): inventário, DRE editável no slide 10, sensibilidade e backlog.
- [Componentes por família](cadu-components-v2.html): usa o mesmo CSS dos produtos, com paletas de ação contrastadas.
- [Brand book existente](cadu-brand-system.html): assets raster reaproveitados, sem nova geração ou SVG de marca.
- CentralX: `/parametros/prototipos-cadu`, pelo menu **Parâmetros → Protótipos Cadu**. As rotas administrativas já existentes servem HTML, JS, CSS e imagens relativamente à mesma pasta. Não houve deploy nesta entrega.

## Fonte única e premissas

`cadu-finance.js` expõe funções puras em browser e CommonJS. A DRE e os cenários de sensibilidade compartilham `calculate`; planos usam o mesmo cálculo e defaults. A carteira de interface é um protótipo em memória, não um ledger persistente.

| Entrada | Valor | Evidência |
|---|---:|---|
| Desenvolvimento histórico | R$ 150.000 | Informado pelo usuário; sem auditoria de fatura |
| Devs / RH | R$ 15.000/mês | Informado |
| Infra de desenvolvimento | US$ 1.000/mês | Informado, separado da infraestrutura de produção |
| Servidor e apps | R$ 1.600/mês | Informado |
| IA de produção observada | R$ 250/mês | Informado, não conciliação independente |
| Câmbio | R$ 6,25/US$ | Cenário de planejamento, não previsão confirmada |
| Imposto sobre receita | 17% | Premissa gerencial, não parecer tributário |

Fixos = 15.000 + 1.000 × 6,25 + 1.600 = **22.850**. Burn atual informado = **23.100**. A projeção substitui os R$ 250 pelo custo calculado; nunca soma ambos.

Preço por uso = variável × markup. Contribuição = receita − imposto − variáveis. Resultado operacional = contribuição − recorrentes. Equilíbrio = recorrentes / percentual de contribuição, somente se positivo. Receita zero retorna percentual indefinido, não Infinity. Investimento histórico não é amortizado automaticamente.

### Receita, caixa e utilização

O cenário inicial usa 20 assinantes mensais, 5 anuais, orçamento comercial de US$ 20 e markup 7,5×. São hipóteses, não base comercial real. As três faixas (US$ 5/20/60 de orçamento) e limites de contas/storage/processamento são demonstrativos. Uma unidade de crédito representa R$ 0,10 de preço comercial nesta demonstração; não representa um token técnico ou um valor de custo fixo.

O câmbio da tabela comercial é separado do câmbio de custo para que um choque cambial não reajuste preços automaticamente. Anuais têm desconto zero por padrão e créditos liberados mensalmente. A simulação mostra o multiplicador efetivo após desconto e câmbio.

“Utilização integral” na tabela completa significa 100% da cesta de operações informada por assinante, não necessariamente o resgate de todos os créditos. A cesta é editável por operação. As referências simplificadas de 5×/7,5×/10× assumem resgate integral e nenhum variável adicional; não são garantias de margem. A concentração em vídeo quadruplica segundos mantendo o preço, expondo o risco de uma quota mal dimensionada.

Anuais são reconhecidos mensalmente e recebidos no primeiro mês, com renovações nos meses 13 e 25. Sem churn, atraso, crescimento ou inadimplência neste cenário. A DRE apresentada é o mês 1; o caixa cobre 36 meses. Taxa de pagamento é rateada sobre receita na DRE e paga sobre recebimentos no caixa. O cronograma tributário de caixa é simplificado pelo reconhecimento de receita; validar regime e obrigações reais com financeiro.

Pacotes entram em receita pelo consumo. Caixa recebe as compras. Saldos são consumidos por antiguidade e expiram após 12 meses; quando o saldo acaba, o consumo projetado é limitado ao disponível. Saldo inicial de extras é assumido recém-adquirido. Extras expirados ficam separados como `expiredExtras`, pendentes de política de reconhecimento financeiro; **não há receita de breakage automática**. Ainda é necessário validar reconhecimento e tributação da expiração antes de usar como DRE contábil.

Payback é o primeiro mês em que o caixa operacional acumulado cobre R$ 150 mil. Caixa inicial não conta como recuperação. Antecipações anuais carregam obrigações futuras de serviço; payback de caixa não equivale a lucro ou caixa livre distribuível.

## Inventário de custo e fontes consultadas

Tarifas consultadas em **15/09/2026**. Modelo/provedor podem variar por configuração. Nenhuma credencial ou conta de faturamento foi acessada.

| Operação | Fonte / caminho local | Evidência e lacuna |
|---|---|---|
| Imagem / edição | `creative_image_fidelity.py`; [GPT Image 2](https://openrouter.ai/openai/gpt-image-2) | US$ 0,006 low 1K e US$ 0,22 high 2K são estimativas configuradas. Comentário local já inclui 5,5%. Tabela oficial: texto US$ 5/M; imagem entrada US$ 8/M; imagem saída US$ 30/M. Qualidade, referências, saídas e tentativas precisam de conciliação. |
| Vídeo | `creative_media/settings.py`, `quoting.py`; [Seedance 2.5](https://openrouter.ai/blog/insights/seedance-2-5-review/) | Tokens = largura × altura × 24 × segundos / 1024. US$ 0,0000107/token; referência US$ 0,0000064/token. 720p 8s sem referência = US$ 1,84896 antes de demais taxas. Duração, referência e fallback precisam de registros reais. |
| Voz | `creative_media/quoting.py`; [Gemini TTS](https://openrouter.ai/google/gemini-3.1-flash-tts-preview) | US$ 1/M texto e US$ 20/M áudio. A heurística de caracteres do código não é tokenização faturada. Exemplo do simulador: 1k texto + 2k áudio = US$ 0,041. Transcrição permanece pendente. |
| Conversas | `services/openrouter_service.py`; [GPT-5 mini](https://openrouter.ai/openai/gpt-5-mini) | Exemplo US$ 0,25/M entrada, 2/M saída, cache OpenAI 0,025/M. 2k entrada + 2k saída = US$ 0,0045. Não é o custo de todo modelo disponível. |
| OCR / relatórios | `services/openrouter_service.py` | Tarifa unitária pendente; contar páginas/imagens, tokens, extração, validação, normalização e reprocessamentos. |
| Planner | `smart_planner/models.py` | Estimativa preview completo: US$ 0,54; generation_map completo: US$ 0,32; one_page: US$ 0,22. Medir caminho efetivamente executado e pesquisa/revisões; não corrigir o editor nesta entrega. |
| Connect/MCP | Conector a contratar / medir | Hospedagem, chamadas, sincronização, bytes, agentes, permissões e suporte. MCP não implica tarifa universal. |
| Projetos/RAG | `services/intelligence/service.py` | SentenceTransformer local e índice presentes no código; não confirma implantação ou custo zero. Medir CPU, ingestão, OCR, embeddings, armazenamento, recuperação e atualizações. |
| Entrega | Renderização / arquivos | Medir retenção, downloads, egress e render. Não duplicar servidor já incluído nos fixos. |
| Skills privadas | Autoria / atualização / execução | Tarifa pendente. Metadados, catálogo público e consulta sem IA não ganham cobrança presumida. |

### Roteamento e intermediário

`uses_direct_openai` usa modelo compatível e disponibilidade de credencial direta; chamadas também podem ser forçadas pelo OpenRouter. A rota precisa ser capturada por job. O catálogo local de imagem já contém comentário de taxa embutida: não aplicar uplift de novo. Outros valores recebem a taxa efetiva assumida conforme a fração de rota direta configurada. A estimativa Planner não documenta taxa inclusa e exige conciliação.

A [FAQ oficial OpenRouter](https://openrouter.ai/docs/faq) informa repasse da tarifa de inferência e cobrança na compra de créditos. O valor numérico da taxa não ficou disponível no conteúdo consultado. O campo inicia em **0 como hipótese explicitamente não validada**, não como isenção; confirmar tarifa efetiva, mínimo por recarga e eventual contrato BYOK antes de fechar preços. Para modelos diretos, validar a tabela oficial do provedor e fatura da rota real; a consulta OpenRouter é apenas referência, não comprovação de faturamento direto.

### Lacunas não viram custo zero

Tarifas desconhecidas permanecem `null`. A interface mostra “Pendente” ou subtotal + pendente por produto. Usuário pode informar tarifa assumida por operação ou um orçamento global para as lacunas; este orçamento não transforma estimativas em dados observados. Toda margem permanece rotulada como parcial enquanto houver operação ativa sem tarifa. Taxas de pagamento/recarga, câmbio financeiro efetivo, IOF/remessa, suporte e impostos adicionais precisam de confirmação; não foram inventados.

## Experiência e limites técnicos

- Navegação local em hash, assets e scripts relativos: funciona via arquivo e via rota administrativa.
- Workspace substitui a nomenclatura Hub. Slug `#hub` permanece alias de compatibilidade; diretório raster `hub` preservado.
- Contexto de organização/marca é persistido localmente; SSO apenas explicado visualmente. Não há fronteira de autorização real nestes fixtures.
- Navegação horizontal do Studio; lateral nas demais famílias; menu recolhível em mobile; conta e créditos sempre disponíveis.
- Onboarding de três passos por produto, dispensável. Não há autoplay ou movimento involuntário.
- Busca pública, filtro por rede, seleção de arquivo sem upload, criação de projeto e versões privadas simulados.
- Skills privadas mostram referências disponíveis e ausentes; documentos ausentes são excluídos da prévia do agente. Dados privados não são injetados no catálogo público. A autorização real deve ser feita no servidor depois.
- Cotação registra tarifa/data/câmbio/markup. Reserva usa vencimento mais próximo. Conclusão ou estorno só podem ocorrer uma vez. Falha não apaga o custo pago ao fornecedor.
- Carteira, projetos e Skills são fixtures em memória e reiniciam ao recarregar; apenas contexto e dispensa de onboarding persistem.
- Nenhum editor PHP, serviço de IA, banco, sessão ou autenticação de produção foi alterado. As rotas administrativas preexistentes foram testadas isoladamente, sem inicializar o aplicativo completo ou banco.

## Backlog para produção em três semanas

| Semana | Prioridade | Responsável sugerido | Critério para fechar |
|---|---|---|---|
| 1 | P0: metering e conciliação | Engenharia + financeiro | Amostras de jobs com request ID, rota, modelo, unidade, tokens/cache, tentativas, custo real, câmbio e fatura; resolver Planner e medir OCR/MCP/RAG. |
| 1 | P0: política comercial | Financeiro + produto | Aprovar crédito, tarifa, impostos, expiração, estorno, quotas, desconto e limites de risco em vídeo. |
| 2 | P0: aceite de UX | Produto + design | Validar cinco famílias, contas/fontes, contratação, cotação, falha e Skills privadas em quatro larguras. |
| 2 | P0: contrato de execução futura | Engenharia | Especificar quote versionada, idempotency key, reserva atômica, captura, reconciliação e expiração. Sem implantar cobrança neste protótipo. |
| 3 | P0: decisão de lançamento | Produto + financeiro | Revisar DRE/mix, fechar pendências tarifárias, testar acessos administrativos e aprovar valores finais. |
| Posterior | Integração de produção | Engenharia | Pagamento/SSO/MCP, jobs, ledger e autorização de referência. Dependem das decisões acima; não implementados aqui. |

## Validação reproduzível

`node --test tests/test_cadu_finance.cjs`

`python3 -m unittest discover -s tests -p test_cadu_prototype_routes.py`

`CADU_NODE_MODULES=/caminho/node_modules node tests/cadu_prototypes_browser.cjs`

Browser usa Playwright e Chrome headless em perfil temporário; sem instalação de pacote no projeto. Resultados e capturas: `output/cadu-validation/`. Testes cobrem 14 rotas × 4 larguras, 12 slides × 4 larguras, troca de contexto, aviso mobile, carteira, Skills, desconto, erro da calculadora e componentes. Revisão visual manual das capturas complementa a verificação de overflow. Testes HTTP são isolados: não equivalem a deploy/aceite em produção.

Resultado final: 18 testes financeiros e 4 administrativos aprovados; 56 verificações de telas e 48 de slides sem overflow de página ou erros JavaScript. Fluxos de teclado (Enter/Escape e retorno de foco), onboarding, contexto, edição mobile, saldo/estorno, Skills e contratação aprovados. Contraste texto branco sobre cores de ação: Workspace 5,06:1; Studio 6,44:1; Connect 5,80:1; Skills 5,60:1; Planner 5,18:1. Isso cobre os pares principais; não substitui auditoria completa WCAG com leitor de tela.
