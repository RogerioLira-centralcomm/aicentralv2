# [Video Studio] Render e exportação profissional

## Objetivo

Exportar toda a composição com fidelidade, presets compreensíveis, histórico e resultados vinculados a uma revisão imutável.

![Mockup — render e exportação](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/06-render-exportacao.png)

## Cena representada no mockup

O modal de exportação mostra formato vertical, 1080p, 30 fps, H.264, captions incorporadas + SRT, áudio estéreo, tamanho estimado e revisão v18. À direita, o histórico apresenta jobs renderizando, prontos e falhos com retry.

## Estado atual

- Exporta MP4 assíncrono de um clipe gerado.
- Preserva trim, velocidade, volumes, uma faixa adicional, fades, grayscale e flip.
- Não exporta composição multiclipes, textos, captions, transições ou várias faixas.

## Escopo funcional

- Compilar o schema v2 em filtergraph seguro no servidor.
- Fases: sequência/transform; áudio multifaixa; texto/captions; transições/keyframes.
- Proporções 16:9, 9:16, 1:1 e 4:5.
- Resoluções 720p e 1080p; 24/25/30/60 fps conforme capacidade.
- Presets Leve, Recomendada e Alta; avançado mostra codec/bitrate.
- MP4/H.264 inicial; captions queimadas ou arquivo SRT/VTT.
- Estimar tamanho, duração e custo antes de iniciar.
- Job referencia projeto, revisão, preset, usuário e ativos.
- Histórico, download, retry, cancelamento e retenção.

## Backend

- Renderizador sem aceitar paths, protocolos ou filtros arbitrários do cliente.
- Snapshot imutável por exportação e manifest do resultado.
- Timeouts, limites, logs por etapa e cleanup recuperável.

## Frontend

- Modal com resumo simples e configurações avançadas recolhidas.
- Progresso persistente, histórico e erros específicos da etapa.
- Possibilidade de continuar editando durante o render.

## Critérios de aceite

- [ ] Projeto com cinco clipes, duas imagens, captions, música e locução exporta corretamente.
- [ ] Saída respeita dimensão, FPS, duração, áudio e opção de captions.
- [ ] Alterar o projeto durante o job não modifica o resultado iniciado.
- [ ] Retry é idempotente e não cobra/gera duas vezes.
- [ ] Preview e export passam nos golden frames e testes de A/V sync.
- [ ] 720p/1080p são validados no ambiente de produção com memória medida.

## Dependências

- Schema de composição, timeline, captions, áudio e efeitos.
- Fila durável.

