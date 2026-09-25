# Reports · próximos passos após a V1

## Estado observado em 25/09/2026

O núcleo já tem isolamento por `client_id`, inventário de contas e campanhas, ingestão diária por Google Ads Script, chaves por cliente, tag de páginas, etapas do Funnel Flow, webhook de conversões, visão geral React com ApexCharts, Link Tester e concessões de acesso próprias do Reports. As correções recentes de permissão, contas MCC, seleção do Link Tester e limite da tag estão no workspace, mas ainda não foram implantadas. O bundle compila; isso não substitui uma validação com banco, navegador, Google Ads e CRM reais.

A V1 ainda abre a biblioteca e a edição de relatórios na interface legada. O Link Tester mostra uma sugestão revisável, sem persistir a associação confirmada. A tag usa identificadores da sessão da aba; não há medição de navegação SPA, eventos personalizados do GTM, audiência persistente ou mapa de calor. Só o Google Ads Script fornece métricas de mídia. O acesso exclusivo do Reports existe para contas já cadastradas no Cadu; o cadastro e a entrada autônomos de um assinante só do Reports ainda precisam ser definidos.

## Sequência de execução

| Ordem | Entrega e escopo | Dependência | Critério de conclusão |
| --- | --- | --- | --- |
| P0.1 | Consolidar somente as mudanças do Reports em um commit; revisar migrações aditivas, `deploy.sh`, backup e reversão de código. Rotacionar a chave TypeSafe compartilhada nesta conversa. Evitar incorporar alterações paralelas do Workspace e de outros produtos. | Nenhuma | Diff restrito ao Reports, migrações aplicáveis duas vezes, nova credencial ativa no servidor e caminho documentado para voltar a versão da aplicação sem apagar dados. |
| P0.2 | Aplicar as duas migrações em ambiente de homologação; conferir permissões por `client_id`, índices, vínculos de contas, campanhas, relatórios e dados antigos. Corrigir qualquer referência órfã antes de liberar escrita. | P0.1 | Inventário de integridade sem cruzamento entre clientes e leitura dos relatórios antigos preservada. |
| P0.3 | Exercitar o ciclo completo com uma conta Google Ads e uma MCC piloto, cada qual com clientes distintos: gerar chave, instalar script, agendar, receber lote, repetir envio, revogar chave e observar falhas. Verificar moeda, fuso da conta, dias sem campanhas e limite de execução do Google Ads. | P0.2 | Métricas conciliadas com a plataforma por conta e dia; nenhum lote aceito para conta fora da lista; reenvio não duplica métricas. |
| P0.4 | Validar tag em domínio piloto e conversão por página de obrigado com consentimento e com webhook do CRM: entrada com UTM, navegação, passagem de etapa, presença online e confirmação de lead/venda. Acrescentar painel de saúde e limites no proxy para a coleta pública. | P0.2 | Funil distingue visita, conversão observada e venda confirmada; origem e `client_id` coerentes; tráfego excessivo visível e contido. |
| P0.5 | Publicar a V1 por cliente piloto, com medição de erros, atraso de dados e uso da quota. Só ampliar após revisar o resultado dos pilotos. | P0.3–P0.4 | Operador consegue localizar falha de script, tag ou CRM sem examinar o banco; plano de retorno executável. |
| P1.1 | Concluir Link Tester no Reports: confirmação humana da campanha sugerida, vínculo com conta/campanha/relatório, histórico da decisão e opção de desfazer. Preservar URL original e final; exigir candidato dentro do mesmo cliente. | P0.2 | Associação persistida somente após confirmação; casos sem evidência ou com mais de 25 candidatos ficam sem associação. |
| P1.2 | Migrar biblioteca, criação, edição, fontes, revisão e publicação dos relatórios para telas React na skin do Reports; reutilizar regras do backend existentes e manter URLs legadas como transição. | P0.2 | Usuário consegue concluir o ciclo do relatório dentro do Reports, inclusive sem projeto; versões e links públicos antigos continuam acessíveis. |
| P1.3 | Completar o onboarding de uma agência e de um usuário exclusivo do Reports: convite/cadastro, seleção inicial só de `client_id`, concessões por cliente e administração de MCC. Projetos e marcas ficam como associação opcional posterior. | P0.2 | Novo usuário autorizado acessa apenas os clientes concedidos; um usuário exclusivo não depende de entrar no Workspace. |
| P1.4 | Evoluir a tag com API explícita de evento, integração GTM e navegação SPA, deduplicação e diagnóstico de instalação. Manter eventos de página e de CRM separados, e atribuição incerta identificada como tal. | P0.4 | Mudanças de rota e eventos configurados aparecem uma vez no funil; a instalação explica páginas sem sinal e divergências de atribuição. |
| P1.5 | Consolidar métricas e relatórios: definições de fonte, janela, fuso, moeda, conversões da plataforma, visitas e vendas confirmadas; filtros de conta e campanha em todas as telas e links compartilháveis. | P0.3–P1.4 | O mesmo recorte produz os mesmos números em visão geral, campanha, Funnel Flow e relatório; moedas diferentes não são somadas indevidamente. |
| P2.1 | Criar adaptadores de ingestão para Meta Ads e Microsoft Ads com contrato comum de conta, campanha, data, métricas, estado da sincronização e reconciliação. | P1.5 | A mesma visão funciona para mais de uma plataforma sem confundir métricas homônimas. |
| P2.2 | Criar conjuntos de dados isolados por cliente no Reports, com vínculos opcionais a marcas/projetos, regras de compartilhamento e auditoria de alterações. | P1.2–P1.3 | Uma agência organiza suboperações dentro do cliente sem multiplicar cadastros nem expor dados entre equipes. |
| P3 | Estudar audiências de conversão, automações e mapas de clique/calor como módulos opcionais, após definir consentimento, finalidade, retenção, custo e qualidade de dados. | P1.4–P2.2 | Protótipo delimitado e aprovado por critérios de privacidade e desempenho antes de ativar coleta adicional. |

## Contratos que devem guiar as implementações

- **Identidade:** `organization_id` + `client_id` delimitam todas as consultas e gravações. A conta de mídia pertence a um cliente; a campanha pertence à conta. MCC é hierarquia, não novo cliente. Scripts são emitidos por cliente/instalação, nunca por campanha.
- **Fontes e verdade:** métricas da plataforma, eventos da tag e confirmações do CRM conservam origem, momento, fuso, estado de processamento e identificador de deduplicação. Visitar uma página de obrigado não equivale a venda confirmada.
- **Escolhas do usuário:** associação de um link, etapa ou conversão ambígua depende de decisão explícita e auditável. Projeto, marca e relatório são vínculos opcionais, criados depois da descoberta automática de contas e campanhas.
- **TypeSafe:** usar para julgamentos semânticos estreitos, como função provável da página, seleção entre candidatas recuperadas e sinalização de evidência insuficiente. IDs exatos, autorização, cálculo, persistência e execução permanecem no código. Guardar a resposta tipada, as probabilidades, a versão da pergunta e a decisão humana para avaliar qualidade; confiança não autoriza associação automática. A chave permanece no servidor.
- **Interface:** skin clara, dock e sidebar do workspace com identidade Reports, largura útil total, cabeçalho até 90 px, duas faixas de filtros até 90 px cada, gráficos ApexCharts e grades de três ou quatro colunas onde houver espaço.

## Primeiro pacote recomendado

Executar P0.1 a P0.4 como um pacote de preparação e piloto. Ele transforma a base já codificada em fluxo verificável de **anúncio → conta/campanha → página → etapa → conversão observada → confirmação do CRM → relatório**. Em seguida, P1.1 e P1.2 removem as duas quebras mais visíveis da experiência no Reports.

## Execução iniciada

| Item | Estado em 25/09/2026 |
| --- | --- |
| P0.1 | Alterações do Reports isoladas na branch `codex/reports-v1-execution`, com commits próprios e [procedimento de implantação](reports-v1-rollout.md). Rotação da credencial TypeSafe compartilhada ainda depende do administrador da integração. |
| P0.2 | Auditoria somente de leitura criada. A conexão configurada é remota e não foi identificada como homologação; nela faltam as tabelas `cadu_reports_*`. Migração e verificação após migração aguardam ambiente de homologação identificado. |
| P0.3–P0.5 | Pilotos Google Ads, MCC, GTM, CRM e publicação restrita aguardam contas e ambiente autorizados. Build e sintaxe locais passaram, sem substituir o piloto. |
| P1.1 | Associação do Link Tester com campanha e relatório, remoção e histórico implementados no backend e React; falta verificar contra banco migrado. |
| P1.2 | Detalhe React, edição de contexto, versões e publicação implementados. Envio/revisão de prints e edição de identidade ainda usam telas anteriores. |
| P1.3 | Concessões para usuários existentes prontas; convite e cadastro autônomo só para Reports pendentes. |
| P1.4 | Tag expõe `trackPage()` para navegação SPA via GTM, com deduplicação imediata; eventos personalizados e diagnóstico de instalação pendentes. |
| P1.5–P3 | Conciliação de métricas, conectores adicionais, conjuntos de dados, audiências e mapas de clique ainda não iniciados. |

## Verificação do plano com TypeSafe

Em 25/09/2026, a API System One respondeu HTTP 200 com `jev-1.13.0` a três perguntas `Choice` independentes sobre o plano: **ordem do piloto coerente** (confiança 0,83), **escopo alinhado** (0,76) e **papel apropriado da TypeSafe** (1,00). A alternativa “outras plataformas tarde” recebeu probabilidade 0,17 na pergunta de escopo; por isso a prioridade P2.1 deve ser revista se um cliente piloto precisar de Meta ou Microsoft Ads para começar. Essa avaliação semântica não comprova o estado do código, a integridade do banco nem a segurança da implantação; os critérios de conclusão da tabela exigem verificação própria.
