# Plano completo de refatoração — página de marca

## Objetivo

Transformar a página de marca em um dossiê progressivo, no qual a quantidade e a autoridade das informações determinam o que aparece. A página não deve simular conteúdo, prontidão ou aprovação quando a auditoria não foi concluída.

Referências de validação:

- Marca 25, Centralcomm 2: estado `insufficient_information`.
- Marca 28, BDMG: estado `data_available_unverified` ou dossiê completo após formalização da aprovação.

## Princípio central

Separar explicitamente três dimensões hoje misturadas:

1. Dados disponíveis: informações importadas, manuais ou legadas.
2. Auditoria: coleta, análise, revisão e rastreabilidade.
3. Identidade aprovada: snapshot validado para uso em projetos, conversas, Planner e Studio.

O percentual atual não pode representar simultaneamente essas três dimensões.

## Máquina de estados da página

### `insufficient_information`

Condição:

- sem auditoria concluída;
- sem perfil substancial;
- pode ou não possuir ativos enviados.

Exibir:

- cabeçalho mínimo;
- ilustração já produzida para estado vazio;
- mensagem “Ainda não há informações suficientes sobre esta marca”;
- ação para corrigir/adicionar fontes e iniciar auditoria;
- biblioteca de ativos sempre disponível.

Ocultar:

- percentual de prontidão;
- direção de trabalho;
- kit de contexto;
- atlas de marca e mercado;
- fontes vazias;
- projetos como “em contexto”;
- conversa sobre a marca como ação principal;
- coluna vazia de cores e tipografia.

### `audit_failed`

É uma variação de `insufficient_information`, não um dossiê completo.

Exibir:

- causa legível;
- campo/site que precisa ser corrigido;
- ação “Corrigir e tentar novamente”;
- histórico técnico recolhido em detalhes;
- ativos preservados.

### `audit_processing`

Exibir:

- ilustração e progresso da auditoria;
- etapa atual, estimativa e modo completo/profundo;
- aviso de processamento em segundo plano;
- ativos disponíveis para novos uploads.

Não renderizar blocos de identidade como se já fossem definitivos.

### `data_available_unverified`

Condição:

- existem dados de identidade;
- não existe snapshot aprovado ou auditoria formal concluída.

Exibir:

- resumo disponível;
- direção da marca;
- coluna de cores e fontes;
- selos discretos de origem: manual, importado, proposto ou verificado;
- chamada única para auditar/verificar.

Não usar as palavras “aprovado”, “pronto” ou “em contexto” sem evidência correspondente.

### `pending_approval`

Exibir:

- proposta comparável com identidade atual;
- evidências, confiança e campos bloqueados;
- ações revisar, corrigir e aprovar;
- coluna visual com sinalização de proposta.

### `approved`

Exibir o dossiê completo e habilitar “Conversar sobre a marca” como ação principal.

## Refatoração por área da página

### 1. Navegação e topo

Manter:

- voltar para Marcas;
- logo ou iniciais;
- nome;
- setor;
- site oficial como link secundário.

Alterar:

- reduzir o título de 56 px para aproximadamente 44–48 px em desktop;
- peso do título entre 600 e 650, evitando preto excessivamente pesado;
- resumo com peso 400 e largura máxima de 68 caracteres;
- remover percentual do cabeçalho;
- exibir um estado textual curto: “Sem auditoria”, “Em análise”, “Revisão pendente”, “Aprovada”.

Ações:

- `approved`: Conversar sobre a marca, Editar, Mais ações;
- sem aprovação: Auditar informações, Editar dados, Mais ações;
- falha: Corrigir e tentar novamente, Editar dados;
- processamento: nenhuma ação concorrente, apenas Ver andamento.

### 1.1 Edição rápida da identidade

Substituir o modal extenso “Editar identidade” por um modal curto chamado
“Editar dados básicos”. Ele deve conter somente:

- nome da marca;
- site oficial;
- logo principal, com prévia, substituir e remover;
- cor principal;
- cor secundária.

O setor não precisa ocupar o fluxo principal. Quando necessário, pode ser
alterado pela conversa com o Cadu/MCP junto com o restante do contexto.

Remover do modal:

- essência da marca;
- posicionamento;
- público e contexto;
- oferta prioritária;
- diferenciais;
- provas e sinais;
- tom e linguagem;
- direção criativa;
- elementos visuais;
- elementos obrigatórios;
- elementos a evitar.

Esses campos estratégicos devem ser alterados pela conversa com o Cadu. A
ferramenta MCP `brands.update_identity` já aceita patches parciais desses
campos, preserva os demais valores, registra histórico e exige confirmação.
O fluxo de logo já existe separadamente em
`brands.prepare_logo_upload`, portanto não é necessário manter um formulário
estratégico paralelo na interface.

Ao lado de “Direção da marca”, substituir “Editar direção” por:

- botão “Atualizar com o Cadu”;
- abertura da conversa já contextualizada na marca;
- sugestão inicial: “Quero atualizar a direção desta marca”.

Para agentes do cliente com MCP, a mesma mudança continua disponível pelas
ferramentas de marca, respeitando tenant, permissão e confirmação.

### 2. Faixa de auditoria

Substituir a caixa larga atual por um bloco de decisão mais compacto.

- uma mensagem;
- uma explicação curta;
- uma ação principal;
- cor de estado apenas em ícone, marcador ou pequena borda, não em um retângulo tingido de ponta a ponta;
- detalhes técnicos ficam recolhidos.

Eliminar a repetição entre faixa, coluna de prontidão e botão “Preparar análise”.

### 3. Estado insuficiente ou falho

Usar a ilustração já criada como principal elemento visual.

Composição:

```text
[ ilustração ]
Ainda não há informações suficientes sobre esta marca
Faça uma auditoria para identificar posicionamento, público e sistema visual.

[ Corrigir fontes e auditar ] [ Adicionar informações ]
```

A biblioteca de ativos aparece imediatamente abaixo.

### 4. Direção da marca

Renomear “O que deve guiar cada entrega” para “Direção da marca”.

Estrutura:

- resumo/essência em texto regular;
- grade de quatro itens: Público, Oferta, Tom e Diferenciais;
- Direção criativa em bloco próprio;
- regras extensas convertidas em listas curtas;
- posicionamento só aparece se for diferente do resumo.

Tipografia:

- valores em peso 400 ou 500;
- negrito apenas em títulos e palavras funcionais;
- remover `<b>` como recipiente padrão de parágrafos;
- corpo entre 13 e 15 px, line-height entre 1.5 e 1.65.

### 5. Coluna lateral de cores e fontes

Preservar: a BDMG mostrou que esta coluna funciona bem quando há conteúdo.

Alterar:

- remover o percentual grande e a recomendação duplicada;
- começar diretamente em “Sistema visual”;
- manter cores, nome/uso e ação de copiar;
- manter fontes e seus papéis;
- acrescentar origem/confiança de forma discreta;
- usar “proposta” ou “verificada”, não “aprovada” quando não houver snapshot aprovado;
- mover Projetos para baixo do sistema visual ou para uma seção independente no corpo;
- reduzir divisórias internas: usar espaço vertical e agrupamento; linha apenas entre Cores, Tipografia e Projetos.

### 6. Contexto para conversas e artefatos

Remover a seção atual inteira.

Motivos:

- duplica logo, site e paleta;
- o link interno do Workspace não é útil;
- ocupa espaço com quatro células e muitas linhas.

Substituição:

- logo fica no cabeçalho;
- site fica no cabeçalho;
- cores ficam na lateral;
- a disponibilidade para produtos aparece em um único status: “Disponível no Workspace, Planner e Studio” somente após aprovação.

### 7. Marca, mercado e execução

Renderizar apenas quando houver conteúdo.

Reorganizar em abas ou grupos recolhíveis:

- Marca: produtos, diferenciais, provas;
- Público: segmentos, personas e ângulos;
- Comunicação: motivos visuais, obrigatório, evitar;
- Mercado: concorrentes e oportunidades;
- Presença: contatos, endereços, políticas e canais.

Não mostrar um título seguido de vazio.

Cada grupo deve usar listas, não texto unido por `·`.

### 8. Evidências e rastreabilidade

Unificar:

- Evidências reunidas;
- Fontes usadas na auditoria;
- Auditorias realizadas;
- captura visual/OCR.

Criar uma única seção “Auditoria e evidências”, fechada por padrão no dossiê aprovado.

Resumo visível:

- modo da auditoria;
- data;
- páginas analisadas;
- evidências visuais;
- status da revisão.

Conteúdo expandido:

- fontes;
- confiança por campo;
- screenshot e OCR;
- agentes/revisões;
- histórico de execuções e erros.

Não exibir seção de fontes quando a lista estiver vazia.

### 9. Campanhas

Exibir apenas se houver campanhas observadas ou oportunidades reais.

- remover rótulos repetidos;
- título, objetivo, público e canais em hierarquia simples;
- ação “Criar projeto” apenas para usuários autorizados;
- campanhas não contam como identidade aprovada.

### 10. Projetos vinculados

Remover duplicação entre a lateral e a grade inferior.

Opção recomendada:

- lista compacta na lateral quando houver até três projetos;
- link “Ver todos” para quantidades maiores;
- não dizer “em contexto” se o projeto tiver zero fontes ou se a identidade não estiver aprovada;
- estados: Vinculado, Recebendo contexto, Contexto disponível.

### 11. Ativos da marca

Manter disponível em todos os estados.

Melhorias:

- subir para logo depois do estado vazio/falha;
- separar por Logo, Referências, Criativos e Outros;
- deixar clara a diferença entre “arquivo aceito” e “identidade aprovada”;
- destacar “Usar como logo” nos uploads que ainda são referência;
- mostrar dimensões, formato, variante e origem quando disponíveis;
- retirar linhas e contornos de todos os cartões; usar fundo e espaçamento;
- manter contorno apenas no dropzone, por ser área interativa.

### 12. Rodapé da página

- histórico e ações destrutivas ficam em “Mais ações”;
- remover qualquer seção vazia residual;
- terminar a página nos ativos ou na auditoria expandida, conforme o estado.

## Redução de linhas

Remover:

- linha inferior do hero;
- borda superior padrão de toda `.cadu-ds-brand-section`;
- linha vertical entre corpo e lateral;
- linha entre todos os itens da direção;
- moldura quadriculada do kit de contexto;
- linha em cada cor e fonte;
- linha em cada item de projeto;
- linha automática em cada bloco do atlas.

Manter somente:

- separação entre grandes capítulos, no máximo 3 ou 4 na página inteira;
- contornos de campos, botões e dropzone;
- divisória discreta dentro de detalhes expansíveis.

Usar espaço de 32–56 px entre capítulos e 12–20 px entre itens como principal recurso de hierarquia.

## Redução de negritos

Regras:

- título principal: 600–650;
- títulos de seção: 550–600;
- rótulos: 500–600;
- corpo e valores: 400;
- números operacionais: 500–600;
- botões: 550–600;
- negrito dentro de conteúdo somente para uma decisão ou alerta.

Trocas de implementação:

- `FilledReading` deve renderizar valores com `<p>` ou `<span>`, não `<b>`;
- projetos e ativos usam peso 550 somente no nome;
- hexadecimais podem usar peso 500;
- textos de direção e listas permanecem regulares.

## Arquivos principais

- `frontend/cadu-design-system/components/WorkspaceBrand.jsx`
  - máquina de estados;
  - renderização condicional;
  - redução de `IdentityDialog` para nome, site, logo e duas cores;
  - envio das mudanças estratégicas para a conversa com o Cadu;
  - remoção do `BrandKit` atual;
  - unificação da auditoria;
  - nova hierarquia de direção, projetos e ativos.

- `frontend/cadu-design-system/styles.css`
  - nova hierarquia tipográfica;
  - retirada de bordas;
  - espaçamento entre capítulos;
  - preservação e refinamento da coluna visual;
  - responsividade.

- `aicentralv2/cadu_workspace/routes.py`
  - fornecer estado derivado explícito;
  - separar disponibilidade, auditoria e aprovação;
  - não chamar paleta de aprovada sem snapshot;
  - corrigir readiness semântico.

- `aicentralv2/cadu_workspace/brand_mcp_service.py`
  - manter `brands.update_identity` como fonte de edição estratégica;
  - manter o patch parcial e o histórico de alterações;
  - usar `brands.prepare_logo_upload` para substituição da logo;
  - não duplicar a lógica estratégica no formulário da página.

- `tests/test_workspace_brands.py`
  - testes dos cinco estados;
  - ausência de blocos vazios;
  - ausência do link interno;
  - ativos sempre disponíveis;
  - ações corretas por estado.

## Sequência de implementação

1. Criar função de domínio que derive o estado da marca.
2. Corrigir o contrato do bootstrap e a semântica de prontidão.
3. Dividir `WorkspaceBrand` em componentes por capítulo e estado.
4. Reduzir o modal de edição aos cinco dados básicos e conectar a troca de logo.
5. Direcionar edições estratégicas para a conversa/MCP.
6. Implementar estado insuficiente/falho usando a ilustração.
7. Refatorar o estado completo usando BDMG.
8. Remover o kit duplicado e unificar evidências.
9. Reduzir pesos tipográficos e bordas.
10. Ajustar desktop, tablet e mobile.
11. Criar testes unitários dos estados e dos dois fluxos de edição.
12. Fazer verificação visual com marcas 25 e 28.

## Critérios de aceite

- Marca 25 não mostra percentual, direção, paleta, fontes, fontes públicas ou kit vazio.
- Marca 25 mostra erro, ação de correção, ilustração e os dois ativos.
- BDMG mantém a coluna de cores e fontes.
- BDMG não chama dados de aprovados sem snapshot aprovado.
- Link interno do Workspace não aparece.
- Não existe seção sem conteúdo.
- Não existe informação operacional repetida em dois lugares.
- A página usa no máximo quatro grandes divisórias visuais.
- Textos corridos não são renderizados em negrito.
- Upload de ativos funciona em todos os estados.
- “Editar dados básicos” contém apenas nome, site, logo e duas cores.
- Nenhum campo estratégico permanece no modal.
- “Atualizar com o Cadu” abre uma conversa contextualizada na marca.
- Alterações estratégicas continuam possíveis por `brands.update_identity`.
- Desktop e mobile preservam ordem de decisão e ações.
- Testes cobrem `insufficient_information`, `audit_failed`, `audit_processing`, `data_available_unverified`, `pending_approval` e `approved`.
