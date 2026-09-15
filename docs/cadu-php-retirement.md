# Preservação e desligamento do Cadu PHP

## Referência preservada em 15/09/2026

Snapshot local: `.legacy-reference/cadu-2026-09-15-v2/`.
Manifesto: `manifest.json` dentro desse diretório.

- 2.094 arquivos verificados por SHA-256: 2.011 cópias e 83 versões sanitizadas.
- 166 regras de rota PHP extraídas do `.htaccess` principal.
- 420 nomes candidatos de tabelas encontrados no código; não equivalem a tabelas confirmadas nem a um backup de dados.
- Origem: `/Users/apololira/PhpstormProjects/centralcomm/www/cadu`.
- Snapshot privado, ignorado pelo Git, com arquivos sufixados `.reference` para não executar PHP.
- Configurações sensíveis, arquivos não classificados e diretórios de runtime estão excluídos. As exclusões estão no manifesto e no script.
- A detecção de credenciais é conservadora e não garante ausência de todo segredo. Não publicar nem anexar a serviços externos sem revisão.
- `product_hint` é classificação inicial por nomes, não comprovação de responsabilidade funcional.

O primeiro snapshot `cadu-2026-09-15/` é uma captura preliminar, também local. Usar `v2` como referência principal: contém as versões sanitizadas e o inventário correto de rotas.

## Fontes para reconstrução

| Destino | Referências PHP | O que precisa ser preservado funcionalmente |
| --- | --- | --- |
| Workspace | `configuracoes-*.php`, `centro-inteligencia.php`, `integracoes*.php`, `planos.php`, `checkout-plano.php` | Conta, permissões de equipe, clientes, projetos, marcas, limites, consumo e cobrança |
| SmartPlanner | `audiencias*.php`, `canais*.php`, `formatos*.php`, `interativos*.php`, `smart-docs.php`, `cotacoes*.php` | Catálogos, detalhes, documentos, exportações e cotação independente, sem controles internos |
| Studio | `ferramentas-link-tester*.php`, `creative-analyzer*.php`, `ferramentas-copy*.php` | Inputs, validações, processamento, resultados e históricos |
| Connect | `campanhas*.php`, relatórios e APIs de integrações | Relatórios, associação autorizada a cliente/projeto e integrações operacionais |
| Auth | `login.php`, `auth/`, cadastro, recuperação, SSO e callbacks | Compatibilidade de contas, sessões, cookies e login Google |
| Conversas | `chat-cadu-dify.php`, `includes/dify/`, `assets/js/dify/`, `api/dify-*.php`, `includes/projetos/`, `n8n-prompts/dify/` | Input completo, modos, anexos, streaming, parar, histórico, conhecimento, ferramentas e consumo |

Preservar os assets e comportamentos não significa reutilizar PHP em produção.
O destino é frontend no padrão da família e backend Python 3.
Conversas compartilhadas somente em Workspace, SmartPlanner e Connect; Studio e Skills ficam fora.
As demais ferramentas ficam preservadas como referência, sem publicação automática.

## Bloqueadores para desligar sem perda

1. Backup consistente do PostgreSQL, com restauração de teste. Ainda não realizado nesta tarefa.
2. Backup dos uploads, documentos gerados, logos, anexos e objetos externos, incluindo associação aos IDs do banco. A captura de código não contém os diretórios de uploads/runtime.
3. Exportação da configuração efetivamente publicada dos apps Dify, modelos, ferramentas e bases. Os arquivos locais em `n8n-prompts` podem não representar a versão em produção.
4. Transferência segura de segredos OAuth/Dify/Gemini/Firecrawl e demais provedores para o ambiente Python. Não colocar valores no Git ou neste documento.
5. Inventário das rotinas agendadas, webhooks, callbacks OAuth e armazenamento fora da árvore local.
6. Validação de cada fluxo Python com contas piloto, permissões, históricos e arquivos reais. Só então habilitar redirecionamento de tela e retirar sua dependência PHP.
7. Copiar o snapshot privado e os backups para armazenamento controlado fora desta máquina. Esta cópia local não é redundância de desastre.

O `.htaccess` local atualmente encaminha GET/HEAD para manutenção antes das rotas da aplicação. Isso foi observado no arquivo, não verificado no servidor de produção.

## Repetir a captura

Executar `python3 scripts/preserve_cadu_legacy.py ORIGEM NOVO_DESTINO`.
O destino precisa ser novo; o script não sobrescreve capturas, não altera a origem e não acessa rede/banco.
Revisar o manifesto e as exclusões após cada captura. Os arquivos sanitizados são referências de migração, não código executável nem backup restaurável de produção.
