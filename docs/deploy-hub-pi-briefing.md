# Deploy: Entrada de PI, hub (PI e briefing em três caminhos)

Atualizado em 2026-11-17. Cobre os commits `a9ab77d46` a `989a8aca1` (Entrada de PI no CentralX, envio de PI pelo hub,
briefing com 3 caminhos, cotação com arquivos e prazo de 24 h, PI antigo). Plano: `docs/plans/hub-de-midia-pi-briefing-onboarding.md`.

## 1. Antes de subir

| Item | Situação |
|---|---|
| Commits | 2 ainda não estão no `origin/main` (`e260fd40b` e `989a8aca1`, briefing a partir de PI antigo). Dê `git push` antes. |
| Testes | 164 passam nos arquivos relacionados; 1 falha antiga (`test_texto_do_briefing_reune_os_campos`), sem relação. |
| Migrações | 2 novas no `migrations/ORDER.txt`, ambas idempotentes e testadas duas vezes num Postgres descartável (`create_pi_entrada.sql`, `add_briefing_cotacao.sql`). `tests/test_deploy_order.py` passa. |
| Código sem migração | Se o código subir **antes** da migração, quebram só a Entrada de PI (CentralX e hub) e o briefing de cotação, que usam as tabelas novas. O briefing comum segue normal (`enviar` só toca nas colunas novas no modo cotação). |

## 2. Passos no servidor (dentro de tmux)

1. `./deploy.sh` (roda `migrations/ORDER.txt`, inclusive as duas migrações novas).
2. Pastas privadas de arquivos (fora de `static/`), com escrita para o usuário do gunicorn:
   - `instance/pi_entrada` (PDFs de PI),
   - `instance/hub_briefing` (anexos de cotação).
   O código cria as pastas sozinho; só confirme a permissão de `instance/`.
3. Timer dos lembretes de prazo (12 h, 4 h, atraso), a cada 15 minutos:
   `sudo bash deploy/install_hub_briefing_prazos_timer.sh`
   Teste à mão: `flask --app run:app process-hub-briefing-prazos` (deve imprimir `0 aviso(s), 0 respondido(s)`).
4. Reiniciar o gunicorn (o deploy já faz).

## 3. Variáveis de ambiente (`.env`)

| Variável | Para quê | Padrão |
|---|---|---|
| `OPENROUTER_API_KEY` | Leitura de PI e de arquivos de cotação (já existe) | n/a |
| `PI_ENTRADA_MODELO` | Troca o modelo de leitura | `google/gemini-2.5-flash` |
| `HUB_GESTOR_EMAIL` | Quem recebe o aviso de 4 h e o de atraso (e-mails separados por vírgula). **Sem ela, só o executivo é avisado.** | vazio |
| `AREA_CLIENTE_EMAIL_EQUIPE` | Destino quando a conta não tem executivo (já existe) | `contato@centralcomm.media` |
| `HUB_ATIVACAO_LIBERADA` | Liga a sequência de 4 e-mails de ativação. **Deixe desligada até decidir** (item 5). | desligada |

Upload: nginx e Flask já aceitam 256 MB por requisição; um envio de cotação tem no máximo 5 × 20 MB.

## 4. Verificação depois do deploy (10 minutos)

1. CentralX, Comercial: abrir `/pi-entrada/`, arrastar um PDF de PI e conferir a leitura (cerca de 15 a 25 s) e as duas colunas.
2. Hub, com uma conta de teste: `/pis/enviar`, enviar o mesmo PDF, ver "O que entendi" (sem comissão, líquido nem CNPJ) e enviar ao executivo. O PI deve aparecer na fila do CentralX **só depois** do envio.
3. Hub: `/briefing` mostra os 3 cartões; `/briefing/cotacao` com um PDF e uma planilha; conferir no CentralX, em Briefings, a marca "Cotação 24 h" e o texto com anexos e leitura.
4. Hub: `/briefing/pi-antigo` lista PIs da conta; escolher um e ver o formulário preenchido.
5. E-mails: a equipe recebe "novo briefing" com anexos e prazo; o cliente recebe "recebemos o seu briefing" com o retorno previsto. Confira no Brevo.
6. Logs: nenhuma linha `Leitura do briefing de cotação ... falhou` nem `E-mails do PI enviado ... não saíram`.

## 5. Decisões que continuam abertas

- **D4, contagem do prazo:** hoje são 24 horas corridas, empurradas para o próximo horário útil (seg a sex, 9h às 18h). Se preferir contar só horas úteis, muda `cotacao.prazo_resposta`.
- **Sequência de ativação:** os e-mails 2 a 4 falam de enviar PI, ler arquivos e retorno em 24 h. Tudo isso já existe, então dá para ligar `HUB_ATIVACAO_LIBERADA=1`. O visual dos e-mails está na sessão `hub-emails`, esperando o HTML de marketing.
- **API do jev (D11):** ainda não sei o que é; fica fora deste deploy.
- Plugar o rascunho da Entrada de PI em `/cadu_pi/novo` (a tela atual não mudou).

## 6. Conta de demonstração (cliente 174, Centralcomm)

Para gravar vídeos e testar as telas sem usar dados de clientes, a conta **174** abre o hub em **modo demonstração**
(`aicentralv2/area_cliente/demo.py`):

- 5 PIs fictícios (2 em andamento, 3 finalizados) com 10 campanhas, notas fiscais e linha do tempo, sempre com datas relativas a hoje.
- **Nada é lido nem gravado no banco**: os PIs têm ids de demonstração (900000001 a 900000005), que não existem na produção, então
  relatórios, cotações e PIs reais do CentralX não enxergam nada disto.
- Envio de PI, de cotação e de briefing (com ou sem anexo) são **simulados na sessão do navegador**: a "leitura" leva 4 segundos e
  mostra um resultado de exemplo; enviar ao executivo só muda a tela, sem linha no banco e sem e-mail.
- Um selo discreto "Demonstração" aparece no topo (some no celular). Para tirá-lo do vídeo, corte a imagem ou desligue o modo.
- Desligar: `HUB_DEMO_CLIENTE_ID=0` no `.env` (a conta 174 volta a ver os dados reais). Trocar de conta: `HUB_DEMO_CLIENTE_ID=<id>`.
- Efeito colateral: enquanto ligado, quem entra no hub com a conta da Centralcomm só vê dados de demonstração. Quem a equipe quer
  ver de verdade usa "Ver como" no cliente real.

## 7. Como desfazer

- Código: `git revert` dos commits do hub; as tabelas e colunas novas ficam (inofensivas) e nada precisa ser apagado.
- Só desligar o envio de PI e de cotação pelo hub: tirar o cartão de `briefing_escolha.html` e o botão de `pis.html`; os dados já gravados continuam acessíveis no CentralX.
