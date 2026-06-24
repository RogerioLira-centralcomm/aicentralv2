"""
Rotas HTML e API do fluxo OFICIAL de cotações (cálculo bottom-up).
Comercial > Cotações em /cotacoes; APIs sob /api/cotacoes/.
Observação: internamente os registros ainda usam a flag origem=teste_calculo
(funções db.*_teste_calculo) por compatibilidade com o histórico.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from aicentralv2 import db
from aicentralv2.auth import login_required

from aicentralv2.db import PLATAFORMA_CATEGORIAS_CANONICAS as _ORDEM_CATEGORIA_PLATAFORMA


def _ordenar_plataformas_campanha_para_select(plataformas):
    """Agrupa por categoria (ordem canônica) e, dentro dela, por índice/descrição."""
    ordem = {nome: i for i, nome in enumerate(_ORDEM_CATEGORIA_PLATAFORMA)}
    fallback = len(_ORDEM_CATEGORIA_PLATAFORMA)

    def chave(p):
        cat = (p.get('categoria') or 'Sem categoria').strip() or 'Sem categoria'
        return (
            ordem.get(cat, fallback),
            p.get('indice') if p.get('indice') is not None else 9999,
            (p.get('descricao') or '').lower(),
        )

    return sorted(plataformas, key=chave)
from aicentralv2.services.cotacao_linhas_image_import import (
    extrair_itens_linhas_de_upload,
    normalizar_itens_para_cotacao,
)

bp = Blueprint('cotacoes', __name__)

# Defaults da Proposta CentralComm Programmatic (campos editáveis na cotação).
FREQUENCIA_IMPACTO_DEFAULT = 3

PREMISSAS_DEFAULT = (
    "1 - Para a campanha ir para o Ar precisamos ter dois itens importantes, PI e todos os itens de material.\n"
    "2 - Precisamos ter o termo de aceite da nossa tag instalada em algum lugar no site.\n"
    "3 - Faturamento 15 DFM."
)

OBSERVACOES_GERAIS_DEFAULT = (
    "* A APROVAÇÃO DE MATERIAIS DE 24 HORAS É DE CADA PLATAFORMA/ TECNOLOGIA, NÃO É DE RESPONSABILIDADE DA CENTRALCOMM.\n"
    "* Qualquer ajuste de entrega sobre a campanha, precisa de alteração de PI ou alguma documentação por e-mail.\n"
    "* Envio de PI de 24 horas antes do início da campanha e Material 48 horas para verificação.\n"
    "* Faturamento 15 DFM.\n"
    "Plataforma Programática\n"
    "Obs. 1: A campanha será trabalhada e otimizada para veicular as metas de entrega previstas. Serão esses nossos KPI's e são esses os resultados que buscaremos e apresentaremos ao final da campanha.\n"
    "Obs. 2: Relatórios semanais/ parciais com os dados de campanha, que o cliente desejar, somente sob prévia solicitação\n"
    "Obs. 3: Relatórios de BI das campanhas, terão que ser avisados antes do inicio da campanha e entregues somente de uma semana a quinze dias, após o final da mesma.\n"
    "Obs. 4: Remarketing: Iniciaremos a campanha à partir da criação de uma base de dados criada. O ideal é que seja após 1 mês de campanha."
)

DESCRICAO_ANEXO_PROPOSTA_PDF = 'Proposta CentralComm Programmatic (PDF)'
DESCRICAO_ANEXO_BRIEFING = 'Briefing da campanha'
BRIEFING_EXTENSOES_PERMITIDAS = {'.pdf', '.doc', '.docx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png'}
BRIEFING_MAX_BYTES = 10 * 1024 * 1024


def _upload_dir_cotacoes():
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'cotacoes')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _substituir_anexo_por_descricao(cotacao_id, descricao):
    for anexo in db.obter_anexos_cotacao(cotacao_id):
        if (anexo.get('descricao') or '') == descricao:
            db.deletar_anexo_cotacao(anexo['id'])


def _salvar_bytes_como_anexo_cotacao(cotacao_id, conteudo_bytes, nome_original, mime_type, descricao, uploaded_by):
    nome_seguro = secure_filename(nome_original) or 'arquivo'
    extensao = os.path.splitext(nome_seguro)[1]
    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    upload_dir = _upload_dir_cotacoes()
    arquivo_path = os.path.join(upload_dir, nome_arquivo)
    with open(arquivo_path, 'wb') as f:
        f.write(conteudo_bytes)
    url_arquivo = f"/static/uploads/cotacoes/{nome_arquivo}"
    return db.criar_anexo_cotacao(
        cotacao_id=cotacao_id,
        nome_original=nome_original,
        nome_arquivo=nome_arquivo,
        url_arquivo=url_arquivo,
        mime_type=mime_type,
        tamanho_bytes=len(conteudo_bytes),
        descricao=descricao,
        uploaded_by=uploaded_by,
    )


def _salvar_file_storage_como_anexo_cotacao(cotacao_id, file_storage, descricao, uploaded_by):
    nome_original = secure_filename(file_storage.filename)
    extensao = os.path.splitext(nome_original)[1].lower()
    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    upload_dir = _upload_dir_cotacoes()
    arquivo_path = os.path.join(upload_dir, nome_arquivo)
    file_storage.save(arquivo_path)
    url_arquivo = f"/static/uploads/cotacoes/{nome_arquivo}"
    tamanho_bytes = os.path.getsize(arquivo_path)
    return db.criar_anexo_cotacao(
        cotacao_id=cotacao_id,
        nome_original=nome_original,
        nome_arquivo=nome_arquivo,
        url_arquivo=url_arquivo,
        mime_type=file_storage.content_type,
        tamanho_bytes=tamanho_bytes,
        descricao=descricao,
        uploaded_by=uploaded_by,
    )


@bp.app_context_processor
def _inject_proposta_defaults():
    return {
        'PREMISSAS_DEFAULT': PREMISSAS_DEFAULT,
        'OBSERVACOES_GERAIS_DEFAULT': OBSERVACOES_GERAIS_DEFAULT,
        'FREQUENCIA_IMPACTO_DEFAULT': FREQUENCIA_IMPACTO_DEFAULT,
    }


def _audit(*args, **kwargs):
    from aicentralv2.routes import registrar_auditoria

    return registrar_auditoria(*args, **kwargs)


def _serializar(obj):
    from aicentralv2.routes import serializar_para_json

    return serializar_para_json(obj)


def _json_forbid():
    return jsonify(
        {'success': False, 'message': 'Cotação não pertence ao ambiente de teste de cálculo.'}
    ), 403


def _guard_cotacao_teste(cotacao_id: int):
    # Fluxo oficial: aceita qualquer cotação existente (teste ou não).
    if not db.obter_cotacao_por_id(cotacao_id):
        return jsonify({'success': False, 'message': 'Cotação não encontrada.'}), 404
    return None


def _guard_linha(linha_id: int):
    linha = db.obter_linha_cotacao(linha_id)
    if not linha:
        return jsonify({'success': False, 'message': 'Linha não encontrada'}), 404
    return _guard_cotacao_teste(linha['cotacao_id'])


def _guard_audiencia_cotacao(audiencia_cotacao_id: int):
    aud = db.obter_audiencia_cotacao_por_id(audiencia_cotacao_id)
    if not aud:
        return jsonify({'error': 'Audiência não encontrada'}), 404
    cid = aud.get('cotacao_id')
    return _guard_cotacao_teste(cid)


def _guard_anexo(cotacao_id: int, anexo_id: int):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    anexo = db.obter_anexo_por_id(anexo_id)
    if not anexo or anexo.get('cotacao_id') != cotacao_id:
        return jsonify({'success': False, 'message': 'Anexo não encontrado'}), 404
    return None


def _parse_float_br(val):
    """Interpreta número em pt-BR ou simples (ex.: '1.234,56' ou '15.5')."""
    if val is None:
        return None
    s = str(val).strip().replace(' ', '')
    if not s:
        return None
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def _delegate_app_view(endpoint: str, *args, **kwargs):
    fn = current_app.view_functions.get(endpoint)
    if not fn:
        current_app.logger.error(f"cotacoes_teste_calculo: view %r não registrada", endpoint)
        return jsonify({'success': False, 'message': 'Serviço indisponível'}), 500
    return fn(*args, **kwargs)


def _to_float(val, default=0.0):
    if val is None or val == '':
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        parsed = _parse_float_br(val)
        return parsed if parsed is not None else default


def _perc_margem_cc_fracao_audiencia(cotacao, data):
    """Fração (0–1) para audiência: override válido 5–30%; senão margem cadastrada do cliente."""
    if not cotacao:
        return None
    mcc_arg = data.get('margem_cc') if isinstance(data, dict) else None
    if mcc_arg not in (None, ''):
        v = _parse_float_br(mcc_arg)
        if v is None:
            try:
                v = float(mcc_arg)
            except (TypeError, ValueError):
                v = None
        if v is not None and 5.0 <= float(v) <= 30.0:
            return float(v) / 100.0
    cid = cotacao.get('client_id')
    if cid:
        return db.obter_margem_cc_fracao_por_cliente(cid)
    return None


def _audiencia_calc_meta_para_criacao(data):
    """Plataforma e KPI persistidos na linha audiência (`plataforma` / `objetivo_kpi` como aliases opcionais).

    Retorna (plataforma, kpi_descricao, id_kpi). id_kpi é o `id_audiencia_calculo_kpi`
    (ou `id_objetivo_kpi` como alias) e quando presente passa a ser a verdade canônica.
    """
    if not isinstance(data, dict):
        return None, None, None
    plat = data.get('audiencia_calculo_plataforma')
    if plat is None and 'plataforma' in data:
        plat = data.get('plataforma')
    kpi = data.get('audiencia_calculo_kpi')
    if kpi is None and 'objetivo_kpi' in data:
        kpi = data.get('objetivo_kpi')
    id_kpi = data.get('id_audiencia_calculo_kpi')
    if id_kpi is None:
        id_kpi = data.get('id_objetivo_kpi')
    return plat, kpi, id_kpi


def _audiencia_calc_sentinels_para_atualizar(data):
    """PATCH só inclusão omite meta; atualização envia apenas chaves presentes no JSON.

    Retorna (plataforma_sentinel, kpi_sentinel, id_kpi_sentinel).
    """
    if not isinstance(data, dict):
        return db._OMIT_AUD_CALC_PLATAFORMA, db._OMIT_AUD_CALC_KPI, db._OMIT_AUD_ID_CALC_KPI
    if set(data.keys()) == {'incluido_proposta'}:
        return db._OMIT_AUD_CALC_PLATAFORMA, db._OMIT_AUD_CALC_KPI, db._OMIT_AUD_ID_CALC_KPI
    plat = db._OMIT_AUD_CALC_PLATAFORMA
    kpi = db._OMIT_AUD_CALC_KPI
    id_kpi = db._OMIT_AUD_ID_CALC_KPI
    if 'audiencia_calculo_plataforma' in data or 'plataforma' in data:
        plat = data.get('audiencia_calculo_plataforma')
        if plat is None:
            plat = data.get('plataforma')
    if 'audiencia_calculo_kpi' in data or 'objetivo_kpi' in data:
        kpi = data.get('audiencia_calculo_kpi')
        if kpi is None:
            kpi = data.get('objetivo_kpi')
    if 'id_audiencia_calculo_kpi' in data or 'id_objetivo_kpi' in data:
        id_kpi = data.get('id_audiencia_calculo_kpi')
        if id_kpi is None:
            id_kpi = data.get('id_objetivo_kpi')
    return plat, kpi, id_kpi


def _recalcular_e_montar_breakdown(cotacao, data):
    """Reexecuta `calcular_preco_unitario_teste_calculo` e devolve perc_* e val_* já derivados.

    Retorna `(payload_extra, error_response, status)`:
      - payload_extra: dict com perc_*, val_*, valor_unitario_negociado, volume_contratado e
        investimento_bruto recalculados.
      - Em caso de erro, payload_extra é None e error_response/status carregam o JSON de erro.
    """
    plat = (data.get('plataforma') or '').strip()
    kpi = (data.get('objetivo_kpi') or '').strip()
    # Quando o front enviar id_objetivo_kpi (FK), resolve a descrição para que a
    # comparação `is_cpm = kpi == 'CPM'` mais abaixo permaneça correta.
    id_kpi_in = data.get('id_objetivo_kpi') or data.get('id_audiencia_calculo_kpi')
    if id_kpi_in not in (None, '', 0, '0'):
        desc_resolvida = db.obter_descricao_objetivo_campanha(id_kpi_in)
        if desc_resolvida:
            kpi = desc_resolvida
    val_tab = _to_float(data.get('valor_unitario_tabela'))
    inv_bruto_in = _to_float(data.get('investimento_bruto'))
    vol_in = _to_float(data.get('volume_contratado'))
    mcc_arg = data.get('margem_cc')
    mcc_override = _parse_float_br(mcc_arg) if mcc_arg not in (None, '') else None
    fator_raw = data.get('fator_desconto')
    fator_desconto = _to_float(fator_raw) if fator_raw not in (None, '') else 1.0
    if fator_desconto <= 0:
        fator_desconto = 1.0

    if not plat:
        return None, jsonify({'error': 'Informe a plataforma para calcular.'}), 400
    if not kpi:
        return None, jsonify({'error': 'Informe o KPI (Tipo de Compra) para calcular.'}), 400
    if val_tab <= 0:
        return None, jsonify({'error': 'Valor unitário tabela inválido.'}), 400
    if inv_bruto_in <= 0 and vol_in <= 0:
        return None, jsonify({
            'error': 'Preencha Invest. Bruto ou Vol. Contratado.'
        }), 400

    imp_pct = float(current_app.config.get('PI_IMPOSTO_PERCENTUAL', 15))

    out = db.calcular_preco_unitario_teste_calculo(
        valor_unitario_tabela=val_tab,
        nome_plataforma=plat,
        cliente_id=cotacao.get('client_id'),
        id_resp_comercial=cotacao.get('responsavel_comercial'),
        volume_contratado=vol_in,
        imposto_percentual_externo=imp_pct,
        agencia_id=cotacao.get('agencia_id'),
        margem_cc_override=mcc_override,
        fator_desconto=fator_desconto,
    )
    if not out.get('success'):
        return None, jsonify({'error': out.get('message') or 'Falha no cálculo do preço.'}), 400

    preco_unit = float(out.get('preco_unit') or 0.0)
    opex_unit = float(out.get('opex_unit') or 0.0)
    if preco_unit <= 0:
        return None, jsonify({'error': 'Preço unitário inválido após cálculo.'}), 400

    is_cpm = kpi == 'CPM'

    if inv_bruto_in > 0 and vol_in > 0:
        # Caminho de save: ambos vieram preenchidos do front (um digitado, outro derivado
        # pelo `derivarValorPendente`). Confiamos nos valores e calculamos volume_efetivo
        # a partir do volume_contratado para manter consistência com a base CPM.
        volume_contratado = vol_in
        volume_efetivo = (volume_contratado / 1000.0) if is_cpm else volume_contratado
        invest_bruto = inv_bruto_in
    elif vol_in > 0:
        volume_contratado = vol_in
        volume_efetivo = (volume_contratado / 1000.0) if is_cpm else volume_contratado
        invest_bruto = volume_efetivo * preco_unit
    else:
        invest_bruto = inv_bruto_in
        volume_efetivo = invest_bruto / preco_unit
        volume_contratado = round(volume_efetivo * 1000.0) if is_cpm else round(volume_efetivo)
        volume_efetivo = (volume_contratado / 1000.0) if is_cpm else float(volume_contratado)
        invest_bruto = volume_efetivo * preco_unit

    tf = float(out.get('tf') or 0.0)
    mcc = float(out.get('mcc') or 0.0)
    com = float(out.get('com') or 0.0)
    inc = float(out.get('inc') or 0.0)
    imp = float(out.get('imp') or 0.0)

    val_tech_fee = max(opex_unit - val_tab * fator_desconto, 0.0) * volume_efetivo
    val_margem_cc = invest_bruto * mcc
    val_com_vendas = invest_bruto * com
    val_pl_incentivos = invest_bruto * inc
    val_impostos = invest_bruto * imp

    payload_extra = {
        'perc_tech_fee': tf,
        'perc_margem_cc': mcc,
        'perc_com_vendas': com,
        'perc_pl_incentivos': inc,
        'perc_impostos': imp,
        'val_tech_fee': round(val_tech_fee, 2),
        'val_margem_cc': round(val_margem_cc, 2),
        'val_com_vendas': round(val_com_vendas, 2),
        'val_pl_incentivos': round(val_pl_incentivos, 2),
        'val_impostos': round(val_impostos, 2),
        'valor_unitario_negociado': round(preco_unit, 6),
        'valor_unitario': round(preco_unit, 6),
        'volume_contratado': int(volume_contratado),
        'investimento_bruto': round(invest_bruto, 2),
        'fator_desconto': fator_desconto,
    }
    return payload_extra, None, None


# --- HTML ---


@bp.route('/cotacoes')
@login_required
def cotacoes_list():
    try:
        db.criar_tabela_cotacoes()
        cliente_id = request.args.get('cliente_id', type=int)
        responsavel_id = request.args.get('responsavel_comercial', type=int)
        mes = request.args.get('mes')
        busca = request.args.get('busca', '').strip()
        status = request.args.get('status', 'Enviada')
        if status == 'TODOS':
            status = None

        cliente_info = None
        if cliente_id:
            conn = db.get_db()
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT id_cliente, nome_fantasia, razao_social FROM tbl_cliente WHERE id_cliente = %s',
                    (cliente_id,),
                )
                cliente_info = cursor.fetchone()

        cotacoes = db.obter_cotacoes_filtradas(
            cliente_id=cliente_id,
            responsavel_id=responsavel_id,
            mes=mes,
            busca=busca,
            status=status,
            excluir_teste_calculo=False,
            apenas_teste_calculo=False,
        )
        vendedores = db.obter_vendedores_centralcomm()
        return render_template(
            'cadu_cotacoes.html',
            cotacoes=cotacoes or [],
            cliente_filtro=cliente_info,
            vendedores=vendedores,
            now=datetime.now,
        )
    except Exception as e:
        current_app.logger.error(f"cotacoes_list: {e}", exc_info=True)
        flash('Erro ao carregar cotações.', 'error')
        vendedores = db.obter_vendedores_centralcomm()
        return render_template(
            'cadu_cotacoes.html',
            cotacoes=[],
            cliente_filtro=None,
            vendedores=vendedores,
            now=datetime.now,
        )


@bp.route('/cotacoes/nova', methods=['GET', 'POST'])
@login_required
def cotacao_nova():
    if request.method == 'POST':
        try:
            client_id = request.form.get('client_id', type=int)
            nome_campanha = request.form.get('nome_campanha', '').strip()
            periodo_inicio = request.form.get('periodo_inicio', '').strip()
            valor_total_str = request.form.get('valor_total_proposta') or request.form.get(
                'valor_total_proposta_display', '0'
            )

            if not client_id or not nome_campanha or not periodo_inicio or not valor_total_str:
                flash('Cliente, nome da campanha, data de início e valor total são obrigatórios.', 'error')
                clientes = db.obter_clientes_simples()
                vendedores = db.obter_vendedores_centralcomm()
                return render_template(
                    'cadu_cotacoes_form.html',
                    clientes=clientes,
                    vendedores=vendedores,
                    modo='novo',
                    tipos_cliente=db.obter_tipos_cliente(),
                    agencias_opts=db.obter_aux_agencia(),
                    vendedores_cc=db.obter_vendedores_centralcomm(),
                    estados=db.obter_estados(),
                )

            valor_total = float(valor_total_str) if valor_total_str else 0.0

            kwargs = {
                'objetivo_campanha': request.form.get('objetivo_campanha', '').strip(),
                'apresentacao_dados': request.form.get('apresentacao_dados', '').strip() or None,
                'periodo_fim': request.form.get('periodo_fim', '').strip() or None,
                'status': request.form.get('status', 'Rascunho').strip(),
                'responsavel_comercial': request.form.get('responsavel_comercial', type=int),
                'briefing_id': request.form.get('briefing_id', type=int)
                if request.form.get('briefing_id')
                else None,
                'budget_estimado': float(request.form.get('budget_estimado', '0') or 0)
                if request.form.get('budget_estimado')
                else None,
                'frequencia_impacto': request.form.get('frequencia_impacto', type=int) or FREQUENCIA_IMPACTO_DEFAULT,
                'premissas': request.form.get('premissas', '').strip() or PREMISSAS_DEFAULT,
                'observacoes_gerais': request.form.get('observacoes_gerais', '').strip() or OBSERVACOES_GERAIS_DEFAULT,
                'origem': request.form.get('origem', '').strip(),
                'link_publico_ativo': 'link_publico_ativo' in request.form,
                'link_publico_token': request.form.get('link_publico_token', '').strip(),
                'link_publico_expires_at': request.form.get('link_publico_expires_at', '').strip() or None,
                'agencia_id': request.form.get('agencia_id', type=int)
                if request.form.get('agencia_id')
                else None,
                'agencia_user_id': request.form.get('agencia_user_id', type=int)
                if request.form.get('agencia_user_id')
                else None,
                'id_parceiro': request.form.get('id_parceiro', type=int)
                if request.form.get('id_parceiro')
                else None,
                'parceiro_user_id': request.form.get('parceiro_user_id', type=int)
                if request.form.get('parceiro_user_id')
                else None,
            }
            kwargs = {k: v for k, v in kwargs.items() if v is not None and v != ''}

            resultado = db.criar_cotacao(
                client_id=client_id,
                nome_campanha=nome_campanha,
                periodo_inicio=periodo_inicio,
                valor_total_proposta=valor_total,
                **kwargs,
            )

            cotacao_id = resultado['id']
            briefing_arquivo = request.files.get('briefing_arquivo')
            if briefing_arquivo and briefing_arquivo.filename:
                nome_original = secure_filename(briefing_arquivo.filename)
                extensao = os.path.splitext(nome_original)[1].lower()
                if extensao not in BRIEFING_EXTENSOES_PERMITIDAS:
                    flash('Formato de briefing não permitido. Use PDF, DOC, PPT, JPG ou PNG.', 'error')
                else:
                    briefing_arquivo.seek(0, os.SEEK_END)
                    tamanho = briefing_arquivo.tell()
                    briefing_arquivo.seek(0)
                    if tamanho > BRIEFING_MAX_BYTES:
                        flash('Briefing excede o limite de 10MB e não foi anexado.', 'error')
                    else:
                        anexo_id = _salvar_file_storage_como_anexo_cotacao(
                            cotacao_id,
                            briefing_arquivo,
                            DESCRICAO_ANEXO_BRIEFING,
                            session.get('user_id'),
                        )
                        _audit(
                            acao='CREATE',
                            modulo='cotacoes_anexos',
                            descricao=f'Briefing cotação {cotacao_id}: {nome_original}',
                            registro_id=anexo_id,
                            registro_tipo='cadu_cotacao_anexos',
                        )

            _audit(
                acao='INSERT',
                modulo='cotacoes',
                descricao=f'Cotação criada: {resultado["numero_cotacao"]}',
                registro_id=resultado['id'],
                registro_tipo='cadu_cotacoes',
                dados_novos={'nome_campanha': nome_campanha, 'origem': request.form.get('origem', '').strip()},
            )

            flash(f'Cotação {resultado["numero_cotacao"]} criada com sucesso!', 'success')
            return redirect(url_for('cotacoes.cotacao_detalhes', cotacao_id=resultado['id']))

        except Exception as e:
            current_app.logger.error(f"cotacao_nova POST: {e}", exc_info=True)
            flash(f'Erro ao criar cotação: {str(e)}', 'error')
            clientes = db.obter_clientes_simples()
            vendedores = db.obter_vendedores_centralcomm()
            return render_template(
                'cadu_cotacoes_form.html',
                clientes=clientes,
                vendedores=vendedores,
                modo='novo',
                tipos_cliente=db.obter_tipos_cliente(),
                agencias_opts=db.obter_aux_agencia(),
                vendedores_cc=db.obter_vendedores_centralcomm(),
                estados=db.obter_estados(),
            )

    clientes = db.obter_clientes_simples()
    vendedores = db.obter_vendedores_centralcomm()
    cliente_selecionado = None
    briefings = []
    cliente_id_url = request.args.get('cliente_id', type=int)
    if cliente_id_url:
        cliente_selecionado = cliente_id_url
        briefings = db.obter_briefings_por_cliente(cliente_id_url)

    return render_template(
        'cadu_cotacoes_form.html',
        clientes=clientes,
        vendedores=vendedores,
        briefings=briefings,
        modo='novo',
        cliente_selecionado=cliente_selecionado,
        tipos_cliente=db.obter_tipos_cliente(),
        agencias_opts=db.obter_aux_agencia(),
        vendedores_cc=db.obter_vendedores_centralcomm(),
        estados=db.obter_estados(),
    )


@bp.route('/cotacoes/<int:cotacao_id>/editar', methods=['GET', 'POST'])
@login_required
def cotacao_editar(cotacao_id):
    try:
        cotacao = db.obter_cotacao_por_id(cotacao_id)
        if not cotacao:
            flash('Cotação não encontrada.', 'error')
            return redirect(url_for('cotacoes.cotacoes_list'))

        if request.method == 'POST':
            nome_campanha = request.form.get('nome_campanha', '').strip()
            periodo_inicio = request.form.get('periodo_inicio', '').strip()
            valor_total_str = request.form.get('valor_total_proposta') or request.form.get(
                'valor_total_proposta_display', '0'
            )

            if not nome_campanha or not periodo_inicio or not valor_total_str:
                flash('Nome da campanha, data de início e valor total são obrigatórios.', 'error')
                clientes = db.obter_clientes_simples()
                vendedores = db.obter_vendedores_centralcomm()
                return render_template(
                    'cadu_cotacoes_form.html',
                    cotacao=cotacao,
                    clientes=clientes,
                    vendedores=vendedores,
                    modo='editar',
                    tipos_cliente=db.obter_tipos_cliente(),
                    agencias_opts=db.obter_aux_agencia(),
                    vendedores_cc=db.obter_vendedores_centralcomm(),
                    estados=db.obter_estados(),
                )

            valor_total = float(valor_total_str) if valor_total_str else 0.0

            update_kwargs = {
                'nome_campanha': nome_campanha,
                'periodo_inicio': periodo_inicio,
                'valor_total_proposta': valor_total,
                'objetivo_campanha': request.form.get('objetivo_campanha', '').strip(),
                'periodo_fim': request.form.get('periodo_fim', '').strip() or None,
                'responsavel_comercial': request.form.get('responsavel_comercial', type=int),
                'client_user_id': request.form.get('client_user_id', type=int)
                if request.form.get('client_user_id')
                else None,
                'briefing_id': request.form.get('briefing_id', type=int)
                if request.form.get('briefing_id')
                else None,
                'agencia_id': request.form.get('agencia_id', type=int)
                if request.form.get('agencia_id')
                else None,
                'agencia_user_id': request.form.get('agencia_user_id', type=int)
                if request.form.get('agencia_user_id')
                else None,
                'id_parceiro': request.form.get('id_parceiro', type=int)
                if request.form.get('id_parceiro')
                else None,
                'parceiro_user_id': request.form.get('parceiro_user_id', type=int)
                if request.form.get('parceiro_user_id')
                else None,
                'budget_estimado': float(request.form.get('budget_estimado', '0') or 0)
                if request.form.get('budget_estimado')
                else None,
                'observacoes': request.form.get('observacoes', '').strip(),
                'observacoes_internas': request.form.get('observacoes_internas', '').strip(),
                'frequencia_impacto': request.form.get('frequencia_impacto', type=int),
                'premissas': request.form.get('premissas', '').strip(),
                'observacoes_gerais': request.form.get('observacoes_gerais', '').strip(),
                'link_publico_ativo': 'link_publico_ativo' in request.form,
                'link_publico_token': request.form.get('link_publico_token', '').strip(),
                'link_publico_expires_at': request.form.get('link_publico_expires_at', '').strip() or None,
            }
            update_kwargs = {k: v for k, v in update_kwargs.items() if v is not None and v != ''}

            # Status não é alterável pelo formulário de edição (somente na tela de detalhes).
            db.atualizar_cotacao(cotacao_id=cotacao_id, **update_kwargs)

            flash('Cotação atualizada com sucesso!', 'success')

            _audit(
                acao='UPDATE',
                modulo='cotacoes',
                descricao=f'Cotação atualizada: {cotacao["numero_cotacao"]}',
                registro_id=cotacao_id,
                registro_tipo='cadu_cotacoes',
                dados_anteriores={
                    'nome_campanha': cotacao.get('nome_campanha'),
                    'valor_total_proposta': cotacao.get('valor_total_proposta'),
                },
                dados_novos={'nome_campanha': nome_campanha, 'valor_total_proposta': valor_total},
            )

            return redirect(url_for('cotacoes.cotacao_detalhes', cotacao_id=cotacao_id))

        clientes = db.obter_clientes_simples()
        vendedores = db.obter_vendedores_centralcomm()
        briefings = []
        contatos_cliente = []
        contatos_agencia = []
        contatos_parceiro = []
        if cotacao.get('client_id'):
            briefings = db.obter_briefings_por_cliente(cotacao['client_id'])
            contatos_cliente = db.obter_contatos_comerciais_por_cliente(cotacao['client_id'])
        if cotacao.get('agencia_id'):
            contatos_agencia = db.obter_contatos_por_cliente(cotacao['agencia_id'])
        if cotacao.get('id_parceiro'):
            contatos_parceiro = db.obter_contatos_por_cliente(cotacao['id_parceiro'])

        return render_template(
            'cadu_cotacoes_form.html',
            cotacao=cotacao,
            clientes=clientes,
            vendedores=vendedores,
            briefings=briefings,
            contatos_cliente=contatos_cliente,
            contatos_agencia=contatos_agencia,
            contatos_parceiro=contatos_parceiro,
            modo='editar',
            tipos_cliente=db.obter_tipos_cliente(),
            agencias_opts=db.obter_aux_agencia(),
            vendedores_cc=db.obter_vendedores_centralcomm(),
            estados=db.obter_estados(),
        )

    except Exception as e:
        current_app.logger.error(f"cotacao_editar: {e}", exc_info=True)
        flash(f'Erro ao editar cotação: {str(e)}', 'error')
        return redirect(url_for('cotacoes.cotacoes_list'))


@bp.route('/cotacoes/<int:cotacao_id>/detalhes', methods=['GET', 'POST'])
@login_required
def cotacao_detalhes(cotacao_id):
    try:
        cotacao = db.obter_cotacao_por_id(cotacao_id)
        if not cotacao:
            flash('Cotação não encontrada.', 'error')
            return redirect(url_for('cotacoes.cotacoes_list'))

        if request.method == 'POST':
            try:
                resp_comercial = request.form.get('responsavel_comercial')
                client_user_id_raw = request.form.get('client_user_id')
                client_user_id = (
                    int(client_user_id_raw) if client_user_id_raw and client_user_id_raw.strip() else None
                )

                periodo_fim = request.form.get('periodo_fim')
                periodo_fim = periodo_fim if periodo_fim and periodo_fim.strip() else None

                expires_at = request.form.get('expires_at')
                expires_at = expires_at if expires_at and expires_at.strip() else None

                dados = {
                    'client_id': request.form.get('client_id'),
                    'nome_campanha': request.form.get('nome_campanha'),
                    'responsavel_comercial': resp_comercial if resp_comercial and resp_comercial.strip() else None,
                    'client_user_id': client_user_id,
                    'briefing_id': request.form.get('briefing_id') if request.form.get('briefing_id') else None,
                    'objetivo_campanha': request.form.get('objetivo_campanha'),
                    'periodo_inicio': request.form.get('periodo_inicio'),
                    'periodo_fim': periodo_fim,
                    'expires_at': expires_at,
                    'budget_estimado': request.form.get('budget_estimado'),
                    'valor_total_proposta': request.form.get('valor_total_proposta'),
                    'status': request.form.get('status'),
                    'observacoes': request.form.get('observacoes'),
                    'observacoes_internas': request.form.get('observacoes_internas'),
                    'frequencia_impacto': request.form.get('frequencia_impacto', type=int),
                    'premissas': request.form.get('premissas'),
                    'observacoes_gerais': request.form.get('observacoes_gerais'),
                    'desconto_total': request.form.get('desconto_total'),
                    'condicoes_comerciais': request.form.get('condicoes_comerciais'),
                }

                novo_status = dados.get('status')
                status_anterior = cotacao.get('status') if cotacao else None
                if novo_status == 'Aprovada' and status_anterior != 'Aprovada':
                    dados['aprovada_em'] = datetime.now()

                db.atualizar_cotacao(cotacao_id, **dados)
                flash('Cotação de teste atualizada (PI não é gerado neste ambiente).', 'success')
                return redirect(url_for('cotacoes.cotacao_detalhes', cotacao_id=cotacao_id))

            except Exception as e:
                current_app.logger.error(f"POST detalhes teste: {e}", exc_info=True)
                flash('Erro ao atualizar cotação.', 'error')

        cotacao = db.obter_cotacao_por_id(cotacao_id)
        clientes = db.obter_clientes_simples()
        vendedores = db.obter_vendedores_centralcomm()
        cliente = None
        if cotacao.get('client_id'):
            cliente = db.obter_cliente_por_id(cotacao['client_id'])

        contatos_cliente = []
        contatos_agencia = []
        contatos_parceiro = []
        briefings = []
        briefing_atual = None
        if cotacao.get('client_id'):
            contatos_cliente = db.obter_contatos_comerciais_por_cliente(cotacao['client_id'])
            briefings = db.obter_briefings_por_cliente(cotacao['client_id'])
        if cotacao.get('agencia_id'):
            contatos_agencia = db.obter_contatos_por_cliente(cotacao['agencia_id'])
        if cotacao.get('id_parceiro'):
            contatos_parceiro = db.obter_contatos_por_cliente(cotacao['id_parceiro'])
        if cotacao.get('briefing_id'):
            briefing_atual = db.obter_briefing_por_id(cotacao['briefing_id'])

        linhas = db.obter_linhas_cotacao(cotacao_id)
        audiencias = db.obter_audiencias_cotacao(cotacao_id)
        comentarios = db.obter_comentarios_cotacao(cotacao_id)
        plataformas_campanha = []
        for p in db.obter_plataformas_campanha():
            if p.get('status', True) is False:
                continue
            cat = (p.get('categoria') or '').strip()
            p['categoria'] = cat if cat else 'Sem categoria'
            plataformas_campanha.append(p)
        plataformas_campanha = _ordenar_plataformas_campanha_para_select(plataformas_campanha)

        objetivos_campanha = [
            obj for obj in db.obter_objetivos_campanha()
            if obj.get('status', True) is not False
        ]

        return render_template(
            'cadu_cotacoes_detalhes.html',
            modo='editar',
            cotacao=cotacao,
            cliente=cliente,
            clientes=clientes,
            vendedores=vendedores,
            contatos_cliente=contatos_cliente,
            contatos_agencia=contatos_agencia,
            contatos_parceiro=contatos_parceiro,
            briefings=briefings,
            briefing_atual=briefing_atual,
            linhas=linhas,
            audiencias=audiencias,
            comentarios=comentarios,
            plataformas_campanha=plataformas_campanha,
            objetivos_campanha=objetivos_campanha,
        )

    except Exception as e:
        current_app.logger.error(f"cotacao_detalhes: {e}", exc_info=True)
        flash('Erro ao carregar cotação.', 'error')
        return redirect(url_for('cotacoes.cotacoes_list'))


@bp.route('/cotacoes/<int:cotacao_id>/proposta-pdf')
@login_required
def cotacao_proposta_pdf(cotacao_id):
    """Gera e retorna o PDF da Proposta CentralComm Programmatic da cotação."""
    from flask import make_response
    from aicentralv2.services.proposta_pdf import gerar_proposta_programmatic_pdf

    try:
        if not db.obter_cotacao_por_id(cotacao_id):
            flash('Cotação não encontrada.', 'error')
            return redirect(url_for('cotacoes.cotacoes_list'))

        pdf_bytes, filename = gerar_proposta_programmatic_pdf(cotacao_id)

        nome_personalizado = (request.args.get('nome') or '').strip()
        if nome_personalizado:
            base = secure_filename(os.path.splitext(nome_personalizado)[0]) or os.path.splitext(filename)[0]
            filename = f"{base}.pdf"

        baixar = request.args.get('download') in ('1', 'true', 'sim')

        _substituir_anexo_por_descricao(cotacao_id, DESCRICAO_ANEXO_PROPOSTA_PDF)
        anexo_id = _salvar_bytes_como_anexo_cotacao(
            cotacao_id,
            pdf_bytes,
            filename,
            'application/pdf',
            DESCRICAO_ANEXO_PROPOSTA_PDF,
            session.get('user_id'),
        )
        _audit(
            acao='CREATE',
            modulo='cotacoes_anexos',
            descricao=f'Proposta PDF cotação {cotacao_id}: {filename}',
            registro_id=anexo_id,
            registro_tipo='cadu_cotacao_anexos',
        )

        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        disposicao = 'attachment' if baixar else 'inline'
        response.headers['Content-Disposition'] = f'{disposicao}; filename="{filename}"'
        return response
    except Exception as e:
        current_app.logger.error(f"cotacao_proposta_pdf: {e}", exc_info=True)
        flash(f'Erro ao gerar proposta em PDF: {e}', 'error')
        return redirect(url_for('cotacoes.cotacao_detalhes', cotacao_id=cotacao_id))


# --- API ---


@bp.route('/api/cotacoes/<int:cotacao_id>/preco-calculo', methods=['GET'])
@login_required
def api_preco_calculo_cotacao_teste(cotacao_id):
    """Opex e preço unitário (TF, Mcc, COM, Inc, Imp) para linha com plataforma + val. tabela."""
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        plat = (request.args.get('plataforma') or '').strip()
        if not plat:
            return jsonify({'success': False, 'message': 'Informe a plataforma.'}), 400

        val_tab = _parse_float_br(request.args.get('valor_unitario_tabela'))
        if val_tab is None or val_tab <= 0:
            return jsonify({'success': False, 'message': 'Valor unitário tabela inválido.'}), 400

        vol = _parse_float_br(request.args.get('volume_contratado'))
        if vol is None:
            vol = 0.0

        cotacao = db.obter_cotacao_por_id(cotacao_id)
        if not cotacao:
            return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404

        imp = float(current_app.config.get('PI_IMPOSTO_PERCENTUAL', 15))

        mcc_arg = request.args.get('margem_cc')
        mcc_override = _parse_float_br(mcc_arg) if mcc_arg not in (None, '') else None

        fator_arg = request.args.get('fator_desconto')
        fator_desconto = _parse_float_br(fator_arg) if fator_arg not in (None, '') else 1.0
        if fator_desconto is None or fator_desconto <= 0:
            fator_desconto = 1.0

        out = db.calcular_preco_unitario_teste_calculo(
            valor_unitario_tabela=val_tab,
            nome_plataforma=plat,
            cliente_id=cotacao.get('client_id'),
            id_resp_comercial=cotacao.get('responsavel_comercial'),
            volume_contratado=vol,
            imposto_percentual_externo=imp,
            agencia_id=cotacao.get('agencia_id'),
            margem_cc_override=mcc_override,
            fator_desconto=fator_desconto,
        )
        if not out.get('success'):
            return jsonify(out), 400
        body = {'success': True, **_serializar(out)}
        return jsonify(body)
    except Exception as e:
        current_app.logger.error(f"api_preco_calculo_cotacao_teste: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/atualizar', methods=['PATCH'])
@login_required
def api_atualizar_cotacao_teste(cotacao_id):
    try:
        err = _guard_cotacao_teste(cotacao_id)
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Nenhum dado fornecido'}), 400

        cotacao = db.obter_cotacao_por_id(cotacao_id)
        if not cotacao:
            return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404

        dados_anteriores = {}
        dados_novos = {}

        campos_permitidos = [
            'nome_campanha',
            'objetivo_campanha',
            'responsavel_comercial',
            'periodo_inicio',
            'periodo_fim',
            'expires_at',
            'budget_estimado',
            'valor_total_proposta',
            'desconto_percentual',
            'desconto_total',
            'briefing_id',
            'client_id',
            'client_user_id',
            'agencia_id',
            'agencia_user_id',
            'id_parceiro',
            'parceiro_user_id',
            'observacoes',
            'observacoes_internas',
            'frequencia_impacto',
            'premissas',
            'observacoes_gerais',
            'origem',
            'condicoes_comerciais',
            'status',
            'link_publico_ativo',
            'link_publico_token',
            'link_publico_expires_at',
            'aprovada_em',
        ]

        campos_data = ['periodo_inicio', 'periodo_fim', 'expires_at', 'link_publico_expires_at', 'aprovada_em']

        update_data = {}
        for campo in campos_permitidos:
            if campo in data:
                valor_novo = data[campo]
                valor_anterior = cotacao.get(campo)
                if campo in campos_data:
                    valor_anterior_str = str(valor_anterior) if valor_anterior else None
                    valor_novo_str = valor_novo if valor_novo else None
                    if valor_anterior_str != valor_novo_str:
                        update_data[campo] = valor_novo
                        dados_anteriores[campo] = valor_anterior_str
                        dados_novos[campo] = valor_novo_str
                elif valor_anterior != valor_novo:
                    update_data[campo] = valor_novo
                    dados_anteriores[campo] = valor_anterior
                    dados_novos[campo] = valor_novo

        # Origem é imutável por esta API: preserva o tipo da cotação (normal ou teste).
        update_data.pop('origem', None)
        dados_anteriores.pop('origem', None)
        dados_novos.pop('origem', None)

        if not update_data:
            return jsonify({'success': True, 'message': 'Nenhuma alteração necessária'})

        # Cotações aprovadas têm o status travado: ninguém pode alterá-lo após a aprovação.
        if cotacao.get('status') == 'Aprovada' and 'status' in update_data:
            return jsonify({
                'success': False,
                'message': 'Cotação aprovada: o status não pode ser alterado.',
            }), 409

        codigo_pi_cc = (data.get('codigo_pi_cc') or '').strip() or None
        if update_data.get('status') == 'Aprovada' and cotacao.get('status') != 'Aprovada':
            if not codigo_pi_cc:
                return jsonify({
                    'success': False,
                    'message': 'Informe o código PI CC para aprovar e gerar o PI.',
                }), 400

        db.atualizar_cotacao(cotacao_id=cotacao_id, **update_data)

        id_pi_gerado = None
        status_anterior = cotacao.get('status')
        if update_data.get('status') == 'Aprovada' and status_anterior != 'Aprovada':
            try:
                id_pi_gerado = db.gerar_pi_de_cotacao(cotacao_id, codigo_pi_cc=codigo_pi_cc)
                if id_pi_gerado:
                    current_app.logger.info(
                        f"PI {id_pi_gerado} gerado automaticamente para cotação teste {cotacao_id}"
                    )
                    from aicentralv2.services.pi_make_webhooks import (
                        PiMakeWebhookError,
                        executar_fluxo_producao_completo,
                    )

                    try:
                        executar_fluxo_producao_completo(id_pi_gerado)
                    except PiMakeWebhookError as wh_err:
                        current_app.logger.error(
                            f"Rollback PI teste {id_pi_gerado} após falha Make: {wh_err}",
                            exc_info=True,
                        )
                        try:
                            db.excluir_campanhas_pi_por_id_pi(id_pi_gerado)
                            db.excluir_cadu_pi(id_pi_gerado)
                        except Exception as rollback_err:
                            current_app.logger.error(
                                f"Erro no rollback do PI {id_pi_gerado}: {rollback_err}",
                                exc_info=True,
                            )
                        db.atualizar_cotacao(
                            cotacao_id=cotacao_id,
                            status=status_anterior,
                            aprovada_em=None,
                        )
                        return jsonify({
                            'success': False,
                            'message': f'Erro ao enviar PI para operação: {wh_err}',
                        }), 500
            except Exception as pi_err:
                current_app.logger.error(
                    f"Erro ao gerar PI da cotação teste {cotacao_id}: {pi_err}",
                    exc_info=True,
                )
                db.atualizar_cotacao(
                    cotacao_id=cotacao_id,
                    status=status_anterior,
                    aprovada_em=None,
                )
                return jsonify({
                    'success': False,
                    'message': f'Erro ao gerar PI: {pi_err}',
                }), 500

        _audit(
            acao='UPDATE',
            modulo='cotacoes_teste_calculo',
            descricao=f'Cotação teste atualizada (API): {cotacao["numero_cotacao"]}',
            registro_id=cotacao_id,
            registro_tipo='cadu_cotacoes',
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
        )

        response_data = {'success': True, 'message': 'Cotação atualizada com sucesso'}
        if id_pi_gerado:
            response_data['id_pi'] = id_pi_gerado
            response_data['message'] = (
                f'Cotação aprovada, PI #{id_pi_gerado} gerado e enviado para operação'
            )
        return jsonify(response_data)

    except Exception as e:
        current_app.logger.error(f"api_atualizar_cotacao_teste: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/enviar-email', methods=['POST'])
@login_required
def enviar_email_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    return _delegate_app_view('enviar_email_cotacao', cotacao_id)


@bp.route('/api/cotacoes/<int:cotacao_id>/enviar-email-tipo', methods=['POST'])
@login_required
def enviar_email_cotacao_por_tipo_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    return _delegate_app_view('enviar_email_cotacao_por_tipo', cotacao_id)


@bp.route('/api/cotacoes/<int:cotacao_id>/duplicar', methods=['POST'])
@login_required
def duplicar_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    resp = _delegate_app_view('duplicar_cotacao', cotacao_id)
    try:
        r = resp
        if isinstance(resp, tuple) and resp:
            r = resp[0]
        if hasattr(r, 'get_json'):
            body = r.get_json(silent=True)
            nid = body and body.get('nova_cotacao_id')
            if nid:
                db.atualizar_cotacao(nid, origem=db.ORIGEM_TESTE_CALCULO)
    except Exception as ex:
        current_app.logger.warning(f"duplicar_cotacao_teste pós-ajuste origem: {ex}")
    return resp


@bp.route('/api/cotacoes/<int:cotacao_id>/linhas/extrair-imagem', methods=['POST'])
@login_required
def extrair_linhas_cotacao_de_imagem_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err

    _MAX_BYTES = 12 * 1024 * 1024
    _ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.pdf'}
    try:
        f = request.files.get('imagem')
        if not f or not getattr(f, 'filename', None):
            return jsonify({'success': False, 'error': 'Envie um arquivo (campo "imagem"): imagem ou PDF.'}), 400

        name = (f.filename or '').lower()
        ext = os.path.splitext(name)[1]
        if ext not in _ALLOWED_EXT:
            return jsonify({'success': False, 'error': 'Formato não suportado. Use PNG, JPEG, WebP, GIF ou PDF.'}), 400

        data = f.read()
        if not data:
            return jsonify({'success': False, 'error': 'Arquivo vazio.'}), 400
        if len(data) > _MAX_BYTES:
            return jsonify({'success': False, 'error': 'Arquivo muito grande (máx. 12 MB).'}), 400

        model = (request.form.get('model') or '').strip() or None
        itens, err_msg = extrair_itens_linhas_de_upload(data, ext, filename=f.filename, model=model)
        if err_msg:
            return jsonify({'success': False, 'error': err_msg, 'itens': []}), 422
        if itens:
            try:
                itens = normalizar_itens_para_cotacao(itens)
            except Exception as ex:
                current_app.logger.warning(
                    f"normalizar_itens_para_cotacao (teste) falhou: {ex}", exc_info=True
                )
        return jsonify({'success': True, 'itens': _serializar(itens), 'n': len(itens)})
    except RuntimeError as e:
        current_app.logger.warning(f"extrair_linhas_cotacao_de_imagem_teste: {e}")
        return jsonify({'success': False, 'error': str(e)}), 503
    except Exception as e:
        current_app.logger.error(f"extrair_linhas_cotacao_de_imagem_teste: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cotacoes/linhas', methods=['POST'])
@login_required
def criar_linha_cotacao_api_teste():
    try:
        data = request.get_json()
        cotacao_id = data.get('cotacao_id')
        if not cotacao_id:
            return jsonify({'error': 'cotacao_id é obrigatório'}), 400
        err = _guard_cotacao_teste(int(cotacao_id))
        if err:
            return err

        cotacao = db.obter_cotacao_por_id(int(cotacao_id))
        if not cotacao:
            return jsonify({'error': 'Cotação não encontrada'}), 404

        breakdown, err_resp, err_status = _recalcular_e_montar_breakdown(cotacao, data)
        if err_resp is not None:
            return err_resp, err_status

        linha_id = db.criar_linha_cotacao(
            cotacao_id=cotacao_id,
            pedido_sugestao=data.get('pedido_sugestao'),
            target=data.get('target'),
            veiculo=data.get('veiculo'),
            plataforma=data.get('plataforma'),
            produto=data.get('produto'),
            detalhamento=data.get('detalhamento'),
            formato=data.get('formato'),
            formato_compra=data.get('formato_compra'),
            periodo=data.get('periodo'),
            viewability_minimo=data.get('viewability_minimo'),
            volume_contratado=breakdown['volume_contratado'],
            valor_unitario=breakdown['valor_unitario'],
            valor_total=data.get('valor_total'),
            is_header=data.get('is_header', False),
            is_subtotal=data.get('is_subtotal', False),
            subtotal_label=data.get('subtotal_label'),
            meio=data.get('meio'),
            tipo_peca=data.get('tipo_peca'),
            segmentacao=data.get('segmentacao'),
            formatos=data.get('formatos'),
            canal=data.get('canal'),
            objetivo_kpi=data.get('objetivo_kpi'),
            id_objetivo_kpi=data.get('id_objetivo_kpi'),
            data_inicio=data.get('data_inicio'),
            data_fim=data.get('data_fim'),
            investimento_bruto=breakdown['investimento_bruto'],
            especificacoes=data.get('especificacoes'),
            praca=data.get('praca'),
            valor_unitario_tabela=data.get('valor_unitario_tabela'),
            desconto_percentual=data.get('desconto_percentual'),
            valor_unitario_negociado=breakdown['valor_unitario_negociado'],
            investimento_liquido=data.get('investimento_liquido'),
            perc_margem_cc=breakdown['perc_margem_cc'],
            perc_tech_fee=breakdown['perc_tech_fee'],
            perc_com_vendas=breakdown['perc_com_vendas'],
            perc_pl_incentivos=breakdown['perc_pl_incentivos'],
            perc_impostos=breakdown['perc_impostos'],
            val_margem_cc=breakdown['val_margem_cc'],
            val_tech_fee=breakdown['val_tech_fee'],
            val_com_vendas=breakdown['val_com_vendas'],
            val_pl_incentivos=breakdown['val_pl_incentivos'],
            val_impostos=breakdown['val_impostos'],
            fator_desconto=breakdown.get('fator_desconto'),
        )
        return jsonify({'success': True, 'linha_id': linha_id}), 201
    except Exception as e:
        current_app.logger.error(f"criar_linha_cotacao_api_teste: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/linhas/<int:linha_id>', methods=['GET'])
@login_required
def obter_linha_cotacao_api_teste(linha_id):
    err = _guard_linha(linha_id)
    if err:
        return err
    try:
        linha = db.obter_linha_cotacao(linha_id)
        return jsonify({'success': True, 'linha': linha})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/linhas/<int:linha_id>', methods=['PUT'])
@login_required
def atualizar_linha_cotacao_api_teste(linha_id):
    err = _guard_linha(linha_id)
    if err:
        return err
    try:
        data = request.get_json()
        linha = db.obter_linha_cotacao(linha_id)
        if not linha:
            return jsonify({'error': 'Linha não encontrada'}), 404
        cotacao = db.obter_cotacao_por_id(linha['cotacao_id'])
        if not cotacao:
            return jsonify({'error': 'Cotação não encontrada'}), 404

        breakdown, err_resp, err_status = _recalcular_e_montar_breakdown(cotacao, data)
        if err_resp is not None:
            return err_resp, err_status

        db.atualizar_linha_cotacao(
            linha_id=linha_id,
            pedido_sugestao=data.get('pedido_sugestao'),
            target=data.get('target'),
            veiculo=data.get('veiculo'),
            plataforma=data.get('plataforma'),
            produto=data.get('produto'),
            detalhamento=data.get('detalhamento'),
            formato=data.get('formato'),
            formato_compra=data.get('formato_compra'),
            periodo=data.get('periodo'),
            viewability_minimo=data.get('viewability_minimo'),
            volume_contratado=breakdown['volume_contratado'],
            valor_unitario=breakdown['valor_unitario'],
            valor_total=data.get('valor_total'),
            meio=data.get('meio'),
            tipo_peca=data.get('tipo_peca'),
            is_subtotal=data.get('is_subtotal'),
            subtotal_label=data.get('subtotal_label'),
            segmentacao=data.get('segmentacao'),
            formatos=data.get('formatos'),
            canal=data.get('canal'),
            objetivo_kpi=data.get('objetivo_kpi'),
            id_objetivo_kpi=data.get('id_objetivo_kpi'),
            data_inicio=data.get('data_inicio'),
            data_fim=data.get('data_fim'),
            investimento_bruto=breakdown['investimento_bruto'],
            especificacoes=data.get('especificacoes'),
            praca=data.get('praca'),
            valor_unitario_tabela=data.get('valor_unitario_tabela'),
            desconto_percentual=data.get('desconto_percentual'),
            valor_unitario_negociado=breakdown['valor_unitario_negociado'],
            investimento_liquido=data.get('investimento_liquido'),
            perc_margem_cc=breakdown['perc_margem_cc'],
            perc_tech_fee=breakdown['perc_tech_fee'],
            perc_com_vendas=breakdown['perc_com_vendas'],
            perc_pl_incentivos=breakdown['perc_pl_incentivos'],
            perc_impostos=breakdown['perc_impostos'],
            val_margem_cc=breakdown['val_margem_cc'],
            val_tech_fee=breakdown['val_tech_fee'],
            val_com_vendas=breakdown['val_com_vendas'],
            val_pl_incentivos=breakdown['val_pl_incentivos'],
            val_impostos=breakdown['val_impostos'],
            fator_desconto=breakdown.get('fator_desconto'),
        )
        return jsonify({'success': True, 'message': 'Linha atualizada com sucesso'})
    except Exception as e:
        current_app.logger.error(f"atualizar_linha_cotacao_api_teste: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/linhas/<int:linha_id>', methods=['DELETE'])
@login_required
def remover_linha_cotacao_api_teste(linha_id):
    err = _guard_linha(linha_id)
    if err:
        return err
    try:
        db.deletar_linha_cotacao(linha_id)
        return jsonify({'success': True, 'message': 'Linha removida com sucesso'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/linhas/<int:linha_id>/duplicar', methods=['POST'])
@login_required
def duplicar_linha_cotacao_api(linha_id):
    err = _guard_linha(linha_id)
    if err:
        return err
    try:
        nova_id = db.duplicar_linha_cotacao(linha_id)
        if not nova_id:
            return jsonify({'error': 'Linha não encontrada'}), 404
        return jsonify({'success': True, 'message': 'Item duplicado com sucesso', 'linha_id': nova_id})
    except Exception as e:
        current_app.logger.error(f"duplicar_linha_cotacao_api: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/audiencias', methods=['POST'])
@login_required
def criar_audiencia_cotacao_api_teste():
    try:
        data = request.get_json()
        cotacao_id = data.get('cotacao_id')
        audiencia_nome = data.get('audiencia_nome')
        if not cotacao_id or not audiencia_nome:
            return jsonify({'error': 'cotacao_id e audiencia_nome são obrigatórios'}), 400
        err = _guard_cotacao_teste(int(cotacao_id))
        if err:
            return err
        cotacao = db.obter_cotacao_por_id(int(cotacao_id))
        if not cotacao:
            return jsonify({'error': 'Cotação não encontrada'}), 404
        perc_mcc = _perc_margem_cc_fracao_audiencia(cotacao, data)
        aud_plat, aud_kpi, aud_id_kpi = _audiencia_calc_meta_para_criacao(data)

        breakdown, err_resp, err_status = _recalcular_e_montar_breakdown(cotacao, data)
        if err_resp is not None:
            return err_resp, err_status

        investimento_liquido = _to_float(data.get('investimento_liquido'))
        if investimento_liquido <= 0:
            investimento_liquido = breakdown['investimento_bruto']

        audiencia_id = db.adicionar_audiencia_cotacao(
            cotacao_id=cotacao_id,
            audiencia_id=data.get('audiencia_id'),
            audiencia_nome=audiencia_nome,
            audiencia_publico=data.get('audiencia_publico'),
            audiencia_categoria=data.get('audiencia_categoria'),
            audiencia_subcategoria=data.get('audiencia_subcategoria'),
            cpm_estimado=_to_float(data.get('valor_unitario_tabela')) or data.get('cpm_estimado'),
            investimento_sugerido=breakdown['investimento_bruto'],
            impressoes_estimadas=breakdown['volume_contratado'],
            incluido_proposta=data.get('incluido_proposta', True),
            perc_margem_cc=perc_mcc,
            audiencia_calculo_plataforma=aud_plat,
            audiencia_calculo_kpi=aud_kpi,
            id_audiencia_calculo_kpi=aud_id_kpi,
            data_inicio=data.get('data_inicio') or None,
            data_fim=data.get('data_fim') or None,
            fator_desconto=breakdown.get('fator_desconto'),
            perc_tech_fee=breakdown['perc_tech_fee'],
            perc_com_vendas=breakdown['perc_com_vendas'],
            perc_pl_incentivos=breakdown['perc_pl_incentivos'],
            perc_impostos=breakdown['perc_impostos'],
            val_margem_cc=breakdown['val_margem_cc'],
            val_tech_fee=breakdown['val_tech_fee'],
            val_com_vendas=breakdown['val_com_vendas'],
            val_pl_incentivos=breakdown['val_pl_incentivos'],
            val_impostos=breakdown['val_impostos'],
            valor_unitario_tabela=_to_float(data.get('valor_unitario_tabela')),
            valor_unitario=breakdown['valor_unitario'],
            valor_unitario_negociado=breakdown['valor_unitario_negociado'],
            investimento_bruto=breakdown['investimento_bruto'],
            investimento_liquido=investimento_liquido,
            volume_contratado=breakdown['volume_contratado'],
        )
        return jsonify({'success': True, 'audiencia_id': audiencia_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/audiencias/<int:audiencia_id>', methods=['PUT'])
@login_required
def atualizar_audiencia_cotacao_api_teste(audiencia_id):
    err = _guard_audiencia_cotacao(audiencia_id)
    if err:
        return err
    try:
        data = request.get_json() or {}
        audiencia_row = db.obter_audiencia_cotacao_por_id(audiencia_id)
        if not audiencia_row:
            return jsonify({'error': 'Audiência não encontrada'}), 404

        toggle_apenas_inclusao = set(data.keys()) == {'incluido_proposta'}
        perc_margem_cc_kw = {'perc_margem_cc': db._OMIT_PERC_MARGEM_CC_AUDIENCIA}
        breakdown_kw = {}
        cpm_kw = {}
        invest_sug_kw = {}
        impr_est_kw = {}
        fator_kw = {}

        if not toggle_apenas_inclusao:
            cotacao = db.obter_cotacao_por_id(audiencia_row['cotacao_id'])
            perc_margem_cc_kw = {
                'perc_margem_cc': _perc_margem_cc_fracao_audiencia(cotacao, data),
            }

            breakdown, err_resp, err_status = _recalcular_e_montar_breakdown(cotacao, data)
            if err_resp is not None:
                return err_resp, err_status

            investimento_liquido = _to_float(data.get('investimento_liquido'))
            if investimento_liquido <= 0:
                investimento_liquido = breakdown['investimento_bruto']

            breakdown_kw = {
                'perc_tech_fee': breakdown['perc_tech_fee'],
                'perc_com_vendas': breakdown['perc_com_vendas'],
                'perc_pl_incentivos': breakdown['perc_pl_incentivos'],
                'perc_impostos': breakdown['perc_impostos'],
                'val_margem_cc': breakdown['val_margem_cc'],
                'val_tech_fee': breakdown['val_tech_fee'],
                'val_com_vendas': breakdown['val_com_vendas'],
                'val_pl_incentivos': breakdown['val_pl_incentivos'],
                'val_impostos': breakdown['val_impostos'],
                'valor_unitario_tabela': _to_float(data.get('valor_unitario_tabela')),
                'valor_unitario': breakdown['valor_unitario'],
                'valor_unitario_negociado': breakdown['valor_unitario_negociado'],
                'investimento_bruto': breakdown['investimento_bruto'],
                'investimento_liquido': investimento_liquido,
                'volume_contratado': breakdown['volume_contratado'],
            }
            cpm_kw['cpm_estimado'] = (
                _to_float(data.get('valor_unitario_tabela'))
                or data.get('cpm_estimado')
            )
            invest_sug_kw['investimento_sugerido'] = breakdown['investimento_bruto']
            impr_est_kw['impressoes_estimadas'] = breakdown['volume_contratado']
            fator_kw['fator_desconto'] = breakdown.get('fator_desconto') or 1.0
        else:
            if 'cpm_estimado' in data:
                cpm_kw['cpm_estimado'] = data.get('cpm_estimado')
            if 'investimento_sugerido' in data:
                invest_sug_kw['investimento_sugerido'] = data.get('investimento_sugerido')
            if 'impressoes_estimadas' in data:
                impr_est_kw['impressoes_estimadas'] = data.get('impressoes_estimadas')
            if 'fator_desconto' in data:
                fator_val = data.get('fator_desconto')
                try:
                    fator_num = float(fator_val) if fator_val not in (None, '') else 1.0
                except (TypeError, ValueError):
                    fator_num = 1.0
                if fator_num <= 0:
                    fator_num = 1.0
                fator_kw['fator_desconto'] = fator_num

        aud_plat, aud_kpi, aud_id_kpi = _audiencia_calc_sentinels_para_atualizar(data)

        datas_kw = {}
        if 'data_inicio' in data:
            datas_kw['data_inicio'] = data.get('data_inicio') or None
        if 'data_fim' in data:
            datas_kw['data_fim'] = data.get('data_fim') or None

        db.atualizar_audiencia_cotacao(
            audiencia_cotacao_id=audiencia_id,
            incluido_proposta=data.get('incluido_proposta'),
            audiencia_calculo_plataforma=aud_plat,
            audiencia_calculo_kpi=aud_kpi,
            id_audiencia_calculo_kpi=aud_id_kpi,
            **perc_margem_cc_kw,
            **cpm_kw,
            **invest_sug_kw,
            **impr_est_kw,
            **datas_kw,
            **fator_kw,
            **breakdown_kw,
        )
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/audiencias/<int:audiencia_id>', methods=['GET'])
@login_required
def obter_audiencia_cotacao_api_teste(audiencia_id):
    err = _guard_audiencia_cotacao(audiencia_id)
    if err:
        return err
    try:
        audiencia = db.obter_audiencia_cotacao_por_id(audiencia_id)
        payload = _serializar(audiencia)
        if isinstance(payload, dict):
            payload['plataforma'] = payload.get('audiencia_calculo_plataforma')
            payload['objetivo_kpi'] = payload.get('audiencia_calculo_kpi')
            payload['id_objetivo_kpi'] = payload.get('id_audiencia_calculo_kpi')
        return jsonify(payload), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/audiencias/<int:audiencia_id>', methods=['DELETE'])
@login_required
def remover_audiencia_cotacao_api_teste(audiencia_id):
    err = _guard_audiencia_cotacao(audiencia_id)
    if err:
        return err
    try:
        db.remover_audiencia_cotacao(audiencia_id)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/audiencias/<int:audiencia_id>/duplicar', methods=['POST'])
@login_required
def duplicar_audiencia_cotacao_api(audiencia_id):
    err = _guard_audiencia_cotacao(audiencia_id)
    if err:
        return err
    try:
        nova_id = db.duplicar_audiencia_cotacao(audiencia_id)
        if not nova_id:
            return jsonify({'error': 'Audiência não encontrada'}), 404
        return jsonify({'success': True, 'message': 'Audiência duplicada com sucesso', 'audiencia_id': nova_id})
    except Exception as e:
        current_app.logger.error(f"duplicar_audiencia_cotacao_api: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/deletar', methods=['DELETE'])
@login_required
def deletar_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        cotacao = db.obter_cotacao_por_id(cotacao_id)
        if not cotacao:
            return jsonify({'success': False, 'message': 'Cotação não encontrada'}), 404

        status = cotacao.get('status') or 'Rascunho'
        if status == 'Pendente':
            status = 'Rascunho'
        if status != 'Rascunho':
            return (
                jsonify(
                    {
                        'success': False,
                        'message': f'Não é possível excluir cotações com status "{status}". Apenas cotações em Rascunho podem ser excluídas.',
                    }
                ),
                400,
            )

        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute(
                'SELECT id_pi FROM cadu_pi WHERE cotacao_id = %s LIMIT 1',
                (cotacao_id,),
            )
            pi_row = cur.fetchone()
        if pi_row:
            id_pi_vinculado = pi_row['id_pi']
            return (
                jsonify(
                    {
                        'success': False,
                        'message': (
                            f'Não é possível excluir: cotação possui PI vinculado '
                            f'(id_pi {id_pi_vinculado}).'
                        ),
                    }
                ),
                400,
            )

        db.deletar_cotacao(cotacao_id)
        _audit(
            acao='DELETE',
            modulo='cotacoes_teste_calculo',
            descricao=f'Cotação teste deletada: {cotacao["numero_cotacao"]}',
            registro_id=cotacao_id,
            registro_tipo='cadu_cotacoes',
            dados_anteriores={
                'numero_cotacao': cotacao['numero_cotacao'],
            },
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/comentarios', methods=['GET'])
@login_required
def obter_comentarios_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        comentarios = db.obter_comentarios_cotacao(cotacao_id)
        return jsonify({'success': True, 'comentarios': _serializar(comentarios)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/comentarios', methods=['POST'])
@login_required
def adicionar_comentario_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    return _delegate_app_view('adicionar_comentario_cotacao', cotacao_id)


@bp.route('/api/cotacoes/<int:cotacao_id>/historico', methods=['GET'])
@login_required
def obter_historico_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        historico = db.obter_historico_cotacao(cotacao_id)
        return jsonify({'success': True, 'historico': historico})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/criar-briefing', methods=['POST'])
@login_required
def criar_briefing_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    return _delegate_app_view('criar_briefing_cotacao', cotacao_id)


@bp.route('/api/cotacoes/<int:cotacao_id>/link-publico', methods=['PUT', 'POST', 'PATCH'])
@login_required
def atualizar_link_publico_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    return _delegate_app_view('atualizar_link_publico', cotacao_id)


@bp.route('/api/cotacoes/<int:cotacao_id>/calcular-total', methods=['POST'])
@login_required
def calcular_total_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        total = db.calcular_valor_total_cotacao(cotacao_id)
        total_formatado = float(total) if total is not None else 0.0
        _audit(
            acao='UPDATE',
            modulo='cotacoes_teste_calculo',
            descricao=f'Valor total calculado (teste) cotação {cotacao_id}: R$ {total_formatado:,.2f}',
            registro_id=cotacao_id,
            registro_tipo='cadu_cotacoes',
        )
        return jsonify(
            {'success': True, 'valor_total': total_formatado, 'message': 'Valor total calculado com sucesso'}
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/anexos', methods=['GET'])
@login_required
def listar_anexos_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        anexos = db.obter_anexos_cotacao(cotacao_id)
        return jsonify({'success': True, 'anexos': anexos})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/anexos', methods=['POST'])
@login_required
def adicionar_anexo_cotacao_teste(cotacao_id):
    err = _guard_cotacao_teste(cotacao_id)
    if err:
        return err
    try:
        if 'arquivo' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'}), 400
        arquivo = request.files['arquivo']
        if arquivo.filename == '':
            return jsonify({'success': False, 'message': 'Arquivo sem nome'}), 400

        descricao = request.form.get('descricao', '')
        nome_original = secure_filename(arquivo.filename)
        extensao = os.path.splitext(nome_original)[1]
        nome_arquivo = f"{uuid.uuid4().hex}{extensao}"

        upload_dir = os.path.join(current_app.static_folder, 'uploads', 'cotacoes')
        os.makedirs(upload_dir, exist_ok=True)
        arquivo_path = os.path.join(upload_dir, nome_arquivo)
        arquivo.save(arquivo_path)
        url_arquivo = f"/static/uploads/cotacoes/{nome_arquivo}"
        tamanho_bytes = os.path.getsize(arquivo_path)

        anexo_id = db.criar_anexo_cotacao(
            cotacao_id=cotacao_id,
            nome_original=nome_original,
            nome_arquivo=nome_arquivo,
            url_arquivo=url_arquivo,
            mime_type=arquivo.content_type,
            tamanho_bytes=tamanho_bytes,
            descricao=descricao,
            uploaded_by=session.get('user_id'),
        )
        _audit(
            acao='CREATE',
            modulo='cotacoes_anexos',
            descricao=f'Anexo (teste) cotação {cotacao_id}: {nome_original}',
            registro_id=anexo_id,
            registro_tipo='cadu_cotacao_anexos',
        )
        return jsonify({'success': True, 'anexo_id': anexo_id, 'message': 'Anexo adicionado com sucesso'})
    except Exception as e:
        current_app.logger.error(f"adicionar_anexo_cotacao_teste: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/anexos/<int:anexo_id>', methods=['GET'])
@login_required
def obter_anexo_cotacao_teste(cotacao_id, anexo_id):
    err = _guard_anexo(cotacao_id, anexo_id)
    if err:
        return err
    try:
        anexo = db.obter_anexo_por_id(anexo_id)
        return jsonify({'success': True, 'anexo': anexo})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/anexos/<int:anexo_id>', methods=['PUT'])
@login_required
def editar_anexo_cotacao_teste(cotacao_id, anexo_id):
    err = _guard_anexo(cotacao_id, anexo_id)
    if err:
        return err
    try:
        data = request.json
        sucesso = db.atualizar_anexo_cotacao(
            anexo_id,
            nome_original=data.get('nome_original'),
            descricao=data.get('descricao'),
        )
        if sucesso:
            return jsonify({'success': True, 'message': 'Anexo atualizado com sucesso'})
        return jsonify({'success': False, 'message': 'Nenhuma alteração realizada'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/cotacoes/<int:cotacao_id>/anexos/<int:anexo_id>', methods=['DELETE'])
@login_required
def deletar_anexo_cotacao_teste(cotacao_id, anexo_id):
    err = _guard_anexo(cotacao_id, anexo_id)
    if err:
        return err
    try:
        sucesso = db.deletar_anexo_cotacao(anexo_id, hard_delete=False)
        if sucesso:
            return jsonify({'success': True, 'message': 'Anexo removido com sucesso'})
        return jsonify({'success': False, 'message': 'Anexo não encontrado'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def register_cotacoes_routes(app):
    app.register_blueprint(bp)
