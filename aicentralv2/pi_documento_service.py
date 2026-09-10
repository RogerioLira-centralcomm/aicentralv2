"""PDFs de fechamento do PI — exclusivamente a partir do snapshot."""

from __future__ import annotations

import os
import re
import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
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

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover
    colors = None
    TA_RIGHT = A4 = ParagraphStyle = getSampleStyleSheet = mm = None
    Image = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None
    REPORTLAB_AVAILABLE = False

from .pi_fechamento_service import PiFechamentoService, ZONA_LABELS


TIPOS = ("fechamento", "comprovacao", "bonificacao", "passagem")
VARIANTES = ("cliente", "agencia", "interno")

_COR_FUNDO = colors.HexColor("#172d32") if colors else None
_COR_ACCENT = colors.HexColor("#72cd80") if colors else None
_COR_TEXTO = colors.HexColor("#132e30") if colors else None
_COR_MUTED = colors.HexColor("#64748b") if colors else None
_COR_BORDA = colors.HexColor("#dfe5e7") if colors else None
_COR_LINHA = colors.HexColor("#f4f7f7") if colors else None


class DocumentoIndisponivelError(ValueError):
    pass


def _texto(value):
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "null"} else text


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_brl(value):
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _fmt_pct(value):
    try:
        return f"{float(value):.1f}%".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _fmt_data(value):
    if not value:
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    return text[:10] if text else "—"


def _slug(*partes):
    text = "-".join(_texto(item) for item in partes if _texto(item))
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "documento-pi"


def _tem_incentivo(snapshot):
    return _num(snapshot.get("pl_incentivos")) > 0 or bool(_texto(snapshot.get("agencia_nome")))


def _resolver_logo():
    candidatos = []
    try:
        from flask import current_app

        root = current_app.root_path
        candidatos.extend(
            [
                os.path.join(root, "static", "images", "cc_logo.png"),
                os.path.join(root, "static", "images", "cc_logo_proposta.png"),
            ]
        )
    except Exception:
        pass
    base = os.path.normpath(os.path.join(os.path.dirname(__file__), "static", "images"))
    candidatos.extend(
        [
            os.path.join(base, "cc_logo.png"),
            os.path.join(base, "cc_logo_proposta.png"),
        ]
    )
    for caminho in candidatos:
        if caminho and os.path.exists(caminho):
            return caminho
    return None


class PiDocumentoService:
    def __init__(self, fechamento=None):
        self.fechamento = fechamento or PiFechamentoService()

    def listar(self, snapshot):
        persistido = bool(snapshot.get("persistido"))
        documentos = []
        if persistido:
            documentos.extend(
                [
                    {
                        "tipo": "fechamento",
                        "variante": "cliente",
                        "label": "Relatório de fechamento (cliente)",
                    },
                    {
                        "tipo": "fechamento",
                        "variante": "agencia",
                        "label": "Relatório de fechamento (agência)",
                        "disponivel": bool(_texto(snapshot.get("agencia_nome"))),
                    },
                    {
                        "tipo": "comprovacao",
                        "variante": "cliente",
                        "label": "Comprovação de veiculação",
                    },
                ]
            )
            if _tem_incentivo(snapshot):
                documentos.append(
                    {
                        "tipo": "bonificacao",
                        "variante": "agencia",
                        "label": "Carta de bonificação",
                    }
                )
        documentos.append(
            {
                "tipo": "passagem",
                "variante": "interno",
                "label": "Passagem para o financeiro",
            }
        )
        return documentos

    def gerar(self, id_pi, tipo, variante="cliente", id_campanha=None):
        tipo = str(tipo or "").strip()
        variante = str(variante or "cliente").strip()
        if tipo not in TIPOS:
            raise DocumentoIndisponivelError("Tipo de documento inválido.")
        if variante not in VARIANTES:
            raise DocumentoIndisponivelError("Variante de documento inválida.")

        snapshot = self.fechamento.resultado(id_pi)
        if tipo != "passagem" and not snapshot.get("persistido"):
            raise DocumentoIndisponivelError(
                "Gere o snapshot no handoff antes de emitir este documento."
            )
        if tipo == "bonificacao" and not _tem_incentivo(snapshot):
            raise DocumentoIndisponivelError(
                "Carta de bonificação só se aplica a PI com agência ou incentivo."
            )
        if tipo == "fechamento" and variante == "agencia" and not _texto(snapshot.get("agencia_nome")):
            raise DocumentoIndisponivelError("Este PI não possui agência para o relatório.")

        if not REPORTLAB_AVAILABLE:
            raise DocumentoIndisponivelError("Biblioteca reportlab não instalada.")

        campanhas = list(snapshot.get("campanhas") or [])
        if id_campanha is not None:
            campanhas = [
                item
                for item in campanhas
                if str(item.get("id_campanha")) == str(id_campanha)
            ]
            if not campanhas:
                raise DocumentoIndisponivelError("Campanha não encontrada no snapshot.")

        buffer = BytesIO()
        if tipo == "fechamento":
            self._relatorio_fechamento(buffer, snapshot, variante)
        elif tipo == "comprovacao":
            self._comprovacao(buffer, snapshot, campanhas)
        elif tipo == "bonificacao":
            self._bonificacao(buffer, snapshot)
        else:
            self._passagem(buffer, snapshot)

        codigo = _slug(snapshot.get("codigo_pi") or f"pi-{id_pi}")
        nome = f"{codigo}-{tipo}-{variante}.pdf"
        return buffer.getvalue(), nome

    def _styles(self):
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "PiDocTitle",
                parent=base["Heading1"],
                fontSize=15,
                textColor=colors.white,
                leading=18,
                spaceAfter=2,
            ),
            "kicker": ParagraphStyle(
                "PiDocKicker",
                parent=base["Normal"],
                fontSize=8,
                textColor=_COR_ACCENT,
                leading=11,
            ),
            "meta": ParagraphStyle(
                "PiDocMeta",
                parent=base["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#cbd5e1"),
                alignment=TA_RIGHT,
                leading=11,
            ),
            "heading": ParagraphStyle(
                "PiDocHeading",
                parent=base["Heading2"],
                fontSize=11,
                textColor=_COR_TEXTO,
                spaceBefore=10,
                spaceAfter=6,
            ),
            "body": ParagraphStyle(
                "PiDocBody",
                parent=base["Normal"],
                fontSize=9,
                textColor=_COR_TEXTO,
                leading=13,
            ),
            "muted": ParagraphStyle(
                "PiDocMuted",
                parent=base["Normal"],
                fontSize=8,
                textColor=_COR_MUTED,
                leading=11,
            ),
            "th": ParagraphStyle(
                "PiDocTh",
                parent=base["Normal"],
                fontSize=8,
                textColor=colors.white,
                fontName="Helvetica-Bold",
            ),
            "td": ParagraphStyle(
                "PiDocTd",
                parent=base["Normal"],
                fontSize=8,
                textColor=_COR_TEXTO,
                leading=11,
            ),
            "tdr": ParagraphStyle(
                "PiDocTdR",
                parent=base["Normal"],
                fontSize=8,
                textColor=_COR_TEXTO,
                alignment=TA_RIGHT,
                leading=11,
            ),
        }

    def _header(self, story, styles, titulo, snapshot, destinatario):
        codigo = escape(_texto(snapshot.get("codigo_pi") or snapshot.get("id_pi")))
        cliente = escape(_texto(snapshot.get("cliente_nome")) or "Cliente não informado")
        logo_path = _resolver_logo()
        if logo_path:
            try:
                logo = Image(logo_path, width=18 * mm, height=18 * mm, kind="proportional")
            except Exception:
                logo = Paragraph("CentralComm", styles["title"])
        else:
            logo = Paragraph("CentralComm", styles["title"])

        esquerda = [
            logo,
            Paragraph(escape(titulo), styles["title"]),
            Paragraph(f"{cliente} · PI {codigo}", styles["kicker"]),
        ]
        direita = Paragraph(
            f"{escape(destinatario)}<br/>Zona {escape(str(snapshot.get('zona_lucratividade') or '—'))}"
            f" · {escape(_texto(snapshot.get('saude_label') or snapshot.get('saude_pi')))}",
            styles["meta"],
        )
        tabela = Table([[esquerda, direita]], colWidths=[120 * mm, 50 * mm])
        tabela.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _COR_FUNDO),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(tabela)
        story.append(Spacer(1, 8 * mm))

    def _kv_table(self, rows, styles, col_label=48 * mm, col_value=122 * mm):
        data = [
            [Paragraph(escape(label), styles["muted"]), Paragraph(escape(value), styles["td"])]
            for label, value in rows
        ]
        table = Table(data, colWidths=[col_label, col_value])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.4, _COR_BORDA),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.3, _COR_BORDA),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return table

    def _grid_table(self, headers, rows, styles, col_widths):
        head = [Paragraph(escape(item), styles["th"]) for item in headers]
        body = []
        for row in rows:
            lined = []
            for index, cell in enumerate(row):
                estilo = styles["tdr"] if index else styles["td"]
                if index and index < len(row) - 0:
                    estilo = styles["tdr"] if index > 0 and headers[index] != "Campanha" else styles["td"]
                lined.append(Paragraph(escape(str(cell)), estilo if index else styles["td"]))
            body.append(lined)
        table = Table([head] + body, colWidths=col_widths, repeatRows=1)
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), _COR_FUNDO),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOX", (0, 0), (-1, -1), 0.4, _COR_BORDA),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, _COR_BORDA),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ]
        for index in range(1, len(body) + 1):
            if index % 2 == 0:
                commands.append(("BACKGROUND", (0, index), (-1, index), _COR_LINHA))
        table.setStyle(TableStyle(commands))
        return table

    def _relatorio_fechamento(self, buffer, snapshot, variante):
        styles = self._styles()
        dest = "Agência" if variante == "agencia" else "Cliente"
        story = []
        self._header(story, styles, "Relatório consolidado de fechamento", snapshot, dest)
        if variante == "agencia":
            intro = (
                f"Consolidado operacional do PI para {snapshot.get('agencia_nome') or 'a agência'}, "
                "com resultado de mídia e evidência das campanhas encerradas."
            )
        else:
            intro = (
                "Consolidado do resultado contratado versus realizado, "
                "para validação do fechamento da campanha."
            )
        story.append(Paragraph(escape(intro), styles["body"]))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Identificação", styles["heading"]))
        story.append(
            self._kv_table(
                [
                    ("Cliente", _texto(snapshot.get("cliente_nome")) or "—"),
                    ("Agência", _texto(snapshot.get("agencia_nome")) or "—"),
                    ("Código PI", _texto(snapshot.get("codigo_pi")) or "—"),
                    ("Saúde", _texto(snapshot.get("saude_label") or snapshot.get("saude_pi")) or "—"),
                    (
                        "Zona",
                        f"{snapshot.get('zona_lucratividade') or '—'} · "
                        f"{snapshot.get('zona_label') or ZONA_LABELS.get(int(snapshot.get('zona_lucratividade') or 0), '—')}",
                    ),
                ],
                styles,
            )
        )
        story.append(Paragraph("Resultado de mídia", styles["heading"]))
        story.append(
            self._kv_table(
                [
                    ("Gasto realizado", _fmt_brl(snapshot.get("gasto_midia_realizado"))),
                    ("Gasto previsto", _fmt_brl(snapshot.get("gasto_midia_previsto"))),
                    ("% gasto", _fmt_pct(snapshot.get("pct_gasto_midia"))),
                    ("% entrega", _fmt_pct(snapshot.get("pct_objetivo"))),
                ],
                styles,
            )
        )
        if variante != "cliente":
            story.append(Paragraph("Resultado comercial", styles["heading"]))
            story.append(
                self._kv_table(
                    [
                        ("Bruto", _fmt_brl(snapshot.get("valor_bruto"))),
                        ("Líquido", _fmt_brl(snapshot.get("valor_liquido"))),
                        ("PL incentivos", _fmt_brl(snapshot.get("pl_incentivos"))),
                        ("Resultado", _fmt_brl(snapshot.get("margem_liquida_calculada"))),
                    ],
                    styles,
                )
            )
        campanhas = snapshot.get("campanhas") or []
        if campanhas:
            story.append(Paragraph("Campanhas", styles["heading"]))
            story.append(
                self._grid_table(
                    ["Campanha", "Plataforma", "Gasto", "Entrega"],
                    [
                        [
                            _texto(item.get("nome_campanha")) or "—",
                            _texto(item.get("plataforma")) or "—",
                            f"{_fmt_pct(item.get('pct_gasto'))} · {_fmt_brl(item.get('gasto_realizado'))}",
                            _fmt_pct(item.get("pct_objetivo")),
                        ]
                        for item in campanhas
                    ],
                    styles,
                    [62 * mm, 32 * mm, 48 * mm, 28 * mm],
                )
            )
        self._build(buffer, story)

    def _comprovacao(self, buffer, snapshot, campanhas):
        styles = self._styles()
        story = []
        self._header(story, styles, "Comprovação de veiculação", snapshot, "Cliente / agência")
        story.append(
            Paragraph(
                "Evidência de veiculação extraída exclusivamente do snapshot de fechamento.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 4 * mm))
        if not campanhas:
            story.append(Paragraph("Nenhuma campanha no snapshot.", styles["muted"]))
        else:
            rows = []
            for item in campanhas:
                periodo = " — ".join(
                    part
                    for part in (_fmt_data(item.get("periodo_inicio")), _fmt_data(item.get("periodo_fim")))
                    if part != "—"
                ) or "—"
                rows.append(
                    [
                        _texto(item.get("nome_campanha")) or "—",
                        _texto(item.get("plataforma") or item.get("status_nome")) or "—",
                        periodo,
                        _fmt_brl(item.get("gasto_realizado")),
                        _fmt_pct(item.get("pct_objetivo")),
                    ]
                )
            story.append(
                self._grid_table(
                    ["Campanha", "Plataforma", "Período", "Gasto", "Entrega"],
                    rows,
                    styles,
                    [46 * mm, 28 * mm, 38 * mm, 30 * mm, 28 * mm],
                )
            )
        self._build(buffer, story)

    def _bonificacao(self, buffer, snapshot):
        styles = self._styles()
        story = []
        self._header(story, styles, "Carta de bonificação", snapshot, "Agência")
        story.append(
            Paragraph(
                "Documento interno de referência para incentivo de agência, "
                "gerado a partir do snapshot de fechamento. Validação jurídica/financeira "
                "permanece necessária antes de uso contratual.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 4 * mm))
        story.append(
            self._kv_table(
                [
                    ("Agência", _texto(snapshot.get("agencia_nome")) or "—"),
                    ("Cliente anunciante", _texto(snapshot.get("cliente_nome")) or "—"),
                    ("PI", _texto(snapshot.get("codigo_pi")) or "—"),
                    ("Valor líquido do PI", _fmt_brl(snapshot.get("valor_liquido"))),
                    ("PL de incentivos", _fmt_brl(snapshot.get("pl_incentivos"))),
                    ("Bruto de referência", _fmt_brl(snapshot.get("valor_bruto"))),
                ],
                styles,
            )
        )
        if snapshot.get("observacoes_operacao"):
            story.append(Paragraph("Observações da operação", styles["heading"]))
            story.append(Paragraph(escape(_texto(snapshot.get("observacoes_operacao"))), styles["body"]))
        self._build(buffer, story)

    def _passagem(self, buffer, snapshot):
        styles = self._styles()
        story = []
        self._header(story, styles, "Passagem para o financeiro", snapshot, "Uso interno")
        story.append(
            Paragraph(
                "Resumo de DRE, pendências e links para o time financeiro após o handoff operacional.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("DRE do snapshot", styles["heading"]))
        story.append(
            self._kv_table(
                [
                    ("Bruto", _fmt_brl(snapshot.get("valor_bruto"))),
                    ("(−) Mídia realizada", _fmt_brl(snapshot.get("gasto_midia_realizado"))),
                    ("Margem CC", _fmt_brl(snapshot.get("margem_cc"))),
                    ("Tech fee", _fmt_brl(snapshot.get("tech_fee"))),
                    ("Comissão de vendas", _fmt_brl(snapshot.get("com_vendas"))),
                    ("PL incentivos", _fmt_brl(snapshot.get("pl_incentivos"))),
                    ("Impostos", _fmt_brl(snapshot.get("impostos"))),
                    ("Resultado", _fmt_brl(snapshot.get("margem_liquida_calculada"))),
                    ("Status financeiro", _texto(snapshot.get("status_financeiro_label")) or "—"),
                ],
                styles,
            )
        )
        pendencias = snapshot.get("pendencias") or []
        story.append(Paragraph("Pendências", styles["heading"]))
        if pendencias:
            for item in pendencias:
                story.append(Paragraph(f"• {escape(item.get('mensagem') or item.get('codigo') or '')}", styles["body"]))
        else:
            story.append(Paragraph("Nenhuma pendência bloqueante no momento da emissão.", styles["muted"]))
        drive = snapshot.get("drive") or {}
        links = [
            ("Pasta principal", drive.get("principal")),
            ("Pasta financeiro", drive.get("financeiro")),
            ("Arquivos assinados", drive.get("assinados")),
        ]
        links = [(label, url) for label, url in links if url]
        if links:
            story.append(Paragraph("Pastas Drive", styles["heading"]))
            story.append(self._kv_table(links, styles))
        if snapshot.get("observacoes_operacao"):
            story.append(Paragraph("Observações da operação", styles["heading"]))
            story.append(Paragraph(escape(_texto(snapshot.get("observacoes_operacao"))), styles["body"]))
        self._build(buffer, story)

    def _build(self, buffer, story):
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=14 * mm,
            bottomMargin=16 * mm,
            title="Documento de fechamento de PI",
            author="CentralComm",
        )
        doc.build(story)
        buffer.seek(0)
