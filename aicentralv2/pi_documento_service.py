"""Cartas de fechamento do PI — comprovação, bonificação e passagem."""

from __future__ import annotations

import base64
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
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


logger = logging.getLogger(__name__)

TIPOS = ("fechamento", "comprovacao", "bonificacao", "passagem")
VARIANTES = ("cliente", "agencia", "interno")

CATALOGO_AGENCIA = (
    {
        "tipo": "comprovacao",
        "variante": "agencia",
        "label": "Comprovação de veiculação",
        "proposito": "Carta à agência com o contratado e o que cada campanha entregou.",
    },
    {
        "tipo": "bonificacao",
        "variante": "agencia",
        "label": "Carta de bonificação",
        "proposito": "Incentivo apurado para a agência neste PI.",
        "requer_incentivo": True,
    },
)

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


def _fmt_vol(value):
    number = _num(value)
    if abs(number - round(number)) < 1e-9:
        return f"{int(round(number)):,}".replace(",", ".")
    return f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _contato(snapshot):
    dest = snapshot.get("contato_agencia") or {}
    return {
        "id": dest.get("id"),
        "nome": _texto(dest.get("nome")),
        "email": _texto(dest.get("email")),
    }


def _tratamento(snapshot):
    dest = _contato(snapshot)
    if dest["nome"]:
        return f"Prezado(a) {dest['nome'].split()[0]}"
    agencia = _texto(snapshot.get("agencia_nome"))
    if agencia:
        return f"Prezada equipe da {agencia}"
    return "Prezados"


def mensagem_padrao(tipo, snapshot):
    dest = _contato(snapshot)
    agencia = _texto(snapshot.get("agencia_nome")) or "a agência"
    codigo = _texto(snapshot.get("codigo_pi") or snapshot.get("id_pi")) or "este PI"
    cliente = _texto(snapshot.get("cliente_nome")) or "o anunciante"
    contr = _fmt_vol(snapshot.get("objetivo_contratado"))
    ating = _fmt_vol(snapshot.get("objetivo_atingido"))
    pct = _fmt_pct(snapshot.get("pct_objetivo"))
    aos_cuidados = dest["nome"] or agencia
    if tipo == "bonificacao":
        return (
            f"{_tratamento(snapshot)},\n\n"
            f"Aos cuidados de {aos_cuidados}, segue a carta de bonificação do PI {codigo} "
            f"({cliente}).\n\n"
            f"O PL de incentivos apurado é {_fmt_brl(snapshot.get('pl_incentivos'))}.\n\n"
            f"Atenciosamente,\nCentralComm"
        )
    return (
        f"{_tratamento(snapshot)},\n\n"
        f"Aos cuidados de {aos_cuidados}, encaminhamos a comprovação de veiculação "
        f"do PI {codigo}, anunciante {cliente}.\n\n"
        f"As campanhas entregaram {ating} de {contr} contratados ({pct}). "
        f"O detalhe por campanha está neste documento.\n\n"
        f"Atenciosamente,\nCentralComm"
    )


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
        cartas = snapshot.get("cartas") or {}
        dest = _contato(snapshot)
        persistido = bool(snapshot.get("persistido"))
        documentos = []
        for item in CATALOGO_AGENCIA:
            if item.get("requer_incentivo") and not _tem_incentivo(snapshot):
                continue
            salvo = cartas.get(item["tipo"]) or {}
            documentos.append(
                {
                    **item,
                    "mensagem": _texto(salvo.get("mensagem")) or mensagem_padrao(item["tipo"], snapshot),
                    "destinatario": dest,
                    "enviado_em": salvo.get("enviado_em"),
                    "enviado_para": salvo.get("destinatario_nome") or dest.get("nome"),
                    "pode_enviar": persistido and bool(dest.get("email")),
                    "pode_gerar": True,
                }
            )
        return documentos

    def gerar(self, id_pi, tipo, variante="agencia", id_campanha=None, mensagem=None):
        tipo = str(tipo or "").strip()
        variante = str(variante or "agencia").strip()
        if tipo not in TIPOS:
            raise DocumentoIndisponivelError("Tipo de documento inválido.")
        if variante not in VARIANTES:
            raise DocumentoIndisponivelError("Variante de documento inválida.")

        snapshot = self.fechamento.resultado(id_pi)
        if tipo == "fechamento" and not snapshot.get("persistido"):
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

        texto = _texto(mensagem) or mensagem_padrao(tipo, snapshot)
        buffer = BytesIO()
        if tipo == "fechamento":
            self._relatorio_fechamento(buffer, snapshot, variante)
        elif tipo == "comprovacao":
            self._comprovacao(buffer, snapshot, campanhas, texto)
        elif tipo == "bonificacao":
            self._bonificacao(buffer, snapshot, texto)
        else:
            self._passagem(buffer, snapshot)

        codigo = _slug(snapshot.get("codigo_pi") or f"pi-{id_pi}")
        nome = f"{codigo}-{tipo}-{variante}.pdf"
        return buffer.getvalue(), nome

    def enviar_para_assinatura(self, id_pi, tipo, mensagem=None, variante="agencia", autor_id=None):
        tipo = str(tipo or "").strip()
        if tipo not in {item["tipo"] for item in CATALOGO_AGENCIA}:
            raise DocumentoIndisponivelError("Este documento não vai para assinatura da agência.")
        snapshot = self.fechamento.resultado(id_pi)
        if not snapshot.get("persistido"):
            raise DocumentoIndisponivelError(
                "Envie o PI ao financeiro antes de solicitar a assinatura."
            )
        dest = _contato(snapshot)
        if not dest.get("email"):
            raise DocumentoIndisponivelError(
                "Cadastre o contato da agência no PI para enviar à assinatura."
            )
        texto = _texto(mensagem) or mensagem_padrao(tipo, snapshot)
        pdf, filename = self.gerar(id_pi, tipo, variante=variante, mensagem=texto)
        nome = dest.get("nome") or _texto(snapshot.get("agencia_nome")) or "Agência"
        html = self._email_html(texto)
        assunto = self._assunto(tipo, snapshot)
        resultado = self.fechamento.brevo.enviar_email(
            to_email=dest["email"],
            to_name=nome,
            subject=assunto,
            html_content=html,
            text_content=texto,
            attachments=[{"name": filename, "content": base64.b64encode(pdf).decode()}],
        )
        if not (resultado.get("success") or resultado.get("messageId")):
            raise DocumentoIndisponivelError(
                resultado.get("user_message")
                or resultado.get("error")
                or "Não foi possível enviar o documento."
            )
        self._registrar_envio(
            id_pi,
            tipo,
            assunto,
            {"nome_completo": nome, "email": dest["email"]},
            html,
            autor_id,
            resultado,
        )
        self.fechamento.registrar_documento(
            id_pi,
            tipo,
            {
                "mensagem": texto,
                "enviado_em": datetime.now(timezone.utc).isoformat(),
                "destinatario_nome": nome,
                "destinatario_email": dest["email"],
                "arquivo": filename,
            },
            autor_id=autor_id,
        )
        try:
            self.fechamento.repository.upsert_status(id_pi, "aguardando_assinatura", autor_id)
        except Exception:
            logger.exception("Não atualizou o status financeiro do PI %s após o envio.", id_pi)
        return {
            "tipo": tipo,
            "destinatario": {"nome": nome, "email": dest["email"]},
            "enviado": True,
        }

    def _assunto(self, tipo, snapshot):
        codigo = _texto(snapshot.get("codigo_pi") or snapshot.get("id_pi")) or "PI"
        if tipo == "bonificacao":
            return f"Carta de bonificação · PI {codigo} · assinatura"
        return f"Comprovação de veiculação · PI {codigo} · assinatura"

    def _email_html(self, mensagem):
        corpo = escape(mensagem or "").replace("\n", "<br/>")
        return (
            "<p>Segue o documento em anexo para assinatura.</p>"
            f"<p>{corpo}</p>"
        )

    def _registrar_envio(self, id_pi, tipo, assunto, dest, html, autor_id, resultado):
        repo = getattr(getattr(self.fechamento, "operacao", None), "repository", None)
        criar = getattr(repo, "criar_email_log", None)
        concluir = getattr(repo, "concluir_email_log", None)
        if not callable(criar):
            return
        try:
            log_id = criar(id_pi, f"documento_{tipo}", assunto, dest, html, autor_id)
            if callable(concluir) and log_id:
                concluir(log_id, resultado)
        except Exception:
            logger.exception("Não registrou o envio do documento %s do PI %s.", tipo, id_pi)

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

    def _destinatario_label(self, snapshot):
        dest = _contato(snapshot)
        if dest["nome"]:
            return f"Aos cuidados de {dest['nome']}"
        if _texto(snapshot.get("agencia_nome")):
            return f"Aos cuidados de {_texto(snapshot.get('agencia_nome'))}"
        return "Aos cuidados da agência"

    def _bloco_carta(self, story, styles, snapshot, mensagem):
        dest = _contato(snapshot)
        story.append(
            self._kv_table(
                [
                    ("Aos cuidados", dest["nome"] or _texto(snapshot.get("agencia_nome")) or "—"),
                    ("E-mail", dest["email"] or "—"),
                    ("Agência", _texto(snapshot.get("agencia_nome")) or "—"),
                    ("Anunciante", _texto(snapshot.get("cliente_nome")) or "—"),
                    ("PI", _texto(snapshot.get("codigo_pi")) or "—"),
                ],
                styles,
            )
        )
        story.append(Spacer(1, 4 * mm))
        for bloco in (mensagem or "").split("\n\n"):
            html = escape(bloco).replace("\n", "<br/>")
            if html.strip():
                story.append(Paragraph(html, styles["body"]))
                story.append(Spacer(1, 2 * mm))

    def _comprovacao(self, buffer, snapshot, campanhas, mensagem):
        styles = self._styles()
        story = []
        self._header(story, styles, "Comprovação de veiculação", snapshot, self._destinatario_label(snapshot))
        self._bloco_carta(story, styles, snapshot, mensagem)
        story.append(Paragraph("Contratado e entregue", styles["heading"]))
        if not campanhas:
            story.append(Paragraph("Nenhuma campanha neste PI.", styles["muted"]))
        else:
            rows = []
            for item in campanhas:
                rows.append(
                    [
                        _texto(item.get("nome_campanha")) or "—",
                        _texto(item.get("plataforma") or item.get("status_nome")) or "—",
                        _fmt_vol(item.get("obj_contratado")),
                        _fmt_vol(item.get("obj_atingido")),
                        _fmt_pct(item.get("pct_objetivo")),
                    ]
                )
            rows.append(
                [
                    "Total do PI",
                    "",
                    _fmt_vol(snapshot.get("objetivo_contratado")),
                    _fmt_vol(snapshot.get("objetivo_atingido")),
                    _fmt_pct(snapshot.get("pct_objetivo")),
                ]
            )
            story.append(
                self._grid_table(
                    ["Campanha", "Plataforma", "Contratado", "Entregue", "Entrega"],
                    rows,
                    styles,
                    [50 * mm, 28 * mm, 30 * mm, 30 * mm, 22 * mm],
                )
            )
        self._build(buffer, story)

    def _bonificacao(self, buffer, snapshot, mensagem):
        styles = self._styles()
        story = []
        self._header(story, styles, "Carta de bonificação", snapshot, self._destinatario_label(snapshot))
        self._bloco_carta(story, styles, snapshot, mensagem)
        story.append(Paragraph("Incentivo", styles["heading"]))
        story.append(
            self._kv_table(
                [
                    ("PL de incentivos", _fmt_brl(snapshot.get("pl_incentivos"))),
                    ("Entrega das campanhas", _fmt_pct(snapshot.get("pct_objetivo"))),
                ],
                styles,
            )
        )
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
