# Plano detalhado de alteração — CentralX Comercial Planner

## 1. Escopo

Evoluir o fluxo real do Smart Planner Comercial para que a página única pública seja uma folha executiva navegável, personalizada por marca e alimentada pelos dados reais do planejamento.

Rota de referência:

`/smart-planner/p/EExkhWnyzq519g/editar?folha=1`

O editor continua sendo o `canvas.html` com modo `folha=1`. A página pública continua sendo servida pelas rotas `/smart-planner/p/<token>` e `/proposta`.

## 2. Resultado esperado

O gestor deverá conseguir:

1. abrir a folha do planejamento;
2. revisar os dados confirmados do plano;
3. selecionar a marca visual do relatório;
4. escolher ou solicitar um hero personalizado;
5. visualizar a galeria de imagens geradas;
6. aplicar uma variação;
7. revisar canais, mix, criativo e defesa;
8. publicar um one page público navegável;
9. entregar o contato do executivo e um WhatsApp já contextualizado pelo nome do plano.

## 3. Fluxo atual a preservar

```text
briefing
  -> revisão
  -> geração one_page
  -> dados_detectados.folha / one_page_v2
  -> /p/<token>/editar?folha=1
  -> canvas.html
  -> salvar revisão
  -> /p/<token> público
```

Arquivos principais:

- `aicentralv2/smart_planner/routes.py`
- `aicentralv2/smart_planner/editor.py`
- `aicentralv2/smart_planner/one_page.py`
- `aicentralv2/smart_planner/canvas.py`
- `aicentralv2/smart_planner/public_view.py`
- `aicentralv2/templates/smart_planner/canvas.html`
- `aicentralv2/templates/smart_planner/public.html`
- `aicentralv2/templates/smart_planner/public_document.html`
- `aicentralv2/static/css/smart_planner_public_v3.css`

## 4. Nova arquitetura da folha

Manter os quatro cards editoriais atuais. O ecossistema de canais entra como
subestrutura do card de mercado e também pode aparecer como apoio visual na
página pública; não criar uma quinta seção `channels` no contrato da folha.

Ordem editorial da folha:

1. cabeçalho do anunciante;
2. tese estratégica;
3. criativo funcionando no canal;
4. dado de mercado com ecossistema de distribuição e densidade do mix;
5. defesa comercial;
6. quadro público, QR e WhatsApp.

O one page não deve virar um documento longo. A navegação será por estados/cartões, com transição lateral ou fade, indicadores de progresso e suporte a teclado, toque e rolagem como fallback.

## 5. Contrato de dados proposto

### 5.1 Ecossistema de canais dentro do card de mercado

Adicionar `channel_roles` ao card `market`, preservando o contrato de quatro
cards (`strategy`, `creative`, `market`, `defense`):

```json
{
  "type": "market",
  "title": "Ecossistema de distribuição",
  "body": "",
  "items": [
    {
      "id": "serasa",
      "label": "Serasa",
      "logo": "/static/...",
      "role": "Ambiente proprietário",
      "status": "confirmed|proposed"
    },
    {
      "id": "display-network",
      "label": "Rede de portais",
      "logo": "/static/...",
      "role": "Cobertura contextual",
    "status": "confirmed|proposed",
    "count": null
    }
  ],
  "overflow_label": "+ rede de portais qualificados"
}
```

Regras:

- renderizar no máximo oito itens;
- buscar logos no catálogo oficial, sem gerar logos por IA;
- agrupar muitos portais em “Rede de portais” ou “Rede de conteúdo”;
- não usar “programática”, “Google” ou “Google Display” como título do agrupamento;
- exibir quantidade somente quando vier confirmada no plano;
- distinguir confirmado de possibilidade sem poluir a interface.

### 5.2 Design público

Adicionar ao plano, sem misturar com o texto editorial:

```json
{
  "public_design": {
    "skin_id": "paper-editorial",
    "selection_mode": "manual|auto|brand",
    "brand_ref": "crm:client:...",
    "brand_revision": "...",
    "tokens": {
      "paper": "#F7F5EF",
      "ink": "#10252D",
      "accent": "#D5AA3B",
      "logo_variant": "dark-on-paper"
    },
    "hero": {
      "asset_url": "",
      "prompt": "",
      "status": "draft|approved|requested"
    },
    "agent_note": ""
  }
}
```

### 5.3 Contato executivo

Normalizar no contexto público:

```json
{
  "executive_contact": {
    "name": "",
    "role": "",
    "photo_url": "",
    "email": "",
    "phone": "",
    "whatsapp_url": "",
    "message": "Quero falar sobre o plano [nome do plano]"
  }
}
```

O botão deve abrir o WhatsApp com mensagem URL-encoded contendo o nome do plano. Se não houver telefone ou foto, o componente deve cair para nome, iniciais ou estado de contato pendente.

## 6. Alterações no editor `/editar?folha=1`

### 6.1 Cabeçalho do editor

- mostrar anunciante, agência e nome do plano;
- mostrar status de geração, hero e publicação;
- incluir ação “Visualizar público”;
- incluir ação “Abrir galeria”;
- exibir alerta quando houver dados “A validar”.

### 6.2 Bloco de marca e skin

Criar modal de personalização:

- CentralComm;
- agência;
- cliente final do CRM;
- cinco skins visuais;
- logo e variantes disponíveis;
- cores aprovadas;
- indicador de contraste;
- preview da hero;
- `Aplicar skin`;
- `Pedir outra variação`.

Não alterar o texto do plano ao aplicar a skin. A ação deve salvar somente `public_design` e invalidar o cache público.

### 6.3 Galeria de hero

Estados:

- `draft`: gerada, ainda não aplicada;
- `approved`: aprovada pelo gestor;
- `requested`: solicitação enviada ao agente.

Cada item deve mostrar:

- imagem;
- skin;
- prompt resumido;
- data;
- botão `Aplicar`;
- botão `Pedir variação`.

### 6.4 Edição editorial

Permitir edição dos campos textuais sem permitir que o gestor destrua o contrato:

- título;
- estratégia;
- criativo;
- canais;
- dado de mercado;
- defesa;
- pendências.

Campos que não devem ser inventados pelo editor:

- verba;
- alcance;
- CTR;
- conversões;
- tamanho de audiência;
- logos não presentes no CRM.

## 7. Geração do plano

### 7.1 Preparação

1. Ler briefing bruto.
2. Resolver anunciante final e agência.
3. Ler marca aprovada do CRM v3, quando vinculada.
4. Separar fatos confirmados, premissas e pendências.
5. Resolver canais e parceiros.

### 7.2 Montagem editorial

1. Gerar estratégia em até três frases.
2. Gerar criativo contextualizado no canal.
3. Gerar `channel_roles` no card de mercado, com até oito itens.
4. Gerar dado de mercado sem inventar métrica.
5. Gerar densidade de mix rotulada como premissa quando aplicável.
6. Gerar defesa comercial.
7. Gerar pendências e validações, incluindo status de fonte para audiência e números.

### 7.3 Imagens

- gerar hero atmosférica separada do criativo no canal;
- não colocar texto, logo, QR ou números na imagem;
- salvar assets em `static/images/smart_planner/generated/`;
- registrar `image_prompt` e `asset_url`;
- não usar uma imagem gigante como substituta do conteúdo editorial;
- para BDMG, usar imagem IAB integrada ao ambiente Serasa;
- para Confins, usar imagem de acesso ao aeroporto e reserva online.

## 8. Página pública

### 8.1 Layout

O link público deve parecer uma página executiva completa, não uma sequência de blocos soltos:

- header fixo e discreto;
- hero com logo, anunciante, título e CTA;
- navegação por capítulos/cartões;
- indicador “1 de 6”, “2 de 6” etc.;
- transição lateral/fade;
- botão de avançar e voltar;
- suporte a swipe no mobile;
- rolagem tradicional como fallback;
- CTA de WhatsApp persistente no rodapé ou último cartão.

### 8.2 Capítulos sugeridos

1. A oportunidade;
2. Como a estratégia vira ação;
3. Ecossistema de distribuição;
4. Criativo no canal;
5. Mercado e mix;
6. Defesa e próximo passo.

### 8.3 Card de canais

Visual recomendado:

- card horizontal com logos em linha ou grade compacta;
- papel do canal abaixo de cada logo;
- rede de portais como um item agrupado;
- logos de Meta, LinkedIn e TikTok em apoio, nunca como destaque principal;
- estados visuais para confirmado, recomendado e a validar.

## 9. Fluxo de publicação

```text
Salvar edição
  -> validar contrato
  -> persistir plan_content / dados_detectados
  -> persistir public_design
  -> validar logos e contraste
  -> invalidar cache
  -> gerar URL pública
  -> renderizar preview
  -> publicar
```

Critérios de bloqueio:

- plano sem anunciante não publica;
- logo com contraste insuficiente não é aplicada;
- imagem com status apenas `draft` não substitui hero aprovada;
- dados numéricos sem origem aparecem como “A validar”;
- WhatsApp sem telefone fica oculto, não quebrado.

## 10. Segurança contra conflito entre agentes

Enquanto outro agente altera o módulo compartilhado:

1. definir ownership por camada antes do patch: geração/contrato, editor ou público;
2. trabalhar primeiro em contratos, fixtures, prompts e testes isolados;
3. integrar em commits pequenos por camada;
4. revisar `git diff` antes de cada patch;
5. nunca usar reset, checkout ou limpeza destrutiva;
6. validar o plano `EExkhWnyzq519g` em leitura antes de persistir qualquer mudança;
7. manter fallback para planos antigos sem `audience_model`, `public_design` ou `asset_manifest`.

## 11. Plano de implementação por fases

### Fase 0 — alinhamento e snapshot

- confirmar estado do plano real;
- exportar fixture sanitizada;
- mapear alterações do outro agente;
- congelar contrato de dados.

### Fase 1 — conteúdo e canais

- adicionar normalização do card `channels`;
- conectar catálogo de logos;
- agrupar rede de portais;
- adicionar testes do BDMG e de um plano com poucos canais.

### Fase 2 — editor de marca e hero

- modal de skin;
- ligação CRM v3;
- validação de logo/contraste;
- galeria de hero;
- persistência de `public_design`.

### Fase 3 — página pública navegável

- capítulos/cartões;
- transições e navegação;
- responsividade;
- card de contato e WhatsApp;
- integração das imagens aprovadas.

### Fase 4 — geração e publicação

- prompt final com dados confirmados;
- geração Image 2/OpenRouter;
- status draft/approved;
- cache e publicação;
- PDF e compartilhamento.

### Fase 5 — QA

- plano BDMG;
- plano de Confins;
- plano sem logo;
- plano sem executivo;
- plano com mais de oito canais;
- plano sem números confirmados;
- desktop, mobile e PDF.

## 12. Critérios de aceite

- a rota real do editor abre a folha correta;
- nenhum dado “A definir” irrelevante aparece no topo;
- o mix confirmado aparece com origem/rotulagem adequada;
- o card de canais nunca ultrapassa oito itens;
- portais são agrupados sem citar “programática” ou “Google”;
- a hero usa a marca selecionada sem deformar logo branca;
- a imagem do criativo aparece dentro do canal;
- o contato mostra foto, nome e cargo quando disponíveis;
- WhatsApp abre com o nome do plano;
- o público consegue navegar sem uma rolagem longa obrigatória;
- o PDF continua legível;
- nenhuma geração inventa KPI, verba, audiência ou logo.
