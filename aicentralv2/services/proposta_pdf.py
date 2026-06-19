"""Geração do PDF da "Proposta CentralComm Programmatic".

Reproduz o modelo de proposta de mídia programática: cabeçalho com dados da
campanha + tabela de linhas (canais, formato, objetivo, target, praça, período,
tipo de compra, valor negociado, volume, investimento bruto/líquido) + totais e
premissas/observações, com a logo da CentralComm.

Segue a mesma abordagem do PDF público da cotação (reportlab), mas desacoplado em
um service reutilizável para que possa ser chamado tanto por rota autenticada
quanto pelo link público.
"""
from __future__ import annotations

import json
import os
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from aicentralv2 import db

# Paleta alinhada ao restante do app (header escuro + verde CentralComm).
_COR_HEADER = colors.HexColor('#1a1a2e')
_COR_TABELA_HEADER = colors.HexColor('#1e3a8a')
_COR_VERDE = colors.HexColor('#72cd80')
_COR_TEXTO = colors.HexColor('#333333')
_COR_LABEL = colors.HexColor('#666666')


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

        caminho = os.path.join(current_app.root_path, 'static', 'images', 'cc_logo.png')
        if os.path.exists(caminho):
            return caminho
    except Exception:
        pass
    fallback = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'cc_logo.png')
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

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'PropTitulo', parent=styles['Heading1'], fontSize=15, textColor=colors.white,
        spaceAfter=2, alignment=TA_LEFT,
    )
    subtitulo_style = ParagraphStyle(
        'PropSubtitulo', parent=styles['Normal'], fontSize=9, textColor=_COR_VERDE, spaceAfter=0,
    )
    secao_style = ParagraphStyle(
        'PropSecao', parent=styles['Heading2'], fontSize=11, textColor=_COR_HEADER,
        spaceAfter=4, spaceBefore=8,
    )
    label_style = ParagraphStyle('PropLabel', parent=styles['Normal'], fontSize=8, textColor=_COR_LABEL)
    valor_style = ParagraphStyle('PropValor', parent=styles['Normal'], fontSize=8, textColor=_COR_TEXTO)
    cel_style = ParagraphStyle('PropCel', parent=styles['Normal'], fontSize=6.5, leading=8)
    cel_header_style = ParagraphStyle(
        'PropCelHeader', parent=styles['Normal'], fontSize=6.5, leading=8,
        textColor=colors.whitesmoke, fontName='Helvetica-Bold',
    )
    nota_style = ParagraphStyle('PropNota', parent=styles['Normal'], fontSize=8, leading=11)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
    )
    largura_util = doc.width
    story = []

    # ---- Cabeçalho com logo + título ----
    logo_path = _resolver_logo_path()
    titulo_par = Paragraph(
        "<b>Proposta CentralComm Programmatic</b><br/>"
        f"<font size='8' color='#cbd5e1'>{escape(_texto(cotacao.get('nome_campanha')) or 'Proposta Comercial')}</font>",
        titulo_style,
    )
    num_par = Paragraph(
        f"<font size='9' color='#ffffff'>Nº {escape(_texto(cotacao.get('numero_cotacao')))}</font>",
        subtitulo_style,
    )
    if logo_path:
        try:
            logo = Image(logo_path, width=20 * mm, height=20 * mm, kind='proportional')
            header_celula_esq = [[logo, titulo_par]]
            header_tbl_esq = Table(header_celula_esq, colWidths=[24 * mm, largura_util - 24 * mm - 40 * mm])
            header_tbl_esq.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            esquerda = header_tbl_esq
        except Exception:
            esquerda = titulo_par
    else:
        esquerda = titulo_par

    header_row = [[esquerda, num_par]]
    header_table = Table(header_row, colWidths=[largura_util - 40 * mm, 40 * mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _COR_HEADER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 5 * mm))

    # ---- Bloco de informações (cabeçalho do modelo) ----
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

    # KPIs agregados a partir das linhas + objetivo da campanha.
    kpis = []
    for ln in linhas:
        if ln.get('is_header') or ln.get('is_subtotal'):
            continue
        k = _texto(ln.get('objetivo_kpi'))
        if k and k not in kpis:
            kpis.append(k)
    kpis_txt = ', '.join(kpis)

    validade_txt = ''
    if cotacao.get('validade_dias') not in (None, ''):
        validade_txt = f"{cotacao.get('validade_dias')} dias"

    info_pares = [
        ('Cliente', cliente_nome),
        ('Agência', agencia_nome),
        ('Executivo', executivo_nome),
        ('Data de envio', _fmt_data(cotacao.get('data_envio'))),
        ('Período da campanha', periodo_txt),
        ("KPI's", kpis_txt or _texto(cotacao.get('objetivo_campanha'))),
        ('Frequência de impacto', _texto(cotacao.get('frequencia_impacto'))),
        ('Estimativa de impactos únicos', _fmt_int(cotacao.get('estimativa_impactos_unicos'))
            if cotacao.get('estimativa_impactos_unicos') not in (None, '') else ''),
        ('Praça', _texto(cotacao.get('praca'))),
        ('Dados demográficos', _texto(cotacao.get('dados_demograficos'))),
        ('Perfil da audiência e interesses', _texto(cotacao.get('perfil_audiencia_interesses'))),
        ('Validade da proposta', validade_txt),
    ]

    info_rows = []
    linha_par = []
    for rotulo, valor in info_pares:
        cel = [
            Paragraph(escape(rotulo), label_style),
            Paragraph(escape(valor) if valor else '-', valor_style),
        ]
        cel_tbl = Table([[cel[0]], [cel[1]]], colWidths=[(largura_util / 2) - 4 * mm])
        cel_tbl.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        linha_par.append(cel_tbl)
        if len(linha_par) == 2:
            info_rows.append(linha_par)
            linha_par = []
    if linha_par:
        linha_par.append('')
        info_rows.append(linha_par)

    info_table = Table(info_rows, colWidths=[largura_util / 2, largura_util / 2])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 5 * mm))

    # ---- Tabela de linhas (modelo) ----
    story.append(Paragraph('Detalhamento da campanha', secao_style))

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
            span_cmds.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor('#eef2ff')))
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

    # Linha de total geral.
    dados_tabela.append([
        Paragraph('<b>TOTAL</b>', cel_style)] + [''] * 7 + [
        Paragraph(f"<b>{_fmt_int(total_volume)}</b>", cel_style),
        Paragraph(f"<b>{_fmt_brl(total_bruto)}</b>", cel_style),
        Paragraph(f"<b>{_fmt_brl(total_liquido)}</b>", cel_style),
    ])
    span_cmds.append(('SPAN', (0, row_i), (7, row_i)))
    span_cmds.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor('#dcfce7')))

    # Larguras proporcionais (somam ~273mm úteis em paisagem A4).
    pesos = [11, 12, 16, 18, 10, 10, 9, 10, 10, 10, 10]
    soma = sum(pesos)
    col_widths = [largura_util * (p / soma) for p in pesos]
    tabela = Table(dados_tabela, colWidths=col_widths, repeatRows=1)
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), _COR_TABELA_HEADER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('ALIGN', (7, 1), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]
    estilo.extend(span_cmds)
    tabela.setStyle(TableStyle(estilo))
    story.append(tabela)
    story.append(Spacer(1, 5 * mm))

    # ---- Premissas ----
    if _texto(cotacao.get('premissas')):
        story.append(Paragraph('Premissas', secao_style))
        for linha_txt in _texto(cotacao.get('premissas')).replace('\r\n', '\n').split('\n'):
            if linha_txt.strip():
                story.append(Paragraph(escape(linha_txt.strip()), nota_style))
        story.append(Spacer(1, 3 * mm))

    # ---- Condições comerciais ----
    if _texto(cotacao.get('condicoes_comerciais')):
        story.append(Paragraph('Condições comerciais', secao_style))
        for linha_txt in _texto(cotacao.get('condicoes_comerciais')).replace('\r\n', '\n').split('\n'):
            if linha_txt.strip():
                story.append(Paragraph(escape(linha_txt.strip()), nota_style))
        story.append(Spacer(1, 3 * mm))

    # ---- Observações gerais ----
    if _texto(cotacao.get('observacoes')):
        story.append(Paragraph('Observações gerais', secao_style))
        for linha_txt in _texto(cotacao.get('observacoes')).replace('\r\n', '\n').split('\n'):
            if linha_txt.strip():
                story.append(Paragraph(escape(linha_txt.strip()), nota_style))

    doc.build(story)
    buffer.seek(0)

    numero = _texto(cotacao.get('numero_cotacao')) or str(cotacao_id)
    filename = f"proposta_programmatic_{numero}.pdf"
    return buffer.read(), filename
