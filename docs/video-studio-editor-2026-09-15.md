# Studio: edição visual, mídia e áudio

## Implementado

- Prévia contida na área de trabalho, mantendo a proporção nativa; abas fixas em cinco colunas e painéis ocultos fora do fluxo.
- Importação de MP4, MOV e WebM, até 150 MB / 5 minutos. Validação por FFprobe, conversão H.264/AAC, reprodução no navegador e exportação pelo mesmo editor de corte, velocidade e efeitos dos clipes gerados.
- Oito quadros reais por vídeo, armazenados em cache; miniaturas maiores das cenas para organização.
- Inspeção do áudio original pelo servidor. Faixas visuais distintas para original e trilha adicional, waveform e mute independente.
- Extração do áudio do vídeo para a biblioteca. Upload de áudio já existente mantém compressão AAC 128 kbps.
- 100 efeitos reais do pacote [Kenney Interface Sounds](https://kenney.nl/assets/interface-sounds), CC0. Arquivos locais em `aicentralv2/static/audio/studio`, com catálogo, origem e licença. Disponíveis para ouvir e exportar, sem download externo em tempo de edição.
- Até oito textos sobrepostos, com tempo, posição, tamanho, cor, ocultação e fade independentes; faixas próprias na timeline. Texto rasterizado com Pillow, sem interpolar texto do usuário em filtros FFmpeg.
- Ajustes preservados por clipe no projeto; trocar de clipe reinicia apenas seu histórico de desfazer.
- Escolha de transição por cena no roteiro. Correção do planner para levar os beats ao prompt da geração.
- Correção do fade visual na prévia quando a velocidade difere de 1×.

## Validação

- Testes existentes de vídeo e projetos, mais cinco testes do novo editor: ingestão, rejeição de arquivo inválido, isolamento por marca, oito quadros, extração, catálogo, exportação real combinando vídeo importado + som público + texto, preservação de áudio/duração e roteiro com transição.
- Teste Playwright com template Jinja e módulos reais; APIs simuladas: abas de 390 a 1440 px, filmstrip, mute, textos, biblioteca de 100 sons, troca de clipe conservando edição e ausência de erros JavaScript.
- Build Tailwind do Studio e verificação de diff.

Execução:

```sh
python3 -m unittest tests.test_video_studio tests.test_studio_projects tests.test_studio_media_editor -q
npm run build:studio
python3 tests/frontend/render-video-editor-fixture.py
node tests/frontend/mc-video-editor.test.cjs
```

## Evolução executada

- Proporção inferida das dimensões reais da referência, com escolha explícita preservada no projeto. Preparação com contain, sem esticar; validação FFprobe impede entregar como sucesso um vídeo em formato ou duração incompatíveis. Exportação de clipe também respeita a proporção do projeto.
- Montagem de até 30 imagens/vídeos, divisão, duplicação, reordenação, corte, velocidade, enquadramento e zoom de imagem. Transições determinísticas por FFmpeg; até oito trilhas adicionais com mute, volume, deslocamento, repetição e fades.
- Legendas manuais ou importadas de SRT, exportação SRT e legendas incorporadas ao MP4; composição em 720p/1080p a 24/30 fps.
- Modal de processamento em tela cheia, imagens de referência, etapas reais, tempo decorrido, retorno à edição e acesso ao resultado. Histórico persistido e notificações opcionais do navegador.
- Fila persistida de geração e exportação; processo separado do servidor web, retomada por ID do provedor, proteção contra execução duplicada e recuperação de exportações interrompidas.
- Barra lateral compacta e painéis recolhíveis, com layout grafite e azul claro.

## Pendências executadas antes do commit

- Preparação de vídeos, inspeção de quadros/áudio e extração agora usam tarefas persistidas, consultadas por AJAX. Fechar a página depois de concluir o upload não perde a preparação.
- Transcrição automática local do áudio da montagem, com detecção de idioma, divisão em legendas temporizadas, revisão e SRT. O histórico permite recuperar o SRT após sair da página. Implementação baseada no [faster-whisper](https://github.com/SYSTRAN/faster-whisper), sem envio do áudio a serviço externo.
- Keyframes de posição X/Y, escala, rotação e opacidade para textos e itens de imagem/vídeo. Até 60 pontos por item, com interpolação linear, suave ou manutenção do valor. Normalização numérica no servidor; nenhum filtro FFmpeg fornecido pelo cliente.
- Prévia instantânea em canvas, sequência de imagens/vídeos, áudio multifaixa, textos, legendas e transições. A prévia renderizada continua disponível para conferir o resultado exato antes de exportar.
- Web Push opt-in por usuário, marca e dispositivo, service worker, checkpoints de entrega e repetição limitada. Compatibilidade com serviços de push Google, Mozilla, Apple e Windows. Implementação de envio usando [pywebpush](https://github.com/web-push-libs/pywebpush). Só envia para dispositivos inscritos; nenhuma mensagem real foi enviada durante os testes.
- Instalador Linux/systemd integrado ao `deploy.sh`, com dependências isoladas no venv existente, download e validação do modelo local, usuário herdado do serviço web, verificação de banco/armazenamento e ativação do worker.

## Deploy — a executar pelo responsável

O usuário solicitou fazer o deploy pessoalmente. Esta execução prepara o código e o commit; não instala serviços nem publica em produção.

O `deploy.sh` chama `deploy/install_media_worker.sh` antes de reiniciar a aplicação. O instalador:

1. usa o Python do venv e instala `requirements-media.txt`;
2. prepara o modelo Whisper small em `instance/media-models/whisper-small` (requer acesso à internet na primeira instalação);
3. verifica banco e armazenamento sem executar jobs;
4. instala, habilita e reinicia `cadu-media-worker.service`;
5. configura o aplicativo para usar `MEDIA_WORKER_MODE=supervised` no próximo restart.

Também pode ser executado separadamente no checkout do servidor:

```sh
bash deploy/install_media_worker.sh
sudo systemctl restart aicentralv2
sudo systemctl status cadu-media-worker --no-pager
```

Aplicativo e worker devem compartilhar banco, configuração e armazenamento. Preservar `instance`/o diretório de mídia entre deploys: ali ficam tarefas, arquivos, assinaturas push e a chave VAPID privada. As permissões são herdadas do usuário do serviço web. A chave de push é criada ao ativar o primeiro dispositivo.

Após o deploy, clicar no botão de notificações do Studio e aceitar a permissão no navegador. Push exige contexto seguro (HTTPS); a entrega com a página fechada depende do suporte do navegador e das permissões do sistema. Não há garantia de entrega com o dispositivo desligado ou o navegador explicitamente impedido de trabalhar em segundo plano.

## Validação

```sh
python3 -m unittest tests.test_video_studio tests.test_studio_projects tests.test_studio_media_editor tests.test_studio_jobs_delivery tests.test_studio_composition tests.test_studio_completion tests.test_trocr_animate -q
npm run build:studio
python3 tests/frontend/render-video-editor-fixture.py
node tests/frontend/mc-video-editor.test.cjs
node tests/frontend/mc-studio-workflow.test.cjs
```

- FFmpeg real: MP4 vertical 720×1280, transição, duas trilhas, texto, legenda, áudio e duração; texto que muda de posição entre quadros; imagem com escala, rotação e opacidade animadas.
- HTTP: tarefas persistidas, execução posterior, recuperação após interrupção, isolamento por usuário e ausência de paths privados na resposta.
- Push: validação de destinos, isolamento da assinatura e envio idempotente com transporte simulado.
- Transcrição real em ambiente temporário: modelo tiny reconheceu a frase sintética de teste e produziu tempos. O instalador de produção prepara o modelo small; sua qualidade em áudio real deve ser conferida após implantação.
- Navegador: abas responsivas, mídia, montagem, keyframes, reprodução instantânea, importação SRT, aplicação de transcrição simulada, exportação e modal de progresso.

## Limites e verificação em produção

- A prévia instantânea privilegia edição rápida; tipografia, mixagem/limiter e transições podem diferir levemente do render FFmpeg. Use “Renderizar prévia” para conferência exata. Não foi realizado benchmark do projeto máximo de 10 minutos/30 itens.
- Objetos ou textos já incorporados aos pixels de um vídeo não voltam a ser camadas independentes. As camadas mantidas no projeto continuam editáveis depois do render.
- Reconhecimento de fala pode errar nomes, música e falas simultâneas. Revise as legendas antes de publicar.
- Múltiplas passagens FFmpeg e transcrição em CPU podem aumentar o tempo de processamento.
- A biblioteca contém 100 efeitos CC0; não representa um catálogo de músicas comerciais.
- A meta “80%” não foi medida contra o backlog completo. Recursos avançados desse backlog, como tracking, máscaras, ducking assistido e colaboração, não são declarados concluídos por esta entrega.
- Após o deploy, validar uma geração real do provedor, reinício do serviço durante um trabalho e recebimento de push em dispositivo inscrito. Esses testes externos não foram executados aqui.
