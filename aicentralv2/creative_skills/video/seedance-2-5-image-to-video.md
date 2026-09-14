# Seedance 2.5 — imagem para vídeo no Studio

Fonte: `genmedia-labs/skills` · `seedance-2-5-image-to-video`.

Use quando o criativo quer animar uma única imagem mantendo identidade, produto e composição. O pedido do modelo contém apenas direção de movimento, uma imagem preparada, duração e a escolha de áudio nativo.

- Uma imagem por geração.
- Saída 720p.
- Duração inteira entre 4 e 30 segundos.
- O vídeo herda a proporção da imagem enviada. O Studio deve enquadrar a imagem no formato de saída escolhido antes do envio.
- Áudio nativo opcional. Quando ativo, nomeie fala, ambiente, efeitos e presença ou ausência de música.
- Não enviar `seed`, resolução, proporção ou múltiplas referências ao modelo.
- Separar movimento do sujeito e movimento da câmera no prompt.
- Pedir “sem texto novo e sem marca-d'água” para proteger peças publicitárias.
- Alterações ficam em plano revisável. A skill não autoriza gerar, exportar ou excluir mídia.
