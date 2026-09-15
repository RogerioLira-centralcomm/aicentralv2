# Estilos de legenda no Studio

## Uso
Em **Editar → Legendas → Estilo das legendas**, escolha um modelo e ajuste fonte, tamanho, posição horizontal/vertical, alinhamento, cor, contorno, fundo e opacidade. Os botões Topo/Centro/Base reposicionam o conjunto. O estilo é global para todas as legendas existentes e futuras, durante seus respectivos intervalos.

Modelos: Clássica, Impacto, Amarelo destaque, Caixa escura, Caixa clara, Cinema, Menta, Azul editorial, Rosa pop e Minimalista.
Fontes: Open Sans, Lato, Lato Bold, Anton e Lora. Fontes adicionais distribuídas com OFL, baixadas do repositório oficial https://github.com/google/fonts/tree/main/ofl. Não depende de fontes instaladas no servidor nem de serviços externos em tempo de edição.

## Comportamento técnico
`composition.caption_style` armazena o estilo e participa da invalidação da prévia. A configuração persiste no documento do projeto e no histórico existente. Catálogo compartilhado em `static/fonts/captions/styles.json`; normalização no backend limita fonte, números e cores. Tamanho e posição são relativos ao quadro. Texto longo quebra linha, encolhe quando necessário e fica dentro do quadro.
A prévia Canvas e a exportação Pillow/FFmpeg usam os mesmos arquivos de fonte, posição, quebra de linhas e parâmetros. Antialiasing pode diferir entre renderizadores. São modelos estáticos; não incluem karaokê nem animação palavra a palavra.
O SRT mantém apenas texto e tempos; a aparência é incorporada no vídeo exportado.

## Verificação
- Dez modelos visualmente distintos, cinco fontes carregadas, acentos, limites e persistência do estilo na normalização.
- Exportação FFmpeg: mesma cor/posição nas duas legendas em quatro instantes diferentes; legenda ausente após o fim.
- Playwright/Chrome: dez modelos, seleção de Anton, tamanho de 6%, posição no topo e parâmetros presentes na exportação.
- Regressão: montagem, transcrição, áudio, keyframes, cortes e exportação.
