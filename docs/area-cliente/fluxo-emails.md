# Área do Cliente: fluxo de 4 e-mails de ativação

Objetivo: trazer o cliente para dentro da Área do Cliente nas primeiras duas semanas,
com e-mails curtos, um recurso por vez, e um vídeo curto quando ele estiver gravado.

Cadência: **segunda, quarta e sexta**. O 4º e-mail cai na segunda da semana seguinte.
Remetente Brevo "clientes" (Centralcomm · Área do Cliente). Todos têm um botão para
a Área do Cliente e um link para o executivo da conta.

## Os 4 e-mails

| # | Quando | Assunto (sugestão) | Recurso em destaque | Ilustração | Vídeo |
|---|---|---|---|---|---|
| 1 | Seg | Seu painel de campanhas já está no ar | Início: campanhas no ar e próximos passos | `inicio.svg` | Vídeo 1 (a gravar) |
| 2 | Qua | Mande seu briefing em 5 minutos | Briefing: formulário que vai direto para o executivo | `briefing.svg` | Vídeo 2 (a gravar) |
| 3 | Sex | Descubra canais e formatos antes de decidir | Descobrir: canais, formatos, audiências e portais | `descobrir.svg` | Vídeo 3 (a gravar) |
| 4 | Seg (semana 2) | Acompanhe PIs, metas e entregas num só lugar | Projetos/PIs e Campanhas contra a meta | `projetos.svg` e `campanhas.svg` | Vídeo 4 (a gravar) |

Relatórios e faturamento entram como “o que mais tem” no e-mail 4, com
`relatorios.svg` no rodapé do texto, sem vídeo próprio.

## Conteúdo de cada e-mail

Regra para todos: no máximo 120 palavras no corpo, um único botão, uma imagem,
um parágrafo de dúvida com o nome do executivo.

### E-mail 1 (seg): o que tem lá
- Abertura: a Área do Cliente mostra as campanhas no ar e o que a Centralcomm
  está fazendo por você agora.
- Três destaques: campanhas no ar, metas e entregas, faturamento e notas fiscais.
- CTA: “Abrir minha Área do Cliente”.
- Vídeo: link do vídeo 1 quando existir (senão, omitir a linha).

### E-mail 2 (qua): briefing
- Abertura: a próxima campanha começa com um briefing. Leva cerca de 5 minutos.
- Explicar: o briefing vai direto para o seu executivo, que responde no próprio e-mail.
- CTA: “Preencher briefing”.
- Dica: “Você pode salvar e voltar depois”, se a funcionalidade permitir.

### E-mail 3 (sex): descobrir
- Abertura: antes de decidir canais e formatos, veja o que existe.
- Mostrar: canais, formatos, audiências e portais, com busca e filtro.
- Explicar: “Incluir no briefing” junta os itens escolhidos no próximo briefing.
- CTA: “Explorar canais e formatos”.

### E-mail 4 (seg da semana 2): acompanhamento
- Abertura: seus projetos e campanhas numa tela só.
- Mostrar: PIs como projetos, campanhas contra a meta, relatórios e faturamento.
- Fechar: “Qualquer dúvida, fale com [executivo]”, com WhatsApp.
- CTA: “Ver meus projetos”.

## Produção

- [ ] Vídeos 1 a 4 gravados (roteiro: 30 a 60 segundos, tela real, conta de demonstração).
- [ ] Ilustrações revisadas: `docs/area-cliente/ilustracoes/*.svg` (6 arquivos, versão
      inicial sem texto, paleta da marca).
- [ ] Template Brevo para cada e-mail (base: `templates/emails/area_cliente/base.html`).
- [ ] Teste de envio para apolo@centralcomm.media antes de ligar a sequência.
- [ ] Sequência ligada só para contas com a Área do Cliente liberada no CRM v3.

## Pontos em aberto

1. **Quem entra na sequência**: só contas com acesso liberado, ou também as que
   ainda não têm senha? Recomendo só as liberadas e com senha criada, para o
   botão levar direto ao painel.
2. **Quando parar**: se o cliente enviar o primeiro briefing, pular o e-mail 2
   e seguir com o 3.
3. **Vídeos**: se atrasarem, os e-mails saem sem vídeo e a linha some.
