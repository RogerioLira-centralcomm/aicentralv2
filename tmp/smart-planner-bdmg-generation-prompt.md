# Prompt de geração — BDMG · Perfil 252

## Briefing real

**Anunciante:** BDMG

**Agência:** Perfil 252

**Objetivo:** estratégia de mídia e dados com Serasa Ads + formatos interativos.

**Direção:** mostrar um criativo display IAB inserido dentro do app ou portal Serasa, explicando a utilização de dados exclusivos B2B — pessoa jurídica — e B2C — pessoa física — na veiculação de mídia dentro dos domínios Serasa, app e web.

**Extensão comercial:** possibilidade de venda/ativação desses dados nas operações da agência em Meta, LinkedIn e TikTok, quando houver aderência e autorização.

**Possibilidade criativa:** avaliar um formato interativo para a campanha do banco.

## Prompt para o agente

Você é o agente que monta a página única pública de um plano de mídia para o anunciante final. Gere uma proposta executiva para o BDMG, apresentada pela agência Perfil 252, com foco no uso de Serasa Ads e dados B2B/B2C.

Não escreva para a agência como heroína. A agência aparece somente como contexto de operação. O centro da tese é o BDMG, sua necessidade de alcançar pessoas físicas e jurídicas com mais precisão e a possibilidade de transformar dados do ambiente Serasa em mídia qualificada dentro do app, portal e, quando autorizado, nas redes sociais da operação.

O documento deve ser textual, visual e executivo. Não invente verba, alcance, CTR, volume de audiência, benchmark, percentual de conversão ou qualquer KPI que não esteja no briefing. Quando faltar um número, use “Premissa” ou “A validar”, nunca um número ilustrativo.

Retorne somente JSON válido neste formato:

```json
{
  "meta": {
    "title": "BDMG · Serasa Ads e dados proprietários",
    "client": "BDMG",
    "agency": "Perfil 252",
    "campaign": "",
    "presenter": "centralcomm"
  },
  "branding": {
    "hero": "client",
    "client": "BDMG",
    "agency": "Perfil 252",
    "presenter": {"id": "centralcomm", "role": "support"},
    "partners": ["serasa", "meta", "linkedin", "tiktok"]
  },
  "theme": {
    "id": "finance",
    "density_caption": "Peso do mix — premissa do pitch",
    "density": []
  },
  "sections": [
    {
      "id": "one_page",
      "type": "one_page",
      "cards": [
        {
          "type": "strategy",
          "title": "Estratégia",
          "body": ""
        },
        {
          "type": "creative",
          "title": "Criativo no canal",
          "body": "",
          "channel": "Serasa Ads",
          "surface": "app",
          "image_url": "",
          "image_prompt": ""
        },
        {
          "type": "market",
          "title": "Dado de mercado",
          "stat": "Premissa",
          "stat_label": "Dado B2B + B2C",
          "body": ""
        },
        {
          "type": "defense",
          "title": "Defesa",
          "body": ""
        },
        {
          "type": "channels",
          "title": "Ecossistema de distribuição",
          "body": "",
          "items": [
            {"id": "serasa", "label": "Serasa", "logo": "", "role": "Ambiente proprietário"},
            {"id": "meta", "label": "Meta", "logo": "", "role": "Extensão social"},
            {"id": "linkedin", "label": "LinkedIn", "logo": "", "role": "Extensão B2B"},
            {"id": "tiktok", "label": "TikTok", "logo": "", "role": "Extensão de alcance"},
            {"id": "display-network", "label": "Rede de portais", "logo": "", "role": "Cobertura contextual"}
          ],
          "overflow_label": "+ rede de portais qualificados"
        }
      ]
    }
  ]
}
```

## Regras editoriais específicas

- Estratégia em até três frases: Serasa Ads é o ambiente de dados e mídia; B2B e B2C são leituras diferentes; redes sociais são extensão condicionada, não promessa automática.
- O criativo deve parecer realmente inserido no app ou portal Serasa, com moldura de interface apenas como contexto visual. Não criar um banner solto.
- A marca BDMG aparece no criativo somente quando houver logo oficial disponível. Se não houver logo aprovada, usar o nome em texto no HTML e não pedir ao GPT Image 2 para desenhar a marca.
- Meta, LinkedIn e TikTok entram como logos de apoio no bloco de ecossistema, nunca no topo e nunca como se fossem parceiros já contratados.
- Incluir um card visual de canais com no máximo oito itens visíveis. Usar as logos oficiais já cadastradas no sistema, sem redesenhar logos no texto ou na imagem gerada.
- Quando houver muitos portais, não listar sites individualmente. Agrupar como “Rede de portais” ou “Rede de conteúdo”, com uma legenda curta de cobertura contextual e um indicador de quantidade somente se esse número estiver disponível no briefing.
- Não chamar o agrupamento de “programática”, “Google” ou “Google Display”. O card deve comunicar ecossistema, cobertura e papel de cada canal em linguagem executiva.
- Diferenciar canal proprietário, extensão social, extensão B2B e rede de portais por microcopy, não por excesso de logos.
- O formato interativo deve ser descrito como possibilidade de campanha, não como entrega garantida.
- O dado de mercado não deve afirmar tamanho de audiência. Usar “dados proprietários B2B + B2C” como argumento qualitativo e rotular como premissa quando necessário.
- Não mencionar IA no texto para o cliente.

## Prompt para GPT Image 2 — criativo no canal

Crie uma imagem-conceito horizontal de um anúncio display IAB inserido naturalmente dentro do app ou portal Serasa, para uma campanha institucional do BDMG. Mostrar uma tela de smartphone ou uma janela de portal financeiro com um espaço publicitário claramente integrado ao ambiente editorial, sem parecer um banner solto. O criativo deve sugerir acesso a crédito, relacionamento financeiro ou solução para pessoa física e pessoa jurídica, com composição modular que permita futuras variações B2B e B2C. Usar linguagem fintech institucional, fundo claro, azul profundo e acento vermelho ou laranja somente se compatível com os assets oficiais fornecidos. Deixar a peça publicitária contida dentro da superfície Serasa e reservar área limpa para o texto ser aplicado posteriormente no HTML. Visual realista, premium, funcional e brasileiro.

Não inserir nenhuma palavra legível, logo, nome BDMG, logo Serasa, Meta, LinkedIn ou TikTok, números, QR code, CTA, promessa financeira específica ou dados de audiência. Não desenhar marcas; os logos oficiais serão sobrepostos no HTML. Não usar dashboard genérico, tela de banco inventada, excesso de cartões, neon ou estética de anúncio flutuante.

## Saída esperada do agente

Além do JSON, o agente deve devolver internamente uma nota de implementação:

```text
Skin sugerida: Moldura de Marca, caso o BDMG tenha brand_profile aprovado.
Fallback: Papel Editorial com tokens CentralComm.
Hero: imagem de apoio institucional, não o criativo de canal em tamanho gigante.
Criativo: display IAB dentro de app/portal Serasa.
Logos de apoio: Serasa, Meta, LinkedIn e TikTok somente no ecossistema.
Pendências: logo BDMG, autorização/escopo de uso de dados em redes sociais e confirmação do formato interativo.
```
