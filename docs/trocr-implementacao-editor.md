# Trocr: implementação do editor

## Implementado no workspace

- Shell compacto, estado resumido, painéis recolhíveis/gavetas, foco, áreas seguras e formatos recolhidos. O CSS é exclusivo do Trocr.
- Módulo `trocr/workspace.js` carregado ao abrir **Editar elemento**.
- Assets autenticados por marca (PNG/JPEG/WebP; até 20 MB e 20 megapixels), miniaturas e identificadores nos pedidos.
- Documento por peça, controle de revisão, campanha, seleção em andamento, anexos, operações, camadas, formatos e referências a jobs.
- Campanhas: criar, renomear, arquivar/reabrir, objetivo, biblioteca e navegação entre peças. Peças anteriores sem vínculo aparecem em **Sem campanha**.
- Pontos positivos/negativos usam o contorno por cor existente em Camadas, com resolução de trabalho limitada. Brilho acompanha a máscara real; pincel corrige a seleção. Não usa SAM2 e não equivale a reconhecimento semântico do iOS.
- Substituir pessoa/produto/fundo, apagar/reconstruir, recriar, proteger região e separar camada. Texto editável exige selecionar a região a remover e informar seu novo conteúdo.
- Cada operação usa base + uma referência, quando aplicável. Etapas seguintes usam o resultado anterior. O servidor recompõe somente a máscara e subtrai as regiões protegidas.
- Jobs persistidos, claim transacional, chave idempotente, progresso, cancelamento de etapas futuras e repetição a partir da primeira etapa pendente. Progresso volta a ser consultado ao reabrir a peça.
- Anexos permanecem em falha; após sucesso a fila ativa é limpa e o job conserva base, máscara, referência, instrução e resultados.
- Camadas persistem posição, tamanho, ordem, visibilidade, proteção, opacidade, sombra e contorno. Texto usa Open Sans disponível no projeto, cor, tamanho, alinhamento e espaçamento. Prévia e PNG usam o mesmo renderer Pillow. Desfazer/refazer de camadas é local.
- Destinos 16:9, 1:1, 9:16 e 4:5 usam bases independentes, resultados individuais e exportação. Ajustes de camada marcam formatos como desatualizados.

## Verificação

Testes automatizados cobrem autenticação/CSRF, uploads, isolamento de assets, revisões, idempotência, bases e referências sequenciais, falhas, retomada parcial, cancelamento, proteção pixel a pixel, máscaras por ponto, recorte, texto e composição persistida, dimensões dos formatos e regressões da sessão legada.

No navegador local, usando os templates/scripts reais e o novo backend SQLite, foram exercitados: campanha, pincel, ponto/contorno luminoso, geração de teste, recarga, camada, posição, prévia/exportação e formatos 1:1/9:16. O fornecedor de imagem foi substituído por uma imagem de teste, sem chamadas pagas. Larguras de 1440, 1280, 1024 e 390 px foram inspecionadas no componente; isso não representa validação do shell completo publicado.

## Limites e pendências de aceite

- A qualidade real de segmentação semântica e geração ainda não foi comprovada. A seleção por cor é uma sugestão explícita, sujeita a revisão manual; não identifica automaticamente todos os objetos.
- O fluxo de campanha/elemento usa um documento complementar à sessão legada. A integração foi exercitada localmente; falta validar a sessão autenticada e a persistência no ambiente publicado.
- A infraestrutura usa SQLite e assets no `media_root()/trocr-editor`, como armazenamento local persistente. Precisa de volume durável/compartilhado compatível com a topologia de produção. Jobs enfileirados são retomados na consulta. Uma etapa já reivindicada que perde o processo **não é reenviada automaticamente**, pois o fornecedor não garante idempotência; após dez minutos a UI informa o estado inconclusivo.
- Prévia de camadas atualiza pelo controle explícito, sem chamar IA. Para extrair novas camadas de uma composição já editada, é necessário exportá-la e abri-la como nova base.
- O gesto de arrastar e “levantar” o objeto diretamente no canvas, menu contextual completo e reconhecimento semântico semelhante ao iOS ainda não estão implementados. Posição/tamanho usam os controles numéricos e há brilho real sobre a máscara.
- Multicanal mantém resultados próprios; ainda falta edição independente de propriedades de camadas por formato e geração dos demais destinos após falha intermediária sem aguardar uma repetição.
- A validação integrada completa (interrupção real de rede, encerramento de worker, duas abas em toda a UI nova e modais no shell publicado) permanece pendente. Não houve deploy.

## Validação com o criativo real da TIM

Arquivo fornecido pelo usuário: captura de tela de 10/09/2026, 1472 × 568 px.

- Apple Vision executado localmente: 9 blocos e 22 palavras com coordenadas; 1 instância de primeiro plano.
- A máscara semântica nativa foi importada no documento de teste do editor. Camadas derivou 206 pontos de contorno.
- Erro real identificado: OCR retornou `os 89,95` com confiança 0,5; o original mostra **R$ 89,99/mês**. O resultado bruto foi preservado e a UI passou a marcar baixa confiança.
- Browser: adicionar retângulo à máscara, desfazer, salvar e encaminhar ao agente. A comparação por identificador de conteúdo confirmou que desfazer restaurou exatamente a máscara original.
- Laço livre, retângulo, modo adicionar/subtrair, cursor de pincel, Alt/Option/Shift, atalhos e histórico próprio de seleção foram acrescentados. “Usar seleção” recolhe as ferramentas e foca a ação; campanha fica recolhida.
- Artefatos em `output/trocr-real-validation`: imagem original, OCR JSON, máscara PNG, pontos JSON, script Swift reproduzível e HTML interativo independente do servidor.

A máscara semântica Apple Vision deste teste **não torna o backend publicado um serviço Apple Vision**. O backend atual segue com sugestão por cor e seleção manual. A demonstração HTML não executa geração paga.
