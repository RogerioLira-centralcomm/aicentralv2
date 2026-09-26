# Plano: Planner React e catálogo de portais

## Objetivo
Modernizar o SmartPlanner como uma solução integrada ao Workspace, mantendo uma única experiência React com a skin do Planner. Acrescentar um catálogo pesquisável de 600–1.500 portais categorizados, com estimativas de audiência claramente identificadas e atributos públicos rastreáveis. Remover o Link Tester da navegação e retirar o frontend legado do Planner após migração validada.

## Decisões de produto e interface
- A entrada de soluções permanece no seletor global do Workspace (Workspace, Planner, Studio, Reports, Skills); o Planner ganha a navegação interna apropriada ao contexto do produto.
- A sidebar do Workspace será compartilhada/reutilizada, com os itens do Planner configurados para: Visão geral, Planos, Audiências, Canais, Formatos, Interativos, Places, Portais e Docs. A rota/ferramenta Link Tester deixa de ser item de menu e atalho na home; API e histórico podem continuar acessíveis sob demanda.
- Usar o shell, dock e comportamentos responsivos existentes do Workspace. Dock: manter como atalho contextual e recolhível no desktop, oculto em telas pequenas e sem duplicar a sidebar; validar com protótipo antes de fixar comportamento.
- Identidade Planner: conservar tipografia, espaçamento e componentes do Planner; propor índigo/ameixa profundo como cor complementar ao verde do Workspace, aplicada em estados ativos, gráficos e acentos, sem alterar os tokens globais.

## Arquitetura alvo
- Um shell React para todas as páginas autenticadas do Planner, montado sob rotas do produto; backend Flask preserva sessão, autorização, CSRF e APIs.
- React consome e normaliza APIs de planos, catálogos, Places, Docs e seleções já existentes. Expandir API com listagem paginada/filtros e endpoints do catálogo de portais.
- Separar módulos React: shell/navegação, planejamento, bibliotecas, portais, documentos e utilitários. Evitar reimplementar regra de negócio no cliente.
- Remoção do legado em ondas: inventariar templates/scripts/styles e consumidores; migrar cada fluxo; substituir referências e testes; apagar arquivos antigos somente quando não houver referências. Não remover backend/API de negócio necessária.

## Catálogo de portais
- Nova seção "Portais" em tabela densa, paginada no servidor, com busca, categorias, filtros, ordenação e destaque editorial dos 200 principais.
- Campos sugeridos: nome, domínio canônico, categoria/subcategoria, descrição, país/idioma, alcance estimado (valor ou faixa), período e metodologia da estimativa, fonte/data, formatos/comercialização pública, atributos públicos e status da última coleta.
- Diferenciar dado observado/publicado de estimativa/inferência; cada valor deve expor origem e data. Ausência de fonte significa "não informado", nunca preencher por geração.
- Corpus cresce em lotes: piloto de 50, primeira curadoria de 200 e depois 600–1.500. Definir categorias, critérios de inclusão, deduplicação por domínio, política de atualização e revisão editorial antes da carga ampla.
- Crawler respeita robots.txt, limites por domínio, termos e políticas aplicáveis, identifica-se, captura somente páginas públicas e metadados permitidos, registra URL/data/hash/evidência e permite remoção/reprocessamento. Não contornar login, paywall, CAPTCHA ou controles de acesso.
- Pipeline: descoberta de domínios → crawl de páginas institucionais/mídia kit → extração determinística de fatos e links → validação de domínio/fonte → revisão de qualidade → publicação versionada. Crawler não estima audiência por si só; métricas quantitativas exigem fonte pública explícita ou parceiro de dados autorizado.

## Uso de TypeSafe
TypeSafe deve apoiar julgamentos sem substituir coleta e validação determinísticas:
1. Choice para classificar o portal em uma taxonomia fechada, com opção "outro/não classificável".
2. Scores independentes para relevância ao planejamento de mídia, qualidade/cobertura da evidência e adequação editorial ao destaque; definir níveis concretos e compor ranking no código com pesos versionados.
3. Choice para escolher candidato de categoria/subcategoria entre valores permitidos; manter evidências e trechos de origem no estado.
4. Confiança orienta revisão humana e exibição de "classificação pendente"; não significa probabilidade de verdade. Ranking editorial não deve se passar por alcance.
5. Executar perguntas independentes em lote sobre o mesmo estado; persistir resposta bruta, versão das perguntas/modelo, confiança, timestamp e evidências para auditoria/reavaliação.
6. Chamada somente no servidor, credencial via variável de ambiente/secret manager. Nunca embutir chave no React, repositório, fixtures ou logs. A chave compartilhada na solicitação deve ser rotacionada/revogada.

## Fases e critérios de aceite
1. **Inventário e contrato**: mapear rotas, páginas, APIs, dependências legadas, sidebar/dock e permissões; congelar contratos de API; validar com usuários a hierarquia e o visual.
2. **Shell React**: integrar seletor de solução e sidebar Workspace; definir navegação Planner, estado ativo, acessibilidade, mobile e cor complementar; dock contextual conforme decisão acima.
3. **Migração das telas**: visão geral, planos e detalhe, catálogos existentes, Places, Docs e Link Tester fora do menu; preservar fluxos e controles de acesso.
4. **Portais piloto**: esquema e migrações, crawler com fila/rate-limit/evidências, admin de revisão, importação inicial de 50 domínios e tabela React. Nenhum número de audiência sem fonte e data.
5. **Ranking e expansão**: validar TypeSafe em amostra rotulada, calibrar limiares e revisão; selecionar 200 destaques; expandir gradualmente até 600–1.500 após métricas de cobertura/erro.
6. **Desativação do legado**: remover templates/JS/CSS exclusivos do Planner em etapas após paridade, eliminar rotas duplicadas sem consumidores e atualizar documentação.
7. **Operação**: monitorar falhas/latência do crawler, frescor por domínio, fontes quebradas, custo/latência TypeSafe, fila de revisão, cobertura por categoria e correções editoriais.

## Riscos e controles
- Escopo de 1.500 fontes pode gerar dados desatualizados ou inconsistentes: expansão progressiva e indicadores de frescor.
- Estimativas de audiência são sensíveis e frequentemente não públicas: não inventar valores; guardar metodologia, faixa e fonte, ou deixar vazio.
- Remoção prematura de legado quebra fluxos em rotas menos usadas: inventário de referências e remoção só após migração por superfície.
- Crawler pode gerar carga ou coletar além do necessário: limites, allowlist inicial, robots/políticas e trilha de auditoria.
- Segredo TypeSafe exposto no chat: revogar e emitir nova credencial antes de qualquer integração.

## Observação de escopo

## Execução inicial concluída
- Planner autenticado servido pelo template React dedicado; o Vite gera `static/cadu_planner/react/app.js` e `app.css`. Navegação interna inclui Portais, sem Link Tester, e mantém o seletor de soluções Workspace/Planner/Studio/Reports/Skills.
- A skin do Planner usa índigo/ameixa como acento complementar. O Dock ficou fora da navegação do Planner até validação de produto.
- Adicionada tabela paginada de portais, schema/API, rotas de detalhe e comando de crawl com respeito a `robots.txt`, controle de taxa e bloqueio de destinos IP privados. Campos de audiência só são mostrados com URL/período de fonte; o crawler não fabrica estimativas.
- Criado importador CSV com `--dry-run`; estimativa de audiência exige URL HTTPS, período e data/hora de verificação. O modelo está em `tmp/planner-portais-curadoria.csv`.
- Pesquisada a API pública do Atlas da Notícia: `/media/verified` retornou 56 veículos com atributos e evidências de transparência; `/media/online` retornou 7.209 nomes/localidades sem domínios, por isso não foi usado isoladamente como catálogo.
- Encontrado o endpoint `/data/analytic`, que expõe canais `Site`. Criado `scripts/build_planner_atlas_portal_candidates.py` e gerado lote de 1.000 candidatos distintos, distribuídos proporcionalmente entre UFs a partir de 6.466 registros ativos do segmento online (4.684 domínios únicos disponíveis). 56 candidatos aparecem também no endpoint de verificação Atlas. Cada linha inclui domínio/canal do diretório, localização e características públicas declaradas, fica pendente de crawl/revisão editorial e não foi ativada.
- Crawl piloto em cinco regiões: 2 sites responderam com metadados; 3 retornaram `robots_unavailable` e foram bloqueados pelo comportamento fail-closed. Nenhum registro piloto foi gravado ou ativado.
- Nenhum número de audiência ou ranking de destaque foi copiado/inferido. A API não fornece métricas de audiência nesse conjunto; a lista de “200 melhores” ainda requer critérios e avaliação humana/TypeSafe validada. Confirmar termos de reutilização antes da publicação.
- A fonte Atlas não fornece audiência neste conjunto; métricas e ranking dos 200 permanecem em branco. Validar termos de reutilização e confirmar cada domínio durante a curadoria.
- A função de avaliação TypeSafe está preparada, mas falta conectá-la ao fluxo de revisão e instalar uma credencial nova; nenhum score TypeSafe foi executado nesta etapa.
- Link Tester foi removido da navegação do Planner; links públicos antigos redirecionam ao relatório de Links em Reports.
- Validação feita: `npm run build:planner`, `python3 -m compileall` nos pacotes Planner/Family e parsing dos templates Jinja.
- Importação: após revisão humana, inclua em `public_attributes` o objeto `{"atributo":"status_curadoria","valor":"aprovado"}`; `flask --app <aplicação> import-planner-portals <arquivo.csv> --dry-run` valida sem gravar. Remova `--dry-run` para gravar ou atualizar os registros aprovados.
- Atualizar candidatos Atlas: `python3 scripts/build_planner_atlas_portal_candidates.py --limit 1000 --output tmp/planner-portais-atlas-candidatos.csv` (limite aceito: 600–1.500; saída fica pendente até curadoria).

## Ainda necessário para concluir o escopo integral
- O catálogo está vazio até importar e revisar um dataset confiável. Não publicar nem simular 600–1.500 portais ou os 200 destaques sem fontes verificáveis. Próximo lote recomendado: curadoria piloto de 50, aprovação editorial, depois 200 e expansão.
- Confirmar a experiência do Dock com o grupo.
- A verificação do mapa completo da aplicação Flask está bloqueada por erro preexistente fora do Planner: `NameError: snapshots` durante import de `aicentralv2/cadu_connect/reports_imports.py`.
- Revogar a chave TypeSafe que foi colada na conversa e emitir outra antes de uso operacional.
