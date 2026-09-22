# Prompts de verificação do agente e dos artefatos

Use uma conversa nova para cada cenário, exceto quando o prompt disser “na mesma conversa”. Abra o artefato gerado e confira o resultado visual antes de publicar.

| Etapa | Prompt para enviar | Resultado esperado |
| --- | --- | --- |
| Contexto do projeto | `Neste projeto, mude o nome de mídia paga para Campanhas de anúncios.` | Uma pergunta objetiva confirma a renomeação do projeto ativo. O nome só muda após confirmar. |
| Documento editável | `Crie um documento editável chamado Plano de lançamento com um resumo, três etapas e uma tabela simples de responsáveis. Use apenas os dados que eu fornecer; se faltarem nomes, deixe essa coluna em aberto.` | Abre um documento no artefato. O texto pode ser editado e salvo sem publicar. |
| Página HTML | `Crie um arquivo HTML no artefato chamado Painel de campanhas. Mostre três cartões: alcance 12.000, cliques 480 e investimento R$ 900. Use esses números exatamente, sem inventar outros dados.` | Abre uma página visual no painel do artefato, com os três números corretos. |
| Interação local | `Crie um dashboard interativo no artefato com dois botões, Semanal e Mensal. Ao clicar, altere o título e os valores entre Semanal: 120 cliques, R$ 200; Mensal: 480 cliques, R$ 900. Tudo deve funcionar na prévia antes de publicar.` | Os botões funcionam dentro do artefato privado. Nenhum serviço externo é necessário. |
| Revisão | Na mesma conversa do painel, envie: `Troque apenas o título do painel para Resultados de anúncios e mantenha os números e os botões funcionando.` | A revisão mantém os valores e a interação. Uma nova versão é salva. |
| Publicação | No artefato HTML revisado, clique em `Publicar`. | O link aparece no painel. `Copiar link` copia a URL; `Abrir` mostra a mesma página. Ao reabrir o artefato publicado, o link continua disponível. |
| Retirada | Em `Ações`, clique em `Despublicar` e tente abrir o link anterior. | A URL pública deixa de servir a página; a prévia privada e as versões continuam acessíveis. |

Se a geração falhar, registre o prompt, o nome da conversa e a etapa em que falhou: resposta do agente, criação do artefato, prévia, interação ou publicação. Isso separa falhas do modelo das falhas de renderização.
