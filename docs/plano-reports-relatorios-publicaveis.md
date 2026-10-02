# Reports → Relatórios publicáveis, editáveis, com métricas personalizadas e agentes

Data: 2026-10-02

## 1. O que existe hoje (revisão)

| Peça | Como funciona hoje | Problema |
| --- | --- | --- |
| Link público `/connect/r/<token>` | Um link por relatório (`cadu_connect_report_public_links`, único por `report_id`), com prazo de 7/30/90 dias ou sem prazo, e revogável | Mostra **só texto** (objetivo, metas, notas). Não mostra os Resultados, o funil nem as métricas. Sempre mostra a **última revisão**, então uma edição depois de publicar já aparece para o cliente. |
| Publicação | Dois caminhos duplicados: o form antigo `/relatorios/<id>/publicar` e a API `/api/v2/reports/workspaces/<id>/publish` | Duas lógicas para manter. Não existe a lista "o que está publicado" nem "relatórios principais". |
| Edição | `POST /workspaces/<id>/document` edita só objetivo, metas, notas, datas e cor. Cada salvamento vira uma versão (`..._workspace_versions`) | Sem blocos, sem ordem, sem esconder seções, sem rascunho separado do que foi publicado. |
| Resultados (novo) | `GET /workspaces/<id>/results`: mídia por campanha ou fluxo, comparação de períodos e funil com a Super Tag | Calculado na hora, só na tela interna. Não fica gravado na versão. |
| Métricas | As fontes enviadas (arquivo ou captura) passam pela revisão TypeSafe (`review_source_metrics`) e viram métricas revisadas por fonte | A métrica vale só para aquela fonte. Não existe catálogo do cliente (nome, fórmula, unidade, meta) reutilizável entre relatórios. |
| Agentes | `suggest_report_plan` escolhe **uma** próxima ação; `review_source_metrics` confere números contra os trechos | Nenhum agente olha a qualidade dos dados capturados nem propõe uma **nova versão** do relatório. |

## 2. Objetivo

1. Os relatórios ganham **links publicáveis**: o principal, que acompanha a última versão publicada, e um por versão, congelado.
   Os dois mostram os Resultados reais.
2. O usuário **edita o relatório em blocos** e decide o que vai para o cliente.
3. O cliente tem **métricas personalizadas** (catálogo) usadas nos relatórios.
4. Os **agentes** melhoram os dados capturados e **propõem novas versões**. Quem aprova é sempre uma pessoa.

## 3. Fases

### Fase A — Publicação com versão congelada (prioridade)
- **Publicar = congelar uma versão.** A versão publicada guarda o documento **e um retrato dos Resultados** (KPIs, funil, campanhas, período e moeda) em `snapshot jsonb`. Editar depois não muda o que o cliente vê até a pessoa publicar de novo.
- **Dois tipos de link:**
  - **Principal** (`/r/<token>`): sempre a última versão publicada. É o link que se manda ao cliente.
  - **Por versão** (`/r/<token>?v=3`): fica para o histórico e a auditoria.
- **Página pública nova:** Resultados, funil do fluxo, tabela de campanhas, métricas personalizadas e texto. Funciona em celular, sem dados pessoais e sem imagens das fontes, e inclui o rodapé com período, versão e data.
- **"Principais":** marcar relatórios como principais (fixados no topo). Na biblioteca, filtros "Publicados", "Principais" e "Em edição", com o status do link (ativo, expira em X dias, revogado).
- **Uma rota só:** o form antigo `/relatorios/<id>/publicar` vira um redirecionamento para a API.
- **Banco:** `cadu_connect_report_workspace_versions.snapshot jsonb`, `cadu_connect_report_public_links.revision` (null = segue a principal), `cadu_connect_report_workspaces.pinned boolean`.

### Fase B — Edição em blocos
- **O documento vira uma lista de blocos:** `resumo`, `resultados`, `funil`, `campanhas`, `métricas`, `texto`, `recomendações` e `próximos passos`. Cada bloco tem título editável, pode ser escondido e pode ser reordenado.
- **Rascunho e publicado:** a tela mostra "alterações não publicadas" e um botão "Publicar nova versão" com nota obrigatória.
- **Comparar versões:** diff do texto e dos números entre a versão N e a N−1, que reaproveita as versões já gravadas.
- **Compatibilidade:** os campos atuais (objetivo, metas, notas) viram blocos padrão. Os relatórios antigos abrem sem migração manual.

### Fase C — Métricas personalizadas
- **Catálogo por cliente** (`cadu_reports_custom_metrics`):
  - nome, definição, unidade, meta opcional e direção ("maior é melhor");
  - a **origem**, que pode ser:
    - uma *fórmula* sobre as métricas base (custo, cliques, impressões, conversões, valor, entradas e conversões do fluxo, sessões de uma etapa);
    - um *valor manual*, revisado;
    - um *valor importado* de arquivo, via `custom_values`.
- **Fórmulas** com parser limitado: + − × ÷, parênteses e só as métricas base. Sem `eval`. Exemplo: `custo / conversões_fluxo`.
- **Uso:** o bloco "Métricas" do relatório escolhe métricas do catálogo. O valor é calculado no período do relatório e entra no retrato publicado.
- **Para os agentes:** cada métrica tem definição e evidência, então eles sabem o que ela significa.

### Fase D — Agentes
Todos rodam pelo TypeSafe, com saída validada. **Nenhum escreve direto**: tudo vira proposta para aprovar.

1. **Revisor de dados capturados:** aponta problemas nos dados do relatório, com evidência, e sugere a ação. Exemplos:
   - dias sem dados no período;
   - o mesmo dia vindo do script **e** de arquivo (soma duplicada);
   - campanhas recebidas sem cadastro;
   - conversões da mídia muito diferentes das conversões do fluxo;
   - etapa do fluxo sem eventos;
   - moedas misturadas.

   As ações sugeridas reaproveitam o que já existe, por exemplo "criar campanha do Google Ads", "ligar campanha ao fluxo" ou "ignorar origem duplicada".
2. **Redator de nova versão:** a partir dos resultados novos, das métricas personalizadas e da versão anterior, propõe um **diff** (texto dos blocos e destaques). A pessoa aceita tudo ou por bloco, e isso vira a versão N+1 em rascunho. Publicar continua manual.
3. **Sugestor de métricas:** com base no objetivo e nas metas do relatório, sugere métricas para o catálogo, como "custo por lead qualificado". A pessoa aprova a fórmula.
4. **Histórico:** cada execução fica em `record_run`, com o que foi proposto e o que foi aceito, para medir a qualidade dos agentes.

## 4. Ordem e tamanho

| Fase | Entrega | Depende de |
| --- | --- | --- |
| A | Link principal e por versão, página pública com Resultados, "Principais" | Migração pequena (3 colunas) |
| B | Editor em blocos, rascunho/publicado, comparar versões | A |
| C | Catálogo de métricas, fórmulas, bloco de métricas | B (bloco) |
| D | Revisor de dados → Redator de versão → Sugestor de métricas | A–C |

## 5. Decisões em aberto

1. **Link principal:** deve seguir automaticamente cada nova publicação? Recomendo **sim**, e o link por versão fica para o histórico.
2. **Página pública:** precisa de **senha opcional** ou do logo do cliente (cobrand já existe no documento)?
3. **Métricas personalizadas:** valem para o cliente todo ou por relatório? Recomendo catálogo do cliente, escolhido por relatório.
4. **Agente revisor:** roda automaticamente a cada envio do script, ou só quando alguém clica "Revisar dados"? Recomendo sob demanda primeiro.
5. **Migrações:** as migrações recentes ainda não foram aplicadas no banco remoto. Quem aplica e quando?
