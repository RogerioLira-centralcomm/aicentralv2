# Connect — relatórios de campanha

Estado: especificação para implementação e contratos iniciais. Não representa integração, upload, cobrança ou publicação já disponíveis.

### Implementação inicial — área de trabalho

Rota `/connect/relatorios` ligada ao menu Connect. Biblioteca do cliente autorizado, cadastro manual de campanha/projeto, IDs externos, datas, objetivo e metas textuais; identidade com marca do projeto e assinatura do cliente; prévia privada; comentários e histórico de versões. Migrations em `migrations/add_connect_report_workspace.sql`, sem aplicação automática. Persistência transacional no PostgreSQL atual com rejeição de revisões concorrentes. O formulário não processa prints, não chama IA, não cobra créditos e não publica links. Metas estruturadas, identidade externa única entre projetos, upload, logos, dados e publicação permanecem nas etapas seguintes. Nome repetido no mesmo projeto abre uma pendência explícita, nunca faz fusão automática. O acesso segue o ambiente do cliente autorizado pelo Workspace.

Co-branding padrão nesta área: marca do projeto em destaque e cliente (`client_id`) como assinatura secundária. Marcas de mesmo nome não se repetem na prévia. Assinatura CentralComm é opcional e futura; não é inserida obrigatoriamente no relatório de cliente.

### Recebimento de prints implementado

Upload privado por relatório, lotes de até 20 imagens, validação de formato real/resolução/tamanho, remoção de metadados e normalização PNG. Fornecedor e período observados registrados por lote; hash do arquivo recebido impede reenvio idêntico na mesma campanha. Lote inválido faz rollback completo. Inclusão de fontes incrementa a revisão sob lock e registra histórico sem substituir o documento; formulário aberto anteriormente precisa recarregar antes de salvar. Rota de leitura revalida cliente e projeto e responde sem cache.

Migration `add_connect_report_sources.sql` aplicada no PostgreSQL configurado. Nesta primeira implementação os prints normalizados ficam em BYTEA privado na tabela de fontes, sem URLs públicas, para evitar dependência de infraestrutura adicional. Isso aumenta tamanho de backups e carga do banco; mover bytes para armazenamento de objetos é a evolução prevista, mantendo IDs e metadados no PostgreSQL. Não armazenar novos arquivos por caminhos públicos em static. Não há extração automática, cobrança ou revisão de valores ainda: estado inicial pending_review. Código da interface ainda depende de deploy no ambiente web.

## Produto e escopo

Relatórios são um módulo do Connect. Workspace continua dono de projetos, clientes e marcas; Connect mantém campanhas, fontes, conjuntos de dados, análises, visões e versões publicadas. Não criar um produto separado.

MVP: prints PNG, JPEG e WebP estáticos, revisão assistida, indicadores, gráficos, comentários de gestão e página compartilhável. Integrações não são pré-requisito. PDF, planilhas, vídeos, imagens animadas, scraping, publicação de anúncios e edição de orçamento ficam fora do processamento inicial.

## Fluxo e portas de qualidade

1. **Contexto:** selecionar cliente autorizado e projeto desse cliente; herdar marcas do Workspace. A API verifica autorização novamente. Cliente sugerido pelo material recebido não concede acesso nem cria cliente automaticamente. Marca deve pertencer ao contexto escolhido.
2. **Campanha:** procurar campanhas do cliente, destacando as do projeto selecionado. Campanha reconhecida abre seu relatório contínuo na ação Atualizar dados. Só criar campanha e análise inicial se não existir correspondência confirmada. Nome sugerido por IA só vira vínculo após confirmação. Nunca associar pelo nome sozinho. Correspondência em outro projeto exige confirmar o vínculo, não duplicar a campanha.
3. **Fontes:** anexar prints, declarar fornecedor quando conhecido, período coberto e tipo de informação. Exibir limites e estimativa de créditos antes de processar.
4. **Compilação:** extrair todos os arquivos, registrar resultados individualmente e reunir candidatos. Não produzir análise final enquanto houver arquivos pendentes, salvo exclusão explícita deles.
5. **Conferência:** print ao lado dos dados; resolver números ilegíveis, unidades, duplicações, datas conflitantes e campanhas ambíguas. Permitir excluir uma fonte mantendo histórico.
6. **Contexto analítico:** confirmar objetivo, datas da campanha, orçamento e metas. Campos desconhecidos ficam vazios; registrar perguntas pendentes. Salvar sem meta é permitido, mas sem avaliação de atingimento.
7. **Visões e indicadores:** escolher datasets compatíveis, filtros, medidas e gráficos. Recalcular em código. Permitir novas visões após compilar todas as fontes.
8. **Narrativa e marca:** na primeira entrega, compor resumo, leitura dos resultados, comentários e próximas ações. Nas atualizações, manter a análise existente e revisar apenas conclusões afetadas, acrescentando O que mudou. Usar por padrão a marca aprovada do projeto; selecionar visibilidade dos blocos.
9. **Publicação:** revisar pendências, fontes incluídas, período e conteúdo público; gerar uma versão imutável e um link revogável. Editar cria novo rascunho; republicar troca a versão servida pelo link.

## Identidade e reconhecimento de campanha

Campos: ID interno, project_ref qualificado, nome confirmado, aliases, fornecedor, plataforma, external_campaign_id como string, external_account_id, objetivo, início/fim planejados, timezone, orçamento/moeda, status declarado, evidência e data de observação do status.

Cada objetivo de indicador contém metric_key, definição do evento, direção (mínimo/máximo), valor alvo, unidade, período, escopo e fonte. Diferenciar objetivo de negócio (vendas), meta quantitativa (500 compras) e resultado observado (320 compras).

Identificação prioritária: plataforma + conta + ID externo no mesmo tenant/cliente, seguida da validação do vínculo ao projeto. ID Meta só é preenchido se visível ou informado. Nome parecido gera sugestão; IDs conflitantes bloqueiam união. Sem ID externo, sugerir campanhas existentes por nome/aliases, período e marca, com confirmação; criar campanha interna somente quando nenhuma corresponder. Prints contendo várias campanhas exigem seleção ou separação das linhas. MVP: um relatório contínuo por campanha, podendo reunir vários fornecedores explicitamente relacionados à mesma campanha. Campanha de negócio pode reunir várias campanhas externas confirmadas; cada identidade externa mantém plataforma, conta e ID próprios.

## Organização por cliente e atualizações incrementais

Navegação: Cliente → Projeto → Campanha → Relatório → Visões / Atualizações. Biblioteca apresenta última cobertura de dados, última atualização, situação planejada, pendências e link publicado. Ações principais: Receber dados, Atualizar campanha, Ver o que mudou. Recebimento começa pelo contexto autorizado; extração pode sugerir cliente/campanha e pedir correção desse contexto, nunca mover dados silenciosamente.

O report_id permanece estável. Cada recebimento cria um update_id com fontes, base_revision, revisões de dados, alterações propostas e estado de revisão. Não criar nova análise independente a cada lote. Cada atualização registra autor, datas de recebimento/observação, fontes incluídas e custo incremental. Histórico mantém os valores anteriores e as análises nas respectivas revisões.

Classificar as alterações antes de consolidar:

| Recebimento | Tratamento |
| --- | --- |
| Arquivo idêntico já recebido no mesmo escopo | Sem processamento ou cobrança adicional; indicar onde já foi utilizado |
| Dados equivalentes em outro print | Registrar nova evidência, sem duplicar valores nem gerar nova análise de mudanças |
| Novo período sem sobreposição | Acrescentar observações; somar somente métricas aditivas compatíveis |
| Novo acumulado com mesma data inicial | Criar snapshot sucessor; nunca somar acumulado antigo com novo |
| Correção do mesmo intervalo | Propor revisão do valor; preservar anterior e motivo; confirmar conflito |
| Sobreposição parcial de intervalos agregados | Manter separado até haver detalhamento ou escolha explícita; não subtrair para inventar dias |
| Novo indicador ou dimensão | Expandir esquema versionado; dados antigos ficam nulos onde faltam |
| Print atrasado | Inserir pela data observada; não substituir o estado mais recente só por ter chegado depois |

O que mudou mostra: novas fontes/cobertura, indicadores antes e depois, diferença absoluta e relativa quando válida, mudanças de metas/prazos, pendências resolvidas/novas e impacto nas recomendações. Variação entre acumulados de janelas diferentes é diferença entre snapshots, não prova de desempenho exclusivo do intervalo novo (atribuição retroativa pode mudar valores). Base zero permite diferença absoluta, mas percentual fica indisponível. Taxas mostram diferença em pontos percentuais, rotulada corretamente. Aumento não significa melhoria automaticamente: CPC menor pode ser desejável, gasto maior depende do objetivo.

Uma nova marca, meta ou janela pode invalidar comparações anteriores: registrar mudança de contexto separadamente da variação de desempenho. Preservar comentários manuais, decisões e visões; marcar textos afetados para revisão. Atualização sem mudanças relevantes não chama o agente de análise novamente. Nova geração integral só por ação explícita Reformular análise, com custo informado.

Concorrência: identidade externa única por tenant/cliente/plataforma/conta/ID; uma identidade não pode criar duas campanhas em uploads simultâneos. Um relatório canônico por campanha. Consolidar atualização com comparação de base_revision em transação: revisão divergente exige reconciliar de novo, nunca sobrescrever. Idempotência por upload/job, sem deduplicação entre clientes que possa revelar dados de outro contexto.

## Regras de tempo e análise

Separar três relógios: período planejado da campanha, período medido pelos dados e data de emissão do relatório.

- Antes do início: início previsto no futuro, não afirmar que não houve entrega sem evidência.
- Dentro da janela: dentro do período planejado, não afirmar que está ativa na plataforma.
- Após fim planejado: prazo previsto encerrado; só afirmar encerramento confirmado com evidência recente ou confirmação do gestor.
- Sem datas suficientes: situação temporal indeterminada.
- Status da plataforma sempre rotulado com a data em que foi observado. Print antigo não prova o estado atual.
- Uma campanha encerrada pode ter relatório parcial. Separar encerramento, cobertura dos dados e entrega final.
- Data final da campanha é inclusiva no timezone configurado. Datas invertidas geram erro de validação.
- Cumprimento de meta só compara mesma definição, unidade, janela e escopo. Abaixo de uma meta mínima antes do fim não significa fracasso final.
- Pacing linear é opcional e rotulado como referência, nunca previsão. Só disponível com início/fim, orçamento/meta e cobertura compatíveis.

## Limites iniciais propostos

São limites de produto do piloto, sujeitos a medição; não limites da OpenAI.

- Até 20 imagens por lote inicial ou atualização, 10 MiB por arquivo e 100 MiB por lote; até 25 megapixels por imagem decodificada; lado máximo 12.000 pixels. Histórico da campanha pode conter vários lotes; a UI informa armazenamento acumulado.
- Verificar assinatura e decodificação, não só extensão. Rejeitar imagem animada, corrompida e arquivos não suportados. Remover metadados desnecessários; armazenar origem de modo privado.
- Até 5.000 registros no conjunto consolidado ativo, 60 campos por dataset e 10 datasets por relatório. Ao exceder, interromper consolidação e propor recorte/arquivamento revisado ou ampliação de capacidade; nunca truncar nem duplicar campanha para contornar o limite. Histórico continua preservado.
- Até 10 visões, 12 blocos por visão e 20 indicadores personalizados por relatório.
- Máximo de 2 execuções de IA simultâneas por organização no piloto; fila com progresso por etapa. Até 2 retentativas por falhas transitórias, com orçamento máximo por job.
- Texto ilegível permanece nulo e pede novo print. Não inferir números por tamanho de barra nem preencher dias ausentes. Zero e desconhecido são distintos.
- Processamento incremental de novos arquivos; fontes idênticas identificadas por hash não são processadas/cobradas novamente sem pedido explícito.

## Modelo de dados

Decisão: começar no PostgreSQL atual da aplicação, em tabelas específicas do Connect, com metadados relacionais e JSONB para campos dinâmicos. Se necessário, separar depois em outra base PostgreSQL. Arquivos no armazenamento de objetos privado. Não criar tabelas por fornecedor ou relatório.

Entidades: report_campaigns; report_campaign_external_ids; report_campaign_projects; report_goals; reports; report_updates; report_sources; report_extractions; report_datasets; report_rows; report_views; report_comments; report_revisions; report_publications; report_jobs. Campanhas têm client_id obrigatório e projetos vinculados explicitamente; cada relatório fixa o projeto e a marca usados na apresentação.

Todas as entidades privadas carregam organization_id e referências consistentes; validar tenant nas leituras, alterações e jobs. O ID do projeto não pode vir apenas de texto inferido pela IA.

Metadados estáveis são colunas relacionais. JSONB guarda esquema dinâmico, dimensões e valores das linhas, configuração de blocos e tema. Valores monetários usam representação decimal exata; não float para cálculo financeiro. Cada revisão fixa dataset_revision, schema_version, prompt_version e regras de cálculo.

Um campo define: key, label original, label normalizado, tipo, unidade, definição, comportamento de agregação, origem e granularidade. Uma observação define período, dimensões, valor bruto e normalizado, referência à evidência, revisão humana e possíveis conflitos. Confiança declarada pelo modelo é sinal de triagem, não garantia estatística.

Separação física de banco só com evidência de necessidade de escala, retenção ou isolamento. O módulo deve ter repositório próprio, migrations próprias e conexão configurável com fallback para a conexão atual. Referências a clientes/projetos são resolvidas por serviços do Workspace; evitar consultas espalhadas com joins cruzados. Separação futura exige cópia validada, reconciliação de versões e corte controlado, preservando IDs e links públicos; não é prometida como migração automática sem trabalho.

## Indicadores, filtros e visões

Visões salvas: Executivo, Entrega, Eficiência e personalizada. Cada visão registra escopo/filtros padrão, blocos e indicadores; não duplica os dados base. Inclusão de novas fontes marca análises dependentes como desatualizadas até recompilar.

Indicadores derivados usam operações permitidas e referências de campos, nunca eval, SQL ou código produzido pelo modelo. Ex.: CPC = investimento/cliques; CTR = cliques/impressões × 100. Divisão por zero retorna indisponível.

Somar apenas parcelas sem sobreposição e com unidade/definição compatíveis. Não somar alcance único entre campanhas ou fornecedores. Frequência, percentuais e taxas não são aditivos. Não combinar moedas nem atribuições de conversão diferentes. Totais e linhas detalhadas do mesmo print são representações alternativas, não parcelas somáveis.

Filtros só existem para dimensões realmente presentes. Totais agregados sem dimensão não recebem rateio inventado. Após filtrar, métricas e metas indicam seu escopo; uma meta global não vira meta do subconjunto automaticamente. Narrativa estática deve indicar o escopo original quando filtros mudam; não disparar IA a cada clique.

Adicionar indicador: escolher campo existente ou fórmula permitida, nome, formato e eventual meta. Campos ausentes geram pedido de fonte adicional. Gráficos de linha exigem série temporal; participação exige partes compatíveis do mesmo total; sempre oferecer tabela acessível.

## Design system e white label

Shell administrativo mantém a identidade Connect. Documento usa tokens próprios: report.background, surface, text, muted, accent, positive, warning, negative, series e fontes. Base: fundo #F5F7FA, superfície #FFFFFF, texto #182B3A, secundário #526475, destaque #1363C5. Corpo 15/24px, títulos 28–40px, números tabulares; largura do documento 1120px. Grids adaptáveis a 360px; nenhuma informação escondida só por ser mobile.

Componentes: cabeçalho de campanha; faixa de período/cobertura; indicador com unidade e origem; meta com direção; gráfico com legenda/tabela; tabela de dados; nota de metodologia; comentário de gestão; próxima ação; rodapé de emissão.

Tema padrão: marca do projeto. Herdar logo, paleta e tipografia aprovados do Workspace, com snapshot por versão publicada. Se houver uma marca vinculada, pré-selecionar; se houver várias, exigir escolha da marca de apresentação. Sem marca, permitir rascunho neutro e solicitar definição antes da publicação personalizada; não adotar a marca do fornecedor do print. CentralComm e co-branding são escolhas explícitas. Atualização de dados preserva o tema escolhido; mudança posterior da marca no Workspace propõe nova versão e nunca modifica silenciosamente o link publicado. Cores da marca não alteram significado de alerta/sucesso. Verificar contraste e oferecer cores acessíveis; estado nunca expresso só por cor. Séries mantêm cores estáveis ao filtrar.

White label da marca: remover navegação Connect, avatar, saldo, botões internos e rodapé institucional Cadu do documento público; título, favicon, logo e metadados sociais seguem a marca. Co-branding mostra ambas as marcas mediante escolha. Não aceitar HTML/CSS/JS arbitrário; renderizar texto escapado e URLs de mídia validadas.

Um link no domínio Connect pode ser visualmente white label. Domínio próprio é fase posterior com DNS e certificado; não prometer domínio personalizado no MVP.

Compartilhamento: token aleatório armazenado como hash, revogação, expiração opcional e noindex. Somente snapshot de campos explicitamente públicos; prints, IDs de contas, notas internas, custos e prompts ficam privados por padrão. Noindex não é controle de acesso. Verificar token em cada requisição de dados; revogação invalida cache público. Visita/filtro não consome IA.

## Prompts e agente

Prompts versionados em aicentralv2/cadu_connect/report_prompts.py. Separar extração, reconciliação, análise inicial, análise de mudanças, composição e edição. Atualizações recebem revisão anterior, delta validado e referências às evidências novas; buscar contexto adicional apenas quando necessário. Dados e texto dos prints são conteúdo, nunca instruções. Saída deve obedecer contrato JSON validado no servidor; saída inválida não altera dados.

O agente opera apenas sobre o relatório e projeto autorizados. Sugere alterações em campos/blocos permitidos; apresenta diff, custo e impacto. Não muda origem para ocultar correção; não publica, cobra ou acessa outra organização por instrução contida no print. Perguntas sobre dados usam consultas restritas, não SQL livre.

O modelo de extração precisa ser validado com prints reais. GPT-5 nano é candidato, não decisão de qualidade já comprovada. Modelo e orçamento configuráveis; escalonamento não pode ultrapassar limite aceito sem novo consentimento.

## Créditos, versões e recuperação

Criar rascunho e editar manualmente não chama IA. Processar fontes, gerar análise ou reformular com IA têm preço explícito. Primeira compilação tem pacote inicial; atualizações cobram apenas extração nova e análise das mudanças, sem cobrar criação de outro relatório. Arquivo idêntico detectado antes da IA não tem custo; equivalência descoberta após extração pode consumir essa extração, mas não nova análise. Mostrar estimativa antes do lote. Reservar saldo antes do job, liquidar uma vez por chave idempotente e liberar reserva em falha. Tokens/custo reais registrados por etapa. Preço base por relatório deve declarar quantidade de imagens incluídas e custo adicional; X será definido após benchmark.

Falha parcial conserva resultados e permite retomada por fonte. Nova execução não pode duplicar movimentos de crédito. Publicação fixa dados + layout + comentários + marca em uma revisão. Correção posterior não altera silenciosamente o relatório público.

## Etapas de entrega e aceitação

1. Contratos de dados, regras temporais, limites, prompts e protótipo completo dentro do Connect.
2. Persistência, autorização por projeto, campanha e metas; upload privado e revisão manual funcional.
3. Jobs de extração com validação, revisão assistida e consumo de créditos idempotente.
4. Visões, indicadores, comentários, temas e publicação segura com revogação.
5. Agente de edição e ajustes de custo/qualidade pelo piloto.

Benchmark: pelo menos 30 prints de fornecedores distintos, incluindo ilegíveis, datas conflitantes, unidades diferentes e sobreposição. Medir precisão numérica contra revisão humana, taxa de campos não resolvidos, tempo e custo. Nenhum valor publicado sem origem/revisão; nenhum total duplicado nos casos de teste; nenhuma campanha marcada como encerrada apenas pela data planejada. Testar isolamento de organizações, alterações durante publicação, falhas/retries e débito único. Testar público em 360/768/1440px, teclado, contraste e revogação. Aprovação do piloto depende de revisão dos resultados, não apenas de resposta JSON válida.
