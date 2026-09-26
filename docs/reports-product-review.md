# Reports · análise de produto e plano de refinamento

**Escopo:** Reports como ferramenta diária para agência, cliente e gestor de tráfego. As áreas do menu permanecem funções distintas; o plano melhora contexto, transições e linguagem entre elas.

## Síntese executiva

Reports já tem uma base funcional ampla: contas/MCC, campanhas e detalhe, workspaces de relatório, importação de CSV/XLSX/prints, reconciliação e conflitos, ingestão do Google Ads e do CRM, tracking, Funnel Flow, eventos/conversões, Link Tester, biblioteca de dados e controle de acesso.

O que prejudica o uso hoje é a distância entre essa base e a experiência operacional:

1. **Bloqueio P0 de disponibilidade:** a tela React troca qualquer seção por uma mensagem única quando as tabelas-base não existem. A tela online observada estava nesse estado. Nenhuma melhoria de navegação resolve isso sem a sequência de migrações e publicação.
2. **Confiança P1:** a Visão geral aproxima números de fontes e canais com cobertura, moeda, janela de atribuição e definição diferentes. Os cartões distinguem parte dessas fontes, mas a síntese ainda não oferece uma leitura de comparabilidade suficientemente explícita.
3. **Fluxo de trabalho P1:** funções separadas não significam tarefas isoladas. Uma linha importada, uma campanha, uma URL com erro e uma conversão precisam abrir a entidade certa já filtrada, preservando cliente, período e origem.
4. **Profundidade por canal P1/P2:** o modelo de métricas diárias nativas está mais completo para Google Ads. Meta, TikTok, LinkedIn e demais canais aparecem principalmente por arquivo; a interface deve dizer isso e preservar as dimensões nativas em vez de simular paridade.
5. **Defeitos encontrados:** o detalhe de campanha era renderizado sem receber `filters`, embora usasse esses filtros para buscar métricas e fluxo. Corrigi essa passagem no React. O filtro global também é exibido em páginas onde sua lista não o aplica; o plano corrige o escopo visual e funcional desse filtro.

Uma chamada TypeSafe, feita com avaliações tipadas em paralelo sobre o inventário de telas e capacidades, apontou: qualidade/rastreabilidade para o analista de agência, resumo em linguagem simples para o cliente e saúde da mensuração para o gestor. O risco de confiança ficou dividido entre migração e semântica de métricas. O valor do plano completo teve score 3,46/4, com confiança 0,57 e probabilidades quase iguais entre “muito alto” e “excepcional”; portanto, uso isso como sinal de priorização, não como fato sobre usuários.

## Princípios de experiência

- **Uma função por tela:** Visão geral, Contas, Campanhas, Relatórios, Importações, Integrações, Tags e tracking, Fluxos, Eventos, Conversões, Link Tester, Biblioteca de dados e Acessos continuam separadas.
- **Contexto atravessa telas:** links carregam `client_id`, entidade, período e filtros compatíveis. Exemplo: um alerta de tag abre a instalação afetada; uma métrica em conflito abre o arquivo e a linha; uma campanha abre seu detalhe na aba de origem correspondente.
- **Observado e interpretado são coisas diferentes:** fatos calculados, importados ou recebidos por API aparecem com fonte e período. Sugestões de IA são rascunhos revisáveis e nunca confirmam importação, atribuição ou otimização por conta própria.
- **Comparar exige semântica:** métricas só são agregadas quando unidade, moeda, granularidade, janela e significado são compatíveis. Caso contrário, mostrar canais em painéis paralelos ou normalizar moeda com taxa e data explicitadas.
- **Sem cobertura não há recomendação:** destacar “sem dado”, “parcial”, “atrasado” e “não conectado”; não preencher lacunas com zero nem produzir benchmark inventado.
- **Preservar identidade visual:** manter logo e estrutura da sidebar existente, paleta predominantemente azul para Reports, ícones pequenos e tipografia atual. Melhorar hierarquia, densidade e estados sem redesenhar a marca.

## Revisão tela a tela

| Tela/função | O que já existe | Lacuna e refinamento proposto |
|---|---|---|
| **Visão geral** | Investimento, impressões, cliques e conversões; comparação de conversões Ads/site/CRM; série diária, Link Tester, contas por canal e dados importados. | Fazer desta a síntese operacional, com abas de leitura **Agência / Cliente / Operação** que mudam ênfase, não dados. Mostrar período atual vs período anterior, variação absoluta/percentual, moeda e fonte em cada KPI. Separar “dados de plataforma”, “tracking próprio” e “CRM”; usar linhas por canal quando moeda ou definição diferirem. Incluir faixa de cobertura/frescor no topo e lista curta de alertas com links para a tela de correção. Dar seletor de métrica ao gráfico e informar dias sem dados. |
| **Contas** | Cadastro de conta, MCC/gerente, vínculo de anunciantes, estado, conexões, histórico de ingestão. | Agrupar visualmente gerente → anunciantes; exibir plataforma, fuso, moeda, escopo autorizado da chave, última tentativa, último sucesso, atraso e erro acionável. Diferenciar “conta cadastrada” de “conta conectada”. Adicionar filtros/busca aplicados à tabela, sincronização/teste e acesso ao histórico da conexão. |
| **Campanhas** | Lista manual/cadastrada e detalhe com abas de performance, canais, páginas, formulários, leads, conversões, mapa de calor, relatórios, origem e configuração. | Aplicar de verdade os filtros globais à lista ou ocultá-los nessa tela. A linha precisa priorizar conta, canal, status, gasto, resultado e atualização. Importações e Script podem conter a mesma campanha/dia; reconciliar ou mostrar origens lado a lado, nunca somar silenciosamente. Na página de detalhe, colocar fonte/atualização junto aos números; abrir diretamente a aba por URL. O mapa de calor precisa indicar ausência de vínculo/cobertura e apontar a instalação a associar. Criativo, palavra-chave, audiência, placement e estratégia só aparecem quando a fonte do canal as fornece. |
| **Detalhe da campanha** | Visão geral e separação entre métricas da plataforma, eventos próprios e confirmações de CRM; tabelas de página/formulário/conversão e dados de origem. | Adicionar comparação de período, série por métrica, tabela diária reconciliada e trilha de mudanças quando o conector entregar esses dados. Deixar claro que “conversão Ads”, “conversão observada” e “venda CRM” são definições distintas. Mostrar a regra/janela de atribuição disponível. A navegação de abas deve sobreviver a refresh/voltar. Criar atalhos para arquivo original, eventos, instalação e relatório associado. |
| **Relatórios** | Workspaces com objetivo, metas, notas, versão, fontes, revisão de evidências e link público com validade/revogação. | Separar biblioteca, editor e publicação sem perder continuidade. O editor deve selecionar campanhas/período/dimensões, inserir blocos suportados, escrever comentário, pré-visualizar como cliente e comparar versões. Mostrar quais números estão confirmados, parciais ou aguardando revisão. Link público com identidade da marca, estado de expiração, cópia com feedback e revisão responsiva. Exportação PDF/CSV e agendamento ficam após estabilidade da composição e do modelo de dados. |
| **Importações** | CSV/XLSX/prints, detecção de duplicado/incremental/revisão/campanha ausente, extração visual com evidência, mapeamento de colunas, conflito auditável e decisão de criar campanha. | Organizar em fila de trabalho com estados claros: recebido → leitura → correspondência → revisar → confirmado/aplicado. No upload, pré-visualizar conta/campanha/período/canal, granularidade e moeda antes de gravar. Para prints, manter recorte/evidência perto de cada número. Mostrar progresso e resultado por linha, opção de desfazer lote/retirar projeção conforme política de retenção, e não apenas contagem agregada. Campanha inexistente pede decisão contextual com nome/IDs e destino dos dados. |
| **Biblioteca de dados** | Valores customizados canal/chave/valor, snapshots de intervalo, dados de origem e conflitos, atualmente alcançados como seção/âncora em Importações. | Tratar como função própria no menu/URL, com tabela explorável e filtros de canal, entidade, período, chave e origem. Distinguir observação diária de total do intervalo para impedir soma dupla. Guardar rótulo, chave estável, tipo, unidade, moeda, escopo, regra de agregação, fonte, versão e evidência. Permitir ver histórico/linhagem e exportar seleção. |
| **Integrações** | Google Ads Script, CRM webhook, MCC e anunciantes permitidos, chaves revogáveis e lotes. | Painel de saúde por conexão: autorizada, recebendo, última tentativa/sucesso, intervalo coberto, linhas aceitas/rejeitadas, duplicados e erro com ação de correção. Onboarding em passos curtos com teste antes de ativar. Tokens secretos aparecem uma vez; copiar, rotacionar e revogar com confirmação contextual. Evitar chamar “tempo real” para envio diário ou periódico. |
| **Tags e tracking (Supertag)** | Domínios, snippet, consentimento, retenção, audiência anônima, eventos agregados, cliques/visibilidade/rolagem e revogação. | Melhorar instalação com checklist de consentimento/CSP, teste de domínio e evento de exemplo, diagnósticos de versão e último sinal recebido. Métricas de audiência devem explicar janela do cookie, consentimento e estimativa. Heatmap precisa de seletor de página/dispositivo/período e estados de amostra insuficiente; avisar que posição é viewport normalizado. Nunca capturar valores de formulário. |
| **Fluxos** | Editor de páginas/origens, formulário, evento, condição, conversão, webhook, publicação, teste simulado, CF interno e URLs independentes de tag. | Adotar salvar rascunho, estado sujo, validação antes de publicar, desfazer/refazer e teclado além de drag and drop. Configuração selecionada sempre acompanha bloco selecionado; erro aponta o bloco e preserva rascunho. Simulação deve distinguir dados fictícios dos coletados. Mostrar teste real da instalação separado da simulação. Conectores e tags usam nomes/logo oficiais quando licenciados; ícone não substitui o status de coleta. |
| **Eventos** | Eventos agregados por tipo, origem/página, recência, atribuição e mapeamento; formulário sem valores pessoais; snippet de evento personalizado. | Filtros aplicados ao endpoint e URL; separar evento recebido de conversão atribuída. Mostrar taxa de atribuição e denominador, duplicidade, visitante estimado e janela. O snippet gerado precisa de validação do nome, cópia confirmada e instrução por ambiente. Paginação/retention deve indicar claramente que a tabela mostra apenas os eventos mais recentes. |
| **Conversões** | Reutiliza a função de Eventos com filtro `conversion`, comparando Ads/site/CRM no detalhe. | Manter como destino próprio do menu, com definição por conversão, fonte, janela, deduplicação e valor. Mostrar funil observado → lead → qualificado → venda, somente onde cada etapa tiver dados, com perdas de cobertura visíveis. Distinguir atribuição de causalidade e evitar declarar incremento sem experimento. |
| **Link Tester** | Teste de destino/redirecionamento, medição, modo agentic, evidências/alertas, compartilhamento, sugestão de associação e histórico. | Separar saúde técnica de qualidade de campanha. Cada alerta precisa ter evidência e URL afetada; mostrar UTMs antes/depois de redirects, domínio final e data do teste. Associação sugerida por IA sempre pede confirmação e apresenta candidatos/certeza; manter regra exata para IDs. Ações para abrir a campanha e refazer teste mantêm contexto. |
| **Acessos** | Papéis viewer/member/admin, acesso exclusivo ao Reports, concessão e revogação. | Explicar efeitos de cada papel em leitura humana, mostrar convite/conta ativa, quem concedeu e quando, e restringir ações de edição/publicação conforme o papel. Pré-visualização “ver como cliente” deve ser somente leitura e proteger links públicos. |

## Fluxos entre telas, mantendo cada função separada

1. **Começar o dia:** Visão geral → alerta de dado atrasado → Integrações → testar/abrir lote → Campanhas afetadas.
2. **Revisar importação:** Importações → validar canal/conta/campanha/período → comparar com campanha existente → criar se explicitamente confirmado → ver campanha e linhagem.
3. **Investigar performance:** Visão geral ou Campanhas → detalhe → período e definição → Eventos/Conversões → CRM ou Tracking, preservando a campanha e o filtro.
4. **Validar conversão:** Fluxos → simular dados fictícios → testar evento real → Eventos → mapear URL → comparar com confirmação CRM, sem misturar os três contadores.
5. **Explicar ao cliente:** Campanha/Visão geral → anotar causa com fonte → Relatórios → pré-visualização/versão → publicar link ou exportar.
6. **Corrigir destino:** Link Tester → alerta e evidência → campanha associada → corrigir URL/UTM fora do Reports → executar novo teste e manter histórico.

Cada transição deve ser um link contextual. A tela de destino continua especializada; não embutir todas as funções em uma tela gigante.

## Contrato de dados para leitura multicanal

Cada métrica deve carregar pelo menos:

```text
client_id, platform, account_id, campaign_id, metric_key, metric_label,
value, unit, currency, metric_date, time_zone, granularity,
attribution_window, conversion_definition, source_kind, source_run_id,
source_updated_at, coverage_state, review_state, evidence_ref, aggregation_rule
```

- Chave estável (`metric_key`) independe do rótulo traduzido.
- A unidade define contagem, percentual, duração ou moeda; moeda não pode ser inferida.
- `granularity` separa dia de intervalo; snapshots de período não entram em soma diária.
- `source_kind` separa API/script, export, print confirmado, Super Tag e CRM.
- `review_state`/`evidence_ref` preservam a decisão humana e a origem do valor.
- Métricas específicas do canal continuam como chave/valor com definição e agregação; não forçar o denominador comum a esconder o vocabulário nativo.

### Interpretação por canal

| Canal/fonte | Métricas/dimensões nativas a preservar | Regra de leitura |
|---|---|---|
| Google Ads | impressões, cliques, custo, conversões/valor reportados, tipo de campanha, rede, termos e grupos quando importados | Conta MCC e fuso/moeda da conta; registrar ação de conversão e janela. Script atual traz um subconjunto, então indicar cobertura limitada. |
| Meta Ads | alcance, impressões, frequência, cliques/CTR, gasto, CPM/CPC e eventos/ROAS conforme export/API | Alcance é deduplicado no ecossistema Meta e não soma entre contas/dias como impressões. Preservar janela de atribuição e tipo de evento. |
| TikTok Ads | impressões, alcance, visualizações por marco, cliques, custo, conversões e eventos de vídeo | Separar visualização de vídeo, clique e conversão; incluir objetivo/campanha e janela disponível. |
| LinkedIn Ads | impressões, cliques, gasto, leads de formulário, engajamento e dimensões profissionais quando disponíveis | Lead nativo não equivale a lead confirmado pelo CRM. Evitar expor detalhamento de público com volume insuficiente. |
| Analytics/CRM | sessão/visita observada, formulário, lead, qualificação, venda e valor enviado pelo CRM | Não é a mesma atribuição da plataforma. Exibir IDs opacos/deduplicação, timestamp, regra e eventual falta de campanha associada. |
| Super Tag | page view, formulário sem conteúdo, clique, evento, conversão, visibilidade e rolagem | Só contar com consentimento e domínio ativo; distinguir sessão/visitante estimado e limitar inferências de amostras pequenas. |
| Importação customizada | qualquer chave de métrica acompanhada de unidade, escopo, intervalo e evidência | Semântica desconhecida fica “não interpretada”; manter valor original e pedir definição em vez de padronizar por suposição. |

## Filtros e comportamento compartilhado

- Manter as duas faixas compactas existentes: **dimensão** (canal → conta → campanha) e **tempo/fonte** (datas, atalhos, comparação, atualização). O cabeçalho permanece dentro do limite visual já definido para Reports.
- Aplicar filtros somente nas telas que os suportam. Nas outras, recolher/ocultar a faixa ou indicar por que não se aplica; nunca deixar controles aparentes sem efeito.
- Opções dependentes se atualizam em cascata. Ao trocar canal, zerar conta/campanha incompatíveis. Ao trocar conta, recalcular campanhas. Filtro e período são refletidos na URL para salvar/compartilhar e restaurados no voltar.
- Atalhos: 7, 30, 90 dias e personalizado; comparação com período anterior de mesma duração; validação do limite suportado pela API antes de carregar.
- Mostrar “Atualizado em”, canal selecionado, período com fuso e estado parcial ao lado dos resultados. “Atualizar” mostra carregamento, sucesso ou erro e não afirma tempo real sem ingestão em tempo real.
- Skeletons por bloco, estados vazios específicos da tela, erro com tentar novamente e resultados parciais preservados. Sem trocar toda a tela por um vazio genérico.

## Feedback e movimento

- Ações locais: botão passa a “Salvando…”, bloqueia duplo envio, confirma com toast/estado `aria-live`; manter o contexto e atualizar somente os dados afetados.
- Ações destrutivas (revogar tag/chave, descartar projeção) mostram consequência, entidade e escopo; registrar auditoria. Oferecer desfazer quando tecnicamente seguro.
- Sincronização e extração: progresso real por etapa, tempo/última resposta e contagens aceitas/pendentes. Não usar barra animada que simule progresso desconhecido.
- Fluxos: estado de rascunho/publicado, alterações não salvas, foco visível, conectores selecionáveis por teclado, arrastar com alternativa de clique/mover, desfazer/refazer; preservar o rascunho em falha de rede.
- Animações discretas de entrada/alteração (150–220 ms), sem movimento contínuo em indicadores; respeitar `prefers-reduced-motion`. Atualização ao vivo pausa com aba em segundo plano e mostra o horário do último evento.

## Plano de entrega recomendado

### P0 · Tornar Reports utilizável

1. Aplicar e auditar, com backup e ambiente confirmado, toda a sequência de migrações de Reports; publicar assets React e backend juntos.
2. Trocar o bloqueio global por readiness por capacidade: cada tela identifica a migração/fonte faltante, mostra impacto e caminho de correção, enquanto páginas que não dependem dela continuam acessíveis.
3. Corrigir erros de navegação e escopo já encontrados, incluindo filtros no detalhe de campanha e filtros globais que atualmente não restringem algumas listas.
4. Confirmar cada ação principal: abrir campanha, salvar, publicar/revogar relatório, importar e revisar, configurar integração, publicar/testar fluxo, ver evento/conversão e testar/associar link.

### P1 · Confiança e rotina diária

1. Criar estado de saúde/cobertura/frescor por origem, conta, período e campanha.
2. Separar métricas por fonte e regra; sinalizar moeda, fuso, janela de atribuição, atualização e compatibilidade.
3. Fazer a Visão geral responder “o que mudou, onde, por quê sabemos e qual tela abre a evidência”.
4. Completar campanha com trilha da importação/ingestão, eventos, conversão confirmada, atribuição e relatório associado.
5. Fazer biblioteca de dados ter tela/URL própria e linhagem pesquisável.
6. Unificar estados de loading, erro, vazio, salvo, pendente e sem permissão com mensagens e retornos consistentes.

### P2 · Especialidade por canal e qualidade analítica

1. Criar adaptadores de canal que preservem nomenclatura e métricas nativas.
2. Priorizar integrações nativas pela demanda e capacidade operacional, começando pelo conector que remove mais importação manual. Até lá, melhorar templates/importações específicas por canal.
3. Cobrir criativos, posicionamentos, públicos, termos e objetivos só quando recebidos com fonte compatível.
4. Adicionar orçado vs realizado, tendência, alertas configuráveis e fila de ações com evidência; recomendações iniciais são revisão humana.

### P3 · Distribuição e colaboração

1. Pré-visualização de cliente, relatório compartilhável versionado, exportações e agendamento.
2. Comentários/nota ligados a campanha e métrica, responsáveis, prazo e registro do que foi feito.
3. Perfis de dashboard e filtros salvos por papel; controle de acesso herdado do cliente.

## TypeSafe dentro do produto

Usar TypeSafe para julgamentos estreitos onde há ambiguidade: mapear cabeçalhos para chaves de métrica; escolher campanha entre candidatos já recuperados; classificar alerta pela causa provável; avaliar se a evidência de um print sustenta um campo; priorizar observações que já têm métricas calculadas. Passar estado nomeado, candidatos completos, critérios fechados e alternativa “nenhum”.

Não usar TypeSafe para calcular custo, ROAS, totais, datas, moeda, deduplicação ou autorização. Código determinístico faz esses cálculos e verifica regras. Resposta incerta fica como sugestão para revisão humana; probabilidade/confiança não significa verdade nem autorização. Cada chamada deve registrar versão/modelo/uso e evitar enviar dados pessoais. A API entrega respostas estruturadas com Choice/Score/Noul e uso por requisição; seguir o endpoint atual documentado pela TypeSafe ([API](https://docs.typesafe.ai/api), [quick start](https://docs.typesafe.ai/introduction/quickstart), [Choice](https://docs.typesafe.ai/primitives/choice)).

## Sinais de sucesso

- Uma pessoa encontra em até dois saltos a fonte por trás de qualquer KPI e o estado de cobertura correspondente.
- Um cliente entende gasto, resultado, meta e lacunas sem precisar interpretar nomes de API.
- Um gestor encontra primeiro a ação de medição/otimização e consegue abrir a evidência e o próximo passo.
- Um analista compara canais sem somar moedas, janelas ou eventos incompatíveis.
- Importar o mesmo período duas vezes não duplica valores; revisão preserva origem, decisão e histórico.
- Toda mudança de tela preserva cliente, campanha e período relevantes, sem esconder erro de carregamento parcial.

## Verificação executada nesta revisão

- Leitura estática do React, rotas/API Reports, modelo de ingestão, importações, Flow, SuperTag e roteiro de migração.
- Build de produção do React Reports concluiu sem erro.
- O ambiente online observado ainda responde `ready=false` no bootstrap; migrations e deploy não foram executados nesta revisão.
