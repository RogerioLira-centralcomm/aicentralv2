# Editor Trocr

A mesa Trocar continua em `/parametros/modelagem-criativos/trocar`. Na tela, o produto se chama Trocr: um editor generativo de criativos a partir de uma imagem de entrada. O chrome da Modelagem não muda.

## Visão geral da tela

Quatro regiões, nesta ordem:

1. Header da página — título, subtítulo e o aviso de que as versões são preservadas
2. Faixa de etapas no topo — Upload, OCR, Análise, Edição, Geração, Revisão (número + nome, sem descrição)
3. Canvas central — visualização, comparar, zoom, download e tela cheia
4. Inspetor direito — marca, formato, textos, análise, preservar/alterar, prompt e geração

A tira de versões fica sob o canvas. Nenhuma geração substitui a anterior.

## Fluxo de edição

1. O usuário envia uma imagem. Ela vira `v1 · Original`.
2. `POST /parametros/api/format-lab/swap/read` lê textos e análise na mesma chamada.
3. Os campos de headline, apoio, preço e CTA são preenchidos.
4. O usuário marca o que preservar e o que alterar, e escreve a instrução livre.
5. `POST /parametros/api/format-lab/swap/prompt` devolve o prompt otimizado.
6. Rascunho ou produção chama `POST /parametros/api/format-lab/swap`.
7. A imagem gerada entra no histórico como nova versão.
8. **Usar como base** troca a base ativa e dispara OCR e análise de novo.

## Lógica de versões

O histórico grava no servidor por marca (`brand_profile.trocr`) e também em arquivo. Sem marca, a chave é o usuário. As imagens vão para `/static/uploads/creative_generated/`.

- Toda geração faz `push`. IDs são `v1`, `v2`, `v3`…
- Selecionar uma versão só muda o canvas.
- Duplicar copia imagem e contexto, sem chamar IA.
- A original não exclui.
- `activeId` é o que o canvas mostra. `baseId` é a referência da próxima edição.

## Lógica de OCR dinâmico

A leitura é visão (GPT-4o-mini), não OCR clássico. Sempre que a base muda:

1. a imagem da base é redimensionada no cliente (lado longo 1280) só para a leitura
2. a geração continua usando a imagem cheia
3. textos e análise são repovoados
4. o cache por `versionId` evita reler ao só visualizar

Ver uma versão não relê. Usar como base invalida o cache daquela versão e relê.

## Componentes

| Componente | Onde vive |
|---|---|
| TrocrEditorPage | `templates/parametros/_mc_trocar.html` |
| TrocrFlowSidebar | `templates/parametros/trocr/_flow_sidebar.html` |
| TrocrCanvas / Compare | `templates/parametros/trocr/_canvas.html` |
| TrocrInspectorPanel | `templates/parametros/trocr/_inspector.html` |
| OCRFieldsForm | `templates/parametros/trocr/_ocr_fields.html` |
| CreativeAnalysisChecklist | `templates/parametros/trocr/_analysis.html` |
| PreserveAlterPanel | `templates/parametros/trocr/_preserve_alter.html` |
| OptimizedPromptPanel | `templates/parametros/trocr/_prompt.html` |
| Quality + Generate | `templates/parametros/trocr/_generate.html` |
| VersionHistoryStrip | `templates/parametros/trocr/_versions.html` |
| Estados e toast | `templates/parametros/trocr/_states.html` |
| Store e fluxo | `static/js/mc-trocar.js` |
| Prompt e leitura | `creative_format_lab/swap.py` |

## Estados principais

| Estado | O que o usuário vê |
|---|---|
| vazio | drop zone, etapa Upload atual |
| OCR | etapa OCR atual, campos ainda vazios |
| análise | checkboxes marcados pelo retorno da leitura |
| edição | etapa Edição, prompt atualizando |
| geração | Análise → prompt → geração → finalização |
| revisão | nova versão no histórico, comparar disponível |
| erro | mensagem acionável: tentar de novo, editar insumos, voltar |

Rota de validação visual: `/lab/trocr/states`. Fora de `MC_DESKS`. Sem OpenRouter.

## Regras de UX

- O usuário sempre sabe qual imagem está editando e qual é a base ativa.
- Todas as versões são preservadas.
- Ao enviar uma nova imagem, o OCR roda automaticamente.
- Texto detectado é editável e entra no prompt.
- Preservar e alterar convivem.
- Formato muda composição e recorte. Apresentação (peça / mockup) é chrome no canvas.
- Rascunho e produção são CTAs distintos.

## Persistência

- `GET/POST /parametros/api/format-lab/swap/history`
- A mesa carrega o histórico ao abrir e ao trocar a marca
- Cada geração e o original são gravados após `pushVersion`

## Próximos passos

- Slider before/after
- Upload multipart em vez de data URL
- Modelo mais barato de rascunho
- Cancelar job de geração
