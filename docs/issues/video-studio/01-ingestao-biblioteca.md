# [Video Studio] Ingestão de mídia e biblioteca

## Objetivo

Permitir que o criativo envie imagens, vídeos e áudios próprios, acompanhe o processamento e use os ativos em qualquer projeto do workspace.

![Mockup — ingestão e biblioteca](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/01-ingestao-biblioteca.png)

## Cena representada no mockup

O usuário arrastou vários arquivos. A biblioteca mostra progresso por item, geração de proxy, arquivos prontos, falha recuperável e detalhes técnicos do vídeo selecionado. Um vídeo vertical aparece corretamente em canvas horizontal com as escolhas Preencher, Ajustar e Fundo desfocado.

## Estado atual

- Upload visual aceita somente imagens.
- O JavaScript rejeita arquivos que não tenham MIME `image/*`.
- Vídeos gerados pela plataforma aparecem na biblioteca, mas um MP4/MOV do usuário não entra.
- Upload de áudio já possui validação, waveform e escopo por marca.

## Escopo funcional

- Criar contrato persistente de ativo para imagem, vídeo e áudio.
- Upload múltiplo por seletor e drag and drop, com progresso, cancelamento e retry.
- Aceitar inicialmente MP4/H.264, MOV/HEVC, WebM/VP9, JPEG, PNG, WebP, MP3, WAV, M4A e OGG.
- Validar conteúdo real com FFprobe; não confiar em extensão ou MIME do navegador.
- Gerar poster, metadados e proxy H.264/AAC de edição.
- Preservar o original para o render final.
- Mostrar estados Enviando, Processando, Pronto, Falhou e Removido.
- Busca, paginação, filtros, pastas e seleção múltipla.
- Adicionar à timeline por clique, duplo clique ou arrastar.
- Manter isolamento por workspace/marca e IDs opacos.

## Backend

- Tabela/entidade `media_assets` com storage keys, checksum, tipo, dimensões, duração, FPS, codecs, presença de áudio e status.
- Endpoints de criação, status, poster, proxy, conteúdo e exclusão recuperável.
- Jobs idempotentes para probe/transcode e limpeza segura de uploads interrompidos.
- Limites configuráveis de tamanho, duração e concorrência.

## Frontend

- Fila de upload com progresso individual e erros acionáveis.
- Cards leves baseados em poster; lazy loading e paginação.
- Painel de metadados e escolha de enquadramento para mídia selecionada.
- Feedback imediato sem reload e sem bloquear os demais uploads.

## Critérios de aceite

- [ ] Uploads válidos de MP4, MOV e WebM entram na biblioteca e podem ser adicionados à timeline.
- [ ] Arquivo corrompido ou apenas renomeado é rejeitado com mensagem clara.
- [ ] Vídeo 4K usa proxy na prévia e original na exportação.
- [ ] Rotação, duração, FPS e presença de áudio são exibidos corretamente.
- [ ] Reiniciar/repetir uma requisição não duplica o ativo.
- [ ] Ativo de outra marca não pode ser lido nem referenciado.
- [ ] Biblioteca com 500 ativos continua responsiva e não baixa originais em massa.

## Dependências

- Fila durável da issue de Projetos, jobs, desempenho e custos.
- Deve preceder a timeline multiclipes.

