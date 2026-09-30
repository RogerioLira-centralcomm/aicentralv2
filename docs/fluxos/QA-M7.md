# QA final do módulo de Fluxos — M7

Executado em 2026-09-30 com o navegador local, contratos simulados e testes do repositório. A matriz abaixo segue a numeração de `RECON.md`. **Coberto** significa que houve correção ou verificação automatizada/visual; **decisão** indica comportamento preservado; **pendente em dados reais** exige o ambiente com o inventário e os eventos da Centralcomm.

| # | Situação | Evidência ou decisão |
|---|---|---|
| 1 | Coberto | M1: toast fixo, teste de posição antes/depois de publicar. |
| 2 | Coberto | M1: pluralização em `flowFeedback`, teste unitário. |
| 3 | Pendente em dados reais | Faixas amarelas não apareceram em 1440×900 nem em 1280×800; sem captura do fluxo Centralcomm, não há elemento seguro a remover. |
| 4 | Coberto | M1: estado e salvamento no cabeçalho; teste de recuperação do rascunho. |
| 5 | Coberto | M1/M5: botão bloqueado, resposta 422 em chamada direta. |
| 6 | Coberto | M3/M6: enquadramento e guia inicial; capturas de 1440×900 e 1280×800. |
| 7 | Decisão | Atribuição React Flow preservada até confirmar condição de licença (D23). |
| 8 | Coberto | M6: minimapa recolocável e legenda de Conexões no canvas. |
| 9 | Coberto | Atalho de comandos tem rótulo e indicação ⌘K/Ctrl K; Escape verificado. |
| 10 | Coberto | M6: controles de zoom com rótulos e minimapa acessível. |
| 11 | Coberto | Rail usa rótulos acessíveis distintos para montar, explorar e adicionar nós. |
| 12 | Coberto | M6: painéis usam `ReportsPanelShell` e Escape fecha. |
| 13 | Coberto | M6: seleção enquadra nó e fecha explorador; captura e teste em 1280×800. |
| 14 | Coberto | M6: teste confirma largura do documento ≤1280 px. |
| 15 | Coberto | Busca de nós usa `ReportsFieldInput`; busca de páginas do catálogo foi verificada com 539 itens. |
| 16 | Coberto | Ícones de plataformas e QR Code verificados no registro; QR usa `QrCode01`. |
| 17 | Coberto | Inspector mantém abas Resumo/Configuração com seleção e navegação por setas. |
| 18 | Coberto | M2: contagens explícitas de descobertas, verificadas, no fluxo e excluídas. |
| 19 | Coberto em fixture | M2: agrupamento global evita repetição; inventário Centralcomm real ainda indisponível. |
| 20 | Coberto em fixture | M2: grupo PT/EN único por chave de tradução; teste de navegador. |
| 21 | Coberto | M2: prévia e confirmação antes de agrupar. |
| 22 | Coberto | Catálogo mostra título completo e URL em tooltip próprio acessível por foco. |
| 23 | Coberto | M3: posição X deriva da Etapa; captura do canvas. |
| 24 | Coberto | M3: inspector, arrasto e teclado sincronizam Etapa e posição. |
| 25 | Coberto | M3: Página em Origem antiga é normalizada de forma conservadora. |
| 26 | Coberto em fixture | M2/M3: traduções podem ser reunidas sem apagar IDs e URLs. |
| 27 | Coberto | M3/M6: miniatura e nome aparecem em nó selecionado na captura de 1280×800. |
| 28 | Coberto | QR Code usa rótulo próprio e ícone reconhecível. |
| 29 | Coberto | M5: Canal isolado recebe aviso e ação de conectar. |
| 30 | Coberto | M6: toolbar usa Duplicar nó, Remover do fluxo e Atualizar captura. |
| 31 | Coberto | M6: contagem de Conexões fora do Funil abre navegação completa. |
| 32 | Decisão | Handles aparecem na borda da miniatura selecionada; captura de 1280×800 não mostra obstrução. |
| 33 | Coberto | M4: Funil não corta Conexões por quantidade. |
| 34 | Coberto | M4: traço diferencia planejada, medida, simulada e Retorno; legenda textual. |
| 35 | Pendente em dados reais | O roteamento visual de 200 nós foi medido, mas cruzamentos do grafo Centralcomm precisam de revisão com seu layout salvo. |
| 36 | Coberto em fixture | M4: Retorno longo tem direção e controle; precisa comparar com dados reais. |
| 37 | Coberto | M4: volume/taxa ou estado sem dados por Conexão; teste de período sem eventos. |
| 38 | Coberto | M4: setas permanecem configuradas; direção também aparece na legenda e no Retorno. |
| 39 | Coberto | M6: título nativo removido do nó que já tem hover próprio. |
| 40 | Coberto | M7: rótulos de Etapa, função e origem traduzidos; teste de mapeamento. |
| 41 | Coberto | M3: Tipo de página, Etapa e função na jornada são campos independentes. |
| 42 | Coberto | M5–M7: Nó/Etapa/Conexão/Retorno/Pendência e ações padronizadas na área de Fluxos. |
| 43 | Coberto | M5: Conversão válida sem bloqueio no fixture compartilhado. |
| 44 | Coberto | M5/M7: painel único para Pendências, com bloqueios e avisos separados. |
| 45 | Coberto | M5: mensagem e consequência completas, quebra de linha no painel. |
| 46 | Coberto | M5: ação em todos os itens; localização de nó/Conexão ou abertura do próximo passo. |
| 47 | Coberto | M5: mensagem de Retorno sem nó de condição em PT-BR. |

## Percursos

| Perspectiva | Passos verificados | Resultado |
|---|---|---|
| Criar e publicar | Guia inicial → adicionar Canal/Página/Conversão → corrigir Pendência → confirmação de versão → publicar | Navegador M1 e fixture M5; bloqueio da API confirmado. |
| Interpretar dados | Abrir versão publicada → selecionar Conexão → trocar camada → comparar período observado e sem eventos | Navegador M4/M6; ausência de dados não aparece como 0%. |
| Consultar sem editar | Abrir versão publicada como viewer → ler monitor → testar ação Publicar | A leitura abriu e Publicar permaneceu desabilitado. |

## Volume e IA

- O catálogo com 539 páginas passou no teste de busca, prévia e agrupamento PT/EN. O teste de 200 nós registrou mediana de 16,7 ms por quadro, p95 de 28,6 ms e cerca de 56 quadros/s durante arrasto; o painel lateral não sofreu mutações. Esses valores são do Chromium local, com fixture, e não medem rede ou banco.
- Não existe, neste checkout, amostra rotulada de páginas Centralcomm com respostas TypeSafe e decisões humanas suficientes para estimar acertos, falsos vínculos, correções, custo e latência. A decisão é manter a sugestão existente opcional e não disponibilizar pareamento ou busca semântica novos. Uma medição posterior deve usar casos reais revisados e registrar tokens, tempo, custo e decisão humana antes de qualquer liberação.
- Os problemas 3 e 35, a triplicação original do grupo Centralcomm, eventos reais e migrations aplicadas no ambiente de destino continuam como verificação operacional. O módulo não depende desses dados para salvar ou publicar um fluxo válido, mas a aceitação do cenário Centralcomm específico depende deles.
