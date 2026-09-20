# Cadu Gestão de NPS e conector global de e-mails

## Objetivo

Centralizar disparos de satisfação por sessão e por processamento relevante, começando pelo Studio. O e-mail deve ser útil para retomar ou avaliar um resultado, nunca um ruído de autosave.

## Regra de disparo

| Evento | Dispara pesquisa | Observação |
| --- | --- | --- |
| Mesa Studio salva pela primeira vez | Sim | Recibo resumível com CTA e contexto da revisão. |
| Finalização de trabalho Studio | Sim | Recibo final já existente, com pesquisa posterior. |
| Processamento de marca | Sim | Após resultado revisável. |
| Criação relevante de projeto | Sim | Após primeiro artefato ou contexto pronto. |
| Anexo complexo processado | Sim | PDF, lote, mídia ou fonte que exige processamento. |
| Texto, link ou arquivo simples | Não | Sem e-mail de satisfação. |

## Contrato global

- Evento nomeado em `CADU_EMAIL_EVENTS`.
- Chave idempotente: `user + sessão/artefato + tipo de evento`.
- Payload mínimo: produto, usuário, marca, projeto, sessão, CTA, artefato de prévia, duração/créditos quando aplicável.
- Pesquisa enviada uma única vez, depois de uma janela de uso ou conclusão; nunca em cada autosave.
- Opt-out, resposta e nota persistidos por evento e produto.

## Cadu Gestão de NPS

Tela administrativa para acompanhar e operar o programa.

1. Visão geral: convite enviados, respostas, taxa, média, detratores e tendência.
2. Filtros: produto, agente, marca, projeto, tipo de evento, período e status.
3. Jornada: evento → e-mail → abertura → resposta → follow-up.
4. Detalhe: contexto da sessão, prévia segura do artefato, nota, comentário e dono do follow-up.
5. Regras: editar elegibilidade, atraso, frequência e templates sem alterar código de cada agente.
6. Governança: auditoria de disparos, reenvio protegido e exclusão/anonimização de respostas.

## Próximo agente

Implementar o conector nos produtos fora do Studio nesta ordem: processamento de marca, projeto/contexto, anexos complexos, Planner e Conversas. Depois construir a tela Cadu Gestão de NPS sobre os eventos persistidos e seus resultados.
