# Briefing da Área do Cliente: wizard qualificado

Análise de 2026-11-06. Código: `aicentralv2/area_cliente/briefing.py`, `templates/area_cliente/briefing.html`,
`static/js/area_cliente_briefing.js`, `static/css/area_cliente_briefing.css`.

## O que faltava no formulário antigo

O formulário tinha título, objetivo livre, "público e praças" num campo só, período, verba e canais.
Para o comercial montar uma proposta sem voltar ao cliente, faltavam:

| Falta | Por que o comercial precisa |
| --- | --- |
| Tipo de objetivo e KPI principal | Define modelo de compra (CPM, CPC, CPL, CPA, CPV) e o que a proposta promete. |
| Público estruturado (idade, gênero, classe, B2B) | Vira segmentação direto na cotação; texto livre volta como pergunta. |
| Praças separadas do público e normalizadas (cidade/UF) | Praça mal escrita ("BH e região") atrasa a checagem de inventário e de OOH. |
| Abrangência (nacional, regiões, estados, cidades, raio de lojas) | Muda canais possíveis (geofence, OOH, rádio local). |
| Datas-chave e antecedência | Campanha que começa em menos de 7 dias pede outro fluxo. |
| Materiais (peças prontas ou produção) | Produção entra no escopo e no prazo. |
| Site e mensuração (pixel, GA4, CRM) | Sem isso, objetivo de conversão não é contratável com meta. |
| Concorrentes e referências | Ajuda o planejamento e a escolha de praças. |
| Histórico do cliente | O comercial reaproveitava o PI anterior manualmente. |

## O que dá para pré-preencher

Do próprio cliente, só campos de texto e nunca valores (regra da casa: sem custo, margem, fee ou valor de PI):

- **Praças e público**: `cadu_cotacao_linhas.praca` e `.segmentacao` das cotações que viraram PI (`cadu_pi.cotacao_id`).
- **Objetivo**: `cadu_cotacoes.objetivo_campanha` e o modelo de compra das campanhas (`cadu_pi_camp_objetivos`: CPM vira
  "Alcance", CPL vira "Leads" etc.).
- **Plataformas**: `cadu_pi_camp_plataforma` das campanhas do PI, mapeadas para os canais do briefing.
- **Período**: duração do PI anterior, sugerida a partir de hoje.
- **Briefings anteriores**: título, objetivo e as linhas "Público"/"Praças" do texto enviado.

O primeiro passo do wizard só aparece quando há histórico; sem histórico, ele começa no objetivo.

## Checagens de qualidade (não bloqueiam o envio)

Somam uma nota de 0 a 100 mostrada ao cliente e enviada ao comercial:

1. Objetivo com tipo e KPI escolhidos.
2. Público com pelo menos um recorte (idade, classe, gênero ou B2B) ou descrição de 20+ caracteres.
3. Praças definidas (nacional ou ao menos uma praça).
4. Período com início e fim; aviso se começa em menos de 7 dias ou dura menos de 7 dias.
5. Verba ou faixa informada.
6. Canais escolhidos ou "quero sugestão".
7. Objetivo de conversão (leads, vendas, app, tráfego) com site e mensuração.
8. Situação dos materiais.

Obrigatórios de verdade continuam só título e objetivo, para não perder briefing por atrito.

## O que chega ao time comercial

`briefing_original` passa a ter seções fixas (Objetivo e KPI, Público, Praças, Período, Verba, Canais, Materiais e mensuração,
Contexto, Do Descobrir, Origem, Qualidade com as pendências). O e-mail `briefing-novo` mostra os mesmos campos e as pendências,
para o executivo saber o que perguntar antes de abrir a cotação.

## Praças com IA

Autocompletar local (UFs, regiões, capitais e cidades grandes) responde na hora. Ao pedir "Organizar com IA", o texto vai
para `POST /briefing/pracas`, que normaliza em cidade/UF/região e sugere praças vizinhas (região metropolitana, polos próximos).
Cache em memória e limite de 20 chamadas por sessão a cada 10 minutos.

## Próximos passos possíveis

- Salvar rascunho no banco (`status = 'rascunho'` já existe em `STATUS_CLIENTE`).
- Ler o briefing estruturado na tela de Briefings do CentralX em vez do texto.
- Usar a nota de qualidade para ordenar a fila do comercial.
