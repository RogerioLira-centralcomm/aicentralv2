# Pastas e responsabilidade dos produtos

As URLs piloto `/familia/<produto>/...` permanecem compatíveis e protegidas pelo
mesmo boundary de autenticação/contexto. O dispatcher não contém mais as consultas
por produto: carrega apenas módulos explicitamente registrados.

| Produto | Python | Páginas Jinja |
| --- | --- | --- |
| Workspace | `aicentralv2/cadu_workspace/pages.py` | `templates/cadu_workspace/family/` |
| SmartPlanner do cliente | `aicentralv2/cadu_planner/pages.py` | `templates/cadu_planner/family/` |
| Studio | `aicentralv2/cadu_studio/` | `templates/cadu_studio/family/` |
| Connect | `aicentralv2/cadu_connect/pages.py` | `templates/cadu_connect/family/` |
| Skills | `aicentralv2/cadu_skills/` existente | `templates/cadu_skills/` existente |
| Auth | `aicentralv2/cadu_identity/` existente | templates Auth existentes |

`smart_planner/` continua sendo o planejamento interno do CentralX. Não importar
seus controllers para a superfície do cliente sem projeção/permissões próprias.

## Compartilhado

- `cadu_family/`: boundary das rotas piloto, contexto autorizado, adaptadores
  legados, registro de produtos e facades de compatibilidade.
- `templates/cadu_family/`: layout comum, componentes de entrada/tabela/visitante.
- `cadu_workspace/conversations/`: serviço de conversa e validações server-side.
- `templates/cadu_workspace/conversations/`: painel/composer compartilhado.
- `static/cadu_workspace/conversations/`: JS do chat, transporte SSE e CSS.
- Copy Ads: implementação em `cadu_studio/copy_ads.py`; import antigo mantido
  como facade para consumidores existentes.

As pastas não significam conclusão funcional. As views específicas atualmente
encaminham alguns módulos aos componentes comuns de consulta/indisponibilidade.
Repositório legado, configuração dos produtos e APIs ainda têm componentes
centralizados: migrar gradualmente, mantendo testes e compatibilidade.

Não houve movimentação/remoção de arquivos PHP, mudanças no banco ou ativação
de novas rotas em produção.
