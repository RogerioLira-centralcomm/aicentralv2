# Inventário Daisy — Operação, Comercial, Parâmetros

Gerado por `tmp/rota_daisy_inventario.py`. **Legacy** = `output-legacy.css` no ERP (`base_erp.html`).

| Módulo | Endpoint | URL (referência) | Tela | Legacy CSS | Template | Classes Daisy |
|--------|----------|------------------|------|------------|----------|---------------|
| comercial | `briefing_create` | — | briefing | Não | `briefing_form.html` | Não |
| comercial | `briefing_edit` | — | briefing | Não | `briefing_form.html` | Não |
| comercial | `briefing_list` | /briefings | briefings | Não | `briefing_list.html` | Não |
| comercial | `cadu_cotacoes` | — | cotacoes | Não | `cadu_cotacoes.html` | Não |
| comercial | `cadu_cotacoes_form` | — | cotacao | Não | `cadu_cotacoes_form.html` | Não |
| comercial | `cadu_pi_novo` | — | pi_recebido | Não | `cadu_pi_form.html` | Não |
| comercial | `crm_pipeline` | — | pipeline | Não | `crm_pipeline.html` | Não |
| comercial | `leads_analise` | — | analise_leads | Não | `leads_analise.html` | Não |
| comercial | `leads_list` | /leads | leads | Não | `cadu_leads.html` | Não |
| comercial | `places.editar` | — | places | Não | `—` | ? |
| comercial | `places.index` | — | places | Não | `places/index.html` | Não |
| comercial | `places.novo` | — | places | Não | `—` | ? |
| comercial | `smart_planner.briefing` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.canais` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.canvas` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.canvas_editar` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.gerar` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.index` | /smart-planner | smart_planner | Não | `smart_planner/index.html` | Não |
| comercial | `smart_planner.novo` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.publico` | — | smart_planner | Não | `—` | ? |
| comercial | `smart_planner.revisao` | — | smart_planner | Não | `—` | ? |
| operacao | `assinaturas.mesa` | — | assinaturas | Não | `assinaturas/mesa.html` | Não |
| operacao | `assinaturas.novo` | — | assinaturas | Não | `—` | ? |
| operacao | `assinaturas.viewer` | — | assinaturas | Não | `—` | ? |
| operacao | `cadu_pi_editar` | /cadu-pi/<id>/editar | pedidos_insercao | Não | `cadu_pi_form.html` | Não |
| operacao | `cadu_pi_lista` | /cadu-pi/lista | pedidos_insercao | Não | `cadu_pi.html` | Não |
| operacao | `campanha_pi_detalhe` | /campanhas-pi/<id> | acompanhamento | Não | `campanha_pi_detalhe.html` | Não |
| operacao | `campanhas_pi` | /campanhas-pi | campanhas | Não | `campanhas_pi.html` | Não |
| operacao | `campanhas_pi_lista` | /campanhas-pi/lista | acompanhamento | Não | `campanhas_pi_lista.html` | Não |
| operacao | `diarios_campanha` | /campanhas-pi/<id>/diarios | diarios | Não | `diarios_campanha.html` | Não |
| operacao | `link_destinos` | /link-destinos | links_destino | Não | `link_destinos.html` | Não |
| operacao | `metricas_semanais` | /metricas/semanais | metricas | Não | `metricas_semanais.html` | Não |
| operacao | `status_campanha` | /status-campanha | status_campanha | Não | `status_campanha.html` | Não |
| parametros | `admin_migrations.page` | /admin/migrations | migrations | Sim | `—` | ? |
| parametros | `brevo_test.formulario_teste_brevo` | — | teste_brevo | Não | `teste_brevo_email.html` | Não |
| parametros | `cadu_pi_com_vendas_lista` | — | comissoes | Não | `cadu_pi_com_vendas.html` | Não |
| parametros | `cotacao_detalhes` | — | cotacao_legado | Sim | `cadu_cotacoes_detalhes_legado.html` | Não |
| parametros | `cotacao_editar` | — | cotacao_legado | Sim | `cadu_cotacoes_form_legado.html` | Sim (btn, btn-ghost, btn-sm, btn-xs, form-control, input-bordered…) |
| parametros | `cotacao_nova` | — | cotacao_legado | Sim | `cadu_cotacoes_form_legado.html` | Sim (btn, btn-ghost, btn-sm, btn-xs, form-control, input-bordered…) |
| parametros | `cotacoes_list` | — | cotacoes_legado | Sim | `cadu_cotacoes_legado.html` | Sim (modal, modal-backdrop, modal-box) |
| parametros | `dv360_pages.diagnostico` | — | diagnostico_dv360 | Sim | `dv360_diagnostico.html` | Sim (btn) |
| parametros | `faixas_calculo_pi_lista` | /faixas-calculo-pi | faixas_pi | Não | `faixas_calculo_pi.html` | Não |
| parametros | `incentivos_lista` | /incentivos | incentivos | Não | `incentivos.html` | Não |
| parametros | `logs_auditoria` | — | auditoria | Não | `audit_logs.html` | Não |
| parametros | `parametros.integracoes` | — | integracoes | Não | `parametros/integracoes.html` | Não |
| parametros | `parametros.lista_old_kpi` | — | kpis_legado | Não | `parametros_lista_old_kpi.html` | Não |
| parametros | `parametros.modelagem_criativos` | /parametros/modelagem-criativos | modelagem_criativos | Sim | `parametros/modelagem_criativos.html` | Não |
| parametros | `parametros.monitoramento_servidor` | — | monitoramento_servidor | Não | `parametros/monitoramento_servidor.html` | Não |
| parametros | `parametros.testes_dv` | — | testes_dv360 | Não | `parametros_testes_dv.html` | Não |
| parametros | `parametros.testes_dv_legado` | — | testes_dv360_legado | Não | `parametros_testes_dv_legado.html` | Não |
| parametros | `parametros.treinamentos` | /parametros/treinamentos | treinamentos | Não | `parametros/treinamentos.html` | Não |
| parametros | `parametros.treinamentos_projetar` | — | treinamentos | Sim | `—` | ? |
| parametros | `parametros.treinamentos_projetar_sessao` | — | treinamentos | Sim | `—` | ? |
| parametros | `plataformas_campanha` | /plataformas-campanha | plataformas | Não | `plataformas_campanha.html` | Não |
| parametros | `tbl_cargo_contato` | — | cargos | Não | `tbl_cargo_contato.html` | Não |
| parametros | `tbl_setor` | — | setores | Não | `tbl_setor.html` | Não |
| parametros | `tipo_cliente_editar` | — | tipo_cliente | Sim | `tipo_cliente_form.html` | Não |
| parametros | `tipo_cliente_novo` | /tipos-cliente/novo | tipo_cliente | Sim | `tipo_cliente_form.html` | Não |
| parametros | `tipos_cliente` | /tipo-cliente | tipos_cliente | Sim | `tipo_cliente.html` | Sim (modal, modal-backdrop, modal-box) |

## Legenda

- **Legacy Sim (Parâmetros)**: carrega DaisyUI compilado; telas só com `cx-*` ainda herdam utilitários/base Daisy.
- **Legacy Não**: Comercial/Operação no ERP — Design System Enterprise (`enterprise-system.css`).
- **Classes Daisy**: tokens `btn`, `modal-box`, `form-control`, etc. no template principal (ignora prefixos `cx-`, `crm-v3-`, `pi-op-`).
- **`?` template**: endpoint no mapa de contexto, template não inferido automaticamente — conferir blueprint.

## Parâmetros: legacy ON vs OFF

**Legacy ON** (Daisy carregado): migrations, tipos de cliente, cotações legado, modelagem criativos, KPI legado, Brevo test, etc.

**Legacy OFF** (só Enterprise): auditoria, setores, cargos, faixas PI, incentivos, plataformas, comissões, treinamentos, integrações, monitoramento, testes DV360, intelligence.