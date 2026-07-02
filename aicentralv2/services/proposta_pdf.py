"""Geração do PDF da "Proposta CentralComm Programmatic".

Reproduz o modelo de proposta de mídia programática no padrão visual CentralComm:
cabeçalho com a logo + tabela de informações da campanha (faixa dourada), tabela de
linhas com títulos dourados, bloco "Total da campanha" + premissas no lado direito e
observações gerais na última página.

Segue a mesma abordagem do PDF público da cotação (reportlab), mas desacoplado em
um service reutilizável para que possa ser chamado tanto por rota autenticada
quanto pelo link público.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from aicentralv2 import db

# Paleta CentralComm: faixa dourada (cabeçalho da tabela de infos, títulos da tabela
# de linhas e caixa de total) com texto preto; verde de apoio.
_COR_GOLD = colors.HexColor('#F2B500')
_COR_GOLD_CLARO = colors.HexColor('#FDF3D0')
_COR_VERDE = colors.HexColor('#3DCB7F')
_COR_TEXTO = colors.HexColor('#1f2937')
_COR_LABEL = colors.HexColor('#555555')
_COR_BORDA = colors.HexColor('#cbd5e1')

_FREQUENCIA_IMPACTO_PADRAO = 3


def _fmt_brl(v):
    if v is None:
        return '-'
    try:
        x = float(v)
    except (TypeError, ValueError):
        return '-'
    if x == 0:
        return '-'
    return f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def _fmt_int(v):
    if v is None:
        return '-'
    try:
        x = float(v)
    except (TypeError, ValueError):
        return '-'
    if x == 0:
        return '-'
    return f"{x:,.0f}".replace(',', '.')


def _fmt_data(v):
    if not v:
        return ''
    if hasattr(v, 'strftime'):
        return v.strftime('%d/%m/%Y')
    return str(v)


def _texto(v):
    if v is None:
        return ''
    s = str(v).strip()
    if s.lower() == 'none':
        return ''
    return s


def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _slug_arquivo(*partes):
    """Monta um slug de nome de arquivo (sem acentos, minúsculo, separado por hífen)."""
    texto = '-'.join(_texto(p) for p in partes if _texto(p))
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('ascii')
    texto = re.sub(r'[^a-zA-Z0-9]+', '-', texto).strip('-').lower()
    return texto


def _join_lista(v):
    """Campos como `canal`/`formatos` podem vir como JSON (lista) ou texto."""
    if v is None:
        return ''
    if isinstance(v, (list, tuple)):
        return ', '.join(str(x) for x in v if x)
    s = str(v).strip()
    if not s or s.lower() == 'none':
        return ''
    if s.startswith('[') or s.startswith('{'):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return ', '.join(str(x) for x in parsed if x)
            if isinstance(parsed, dict):
                return ', '.join(str(x) for x in parsed.values() if x)
        except (ValueError, TypeError):
            return s
    return s


def _resolver_logo_path():
    try:
        from flask import current_app

        caminho = os.path.join(current_app.root_path, 'static', 'images', 'cc_logo_proposta.png')
        if os.path.exists(caminho):
            return caminho
    except Exception:
        pass
    fallback = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'cc_logo_proposta.png')
    fallback = os.path.normpath(fallback)
    return fallback if os.path.exists(fallback) else None


def gerar_proposta_programmatic_pdf(cotacao_id):
    """Gera o PDF da proposta programática.

    Returns:
        tuple[bytes, str]: conteúdo do PDF e nome de arquivo sugerido.

    Raises:
        ValueError: quando a cotação não existe.
    """
    cotacao = db.obter_cotacao_por_id(cotacao_id)
    if not cotacao:
        raise ValueError('Cotação não encontrada.')

    cliente = db.obter_cliente_por_id(cotacao['client_id']) if cotacao.get('client_id') else None
    agencia = db.obter_cliente_por_id(cotacao['agencia_id']) if cotacao.get('agencia_id') else None
    responsavel = (
        db.obter_contato_por_id(cotacao['responsavel_comercial'])
        if cotacao.get('responsavel_comercial')
        else None
    )
    linhas = db.obter_linhas_cotacao(cotacao_id) or []
    audiencias = db.obter_audiencias_cotacao(cotacao_id) or []

    styles = getSampleStyleSheet()
    info_titulo_style = ParagraphStyle(
        'PropInfoTitulo', parent=styles['Normal'], fontSize=9, textColor=colors.black,
        fontName='Helvetica-Bold', alignment=TA_CENTER, leading=10,
    )
    label_style = ParagraphStyle(
        'PropLabel', parent=styles['Normal'], fontSize=7, textColor=_COR_LABEL,
        fontName='Helvetica-Bold', leading=8,
    )
    valor_style = ParagraphStyle(
        'PropValor', parent=styles['Normal'], fontSize=7, textColor=_COR_TEXTO, leading=8,
    )
    secao_style = ParagraphStyle(
        'PropSecao', parent=styles['Heading2'], fontSize=12, textColor=colors.black,
        spaceAfter=6, spaceBefore=4, fontName='Helvetica-Bold',
    )
    cel_style = ParagraphStyle('PropCel', parent=styles['Normal'], fontSize=6.5, leading=8)
    cel_header_style = ParagraphStyle(
        'PropCelHeader', parent=styles['Normal'], fontSize=6.5, leading=7,
        textColor=colors.black, fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    nota_style = ParagraphStyle('PropNota', parent=styles['Normal'], fontSize=8.5, leading=12)
    premissa_titulo_style = ParagraphStyle(
        'PropPremissaTit', parent=styles['Normal'], fontSize=9, textColor=colors.black,
        fontName='Helvetica-Bold', spaceAfter=2,
    )
    premissa_style = ParagraphStyle('PropPremissa', parent=styles['Normal'], fontSize=7.5, leading=10)
    total_titulo_style = ParagraphStyle(
        'PropTotalTit', parent=styles['Normal'], fontSize=9, textColor=colors.black,
        fontName='Helvetica-Bold', alignment=TA_CENTER,
    )
    total_label_style = ParagraphStyle(
        'PropTotalLabel', parent=styles['Normal'], fontSize=7.5, textColor=_COR_TEXTO,
        fontName='Helvetica-Bold',
    )
    total_valor_style = ParagraphStyle(
        'PropTotalValor', parent=styles['Normal'], fontSize=8.5, textColor=_COR_TEXTO,
        fontName='Helvetica-Bold', alignment=TA_RIGHT,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
    )
    largura_util = doc.width
    story = []

    # ---- Dados agregados a partir das linhas ----
    cliente_nome = ''
    if cliente:
        cliente_nome = cliente.get('nome_fantasia') or cliente.get('razao_social') or ''
    agencia_nome = ''
    if agencia:
        agencia_nome = agencia.get('nome_fantasia') or agencia.get('razao_social') or ''
    executivo_nome = responsavel.get('nome_completo', '') if responsavel else ''

    periodo_txt = ''
    if cotacao.get('periodo_inicio'):
        periodo_txt = _fmt_data(cotacao.get('periodo_inicio'))
        if cotacao.get('periodo_fim'):
            periodo_txt += f" a {_fmt_data(cotacao.get('periodo_fim'))}"

    kpis = []
    pracas_linhas = []
    total_volume_impactos = 0.0
    for ln in linhas:
        if ln.get('is_header') or ln.get('is_subtotal'):
            continue
        k = _texto(ln.get('objetivo_kpi'))
        if k and k not in kpis:
            kpis.append(k)
        p = _texto(ln.get('praca'))
        if p and p not in pracas_linhas:
            pracas_linhas.append(p)
        try:
            total_volume_impactos += float(ln.get('volume_contratado') or 0)
        except (TypeError, ValueError):
            pass
    for aud in audiencias:
        k = _texto(aud.get('audiencia_calculo_kpi'))
        if k and k not in kpis:
            kpis.append(k)
        p = _texto(aud.get('audiencia_categoria')) or _texto(aud.get('audiencia_subcategoria'))
        if p and p not in pracas_linhas:
            pracas_linhas.append(p)
        total_volume_impactos += _num(aud.get('volume_contratado') or aud.get('impressoes_estimadas'))
    kpis_txt = ', '.join(kpis)
    praca_txt = '; '.join(pracas_linhas)

    data_envio_txt = _fmt_data(cotacao.get('proposta_enviada_em') or cotacao.get('created_at'))

    validade_txt = ''
    for campo_validade in ('expires_at', 'link_publico_expires_at'):
        v = cotacao.get(campo_validade)
        if v:
            validade_txt = _fmt_data(v)
            break

    # Frequência de impacto e estimativa de impactos únicos (volume total ÷ frequência).
    try:
        frequencia_impacto = int(cotacao.get('frequencia_impacto') or _FREQUENCIA_IMPACTO_PADRAO)
    except (TypeError, ValueError):
        frequencia_impacto = _FREQUENCIA_IMPACTO_PADRAO
    if frequencia_impacto <= 0:
        frequencia_impacto = _FREQUENCIA_IMPACTO_PADRAO

    impactos_unicos = 0.0
    if total_volume_impactos and frequencia_impacto:
        impactos_unicos = round(total_volume_impactos / frequencia_impacto)
    impactos_unicos_txt = _fmt_int(impactos_unicos) if impactos_unicos else ''
    volume_total_txt = _fmt_int(total_volume_impactos) if total_volume_impactos else ''

    # ---- Cabeçalho (área vermelha do modelo): infos à esquerda + logo à direita ----
    info_pares = [
        ('Cliente', cliente_nome),
        ('Agência', agencia_nome),
        ('Executivo', executivo_nome),
        ('Campanha', _texto(cotacao.get('nome_campanha'))),
        ('Período da campanha', periodo_txt),
        ("KPI's", kpis_txt or _texto(cotacao.get('objetivo_campanha'))),
        ('Praça', praca_txt),
        ('Frequência de impacto', str(frequencia_impacto)),
        ('Volume total (impr./views)', volume_total_txt),
        ('Estimativa de impactos únicos', impactos_unicos_txt),
        ('Data de envio', data_envio_txt),
        ('Validade da proposta', validade_txt),
    ]

    info_data = [[Paragraph('Centralcomm - Media as a Service', info_titulo_style), '']]
    for rotulo, valor in info_pares:
        info_data.append([
            Paragraph(escape(rotulo), label_style),
            Paragraph(escape(valor) if valor else '-', valor_style),
        ])

    info_w = (largura_util - 8 * mm) * 0.62
    info_table = Table(info_data, colWidths=[info_w * 0.42, info_w * 0.58])
    info_table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), _COR_GOLD),
        ('GRID', (0, 0), (-1, -1), 0.5, _COR_BORDA),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (1, 0), 1),
        ('BOTTOMPADDING', (0, 0), (1, 0), 1),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, _COR_GOLD_CLARO]),
    ]))

    logo_path = _resolver_logo_path()
    if logo_path:
        try:
            logo = Image(logo_path, width=27 * mm, height=19.8 * mm, kind='proportional')
            logo_celula = Table([[logo]], colWidths=[(largura_util - 8 * mm) * 0.38])
            logo_celula.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            direita = logo_celula
        except Exception:
            direita = ''
    else:
        direita = ''

    header_row = [[info_table, direita]]
    header_table = Table(
        header_row,
        colWidths=[(largura_util - 8 * mm) * 0.62 + 8 * mm, (largura_util - 8 * mm) * 0.38],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5 * mm))

    # ---- Tabela de linhas (títulos dourados / área verde do modelo) ----
    cabecalhos = [
        'Canais', 'Formato', 'Objetivo / Estratégia', 'Target & Interesses', 'Praça',
        'Período', 'Tipo de compra', 'Valor negociado', 'Volume total\n(impr./views)',
        'Invest. bruto', 'Invest. líquido',
    ]
    dados_tabela = [[Paragraph(escape(c).replace('\n', '<br/>'), cel_header_style) for c in cabecalhos]]
    span_cmds = []
    total_volume = 0.0
    total_bruto = 0.0
    total_liquido = 0.0
    row_i = 1
    num_cols = len(cabecalhos)

    for ln in linhas:
        if ln.get('is_header'):
            ht = _texto(ln.get('detalhamento')) or _texto(ln.get('segmentacao')) or _texto(ln.get('subtotal_label')) or '—'
            dados_tabela.append([Paragraph(f"<b>{escape(ht)}</b>", cel_style)] + [''] * (num_cols - 1))
            span_cmds.append(('SPAN', (0, row_i), (num_cols - 1, row_i)))
            span_cmds.append(('BACKGROUND', (0, row_i), (-1, row_i), _COR_GOLD_CLARO))
            row_i += 1
            continue
        if ln.get('is_subtotal'):
            lbl = _texto(ln.get('subtotal_label')) or 'Subtotal'
            bruto_s = _fmt_brl(ln.get('investimento_bruto') or ln.get('valor_total'))
            liq_s = _fmt_brl(ln.get('investimento_liquido'))
            dados_tabela.append([Paragraph(f"<b>{escape(lbl)}</b>", cel_style)] + [''] * 8 + [bruto_s, liq_s])
            span_cmds.append(('SPAN', (0, row_i), (8, row_i)))
            row_i += 1
            continue

        canais = _join_lista(ln.get('canal')) or _texto(ln.get('plataforma')) or _texto(ln.get('veiculo'))
        formato = _join_lista(ln.get('formatos')) or _texto(ln.get('formato')) or _texto(ln.get('formato_compra'))
        objetivo = _texto(ln.get('detalhamento')) or _texto(ln.get('objetivo_kpi'))
        target = _texto(ln.get('target')) or _texto(ln.get('segmentacao'))
        praca = _texto(ln.get('praca'))
        periodo = _texto(ln.get('periodo'))
        if not periodo and ln.get('data_inicio') and ln.get('data_fim'):
            periodo = f"{_fmt_data(ln.get('data_inicio'))} - {_fmt_data(ln.get('data_fim'))}"
        tipo_compra = _texto(ln.get('objetivo_kpi'))
        valor_neg = _fmt_brl(ln.get('valor_unitario_negociado') or ln.get('valor_unitario'))
        volume = ln.get('volume_contratado')
        bruto_val = ln.get('investimento_bruto') or ln.get('valor_total')
        liquido_val = ln.get('investimento_liquido')

        try:
            total_volume += float(volume or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_bruto += float(bruto_val or 0)
        except (TypeError, ValueError):
            pass
        try:
            total_liquido += float(liquido_val or 0)
        except (TypeError, ValueError):
            pass

        dados_tabela.append([
            Paragraph(escape(canais) or '-', cel_style),
            Paragraph(escape(formato) or '-', cel_style),
            Paragraph(escape(objetivo) or '-', cel_style),
            Paragraph(escape(target) or '-', cel_style),
            Paragraph(escape(praca) or '-', cel_style),
            Paragraph(escape(periodo) or '-', cel_style),
            Paragraph(escape(tipo_compra) or '-', cel_style),
            Paragraph(valor_neg, cel_style),
            Paragraph(_fmt_int(volume), cel_style),
            Paragraph(_fmt_brl(bruto_val), cel_style),
            Paragraph(_fmt_brl(liquido_val), cel_style),
        ])
        row_i += 1

    if audiencias:
        dados_tabela.append([Paragraph('<b>Audiências</b>', cel_style)] + [''] * (num_cols - 1))
        span_cmds.append(('SPAN', (0, row_i), (num_cols - 1, row_i)))
        span_cmds.append(('BACKGROUND', (0, row_i), (-1, row_i), _COR_GOLD_CLARO))
        row_i += 1

        for aud in audiencias:
            canais = (
                _texto(aud.get('audiencia_calculo_plataforma'))
                or _texto(aud.get('audiencia_categoria'))
                or _texto(aud.get('fonte'))
            )
            formato = 'Audiência'
            objetivo = _texto(aud.get('audiencia_nome'))
            target = _texto(aud.get('audiencia_publico'))
            praca = '; '.join(
                p for p in (
                    _texto(aud.get('audiencia_categoria')),
                    _texto(aud.get('audiencia_subcategoria')),
                )
                if p
            )
            periodo = _texto(aud.get('periodo'))
            if not periodo and aud.get('data_inicio') and aud.get('data_fim'):
                periodo = f"{_fmt_data(aud.get('data_inicio'))} - {_fmt_data(aud.get('data_fim'))}"
            tipo_compra = _texto(aud.get('audiencia_calculo_kpi'))
            valor_neg = _fmt_brl(
                aud.get('valor_unitario_negociado')
                or aud.get('valor_unitario')
                or aud.get('cpm_estimado')
            )
            volume = aud.get('volume_contratado') or aud.get('impressoes_estimadas')
            bruto_val = aud.get('investimento_bruto') or aud.get('investimento_sugerido')
            liquido_val = aud.get('investimento_liquido') or bruto_val

            total_volume += _num(volume)
            total_bruto += _num(bruto_val)
            total_liquido += _num(liquido_val)

            dados_tabela.append([
                Paragraph(escape(canais) or '-', cel_style),
                Paragraph(escape(formato), cel_style),
                Paragraph(escape(objetivo) or '-', cel_style),
                Paragraph(escape(target) or '-', cel_style),
                Paragraph(escape(praca) or '-', cel_style),
                Paragraph(escape(periodo) or '-', cel_style),
                Paragraph(escape(tipo_compra) or '-', cel_style),
                Paragraph(valor_neg, cel_style),
                Paragraph(_fmt_int(volume), cel_style),
                Paragraph(_fmt_brl(bruto_val), cel_style),
                Paragraph(_fmt_brl(liquido_val), cel_style),
            ])
            row_i += 1

    # Linha de total geral.
    dados_tabela.append([
        Paragraph('<b>TOTAL</b>', cel_style)] + [''] * 7 + [
        Paragraph(f"<b>{_fmt_int(total_volume)}</b>", cel_style),
        Paragraph(f"<b>{_fmt_brl(total_bruto)}</b>", cel_style),
        Paragraph(f"<b>{_fmt_brl(total_liquido)}</b>", cel_style),
    ])
    span_cmds.append(('SPAN', (0, row_i), (7, row_i)))
    span_cmds.append(('BACKGROUND', (0, row_i), (-1, row_i), _COR_GOLD))

    pesos = [11, 12, 16, 18, 10, 10, 9, 10, 10, 10, 10]
    soma = sum(pesos)
    col_widths = [largura_util * (p / soma) for p in pesos]
    tabela = Table(dados_tabela, colWidths=col_widths, repeatRows=1)
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), _COR_GOLD),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, _COR_BORDA),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('ALIGN', (7, 1), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, 0), 1),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
    ]
    estilo.extend(span_cmds)
    tabela.setStyle(TableStyle(estilo))
    story.append(tabela)
    story.append(Spacer(1, 5 * mm))

    # ---- Premissas + Total da campanha (lado direito) ----
    premissas_txt = _texto(cotacao.get('premissas')) or _texto(cotacao.get('condicoes_comerciais'))
    premissas_flow = [Paragraph('Premissas', premissa_titulo_style)]
    if premissas_txt:
        for linha_txt in premissas_txt.replace('\r\n', '\n').split('\n'):
            if linha_txt.strip():
                premissas_flow.append(Paragraph(escape(linha_txt.strip()), premissa_style))
    else:
        premissas_flow.append(Paragraph('-', premissa_style))

    premissas_box = Table([[premissas_flow]], colWidths=[(largura_util - 6 * mm) * 0.55])
    premissas_box.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    total_data = [
        [Paragraph('TOTAL DA CAMPANHA', total_titulo_style), ''],
        [Paragraph('INVESTIMENTO BRUTO TOTAL', total_label_style), Paragraph(_fmt_brl(total_bruto), total_valor_style)],
        [Paragraph('INVESTIMENTO LÍQUIDO TOTAL', total_label_style), Paragraph(_fmt_brl(total_liquido), total_valor_style)],
        [Paragraph('VALIDADE DA PROPOSTA', total_label_style), Paragraph(validade_txt or '-', total_valor_style)],
    ]
    total_w = (largura_util - 6 * mm) * 0.45
    total_box = Table(total_data, colWidths=[total_w * 0.6, total_w * 0.4])
    total_box.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), _COR_GOLD),
        ('GRID', (0, 0), (-1, -1), 0.5, _COR_BORDA),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, _COR_GOLD_CLARO]),
    ]))

    rodape = Table(
        [[premissas_box, total_box]],
        colWidths=[(largura_util - 6 * mm) * 0.55 + 6 * mm, (largura_util - 6 * mm) * 0.45],
    )
    rodape.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(rodape)

    # ---- Observações gerais (última página) ----
    observacoes_gerais_txt = _texto(cotacao.get('observacoes_gerais')) or _texto(cotacao.get('observacoes'))
    if observacoes_gerais_txt:
        story.append(PageBreak())
        story.append(Paragraph('Observações gerais', secao_style))
        for linha_txt in observacoes_gerais_txt.replace('\r\n', '\n').split('\n'):
            if linha_txt.strip():
                story.append(Paragraph(escape(linha_txt.strip()), nota_style))

    doc.build(story)
    buffer.seek(0)

    numero = _texto(cotacao.get('numero_cotacao')) or str(cotacao_id)
    base = _slug_arquivo(cliente_nome, _texto(cotacao.get('nome_campanha')), numero) or f"proposta_{numero}"
    filename = f"{base}.pdf"
    return buffer.read(), filename
