# Roteiro manual — memória, continuidade e limite de contexto

## Objetivo

Validar se uma única conversa preserva fatos, correções, decisões, referências, arquivos, artefatos e próximos passos enquanto o histórico cresce. Execute os prompts abaixo, na ordem, sempre na mesma conversa. Não antecipe ao agente que haverá perguntas de memória.

O roteiro evita solicitar raciocínio interno. No último turno, pede uma síntese verificável das decisões e dos fluxos construídos.

## Critérios gerais

- O `conversation_id` deve permanecer o mesmo em todos os turnos.
- Recarregue a página depois dos prompts 8, 20 e 32.
- Depois do prompt 24, abra outra conversa, envie uma mensagem curta e volte para esta.
- Não corrija respostas de memória erradas durante a execução; registre o erro e continue.
- Quando houver streaming, suba o histórico durante a resposta para validar que o scroll não seja roubado.

## Sequência 1 — fatos simples

1. `Meu nome neste exercício é Marina e a campanha se chama Horizonte.`

2. `A marca da campanha é Aurora Café.`

3. `A cidade prioritária é Curitiba.`

4. `O público principal são profissionais de 25 a 39 anos que trabalham em modelo híbrido.`

5. `Qual é o nome da campanha? Responda somente com o nome.`

6. `Qual marca e qual cidade eu defini?`

7. `Acrescente como objetivo inicial: aumentar experimentação do produto.`

8. `Resuma em quatro linhas o contexto definido até agora.`

## Sequência 2 — correções e precedência

9. `Correção: a cidade prioritária não é Curitiba. A partir de agora é Florianópolis.`

10. `Correção: o público vai de 28 a 44 anos, mantendo profissionais em modelo híbrido.`

11. `A verba preliminar é de R$ 120 mil.`

12. `Na verdade, substitua a verba por R$ 150 mil. O valor anterior não deve mais ser usado.`

13. `Ficou decidido que a campanha terá três fases: descoberta, consideração e ação.`

14. `Repita apenas os valores vigentes de cidade, faixa etária e verba.`

15. `Explique quais informações foram corrigidas, mostrando valor anterior e valor vigente.`

16. `Registre a restrição: não usar descontos como argumento principal da comunicação.`

## Sequência 3 — entidades, referências e continuidade

17. `Considere este endereço como referência principal da pesquisa: https://example.com/aurora-horizonte`

18. `Quando eu mencionar “o link principal”, estarei falando do endereço que acabei de enviar.`

19. `Defina a mensagem central como: uma pausa de qualidade que acompanha a rotina flexível.`

20. `Crie uma proposta curta de campanha usando somente o contexto confirmado nesta conversa.`

21. `No texto anterior, troque a expressão “rotina flexível” por “dia em movimento”, sem alterar as demais decisões.`

22. `De qual link eu estava falando quando disse “link principal”?`

23. `Quais são as três fases que decidimos e qual restrição criativa continua válida?`

24. `Liste, sem inventar informações, tudo que ainda está pendente para transformar a proposta em plano executável.`

## Sequência 4 — carga longa e recuperação posicional

25. `Crie uma hipótese de papel para mídia social na fase de descoberta. Marque tudo como premissa, não como decisão.`

26. `Crie uma hipótese de papel para vídeo online na fase de consideração. Continue marcando como premissa.`

27. `Crie uma hipótese de papel para busca na fase de ação. Continue marcando como premissa.`

28. `Compare as três hipóteses em uma tabela com papel, risco, dependência e sinal de sucesso. Não invente benchmarks.`

29. `Defina como decisão que social e vídeo online entram no primeiro rascunho. Busca continua apenas como hipótese.`

30. `Adicione uma dependência: a equipe da marca precisa entregar vídeos verticais antes da fase de descoberta.`

31. `Adicione outra dependência: a página de destino precisa estar instrumentada antes da fase de ação.`

32. `Monte uma sequência operacional de seis passos, preservando decisões, premissas e dependências como categorias diferentes.`

33. `Qual foi a primeira informação que eu forneci nesta conversa?`

34. `Qual foi a segunda correção explícita que fiz?`

35. `Recupere a decisão tomada no prompt sobre social, vídeo online e busca.`

36. `Sem reescrever o plano, diga se existe algum conflito entre objetivo, mensagem, restrição, canais decididos e dependências.`

## Sequência 5 — pressão adicional sobre contexto

Envie os cinco prompts seguintes em 12 rodadas, alterando apenas o número da rodada. Peça respostas entre 250 e 400 palavras nas rodadas 4 a 12. Isso aumenta o transcript sem introduzir fatos contraditórios e deve acionar checkpoint, recuperação e eventual truncamento da janela recente. Se o painel técnico indicar `context_truncated` antes da rodada 12, conclua a rodada atual e avance para o prompt final.

37. `Rodada 1: descreva dois riscos operacionais da fase de descoberta usando apenas o contexto já registrado.`

38. `Rodada 1: proponha duas perguntas de validação para a equipe da marca, sem transformar respostas presumidas em fatos.`

39. `Rodada 1: explique como a restrição sobre descontos afeta a mensagem central.`

40. `Rodada 1: indique qual dependência deve ser resolvida primeiro e por quê, usando uma justificativa curta.`

41. `Rodada 1: apresente uma síntese executiva de até 120 palavras sem perder os valores vigentes.`

Após concluir a rodada 12 — ou observar truncamento — recarregue a página, saia da conversa, volte e continue para a avaliação final.

## Prompt final — avaliação da conversa e dos fluxos

42. `Faça uma avaliação final desta conversa como um sistema de trabalho contínuo. Entregue: (1) objetivo e contexto vigentes; (2) fatos confirmados; (3) correções aplicadas, com valores substituídos e atuais; (4) decisões tomadas; (5) premissas ainda não aprovadas; (6) restrições e dependências; (7) referências e artefatos mencionados; (8) pendências; (9) fluxo de trabalho que você construiu entre descoberta, consideração e ação; (10) próximos três passos recomendados. Depois, faça uma auditoria de memória informando quais partes você recuperou do início, do meio e do fim da conversa e sinalize qualquer informação que não consiga confirmar. Não exponha raciocínio interno: apresente somente evidências do histórico, critérios usados e conclusões verificáveis.`

## Resultado esperado da avaliação final

- Nome do exercício: Marina.
- Campanha: Horizonte.
- Marca: Aurora Café.
- Cidade vigente: Florianópolis; Curitiba deve aparecer apenas como valor substituído.
- Público vigente: profissionais de 28 a 44 anos em modelo híbrido.
- Objetivo: aumentar experimentação do produto.
- Verba vigente: R$ 150 mil; R$ 120 mil deve aparecer apenas como valor substituído.
- Mensagem vigente: “uma pausa de qualidade que acompanha o dia em movimento”.
- Restrição: descontos não são o argumento principal.
- Fases: descoberta, consideração e ação.
- Decisão de canais: social e vídeo online no primeiro rascunho; busca permanece hipótese.
- Dependências: vídeos verticais e página de destino instrumentada.
- Link principal: `https://example.com/aurora-horizonte`.
- A resposta deve separar fatos, decisões e premissas sem inventar métricas ou benchmarks.
