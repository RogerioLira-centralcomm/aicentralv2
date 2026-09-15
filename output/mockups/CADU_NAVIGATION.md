# Navegação compacta Cadu

Implementação exclusiva do protótipo `cadu-platform.html`, compartilhada pelas cinco famílias. Nenhum arquivo do Cadu/App PHP foi alterado.

## Referência inspecionada

Arquivos do aplicativo em `/Users/apololira/PhpstormProjects/centralcomm/www/cadu/`: `includes/sidebar-main.php`, `assets/css/sidebar-main.css` e `assets/css/theme-tokens.css`.

Adotados: cabeçalho de 60px, símbolo de 28px, lateral de 248px, navegação de 13px com padding 7×10px e raio de 8px. Workspace usa fundo #F7F8FA, superfícies brancas, texto #1F2937, ativo #ECEEF2 e ação mint #06F17B com texto escuro #08311C. O ícone raster teal da família permanece separado da cor de ação do aplicativo.

## Componentes

- Mega menu: cinco colunas alinhadas, imagens padronizadas, nome e estado de cada produto. Em telas menores, a mesma linha tem rolagem horizontal interna, sem alargar a página.
- Contexto: organização, cliente, projeto e marca. Trocar cliente restaura seu último projeto; trocar organização valida novamente os vínculos.
- Conta: avatar com iniciais, organização, plano, créditos, integrações, notificações e materiais. A ação de esquecer contexto limpa a preferência atual.

## Persistência e limites

`cadu-context.js` valida IDs das fixtures antes de recuperar preferências. Retenção de 30 dias em localStorage; quando servido por HTTP, cookie restrito a `/parametros/prototipos-cadu`, SameSite=Lax e Secure em HTTPS, sem Domain compartilhado. No modo file, utiliza apenas armazenamento local. Não é sessão, SSO nem autorização; não altera projetos reais ou arquivos. Os dados continuam demonstrativos.

## Verificação

`tests/test_cadu_context.cjs` verifica memória por cliente, troca de organização, expiração e limpeza. `tests/cadu_navigation_browser.cjs` verifica alinhamento, ausência de overflow da página, conta e persistência em 1440, 1024, 768 e 390px. Capturas em `output/cadu-validation/navbar-*.png` e `account-refined.png`.
