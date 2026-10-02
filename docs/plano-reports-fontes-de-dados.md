# Reports → Fontes de dados: navegação e revisão do fluxo

Data: 2026-10-02

## Problema

- Conectar uma fonte (scripts do Google Ads, CRM, chaves de ingestão) ficava em **Mídia → Dados**, enquanto o
  painel de status ficava em **Fontes de dados**. Super Tag, Eventos e Importações eram itens soltos na barra lateral.
- Os botões "Conectar fonte" de Fontes de dados levavam para dentro de Mídia, o que tirava a pessoa da área.

## Feito (fase 1 – navegação)

Fontes de dados virou um hub com abas, como Mídia e Site & Jornada:

| Aba | URL | Conteúdo |
| --- | --- | --- |
| Visão geral | `/connect/app/data-sources` | Status por tipo: mídia, site, arquivos, CRM |
| Conexões e chaves | `/connect/app/data-sources/connect` | Gerar scripts Google Ads, CRM, chaves de ingestão, lotes |
| Super Tag | `/connect/app/supertag` | Sites e instalação da tag |
| Eventos | `/connect/app/events` | Eventos capturados |
| Importações | `/connect/app/imports` | Arquivos e biblioteca |

- A aba "Dados" saiu de Mídia. `/media/data` e o legado `monitor` redirecionam para `data-sources/connect`.
- A barra lateral, no grupo Dados, mostra só "Fontes de dados". As abas cobrem o resto.
- Os links "Conectar Google Ads" e "Gerar scripts" (Google Ads) e "Conectar fonte" e "Conectar CRM" (visão geral) apontam para a nova aba.

## Próximas fases (propostas)

1. **Conexões e chaves em três passos:** (1) escolher a fonte, (2) configurar e gerar, (3) instalar e acompanhar o primeiro envio.
   O botão "Gerar" mostra o motivo do bloqueio no próprio campo, por exemplo "Escolha ao menos uma conta", não só no rodapé.
2. **Separar as chaves de ingestão em uma subseção recolhível**, com filtro de ativas e revogadas. Hoje são 10 cartões longos.
3. **Visão geral como checklist:** cada tipo de fonte com estado (não conectada / aguardando primeiro envio / ok / atenção),
   último envio e a próxima ação, que leva direto à aba certa.
4. **Contas sem cadastro:** contas e campanhas recebidas pelo script e ainda não cadastradas aparecem na visão geral,
   com link para criar. As campanhas já aparecem em Mídia → Campanhas.
5. **Revisar os textos e "Como funciona"** para uma fonte por vez, com os dois scripts (Leitura e Ações) explicados lado a lado.
