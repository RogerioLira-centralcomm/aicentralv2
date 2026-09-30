# Capturas reais das páginas de Fluxos

As páginas salvas no fluxo são capturadas automaticamente ao abrir editor/monitoramento com permissão de edição. O ícone de atualização do nó solicita nova captura. Visitantes com acesso de leitura visualizam as capturas existentes sem consumir créditos. As capturas são do site público, sem cookies da sessão do usuário.

- Integração existente Firecrawl, chave resolvida no servidor pelo cofre ou FIRECRAWL_API_KEY.
- Capturas assíncronas, no máximo duas por processo; nenhuma fila ilimitada de threads.
- Lock entre processos evita duplicar captura da mesma URL/cliente. Cache por organização, cliente e URL; compartilhado entre fluxos do mesmo cliente.
- Imagem anterior permanece durante regeneração. Nova geração ignora cache do provedor.
- Armazenamento privado em instance/reports-flow-previews, configurável por REPORTS_FLOW_PREVIEW_DIR no Flask. Precisa de diretório persistente com escrita pelo serviço; múltiplos hosts devem compartilhar esse volume.
- Imagens entregues por rota autenticada, após validar fluxo, cliente e nó. Sem URL pública do arquivo privado.
- Destinos limitados às páginas salvas do domínio autorizado; pré-validação de disponibilidade e redirecionamentos; download de imagem HTTPS pública, sem seguir redirects, tamanho limitado e reencodificação WebP.
- Sem migração SQL. Sem serviço worker adicional. Se o processo reiniciar, capturas interrompidas são retomadas ao reabrir a tela após expirar o estado temporário.
- Falhas não geram novas cobranças em loop; usuário regenera manualmente. Não captura páginas ainda não salvas.

Build frontend e compilação Python concluídos. Não executada captura real com cobrança do provedor nem verificação em produção nesta entrega. Sem deploy. Retenção automática de arquivos ainda não implementada; provisionar armazenamento e acompanhar seu uso.
