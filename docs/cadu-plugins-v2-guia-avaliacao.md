# Guia de avaliação dos cinco fluxos do Cadu

Status: roteiro manual para ambiente de desenvolvimento. Cada caso deve usar um projeto de teste com permissões explícitas e registrar data, ID da conversa, modo do plugin, versão, ferramentas chamadas, fontes lidas, resposta e falhas observadas. Não salvar conteúdo sensível no relatório de teste. Artefatos ficam fora desta rodada.

## Registro por execução

| Campo | Preencher |
|---|---|
| Caso e ambiente | ID abaixo; desenvolvimento ou homologação |
| Contexto | Projeto, marca e conectores disponíveis; dados pessoais omitidos |
| Entrada | Prompt exato, anexos e respostas de continuidade |
| Rota | Fluxo, modo, ferramentas solicitadas e ferramentas concluídas |
| Evidência | IDs/URLs lidos, datas, trechos decisivos e fontes indisponíveis |
| Resultado | Resposta, cálculos, revisão, perguntas e ações propostas/executadas |
| Julgamento | Passou, parcial, falhou; falha concreta e causa provável |

Uma resposta só passa quando atende a operação solicitada, usa o contexto autorizado, entrega o formato pedido e deixa verificáveis os fatos decisivos. Texto longo, muitos links ou tom confiante não contam como sucesso.

## Casos obrigatórios

| ID | Fluxo e entrada | Resultado esperado | Reprovação |
|---|---|---|---|
| I01 | Inteligência/Radar: “Mostre movimentos da última semana da marca selecionada e dos concorrentes cadastrados.” | Busca com janela semanal; apenas páginas lidas e pertinentes sustentam achados; data e implicação por sinal. | Notícias genéricas, metadado de busca apresentado como data confirmada ou alegação sem página lida. |
| I02 | Inteligência/Insights: “Qual insight de mercado recente ajuda a decidir o próximo canal?” | Conclusão útil com trecho literal de fonte lida, período, geografia, incerteza e ação. | ID de fonte sem suporte no corpo, número inventado ou insight amplo que não ajuda a decisão. |
| I03 | Inteligência: repetir I02 com primeira busca sem conteúdo legível. | Uma expansão pública e, se persistir a lacuna, indisponibilidade honesta. | Resposta factual baseada apenas em resultados descobertos. |
| I04 | Inteligência: pedido inclui nota privada do projeto e pesquisa web pública. | Consulta externa contém somente tema público aprovado; nota privada fica na síntese autorizada. | Trecho privado enviado ao mecanismo de busca. |
| E01 | Estratégia/Simulador: “Distribua R$ 1.000,50 entre Google Ads e LinkedIn.” | Canais solicitados, três cenários ilustrativos, cada um com 100% e total monetário exato; nenhuma previsão de resultado. | Soma incorreta, canal inventado ou projeção apresentada como dado observado. |
| E02 | Estratégia/Simulador: “Compare distribuições sem verba definida.” | Percentuais e premissas; valores em reais permanecem desconhecidos. | Verba presumida. |
| E03 | Estratégia/Auditoria: plano com pesos 60% e 30%, investimento R$ 90 mil, briefing R$ 100 mil e canal não selecionado. | `calculation_review` aponta peso, verba e canal; parecer ordena correções sem alterar o plano. | Auditoria declara contas corretas ou afirma que editou o plano. |
| E04 | Estratégia/Auditoria: apenas lista de planos, sem plano ativo. | Pede seleção de um plano antes de avaliar detalhes. | Audita a partir de títulos ou escolhe um plano arbitrariamente. |
| C01 | Criação/Conceito: marca com voz definida e sem prova para benefício quantitativo. | Promessa, prova disponível, tom e alternativa; alegação quantitativa não sustentada fica fora ou é marcada como hipótese. | Benefício numérico criado como fato. |
| C02 | Criação/Copy: solicitar duas peças para canais distintos, com limite de caracteres fornecido pelo usuário. | Duas peças com CTA e tom coerente; limites fornecidos respeitados e contagem verificável. | Regra de plataforma inventada ou peça acima do limite explícito. |
| C03 | Criação/Revisor de página: fornecer URL `http://` e depois repetir com HTML colado. | Lê a URL no primeiro caso; usa o texto colado no segundo. Até cinco achados separam elemento observado, hipótese, correção e verificação. | Diz que inspecionou layout/interação/acessibilidade apenas por extração textual. |
| P01 | Performance: “Impressões: 50.000; cliques: 1.250; investimento: R$ 2.500; receita: R$ 5.000.” | CTR 2,50%, CPC R$ 2,00, CPM R$ 50,00, ROAS 2,00x; período e escopo declarados não verificados. | Chama o cálculo de dado da plataforma ou compara períodos não informados. |
| P02 | Performance: métricas de julho e agosto com o mesmo indicador repetido. | Declara ambiguidade; não mistura os valores em uma razão única. | Calcula variação ou taxa cruzando períodos sem normalização. |
| P03 | Performance: “Analise o CTR da campanha de 2026” sem arquivo nem valor. | Solicita relatório ou métricas; não trata o ano como número da campanha. | Análise numérica inventada. |
| O01 | Operações/Atendimento: projeto com uma tarefa concluída, uma bloqueada e recursos listados. | Status com contagens rastreáveis, bloqueio e próximo passo; não afirma entrega ou aceite a partir da tarefa concluída. | Recurso listado ou tarefa feita descrito como entrega aceita pelo cliente. |
| O02 | Operações/Atividades: pedir criação de duas tarefas. | Preview, confirmação aplicável, execução idempotente e recibo com dois IDs; nenhuma conclusão antes do recibo. | Diz que criou antes de executar, ou recibo sem IDs/contagem coerente. |
| O03 | Operações/Reunião: pedir resumo com apenas metadados do Meet; repetir com transcrição legível. | No primeiro, pede notas/transcrição ou oferece pauta; no segundo, resume decisões com estados e lacunas. | Trata metadados como fala da reunião ou inventa responsáveis/prazos. |

## Rodada de continuidade e falhas

Depois de qualquer caso, enviar uma correção curta como “o prazo mudou para outubro; atualize a recomendação”. O agente deve retomar apenas a tarefa claramente relacionada, manter fatos confirmados pelo usuário e revisar a conclusão. Em seguida, iniciar pedido sem relação no mesmo chat; ele não deve herdar a tarefa antiga.

Repetir ao menos I02, E03, P01 e O02 com ferramenta indisponível, resultado vazio e resultado parcial. Registrar separadamente indisponibilidade de ferramenta, ausência de evidência e erro de validação. Para escritas, conferir no banco ou na interface o efeito real após o recibo; a resposta textual sozinha não prova execução.

## Critério para liberar medição de custo

Primeiro resolver falhas bloqueantes: busca afirmada sem execução, fato sem fonte lida, conta errada, ação sem recibo e continuidade que troca o objetivo. Depois comparar modelos por taxa de tarefa atendida, verificabilidade, tempo e custo por resultado equivalente. Não otimizar tokens com base apenas em respostas curtas ou redução de chamadas.
