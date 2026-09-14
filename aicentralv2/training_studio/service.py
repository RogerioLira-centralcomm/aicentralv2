"""Regras de negócio do Studio de Treinamentos."""

from html import escape as html_escape

from ..creative_modeling_fx import brl_from_usd, usd_brl_rate
from .agenda import CHANNELS, ILLUSTRATION_SESSIONS, SESSIONS
from .extract import extract_pdf_text, ingest_url
from .import_plan import build_import_sessions, preview_import_plan
from .orchestrator import run_chat
from .prompts import style_prompt
from .providers import TrainingProviders
from .repository import TrainingNotFoundError, TrainingStudioRepository
from .research import fetch_logo_url, render_channel_html, replace_channel_block, research_channel
from .slides import deck_from_sessao
from .youtube import parse_youtube_id
from .storage import TrainingAssetStorage
from .tools import (
    classify_attachment,
    compose_slide,
    edit_text,
    format_for_session,
    generate_image,
    parse_classification,
    research_market,
)


def format_brl(value):
    number = float(value or 0)
    formatted = f"{number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def annotate_consumo(consumo):
    data = dict(consumo or {})
    data["cost_brl"] = float(data.get("cost_brl") or 0)
    data["cost_usd"] = float(data.get("cost_usd") or 0)
    data["cost_brl_label"] = format_brl(data["cost_brl"])
    by_kind = {}
    for kind, item in (data.get("by_kind") or {}).items():
        by_kind[kind] = {
            "cost_usd": float(item.get("cost_usd") or 0),
            "cost_brl": float(item.get("cost_brl") or 0),
            "cost_brl_label": format_brl(item.get("cost_brl") or 0),
        }
    data["by_kind"] = by_kind
    return data


class TrainingStudioService:
    def __init__(self, repository=None, providers=None, storage=None):
        self.repository = repository or TrainingStudioRepository()
        self.providers = providers or TrainingProviders()
        self.storage = storage or TrainingAssetStorage()

    def bootstrap(self, created_by=None):
        treinamento_id, sessao_id = self.repository.ready(created_by=created_by)
        sessao = self.repository.get_sessao(sessao_id)
        treinamento = self.repository.get_treinamento(treinamento_id)
        sessoes = self.repository.list_sessoes(treinamento_id)
        return {
            "treinamento": treinamento,
            "sessao": self._public_sessao(sessao),
            "sessoes": sessoes,
            "mensagens": self.repository.list_agent_messages(sessao_id),
            "importacoes": self.repository.list_importacoes(treinamento_id),
            "consumo_treinamento": annotate_consumo(
                self.repository.consumo_treinamento(treinamento_id)
            ),
            "pesquisa_pendente": False,
        }

    def enrich_channels(self, treinamento_id):
        sessao = self.repository.get_sessao_by_slug(treinamento_id, "mapa-canais")
        html = sessao.get("conteudo_html") or ""
        existentes = {
            (item.get("url") or "")
            for item in self.repository.list_fontes(sessao["id"])
        }
        enriched = 0
        for channel in CHANNELS:
            marker = f"canal:{channel['key']}"
            if marker in existentes:
                continue
            try:
                researched = research_channel(self.providers, channel)
            except Exception:
                researched = {
                    "resumo": "",
                    "model": None,
                    "usage": {},
                    "cost_usd": 0,
                }
            logo_url = None
            try:
                remote = fetch_logo_url(channel)
                if str(remote).startswith("/static/"):
                    logo_url = remote
                else:
                    logo_url = self.storage.save_remote_logo(remote)
                self.repository.add_imagem(
                    sessao["id"], logo_url, f"Logo {channel['name']}"
                )
            except Exception:
                logo_url = None
            block = render_channel_html(channel, researched.get("resumo"), logo_url)
            html = replace_channel_block(html, channel["key"], block)
            fonte = self.repository.add_fonte(
                sessao["id"],
                marker,
                channel["name"],
                researched.get("resumo") or "",
            )
            self.repository.apply_fonte(sessao["id"], fonte["id"])
            self._record_costs(
                treinamento_id,
                sessao["id"],
                [
                    {
                        "kind": "pesquisa",
                        "model": researched.get("model"),
                        "usage": researched.get("usage") or {},
                        "cost_usd": researched.get("cost_usd") or 0,
                    }
                ],
            )
            enriched += 1
        updated = self.repository.update_sessao(sessao["id"], {"conteudo_html": html})
        return {
            "sessao": self._public_sessao(updated),
            "enriquecidos": enriched,
            "consumo": self.consumo(sessao["id"]),
            "consumo_treinamento": annotate_consumo(
                self.repository.consumo_treinamento(treinamento_id)
            ),
        }

    def get_treinamento(self, treinamento_id):
        return self.repository.get_treinamento(treinamento_id)

    def update_treinamento(self, treinamento_id, data):
        return self.repository.update_treinamento(treinamento_id, data)

    def get_sessao(self, sessao_id):
        return self._public_sessao(self.repository.get_sessao(sessao_id))

    def update_sessao(self, sessao_id, data):
        return self._public_sessao(self.repository.update_sessao(sessao_id, data))

    def create_sessao(self, treinamento_id, data):
        created = self.repository.create_sessao(treinamento_id, data)
        return {
            "sessao": self._public_sessao(created),
            "sessoes": self.repository.list_sessoes(treinamento_id),
        }

    def consumo(self, sessao_id):
        return annotate_consumo(self.repository.consumo(sessao_id))

    def list_imagens(self, sessao_id):
        return self.repository.list_imagens(sessao_id)

    def import_url(self, sessao_id, url):
        sessao = self.repository.get_sessao(sessao_id)
        ingested = ingest_url(url, self.providers, self.storage)
        self._record_costs(sessao["treinamento_id"], sessao_id, ingested.get("costs") or [])
        resumo = ingested.get("resumo") or ingested.get("transcript") or ""
        frames = [
            {key: value for key, value in frame.items() if key != "data_url"}
            for frame in (ingested.get("frames") or [])
        ]
        importacao = self.repository.add_importacao(
            sessao["treinamento_id"],
            sessao_id,
            {
                **ingested,
                "video_id": parse_youtube_id(ingested.get("url") or url),
                "frames": frames,
            },
        )
        fonte = self.repository.add_fonte(
            sessao_id,
            ingested.get("url") or url,
            ingested.get("titulo") or url,
            resumo,
            kind=ingested.get("kind") or "page",
            importacao_id=importacao.get("id"),
            payload={
                "autor": ingested.get("autor") or "",
                "duracao_s": ingested.get("duracao_s") or 0,
                "transcript_source": ingested.get("transcript_source") or "",
            },
        )
        imagens = []
        for frame in frames:
            asset_url = frame.get("asset_url")
            if not asset_url:
                continue
            image = self.repository.add_imagem(
                sessao_id,
                asset_url,
                f"{ingested.get('titulo') or 'vídeo'} · {frame.get('label') or 'quadro'}",
                kind="quadro",
                importacao_id=importacao.get("id"),
                meta={
                    "label": frame.get("label") or "",
                    "second": frame.get("second") or 0,
                },
            )
            frame["image_id"] = image.get("id")
            imagens.append(image)
        return {
            "fonte": fonte,
            "importacao": importacao,
            "kind": ingested.get("kind") or "page",
            "titulo": ingested.get("titulo") or "",
            "autor": ingested.get("autor") or "",
            "url": ingested.get("url") or url,
            "resumo": resumo,
            "transcript": ingested.get("transcript") or "",
            "transcript_source": ingested.get("transcript_source") or "",
            "descricao": ingested.get("descricao") or "",
            "briefing_html": ingested.get("briefing_html") or "",
            "frames": frames,
            "hero_url": ingested.get("hero_url") or "",
            "embed_url": ingested.get("embed_url") or "",
            "duracao_s": ingested.get("duracao_s") or 0,
            "pipeline": ingested.get("pipeline") or [],
            "imagens": imagens,
            "plan": preview_import_plan(ingested),
            "consumo": self.consumo(sessao_id),
        }

    def apply_fonte(self, sessao_id, fonte_id):
        return self.repository.apply_fonte(sessao_id, fonte_id)

    def apply_import(self, sessao_id, fonte_id, data=None):
        data = data or {}
        fonte = self.repository.apply_fonte(sessao_id, fonte_id)
        sessao = self.repository.get_sessao(sessao_id)
        importacao = self.repository.get_importacao(
            data.get("importacao_id") or fonte.get("importacao_id")
        )
        packed = _merge_import_payload(data, importacao, fonte)
        mode = str(data.get("mode") or ("sessions" if data.get("insert_html") else "context"))
        frame_urls = [
            url
            for url in (data.get("frame_urls") or packed.get("frame_urls") or [])
            if isinstance(url, str) and url.startswith(("/static/", "https://"))
        ]
        if mode == "sessions":
            created = self._materialize_import_sessions(
                sessao, fonte, packed, frame_urls, importacao
            )
            first = created[0] if created else self._public_sessao(sessao)
            self.repository.update_importacao(
                (importacao or {}).get("id"),
                {
                    "status": "applied_sessions",
                    "applied_mode": "sessions",
                    "applied": True,
                    "sessao_id": first.get("id") or sessao_id,
                },
            )
            return {
                "fonte": fonte,
                "apply": True,
                "mode": "sessions",
                "sessao": first,
                "criadas": created,
                "sessoes": self.repository.list_sessoes(sessao["treinamento_id"]),
                "fontes": self.repository.list_fontes(first.get("id") or sessao_id),
                "imagens": self.repository.list_imagens(first.get("id") or sessao_id),
                "consumo": self.consumo(sessao_id),
            }
        self.repository.update_importacao(
            (importacao or {}).get("id"),
            {
                "status": "applied_context",
                "applied_mode": "context",
                "applied": True,
                "sessao_id": sessao_id,
            },
        )
        return {
            "fonte": fonte,
            "apply": False,
            "mode": "context",
            "sessao": None,
            "sessoes": self.repository.list_sessoes(sessao["treinamento_id"]),
            "fontes": self.repository.list_fontes(sessao_id),
            "imagens": self.repository.list_imagens(sessao_id),
            "consumo": self.consumo(sessao_id),
        }

    def _materialize_import_sessions(self, sessao, fonte, data, frame_urls, importacao=None):
        importacao_id = (importacao or {}).get("id") or fonte.get("importacao_id")
        plans = build_import_sessions(
            {
                "titulo": data.get("titulo") or fonte.get("titulo") or "Fonte",
                "autor": data.get("autor") or "",
                "url": data.get("url") or fonte.get("url") or "",
                "briefing_html": data.get("briefing_html") or "",
                "transcript": data.get("transcript") or "",
                "descricao": data.get("descricao") or "",
                "duracao_s": data.get("duracao_s") or 0,
                "hero_url": data.get("hero_url") or (frame_urls[0] if frame_urls else ""),
            },
            frame_urls,
        )
        created = []
        after = sessao.get("slug") or ""
        for plan in plans:
            item = self.repository.create_sessao(
                sessao["treinamento_id"],
                {
                    "titulo": plan["titulo"],
                    "tipo": plan.get("tipo") or "fonte",
                    "origem": "fonte",
                    "importacao_id": importacao_id,
                    "conteudo_html": plan.get("conteudo_html") or "",
                    "notas_instrutor": plan.get("notas_instrutor") or {},
                    "apos_slug": after,
                },
            )
            copied = self.repository.add_fonte(
                item["id"],
                fonte.get("url") or "",
                fonte.get("titulo") or plan["titulo"],
                fonte.get("resumo") or "",
                kind=fonte.get("kind") or "page",
                importacao_id=importacao_id,
                payload=fonte.get("payload") or {},
            )
            self.repository.apply_fonte(item["id"], copied["id"])
            for url in frame_urls[:6]:
                self.repository.add_imagem(
                    item["id"],
                    url,
                    plan["titulo"],
                    kind="quadro",
                    importacao_id=importacao_id,
                )
            created.append(self._public_sessao(item))
            after = item.get("slug") or after
        return created

    def project_slug(self, slug):
        from .slides import session_deck

        if not slug:
            from .slides import morning_deck

            return morning_deck(), None
        try:
            return session_deck(slug), None
        except KeyError:
            pass
        treinamento_id, _sessao_id = self.repository.ready()
        try:
            sessao = self.repository.get_sessao_by_slug(treinamento_id, slug)
        except TrainingNotFoundError:
            return None, None
        return deck_from_sessao(sessao), sessao

    def run_action(
        self,
        sessao_id,
        action,
        selection="",
        document="",
        instrucao="",
        prompt="",
        buscar_web=False,
        page_html="",
        surface="",
    ):
        sessao = self.repository.get_sessao(sessao_id)
        fontes = self._agent_fontes(sessao)
        guia = sessao.get("guia_estilo") or {}
        if action in {"gerar_slide", "reorganizar_slide"}:
            result = compose_slide(
                self.providers,
                instrucao or selection,
                page_html,
                "",
                instrucao,
                "gerar" if action == "gerar_slide" else "reorganizar",
            )
        elif action == "pesquisar":
            result = research_market(
                self.providers, instrucao or selection, selection, buscar_web=buscar_web
            )
            self._persist_research_fontes(sessao_id, instrucao or selection, result)
        elif action == "formatar":
            result = format_for_session(
                self.providers, instrucao or selection, "", document
            )
        elif action == "gerar_imagem":
            result = generate_image(
                self.providers, prompt or instrucao or selection, guia, selection
            )
            if result.get("b64_json"):
                asset_url = self.storage.save_generated_base64(
                    result["b64_json"], result.get("output_format") or "png"
                )
                image = self.repository.add_imagem(
                    sessao_id, asset_url, result.get("prompt") or prompt
                )
                result["image"] = image
                result["content"] = asset_url
        elif action in {"reescrever", "expandir", "resumir", "ajustar_tom", "continuar"}:
            result = edit_text(
                self.providers, action, selection, document, fontes, instrucao
            )
        else:
            raise ValueError("Ação não suportada.")
        self._record_costs(
            sessao["treinamento_id"],
            sessao_id,
            [
                {
                    "kind": result.get("kind") or "texto",
                    "model": result.get("model"),
                    "usage": result.get("usage") or {},
                    "cost_usd": result.get("cost_usd") or 0,
                    "provider": result.get("provider"),
                }
            ],
        )
        self.repository.add_agent_message(
            sessao_id,
            "user",
            instrucao or prompt or selection or action,
            tool_used=result.get("tool_used"),
            surface=surface,
            selection=selection,
            importacao_id=sessao.get("importacao_id"),
        )
        message = self.repository.add_agent_message(
            sessao_id,
            "assistant",
            result.get("content") or "",
            tool_used=result.get("tool_used"),
            display={
                "acao": action,
                "image": result.get("image"),
                "surface": surface,
                "apply": bool(result.get("apply")),
                "modo": result.get("modo") or "",
            },
            surface=surface,
            selection=selection,
            importacao_id=sessao.get("importacao_id"),
        )
        return {
            "content": result.get("content") or "",
            "tool_used": result.get("tool_used"),
            "acao": action,
            "image": result.get("image"),
            "prompt": result.get("prompt") or style_prompt(guia),
            "message": message,
            "consumo": self.consumo(sessao_id),
            "apply": bool(result.get("apply")),
            "html": result.get("html") or result.get("content") or "",
            "modo": result.get("modo") or "anexar",
            "fontes": self.repository.list_fontes(sessao_id),
        }

    def run_chat(self, sessao_id, message, selection="", document="", buscar_web=False, page_html="", surface=""):
        sessao = self.repository.get_sessao(sessao_id)
        fontes = self._agent_fontes(sessao)
        history = self.repository.list_agent_messages(sessao_id, limit=8)
        result = run_chat(
            self.providers,
            message,
            selection,
            document,
            fontes,
            sessao.get("guia_estilo") or {},
            buscar_web=buscar_web,
            page_html=page_html,
            surface=surface,
            history=history,
        )
        payload = result.get("payload") or {}
        created = None
        if (result.get("tool_used") == "pesquisa") or (payload.get("kind") == "pesquisa"):
            self._persist_research_fontes(sessao_id, message, payload or result)
        if payload.get("create_session"):
            spec = dict(payload["create_session"])
            if sessao.get("importacao_id") and not spec.get("importacao_id"):
                spec["importacao_id"] = sessao["importacao_id"]
                spec["origem"] = spec.get("origem") or "fonte"
            created = self.create_sessao(sessao["treinamento_id"], spec)
        if payload.get("b64_json"):
            asset_url = self.storage.save_generated_base64(
                payload["b64_json"], payload.get("output_format") or "png"
            )
            image = self.repository.add_imagem(
                sessao_id, asset_url, payload.get("prompt") or message
            )
            payload["image"] = image
            result["content"] = result.get("content") or asset_url
        else:
            image = None
        self._record_costs(sessao["treinamento_id"], sessao_id, result.get("costs") or [])
        self.repository.add_agent_message(
            sessao_id,
            "user",
            message,
            surface=surface,
            selection=selection,
            importacao_id=sessao.get("importacao_id"),
        )
        saved = self.repository.add_agent_message(
            sessao_id,
            "assistant",
            result.get("content") or "",
            tool_used=result.get("tool_used"),
            display={
                "image": (payload or {}).get("image"),
                "surface": surface,
                "apply": bool(result.get("apply") or payload.get("apply")),
                "modo": payload.get("modo") or "",
            },
            surface=surface,
            selection=selection,
            importacao_id=sessao.get("importacao_id"),
        )
        return {
            "content": result.get("content") or "",
            "tool_used": result.get("tool_used"),
            "image": image or (payload or {}).get("image"),
            "message": saved,
            "consumo": self.consumo(sessao_id),
            "apply": bool(result.get("apply") or payload.get("apply")),
            "html": payload.get("html") or "",
            "modo": payload.get("modo") or "anexar",
            "sessao": (created or {}).get("sessao"),
            "sessoes": (created or {}).get("sessoes"),
            "fontes": self.repository.list_fontes(sessao_id),
        }

    def _persist_research_fontes(self, sessao_id, query, result):
        citations = result.get("citations") or []
        title = (query or "Pesquisa")[:300]
        resumo = (result.get("content") or "")[:800]
        if citations:
            for url in citations[:8]:
                self.repository.ensure_fonte(sessao_id, url, title, resumo, incluido=True)
            return
        self.repository.ensure_fonte(
            sessao_id,
            f"pesquisa:{title[:160]}",
            title,
            (result.get("content") or "")[:4000],
            incluido=True,
        )

    def upload_anexo(self, sessao_id, filename, content, mime=""):
        sessao = self.repository.get_sessao(sessao_id)
        asset_url = self.storage.save_upload(filename, content, mime)
        extracted = ""
        if (mime or "").startswith("image/"):
            extracted = f"Imagem enviada: {filename}"
        elif mime == "application/pdf" or str(filename).lower().endswith(".pdf"):
            extracted = extract_pdf_text(content)
        classified = classify_attachment(self.providers, extracted, filename)
        self._record_costs(
            sessao["treinamento_id"],
            sessao_id,
            [
                {
                    "kind": "resumo_url",
                    "model": classified.get("model"),
                    "usage": classified.get("usage") or {},
                    "cost_usd": classified.get("cost_usd") or 0,
                    "provider": classified.get("provider"),
                }
            ],
        )
        parsed = classified.get("classificacao") or parse_classification(
            classified.get("content")
        )
        target = sessao
        slug = parsed.get("sessao_slug") or ""
        if slug and slug != sessao.get("slug"):
            try:
                target = self.repository.get_sessao_by_slug(
                    sessao["treinamento_id"], slug
                )
            except TrainingNotFoundError:
                target = sessao
        fonte = self.repository.add_fonte(
            target["id"],
            f"anexo:{asset_url}",
            filename,
            extracted[:4000],
        )
        if (mime or "").startswith("image/"):
            self.repository.add_imagem(target["id"], asset_url, filename)
        html = parsed.get("html") or ""
        if (mime or "").startswith("image/") and asset_url:
            safe_url = html_escape(asset_url, quote=True)
            figure = (
                f'<figure class="ts-inline-image"><img src="{safe_url}" alt=""></figure>'
            )
            html = figure + html
        bloco = html_escape(parsed.get("bloco") or "dado", quote=True)
        if html:
            html = f'<section class="ts-block" data-bloco="{bloco}">{html}</section>'
        applied = False
        if html:
            updated = self.repository.update_sessao(
                target["id"],
                {"conteudo_html": (target.get("conteudo_html") or "") + html},
            )
            target = updated
            applied = target["id"] == sessao_id
        return {
            "fonte": fonte,
            "asset_url": asset_url,
            "extracted": extracted,
            "classificacao": parsed.get("resumo") or classified.get("content") or "",
            "html": html,
            "bloco": parsed.get("bloco") or "dado",
            "sessao_slug": target.get("slug"),
            "apply": applied,
            "sessao": self._public_sessao(target) if applied else None,
            "fontes": self.repository.list_fontes(sessao_id),
            "consumo": self.consumo(sessao_id),
        }

    def generate_illustrations(self, treinamento_id):
        generated = []
        for item in SESSIONS:
            if item["slug"] not in ILLUSTRATION_SESSIONS or not item.get("illustration"):
                continue
            sessao = self.repository.get_sessao_by_slug(treinamento_id, item["slug"])
            guia = sessao.get("guia_estilo") or {}
            result = generate_image(
                self.providers, item["illustration"], guia
            )
            if result.get("b64_json"):
                asset_url = self.storage.save_generated_base64(
                    result["b64_json"], result.get("output_format") or "png"
                )
                image = self.repository.add_imagem(
                    sessao["id"], asset_url, result.get("prompt") or item["illustration"]
                )
                html = sessao.get("conteudo_html") or ""
                filled = _fill_art_slot(html, asset_url)
                if filled:
                    self.repository.update_sessao(sessao["id"], {"conteudo_html": filled})
                generated.append(image)
            self._record_costs(
                treinamento_id,
                sessao["id"],
                [
                    {
                        "kind": "imagem",
                        "model": result.get("model"),
                        "usage": result.get("usage") or {},
                        "cost_usd": result.get("cost_usd") or 0,
                        "provider": result.get("provider"),
                    }
                ],
            )
        return {
            "imagens": generated,
            "sessoes": self.repository.list_sessoes(treinamento_id),
            "consumo_treinamento": annotate_consumo(
                self.repository.consumo_treinamento(treinamento_id)
            ),
        }

    def _record_costs(self, treinamento_id, sessao_id, entries):
        rate, source = usd_brl_rate()
        for entry in entries or []:
            cost_usd = float(entry.get("cost_usd") or 0)
            kind = str(entry.get("kind") or "texto")
            if kind not in {"texto", "pesquisa", "imagem", "resumo_url", "visao_video", "slide"}:
                kind = "texto"
            self.repository.add_ledger(
                treinamento_id,
                sessao_id,
                kind,
                entry.get("model"),
                entry.get("usage") or {},
                cost_usd,
                brl_from_usd(cost_usd, rate),
                rate,
                source,
                entry.get("provider") or "openai",
            )

    def _agent_fontes(self, sessao):
        fontes = list(self.repository.context_fontes(sessao["id"]))
        importacao = sessao.get("importacao")
        if not importacao:
            return fontes
        snippet = (
            importacao.get("interpretacao")
            or importacao.get("texto")
            or importacao.get("transcript")
            or ""
        )[:1200]
        attached = False
        for item in fontes:
            if item.get("importacao_id") == importacao.get("id"):
                if snippet and len(str(item.get("resumo") or "")) < 80:
                    item["resumo"] = snippet
                attached = True
        if not attached:
            fontes.insert(
                0,
                {
                    "titulo": importacao.get("titulo") or "Importação",
                    "url": importacao.get("url") or "",
                    "resumo": snippet,
                    "kind": importacao.get("kind") or "page",
                    "importacao_id": importacao.get("id"),
                },
            )
        return fontes

    def _public_sessao(self, sessao):
        data = dict(sessao)
        data["consumo"] = annotate_consumo(sessao.get("consumo") or {})
        data["style_prompt"] = style_prompt(sessao.get("guia_estilo") or {})
        data["mensagens"] = self.repository.list_agent_messages(sessao["id"])
        return data


def _merge_import_payload(data, importacao, fonte):
    data = data or {}
    importacao = importacao or {}
    fonte = fonte or {}
    frames = importacao.get("frames") or []
    frame_urls = [
        item.get("asset_url") if isinstance(item, dict) else item
        for item in frames
    ]
    return {
        "titulo": data.get("titulo") or importacao.get("titulo") or fonte.get("titulo") or "",
        "autor": data.get("autor") or importacao.get("autor") or "",
        "url": data.get("url") or importacao.get("url") or fonte.get("url") or "",
        "briefing_html": data.get("briefing_html") or importacao.get("briefing_html") or "",
        "transcript": data.get("transcript") or importacao.get("transcript") or "",
        "descricao": data.get("descricao") or importacao.get("descricao") or "",
        "duracao_s": data.get("duracao_s") or importacao.get("duracao_s") or 0,
        "hero_url": data.get("hero_url") or importacao.get("hero_url") or "",
        "frame_urls": [url for url in frame_urls if url],
    }


def _fill_art_slot(html, url):
    empty = '<figure class="ts-page-art" data-slot="ilustracao"></figure>'
    filled = (
        f'<figure class="ts-page-art" data-slot="ilustracao">'
        f'<img src="{html_escape(url, quote=True)}" alt=""></figure>'
    )
    text = html or ""
    if empty in text:
        return text.replace(empty, filled, 1)
    if "ts-page-art" in text:
        return None
    return (
        f'<article class="ts-page" data-layout="split">'
        f'<div class="ts-page-copy"></div>{filled}</article>'
        + text
    )
