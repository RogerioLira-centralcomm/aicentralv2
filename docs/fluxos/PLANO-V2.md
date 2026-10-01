# Fluxos v2 — Plano de Entrada, Edição e Monitoramento

Complementa o [PLAN.md](PLAN.md) (ExecPlan M1–M7). Este plano trata da experiência de ponta a ponta: o caminho desde registrar uma URL até ler a jornada medida. Cenário de aceite: `www.energyfuture.com.br`.

## 1. Pergunta que cada tela responde

| Tela | Pergunta | Resposta visual |
|---|---|---|
| Entrada (lista de fluxos) | “Qual fluxo precisa de mim agora?” | Tabela curta com status de coleta, conversão do período e pendência principal. |
| Novo fluxo | “Que tipo de site é e qual o caminho até a conversão?” | Um assistente de 3 passos: domínio, teste de conversão e proposta. |
| Editar | “O desenho está certo e pronto para medir?” | Mesa livre, da esquerda para a direita: origem → entrada → meio → conversão/saída. |
| Monitorar | “De onde vêm, por onde passam, onde saem e quantos convertem?” | A mesma mesa, com espessura das linhas proporcional às sessões, barras de saída por nó e um resumo no topo. |

Princípio: **uma única mesa**. Editar e Monitorar usam o mesmo componente (`FlowCanvas` + card `fnode`), e muda só a camada: desenho ou dados. Nada de colunas fixas: as etapas são faixas de leitura, não trilhos.

## 2. Diagnóstico (estado em 30/09/2026)

### Já resolvido nesta rodada (não commitado)
- **Nós:** um card único (`flow-node.css`) substitui círculos e losangos. Os handles agora ficam no meio das bordas: antes estavam presos em `top:65px` dentro de um corpo de 52px. As 4 portas auxiliares continuam lá só para compatibilidade, invisíveis.
- **Linhas:** curvas bezier, espessura proporcional a √sessões, seta pequena de tamanho fixo e hover/inserir/remover funcionando. Conexões por arraste foram testadas no harness.
- **Colunas fixas:** ao soltar um nó, o x deixou de ser forçado para a coluna da etapa. A etapa continua sendo inferida pela posição.
- **Saídas:** cada nó mostra “N saíram aqui · %”. O cálculo é feito no cliente: sessões do nó menos as sessões das conexões de saída. O topo mostra o resumo “chegaram · converteram · saíram · maior saída”.
- **Teste de conversão:**
  - Backend em `reports_flow_probe.py`, com testes. A análise lê só o HTML; o envio real é opcional, exige Playwright, tem limite diário e confirmação explícita.
  - Painel “Testar conversão” no editor, com prévia em fantasma e aplicação via `applyBlueprint`.
  - A proposta inclui as origens do tráfego, deduzidas das tags encontradas (Google Ads, Meta, TikTok e LinkedIn), mais orgânico e direto.
- **Explorador de páginas:** limite de 100 páginas, grupos e paginação de 10 itens (commit `95edc478`).

### Problemas abertos
| # | Problema | Onde |
|---|---|---|
| P1 | Nós de origem em configs v1 perdem `kind` e aparecem todos como “Direto” (`flowBlockFor` usa o `source` do bloco padrão). | `flowBlockRegistry.js`, `_normalize_flow_config` |
| P2 | O backend não calcula saídas nem entradas por nó. Hoje a saída é derivada no cliente e erra quando há conexões não desenhadas. | `reports_flow.py` (journey) |
| P3 | `main.jsx` tem ~2000 linhas e mistura a lista, o editor e a descoberta. O estado do editor está espalhado em dezenas de `useState`. | `main.jsx` |
| P4 | A barra superior da mesa (“Funil / Navegação completa / Mostrar retornos / Legenda”) é técnica e compete com o resumo. | `FlowCanvas.jsx` |
| P5 | O layout ELK coloca as etapas em colunas rígidas (`stageX`) e ignora a espessura do tráfego. | `flowLayout.js` |
| P6 | Monitorar (`FlowMonitorWorkspace`) tem um shell, um rail e uma legenda próprios, diferentes do editor. | `FlowMonitorWorkspace.jsx`, `flow-monitor-workspace.css` |
| P7 | A entrada não diz o que fazer: falta “próxima ação” por fluxo e o estado vazio não guia o primeiro teste. | `main.jsx` (lista) |
| P8 | CSS em camadas, com 4 arquivos de fluxo e regras `!important` sobrepostas. | `flow-canvas.css`, `flow-workspace.css`, `styles.css`, `reports-refinement.css` |
| P9 | O caminho de envio real (Playwright) nunca rodou. Falta instalar o Playwright no servidor e validar em uma página própria. | `reports_flow_probe.py` |
| P10 | Eventos dentro da página (landing) não têm medição dedicada: `scroll_50` e `cta_click` são propostos, mas a Super Tag não os emite automaticamente. | Super Tag / `reports_flow.py` ingest |

## 3. Fases

### Fase A — Fechar a mesa (1 sprint)
1. **P1:** persistir `kind` também no v1 (whitelist em `_normalize_flow_config`). `flowBlockFor` passa a resolver pela plataforma em `node.source` antes do bloco padrão. Teste: nó Meta salvo e recarregado continua Meta.
2. **P4:** trocar a barra superior por um seletor de camada (`Desenho | Jornada medida`), com o período ao lado. “Retornos” e “Navegação completa” vão para um menu “Exibir”. O resumo da jornada ocupa o topo quando houver dados.
3. **P5:** layout “Organizar” com ELK `layered`, sem partição rígida. As faixas de etapa viram fundo. Os nós mais trafegados ficam no centro vertical de cada camada.
4. Estado vazio da mesa: um único CTA “Testar conversão da página inicial” e um link secundário “Explorar páginas”.
5. **Aceite:** no fluxo energyfuture, todas as conexões são arrastáveis entre quaisquer nós, os handles ficam alinhados em zoom de 0,3 a 2, e não há sobreposição depois de “Organizar”.

### Fase B — Entrada e criação (1 sprint)
1. **Lista:** colunas `Fluxo · Site · Coleta (ok/parcial/sem dados) · Conversão 30d · Próxima ação`. “Próxima ação” é calculada a partir de `useFlowReadiness` (instalar tag, definir conversão, publicar ou revisar saída alta).
2. **Novo fluxo** (drawer em 3 passos, sem sair da lista):
   1. domínio, com verificação da tag ou instruções de instalação;
   2. “Testar conversão” da URL inicial: análise do HTML, tipo de site sugerido e editável, e envio de teste opcional;
   3. proposta conforme o tipo de site:
      - landing: eventos na página;
      - institucional: menu → contato → conversão;
      - multipágina: explorador de páginas, com grupos;
      - e-commerce: produto → carrinho → checkout → compra.
3. Ao concluir, o editor abre com a proposta já aplicada e o painel de pendências visível.
4. Persistir `site_kind` no config (`config.site_kind`, whitelist e validação em `SITE_KINDS`).
5. **Aceite:** com energyfuture, um fluxo com origens, entrada, contato/orçamento e conversão fica pronto em menos de 2 minutos, sem nenhuma captura de tela automática.

### Fase C — Monitoramento real (1–2 sprints)
1. **P2:** o endpoint de jornada passa a devolver por nó `entrances` (primeira página da sessão), `exits` (última página) e `conversions`. Por conexão: `sessions` e `rate`. Para origem: `utm_source/medium` ou `referrer_host`, normalizados para a plataforma.
   - SQL: uma janela por sessão (`ROW_NUMBER` asc/desc) sobre `cadu_reports_flow_events` no período.
2. A mesa usa os números do servidor. O cálculo derivado no cliente fica só como fallback, marcado como “estimado”.
3. **P6:** `FlowMonitorWorkspace` passa a ser o editor em modo leitura, com camada “Jornada medida”. O shell, o rail e a legenda próprios são removidos.
4. **Nó “Saiu do site” agregado (opcional):** um sorvedouro à direita que recebe linhas laranja finas de cada nó com saída acima de 20%. Liga e desliga pelo menu “Exibir”.
5. **Origens desconhecidas:** sessões cuja origem não tem nó viram “Outras origens”, sem somar duas vezes.
6. **Aceite:**
   - a soma das saídas mais as conversões é igual às sessões de entrada (tolerância de sessões abertas);
   - “sem dados” é diferente de “0 observado”;
   - período, versão publicada e fuso aparecem junto do resumo.

### Fase D — Motor e contratos (contínuo; precisa terminar antes da Fase C)
1. **P3:** extrair de `main.jsx`:
   - `FlowsIndex.jsx` (lista e criação);
   - `FlowEditor.jsx` (shell e painéis);
   - `useFlowEditorState` (um reducer com ações `addNode`, `connect`, `move`, `applyProposal`, `undo/redo`, substituindo os `setFlowConfig` espalhados);
   - `useDiscovery` (mapeamento e catálogo).
2. **Contrato único** documentado em `docs/fluxos/CONTRACT.md`: nó (`id`, `type`, `kind`, `source`, `title`, `path`, `host`, `stage`, `event_name`, `origin`, `x`, `y`, `description`), aresta (`id`, `from`, `to`, `from_port`, `to_port`, `variant`, `label`, `origin`) e `site_kind`. Testes de paridade entre o Python (`_normalize_flow_config`) e o JS (`flowValidation.js`).
3. **P8:** consolidar o CSS de fluxo em `flow-canvas.css` (mesa) e `flow-panels.css` (painéis), removendo `!important` e regras mortas. Meta: menos 40% de linhas.

### Fase E — Teste de conversão completo (depende de infraestrutura)
1. **P9:** instalar o Playwright e o Chromium no servidor (`pip install playwright && playwright install --with-deps chromium`) e validar o envio em uma página de teste própria antes de qualquer cliente.
2. Leitura renderizada opcional, para tags carregadas via GTM: Playwright sem screenshot, que captura os hosts de rede e confirma pixels (Meta, Google Ads, TikTok) disparados no carregamento e após o envio.
3. **P10:** eventos padrão da Super Tag para landing: `scroll_50`, `cta_click` (botões e links com intenção) e `form_submit`. Opt-in por fluxo.

## 4. Regras que não mudam
- Nunca capturar tela sem pedido explícito, por nó.
- O envio real é sempre uma ação separada, confirmada, limitada a 3 por dia por fluxo e restrita ao domínio autorizado, com dados fictícios `.invalid`. Formulários com captcha, senha, cartão, arquivo ou busca nunca são enviados.
- Sugestão nunca vira publicação sem revisão. Todo nó gerado guarda `origin` (`probe`, `blueprint` ou `manual`).

## 5. Ordem recomendada
A (mesa) → D.1/D.2 (motor e contrato) → B (entrada) → C (monitoramento real) → E (navegador). D.3 acompanha cada fase.

## 6. Progresso
- [x] A.1 `kind` persistido também no v1; `flowBlockFor` resolve origem por `node.source`.
- [x] A.2 Barra da mesa trocada por menu “Exibir” (navegação completa, retornos, legenda).
- [x] A.3 “Organizar” sem colunas rígidas; faixas de etapa seguem os nós. **Corrigido bug de produção:** o worker de layout (ELK) falhava ao construir (`h7 is not a constructor`); agora usa o protocolo do próprio `elk-worker`.
- [x] A.4 Estado vazio com um único CTA “Testar conversão”.
- [x] B.1 Lista com coluna “Próxima ação” (`flowNextAction.js` + teste).
- [x] B.2/B.4 “Novo fluxo” pede o tipo de site (`config.site_kind`, validado no backend) e abre o editor com o teste de conversão pronto (`?testar=1`, sem executar nada).
- [x] B.x Removida a segunda tela de entrada (`FlowLibrary`, atrás de feature flag) e os modelos fixos (`flowTemplates.js`).
- [x] C.1 Jornada no servidor: `entrances`/`exits` por página, sessões por origem (Google Ads, Meta, orgânico, direto, redes, outros sites) aplicadas aos nós de origem e às suas conexões, e `origins` no payload (`reports_flow_metrics.py` + testes).
- [x] C.2 A mesa usa as saídas do servidor; o cálculo local fica como “(est.)”.
- [ ] C.3 Monitorar = editor em modo leitura (remover `FlowMonitorWorkspace`).
- [ ] C.4 Nó agregado “Saiu do site”.
- [ ] D.1 Extrair `FlowsIndex`, `FlowEditor`, `useFlowEditorState`, `useDiscovery` de `main.jsx`.
- [ ] D.2 `CONTRACT.md` + testes de paridade Python/JS.
- [ ] D.3 Consolidar CSS de fluxo.
- [ ] E Playwright no servidor, leitura renderizada e eventos de landing na Super Tag.
