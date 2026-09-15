# Registro de entregas — 14 e 15 de setembro de 2026

Este registro consolida as entregas feitas no repositório e o estado das issues do GitHub ao final da revisão. Ele não substitui a validação em produção.

## Entregas de 14/09

### Operação, faturamento e CRM

- Emissão de NFS-e pela Spedy passou a ter preview, ambiente explícito, trilha de request/response e proteção para não alterar o status de negócio do PI em sandbox. Commit: [`6bb0065`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/6bb0065684a95612bc260153aa960c209540ee8e).
- O valor percentual foi consolidado como fee no cliente, na cotação e no PI. Commit: [`5ea45f3`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/5ea45f36849d0501452a0107bb108c332982a63c).
- A descoberta de contatos da Spedy deixou de inventar números e o parser do CRM passou a recuperar JSON truncado. Commits: [`687e221`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/687e2211eb8b30b349d28f259abf8bcb5a620b15) e [`d2d184d`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/d2d184d498310d8a26d9d076d9c9ff704f60b8ab).

### Smart Planner e Places

- O Smart Planner passou a trabalhar com Places reais na mesa, briefing e documentos; o link público ganhou folha visual, revisão do mix e alternância entre página única e plano completo. Commits: [`8e928d5`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/8e928d5d2a15470700248c5806437f892d58aee7), [`c504d07`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/c504d07e5f106cd424c6c965a92fdb41be940537), [`b07f6c8`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/b07f6c8ddcf4755875d0583adfe3a0b5b73b3d25) e [`b187abf`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/b187abfe29d3d5af4b1bbdd14691c6500eb98644).
- Places recebeu malls nas três capitais, fontes reais para criação do lugar e uma folha pública orientada a briefing executivo. Commits: [`4a5c15b`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/4a5c15b5e16750088078694d53c1104c0a607dfd), [`4e3d15d`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/4e3d15db9f69e821057e7d34047573186d54695e) e [`58ef0c4`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/58ef0c44a5b138d95117c44bc93c5281fb9b90fb).

### Cadu Media / Video Studio

- O Studio recebeu projetos versionados, editor visual, timeline, locução, histórico de custo e edição por agente. Commits: [`0c99d10`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/0c99d10848b128435ec8a94d8b4e5de2472c82b7), [`e25424f`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/e25424f109d66ff70921e6dbd645f415857c9db6), [`9e6f563`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/9e6f563d88f5be014bf25fc693506cf6107dbbde) e [`07a289a`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/07a289ae36e3c085fe649ef4e5b43e809fc86a7e).
- O backlog macro e os mockups do Video Studio foram publicados e vinculados às issues #19–#26. Commits: [`f7efdf2`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/f7efdf27b2eb4792058b46e440fd40c853a18dca), [`a2d878f`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/a2d878f481a4bb43d41d334bce166e818fba1ef1) e [`f2ca968`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/f2ca968567112448526571d979533e2ff7caf446).

## Entregas de 15/09

- O Studio passou a oferecer fluxo de edição durável, captions e composição animada; download nomeado com progresso e HTML público; e importação de clientes/agências no modelo de marcas. Commits: [`389b761`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/389b7618351fa9ee966d19696794116d913b82b4), [`059e92d`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/059e92dd4fb75e1077171ac51529f5a5a27aab11) e [`4c853fa`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/4c853fae6e127d42eb24f3dabb66b6ce2b5f2e4a).
- Places consolidou planejamento e curadoria de imagens; o Smart Planner recebeu refinamentos de fluxo e documentos públicos. Commits: [`10ee1fa`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/10ee1fafc31fe62330edf6faf9b5904a74966d7b), [`cfd45d8`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/cfd45d84754de7fbeecd0136c4a6ed3533d1521c) e [`99c5bc2`](https://github.com/RogerioLira-centralcomm/aicentralv2/commit/99c5bc2c983dde3511eec50e25bdbb2f860a347c).

## Decisão sobre as issues abertas

| Issue | Decisão | Motivo |
|---|---|---|
| #3 — Emissão de NF | Fechada como concluída | A entrega Spedy cobre emissão, preview, ambiente e rastreabilidade; a operação em produção continua exigindo configuração e validação operacional. |
| #4, #5, #6, #12, #13 e #18 | Permanecem abertas | Não há evidência suficiente, nesta revisão, para afirmar que todos os critérios foram concluídos. |
| #19–#26 — Video Studio | Permanecem abertas | Houve avanço material, mas a auditoria técnica de 15/09 encontrou lacunas P0/P1 que impedem encerramento responsável. |

## Backlog priorizado do Video Studio

Referência: [`auditoria-editor-narracao-audio-timeline-cor-2026-09-15.md`](auditoria-editor-narracao-audio-timeline-cor-2026-09-15.md).

1. P0: contrato temporal único para fonte/projeto, split correto e vínculos entre vídeo, áudio e legendas.
2. P0: locução com texto limpo, voz explícita, ritmo efetivo e política que nunca corte fala silenciosamente.
3. P1: áudio visual por item — waveform, trim, split, posição, solo/mute, fades e sincronização com a prévia/exportação.
4. P1: correção de cor por clipe, persistida e aplicada de forma determinística no render.
5. P1: decupagem adaptativa e propostas revisáveis de corte automático/remoção de silêncio.
6. Depois: agentes de edição, efeitos avançados e a validação da jornada completa com mídia real e produção.

As issues #19–#26 continuam sendo os épicos de acompanhamento. Qualquer fechamento futuro deve citar o commit ou pull request e a evidência dos critérios de aceite, usando `Fixes #<número>` no texto do pull request ou do commit que chega à branch principal.
