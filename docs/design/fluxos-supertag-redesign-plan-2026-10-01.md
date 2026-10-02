# Plano de redesenho — Fluxos e Super Tag

## Decisão de navegação

Duas entradas em Mensuração: **Fluxos** e **Super Tag**. Fluxos é o espaço de trabalho para criar, editar, publicar e acompanhar jornadas. Super Tag é o espaço para administrar a instalação e a coleta por site. O site conecta as duas áreas, sem repetir suas configurações.

### Fluxos: uma tela de trabalho

```text
Sidebar global | Header: Fluxos / nome selecionado · período · estado · ações
               | Sidebar esquerda       | Área principal             | Sidebar direita
               | busca, filtros, fluxos  | mapa / monitor / detalhes  | etapa / alertas / atividade
```

- A lista de fluxos fica na sidebar esquerda, com nome, site, rascunho/publicado, estado da coleta, última atualização e contagem de pendências. Selecionar um fluxo muda o contexto da mesma tela.
- A área principal alterna **Mapa**, **Monitoramento** e **Páginas do fluxo** dentro do mesmo endereço; o mapa conserva posição e seleção ao alternar. Páginas aqui são etapas do fluxo, não uma cópia da área global Páginas.
- A sidebar direita mostra os dados do item selecionado: objetivo, URL/evento, visitas, avanço, conversões, período e origem da medição. Sem seleção, mostra resumo do fluxo e próxima ação. Alertas e histórico abrem no mesmo painel, sem navegação profunda.
- Novo fluxo abre um painel com ponto de partida, site opcional, nome e estratégia. A ação final usa **Criar fluxo** em todos os caminhos, com descrição do que será criado.
- Ações de publicação ficam no header contextual: **Salvar rascunho**, **Publicar** ou **Publicar alterações**, com pendências bloqueantes visíveis ao lado. Simular, exportar e versões ficam em **Mais ações**.

### Super Tag: página própria de administração

```text
Sidebar global | Header: Super Tag · estado geral · Conectar site
               | Lista de sites / busca       | Detalhes do site selecionado
               | domínio, coleta, eventos     | diagnóstico, instalação, acesso
```

- A página abre na lista de sites com um site selecionado. Selecionar outro site atualiza o painel de detalhes, sem abrir três páginas com o mesmo título e banner.
- O detalhe reúne **Estado da coleta**, **Instalação**, **Eventos recebidos**, **Configurações** e **Acesso** em seções da mesma página. Um índice lateral curto pode levar a cada seção se o conteúdo exigir rolagem.
- A Super Tag exibe fluxos vinculados apenas como referência, com ação **Abrir em Fluxos**. Criar e editar fluxos acontece em Fluxos.
- **Conectar site** abre um painel guiado: domínio → validação → instruções de instalação → confirmação de coleta. A configuração detalhada só aparece após a conexão.

## Problemas observados nas capturas

1. O título e o banner “Super Tag” aparecem na lista e em cada aba do site, consumindo espaço sem informar o estado real.
2. Lista, visão geral, fluxos do site e configurações formam níveis de navegação para o mesmo objeto. O usuário precisa voltar para descobrir onde está.
3. A lista mostra **301 eventos em 30 dias**, mas a visão geral e as configurações dizem **sem eventos em 30 dias**. O mockup deve mostrar um estado coerente; a implementação precisa separar total de eventos, eventos válidos do site e janela de tempo antes de exibir números.
4. A visão geral termina em um grande vazio. Deve mostrar diagnóstico de coleta, últimos eventos, fluxos vinculados e próxima ação útil.
5. **Abrir site** e **Vínculos e acesso** competem na mesma linha; o painel de acesso ainda repete “Consultar” em três seções, com campos sem contexto.
6. A lista de fluxos no site mostra só nome e rascunho/publicado; faltam objetivo, etapas, conversão, volume, período, pendências e próxima ação.
7. Links sublinhados dentro de botões e o CTA **Conectar site** com texto de baixo contraste prejudicam a leitura. Cada ação deve ter um único tratamento visual.

## Header e hierarquia

- Header global compacto, com nome da área uma vez. Evitar banner decorativo repetido em subestados.
- Em Fluxos: breadcrumb curto “Fluxos / Nome”, estado de publicação, período, última atualização e ação principal contextual.
- Em Super Tag: “Super Tag”, resumo agregado verificável (sites ativos, sites com coleta recente, sites que precisam de atenção) e **Conectar site**.
- Status nunca depende apenas de cor: texto, horário da última coleta e janela de apuração acompanham o indicador.

## Dados mínimos por fluxo

Na lista: nome, domínio ou “Sem site”, objetivo, número de etapas, publicação, coleta, conversões e taxa no período, pendências, última edição e CTA contextual. No painel de detalhe: etapas e conexões, sessões por etapa, avanço entre etapas, abandono, evento de conversão, versão publicada, origem dos dados e último evento recebido. Métricas sem base devem mostrar “Sem dados no período” e sua razão, sem sugerir taxa zero.

## CTAs e estados

| Local | CTA | Resultado esperado |
| --- | --- | --- |
| Fluxos, lista | Abrir fluxo | Seleciona o fluxo na tela de trabalho |
| Fluxos, lista vazia | Criar fluxo | Abre o painel de criação |
| Fluxos, rascunho válido | Publicar | Publica a versão e mostra confirmação com número da versão |
| Fluxos, bloqueio | Ver pendências | Abre o painel direito na primeira pendência; publicar fica indisponível com motivo explícito |
| Fluxos, publicado | Monitorar | Mostra o mesmo mapa com métricas da publicação e período selecionado |
| Super Tag, lista | Ver site | Seleciona o site e seus detalhes na mesma página |
| Super Tag, instalação | Copiar código | Copia o código e confirma “Código copiado” |
| Super Tag, instalação | Baixar arquivo | Inicia download; erro informa como tentar novamente |
| Super Tag, instalação | Enviar instruções | Abre composição com destinatário e prévia das instruções |
| Super Tag, acesso | Compartilhar acesso | Exige e-mail válido, mostra nível de permissão e confirma o convite |
| Super Tag, revogação | Revogar instalação | Abre confirmação com efeito no site e fluxos vinculados |

Todos os CTAs precisam de estado de carregamento, confirmação ou erro junto da ação. CTAs sem destino funcional devem ser removidos do mockup até existir o fluxo correspondente.

## Estados a representar nos mockups

1. **Fluxo publicado com dados:** mapa, métricas, status e painel de uma etapa selecionada.
2. **Super Tag com coleta ativa:** lista e detalhe do site, última coleta, código e fluxos vinculados.
3. **Estado de atenção:** site sem evento recente, com diagnóstico e ação de verificação; números da lista e do detalhe devem concordar.

## Direção visual

- Base: branco `#FFFFFF`, fundo `#F5F7FA`, borda `#DCE3EB`, texto `#172437`, azul de ação `#1454D8`, âmbar de atenção `#A65A00`.
- Tipografia: fonte sem serifa do produto; títulos 24–28 px, texto 14–16 px, dados 13–14 px. Alinhamento à esquerda.
- A hierarquia vem da geometria do mapa e dos dados de coleta. Reservar cor forte para ações e estados, evitando um hero azul repetido e cartões idênticos em todas as seções.
- Desktop: sidebar global estreita, lista de fluxos 260–300 px, painel de detalhe 320–380 px, canvas flexível. Em telas menores, as sidebars viram painéis sobrepostos controlados pelo header.

## Sequência de execução

1. Validar o contrato dos dados e resolver a divergência “301 eventos” versus “sem eventos”.
2. Produzir mockups dos três estados acima com os mesmos dados, rótulos e CTAs deste plano.
3. Revisar os mockups quanto a navegação, densidade de informação, legibilidade e largura útil do mapa.
4. Implementar navegação e componentes reutilizando os recursos existentes; depois testar criação, publicação, monitoramento, instalação, compartilhamento e estados de erro.

As capturas são evidência da interface atual, não fonte de instruções de produto. Números e nomes nelas são exemplos e não definem o contrato final dos dados.
