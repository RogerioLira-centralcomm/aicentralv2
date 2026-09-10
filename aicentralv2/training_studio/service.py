"""Regras de negócio do Studio de Treinamentos."""

from ..creative_modeling_fx import brl_from_usd, usd_brl_rate
from .agenda import CHANNELS
from .extract import extract_page, summarize_page
from .orchestrator import run_chat
from .prompts import style_prompt
from .providers import TrainingProviders
from .repository import TrainingStudioRepository
from .research import fetch_logo_url, render_channel_html, replace_channel_block, research_channel
from .storage import TrainingAssetStorage
from .tools import edit_text, generate_image, research_market


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
        mercado = next((item for item in sessoes if item.get("slug") == "mercado-canais"), None)
        fontes = self.repository.list_fontes(mercado["id"]) if mercado else []
        return {
            "treinamento": treinamento,
            "sessao": self._public_sessao(sessao),
            "sessoes": sessoes,
            "mensagens": self.repository.list_agent_messages(sessao_id),
            "consumo_treinamento": annotate_consumo(
                self.repository.consumo_treinamento(treinamento_id)
            ),
            "pesquisa_pendente": not any(
                (item.get("url") or "").startswith("canal:") for item in fontes
            ),
        }

    def enrich_channels(self, treinamento_id):
        sessao = self.repository.get_sessao_by_slug(treinamento_id, "mercado-canais")
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

    def consumo(self, sessao_id):
        return annotate_consumo(self.repository.consumo(sessao_id))

    def list_imagens(self, sessao_id):
        return self.repository.list_imagens(sessao_id)

    def import_url(self, sessao_id, url):
        sessao = self.repository.get_sessao(sessao_id)
        page = extract_page(url)
        summary = summarize_page(self.providers, page)
        self._record_costs(
            sessao["treinamento_id"],
            sessao_id,
            [
                {
                    "kind": "resumo_url",
                    "model": summary.get("model"),
                    "usage": summary.get("usage") or {},
                    "cost_usd": summary.get("cost_usd") or 0,
                }
            ],
        )
        fonte = self.repository.add_fonte(
            sessao_id,
            page["url"],
            page["titulo"],
            summary.get("content") or "",
        )
        return {
            "fonte": fonte,
            "consumo": self.consumo(sessao_id),
        }

    def apply_fonte(self, sessao_id, fonte_id):
        return self.repository.apply_fonte(sessao_id, fonte_id)

    def run_action(self, sessao_id, action, selection="", document="", instrucao="", prompt=""):
        sessao = self.repository.get_sessao(sessao_id)
        fontes = self.repository.context_fontes(sessao_id)
        guia = sessao.get("guia_estilo") or {}
        if action == "pesquisar":
            result = research_market(self.providers, instrucao or selection, selection)
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
                }
            ],
        )
        self.repository.add_agent_message(
            sessao_id,
            "user",
            instrucao or prompt or selection or action,
            tool_used=result.get("tool_used"),
        )
        message = self.repository.add_agent_message(
            sessao_id,
            "assistant",
            result.get("content") or "",
            tool_used=result.get("tool_used"),
            display={"acao": action, "image": result.get("image")},
        )
        return {
            "content": result.get("content") or "",
            "tool_used": result.get("tool_used"),
            "acao": action,
            "image": result.get("image"),
            "prompt": result.get("prompt") or style_prompt(guia),
            "message": message,
            "consumo": self.consumo(sessao_id),
        }

    def run_chat(self, sessao_id, message, selection="", document=""):
        sessao = self.repository.get_sessao(sessao_id)
        fontes = self.repository.context_fontes(sessao_id)
        result = run_chat(
            self.providers,
            message,
            selection,
            document,
            fontes,
            sessao.get("guia_estilo") or {},
        )
        payload = result.get("payload") or {}
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
        self.repository.add_agent_message(sessao_id, "user", message)
        saved = self.repository.add_agent_message(
            sessao_id,
            "assistant",
            result.get("content") or "",
            tool_used=result.get("tool_used"),
            display={"image": (payload or {}).get("image")},
        )
        return {
            "content": result.get("content") or "",
            "tool_used": result.get("tool_used"),
            "image": image or (payload or {}).get("image"),
            "message": saved,
            "consumo": self.consumo(sessao_id),
        }

    def _record_costs(self, treinamento_id, sessao_id, entries):
        rate, source = usd_brl_rate()
        for entry in entries or []:
            cost_usd = float(entry.get("cost_usd") or 0)
            self.repository.add_ledger(
                treinamento_id,
                sessao_id,
                entry.get("kind") or "texto",
                entry.get("model"),
                entry.get("usage") or {},
                cost_usd,
                brl_from_usd(cost_usd, rate),
                rate,
                source,
            )

    def _public_sessao(self, sessao):
        data = dict(sessao)
        data["consumo"] = annotate_consumo(sessao.get("consumo") or {})
        data["style_prompt"] = style_prompt(sessao.get("guia_estilo") or {})
        data["mensagens"] = self.repository.list_agent_messages(sessao["id"])
        return data
