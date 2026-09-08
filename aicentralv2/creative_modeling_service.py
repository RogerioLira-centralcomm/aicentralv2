"""Regras de negócio e composição de prompts da Modelagem de Criativos."""

from datetime import date, datetime
from decimal import Decimal
import json
import os
import re
import secrets

from .creative_modeling_generation import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TEXT_MODEL,
    CreativeGenerationClient,
    build_higgsfield_payload,
)
from .creative_modeling_repository import (
    CreativeModelingRepository,
    CreativeNotFoundError,
)
from .creative_modeling_storage import CreativeAssetStorage


MOCKUPS = {
    "portal": (
        "Photorealistic mockup of a news/content portal on a desktop "
        "browser, article layout visible around the ad unit."
    ),
    "tv": (
        "Photorealistic mockup of a smart TV screen (16:9), living room, "
        "soft ambient lighting."
    ),
    "celular": (
        "Photorealistic mockup of a vertical mobile phone (iPhone 17 Pro), "
        "front-facing, no extra UI chrome."
    ),
    "tablet": (
        "Photorealistic mockup of a tablet in landscape orientation, "
        "generous margins."
    ),
}


def _text(value, field, required=False, max_length=None):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} deve ser texto.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} é obrigatório.")
    if max_length and len(value) > max_length:
        raise ValueError(f"{field} deve ter no máximo {max_length} caracteres.")
    return value or None


def _integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} inválido.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} inválido.") from exc
    if result <= 0:
        raise ValueError(f"{field} inválido.")
    return result


def _serialize(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


def _color(value, field):
    value = _text(value, field, max_length=20)
    if value and not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError(f"{field} deve usar o formato #RRGGBB.")
    return value


def _money(value, field="Orçamento"):
    try:
        result = Decimal(str(value if value not in (None, "") else "0"))
    except Exception as exc:
        raise ValueError(f"{field} inválido.") from exc
    if result < 0:
        raise ValueError(f"{field} não pode ser negativo.")
    return result.quantize(Decimal("0.000001"))


class CreativeModelingService:
    def __init__(self, repository=None, generator=None, storage=None):
        self.repository = repository or CreativeModelingRepository()
        self.generator = generator or CreativeGenerationClient()
        self.storage = storage or CreativeAssetStorage()

    def list_formats(self):
        return _serialize(self.repository.list_formats())

    def update_format_modeling(self, format_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("Corpo JSON inválido.")
        safe_area = payload.get("safe_area") or {}
        if not isinstance(safe_area, dict):
            raise ValueError("Área segura deve ser um objeto JSON.")
        data = {
            "safe_area": safe_area,
            "responsive_rules": _text(
                payload.get("responsive_rules"),
                "Regras responsivas",
                max_length=4000,
            ),
            "background_guidance": _text(
                payload.get("background_guidance"),
                "Orientação de background",
                max_length=8000,
            ),
            "foreground_guidance": _text(
                payload.get("foreground_guidance"),
                "Orientação de conteúdo",
                max_length=8000,
            ),
        }
        format_id = _integer(format_id, "Formato")
        self.repository.update_format_modeling(format_id, data)
        return {"id": format_id}

    def list_clients(self):
        return _serialize(self.repository.list_clients())

    def get_client(self, client_id):
        return _serialize(self.repository.get_client(_integer(client_id, "Cliente")))

    def create_client(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        logo_url = _text(payload.get("logo_url"), "URL do logo", max_length=2000)
        if logo_url and not logo_url.lower().startswith(("http://", "https://")):
            raise ValueError("URL do logo deve começar com http:// ou https://.")
        data = {
            "name": _text(
                payload.get("name"), "Nome do cliente", required=True, max_length=150
            ),
            "sector": _text(payload.get("sector"), "Setor", max_length=80),
            "tone_of_voice": _text(
                payload.get("tone_of_voice"), "Tom de voz", max_length=4000
            ),
            "logo_url": logo_url,
            "primary_color": _color(
                payload.get("primary_color"), "Cor primária"
            ),
            "secondary_color": _color(
                payload.get("secondary_color"), "Cor secundária"
            ),
            "price_policy": (
                "show_price" if payload.get("show_price") is True else "hide_price"
            ),
        }
        return {"id": self.repository.create_client(data)}

    def delete_client(self, client_id):
        client_id = _integer(client_id, "Cliente")
        client = self.repository.get_client(client_id)
        self.repository.delete_client(client_id)
        return client

    def set_client_logo(self, client_id, public_path):
        client_id = _integer(client_id, "Cliente")
        client = self.repository.get_client(client_id)
        self.repository.set_client_logo(client_id, public_path)
        return client.get("logo_upload_path")

    def list_campaigns(self):
        return _serialize(self.repository.list_campaigns())

    def create_campaign(self, payload):
        payload = payload if isinstance(payload, dict) else {}
        show_price = payload.get("show_price", False)
        if not isinstance(show_price, bool):
            raise ValueError("Exibir preço deve ser verdadeiro ou falso.")
        data = {
            "client_id": _integer(payload.get("client_id"), "Cliente"),
            "name": _text(
                payload.get("name"),
                "Nome da campanha",
                required=True,
                max_length=200,
            ),
            "objective": _text(
                payload.get("objective"), "Objetivo", max_length=120
            ),
            "campaign_text": _text(
                payload.get("campaign_text"),
                "Texto da campanha",
                max_length=12000,
            ),
            "cta_text": _text(payload.get("cta_text"), "CTA", max_length=1000),
            "show_price": show_price,
            "budget_usd": _money(payload.get("budget_usd")),
        }
        return self.repository.create_campaign_with_variation_a(data)

    def campaign_detail(self, campaign_id):
        return _serialize(
            self.repository.get_campaign(_integer(campaign_id, "Campanha"))
        )

    def create_variation(self, campaign_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        notes = _text(payload.get("notes"), "Hipótese", max_length=2000)
        return self.repository.create_variation(
            _integer(campaign_id, "Campanha"), notes
        )

    def save_variation(self, variation_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("Corpo JSON inválido.")
        notes = _text(payload.get("notes"), "Hipótese", max_length=2000)
        raw_steps = payload.get("steps")
        if not isinstance(raw_steps, list):
            raise ValueError("steps deve ser uma lista.")
        if len(raw_steps) > 20:
            raise ValueError("Cada variação pode ter no máximo 20 steps.")
        steps = []
        for index, raw in enumerate(raw_steps, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Step {index} inválido.")
            mockup = _text(
                raw.get("mockup"), f"Mockup do step {index}", required=True
            )
            if mockup not in MOCKUPS:
                raise ValueError(f"Mockup do step {index} inválido.")
            step = {
                "format_template_id": _integer(
                    raw.get("format_template_id"),
                    f"Formato do step {index}",
                ),
                "mockup": mockup,
                "scene_description": _text(
                    raw.get("scene_description"),
                    f"Descrição do step {index}",
                    max_length=8000,
                ),
            }
            if raw.get("id") not in (None, ""):
                step["id"] = _integer(raw["id"], f"ID do step {index}")
            steps.append(step)
        saved = self.repository.save_variation(
            _integer(variation_id, "Variação"), notes, steps
        )
        return {"steps": saved}

    def delete_variation(self, variation_id):
        self.repository.delete_variation(_integer(variation_id, "Variação"))

    @staticmethod
    def build_prompt(context, step, total_steps):
        scene = step.get("scene_description") or context.get("campaign_text") or ""
        client_name = context.get("client_name") or ""
        client_sector = context.get("client_sector") or ""
        logo_ref = context.get("logo_upload_path") or context.get("logo_url")
        mockup_desc = MOCKUPS[step["mockup"]]

        lines = [
            "[CONTEXTO DE TELA]",
            mockup_desc,
            "",
            "[CLIENTE]",
            f"Marca: {client_name}",
            f"Setor: {client_sector}",
        ]
        if context.get("tone_of_voice"):
            lines.append(f"Tom de marca: {context['tone_of_voice']}")
        if logo_ref:
            lines.append(f"Referência de logo (URL): {logo_ref}")
        if context.get("primary_color"):
            lines.append(f"Cor primária da marca: {context['primary_color']}")
        if context.get("secondary_color"):
            lines.append(f"Cor secundária da marca: {context['secondary_color']}")

        lines.extend(
            [
                "",
                "[CAMPANHA]",
                f"Objetivo: {context.get('objective') or ''}",
                f"Mensagem principal: {scene}",
            ]
        )
        if context.get("cta_text"):
            lines.append(f"Chamada para ação: {context['cta_text']}")
        price_instruction = (
            "sim" if context.get("show_price") else "não — nenhum texto de preço"
        )
        lines.append(f"Exibir preço: {price_instruction}")
        lines.extend(
            [
                "",
                f"[FORMATO — {step['format_name']}]",
                f"Mecânica: {step.get('mechanic') or ''}",
            ]
        )
        if step.get("channel_name"):
            lines.append(f"Canal parceiro: {step['channel_name']}")
        if step.get("partner_primary_color"):
            lines.append(
                f"Cor de contexto do parceiro: {step['partner_primary_color']}"
            )
        if step.get("partner_secondary_color"):
            lines.append(
                f"Cor secundária do parceiro: {step['partner_secondary_color']}"
            )
        if step.get("background_guidance"):
            lines.append(f"Background/base: {step['background_guidance']}")
        if step.get("foreground_guidance"):
            lines.append(f"Foreground/conteúdo: {step['foreground_guidance']}")
        replacements = {
            "{{client_sector}}": client_sector or "the brand",
            "{{brand_primary_tone}}": "the brand primary tone",
            "{{brand_name}}": client_name,
            "{{scene_description}}": scene,
            "{{sponsor_label}}": f"Uma mensagem de {client_name}",
        }
        for layer in step.get("layers") or []:
            role = layer.get("role", "layer")
            description = layer.get("description_template", "")
            for source, target in replacements.items():
                description = description.replace(source, target)
            lines.append(f"- {role}: {description}")

        engine_label = (
            "GPT Image 2" if step["engine"] == "gpt_image_2" else "Higgsfield"
        )
        media_label = (
            "imagem estática" if step["media_type"] == "image" else "vídeo"
        )
        lines.extend(
            [
                "",
                "[ESPECIFICAÇÃO TÉCNICA]",
                f"Tipo de saída: {media_label}",
                f"Engine: {engine_label}",
                "Estilo: fotorrealista, qualidade de campanha premium.",
                "",
                "[RESTRIÇÕES]",
                "Não reproduzir logos ou identidade visual de terceiros/plataformas.",
            ]
        )
        for forbidden in step.get("forbidden_elements") or []:
            lines.append(f"Não incluir: {forbidden}.")
        if not context.get("show_price"):
            lines.append("Nenhum texto de preço.")

        lines.extend(
            [
                "",
                f"[VARIAÇÃO {context['label']} — STEP {step['position']}]",
                (
                    f"Este é o step {step['position']} de {total_steps} na "
                    f"sequência da variação {context['label']}."
                ),
            ]
        )
        return "\n".join(lines).strip() + "\n"

    def generate_variation_prompts(self, variation_id, created_by=None):
        context = self.repository.get_variation_context(
            _integer(variation_id, "Variação")
        )
        steps = context.get("steps") or []
        if not steps:
            raise ValueError("Adicione ao menos um step antes de gerar prompts.")
        results = []
        for step in steps:
            generated = self.generate_step_prompt(step["id"], created_by)
            results.append(
                {
                    "step_id": step["id"],
                    "position": step["position"],
                    "prompt": generated["prompt"],
                    "job_id": generated["job_id"],
                }
            )
        return results

    @staticmethod
    def _estimate(kind):
        defaults = {"prompt": "0.020000", "script": "0.030000", "image": "0.150000"}
        env = f"CREATIVE_{kind.upper()}_ESTIMATED_COST_USD"
        return _money(os.getenv(env, defaults[kind]), "Custo estimado")

    def generate_step_prompt(self, step_id, created_by=None):
        step_id = _integer(step_id, "Step")
        context = self.repository.get_step_context(step_id)
        step = context["step"]
        request_context = {
            "campaign": {
                "name": context["campaign_name"],
                "objective": context.get("objective"),
                "message": step.get("scene_description")
                or context.get("campaign_text"),
                "cta": context.get("cta_text"),
                "show_price": context.get("show_price"),
                "variation": context["label"],
                "step": step["position"],
            },
            "client_identity": {
                "name": context["client_name"],
                "sector": context.get("client_sector"),
                "tone": context.get("tone_of_voice"),
                "logo": context.get("logo_upload_path") or context.get("logo_url"),
                "primary_color": context.get("primary_color"),
                "secondary_color": context.get("secondary_color"),
            },
            "partner_identity": {
                "name": step.get("channel_name"),
                "primary_color": step.get("partner_primary_color"),
                "secondary_color": step.get("partner_secondary_color"),
                "guidelines": step.get("brand_guidelines") or {},
            },
            "format": {
                key: step.get(key)
                for key in (
                    "format_name",
                    "mechanic",
                    "media_type",
                    "aspect_ratio",
                    "default_size",
                    "safe_area",
                    "responsive_rules",
                    "background_guidance",
                    "foreground_guidance",
                    "layers",
                    "forbidden_elements",
                )
            },
            "mockup": step["mockup"],
        }
        estimate = self._estimate("prompt")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "prompt",
            "openrouter",
            DEFAULT_TEXT_MODEL,
            estimate,
            request_payload=request_context,
            created_by=created_by,
        )
        try:
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_prompt(request_context)
            prompt = generated["result"]["prompt_en"].strip()
            self.repository.update_step_prompt(step_id, prompt, "generated")
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {
                    "usage": generated.get("usage") or {},
                    "rationale_pt": generated["result"].get("rationale_pt"),
                    "checks": generated["result"].get("checks") or [],
                },
                "review",
            )
            return {
                "job_id": job_id,
                "prompt": prompt,
                "rationale": generated["result"].get("rationale_pt"),
                "checks": generated["result"].get("checks") or [],
            }
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            raise

    def review_step_prompt(self, step_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        prompt = _text(
            payload.get("prompt"), "Prompt", required=True, max_length=20000
        )
        approve = payload.get("approved") is True
        return self.repository.update_step_prompt(
            _integer(step_id, "Step"),
            prompt,
            "approved" if approve else "reviewed",
        )

    def generate_step_image(self, step_id, files, created_by=None):
        step_id = _integer(step_id, "Step")
        references = list(files or [])
        if len(references) > 2:
            raise ValueError("Use no máximo duas imagens de referência.")
        context = self.repository.get_step_context(step_id)
        step = context["step"]
        if step.get("prompt_status") != "approved":
            raise ValueError("Revise e aprove o prompt antes de gerar a imagem.")
        estimate = self._estimate("image")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "image",
            "openrouter",
            DEFAULT_IMAGE_MODEL,
            estimate,
            prompt=step.get("rendered_prompt"),
            created_by=created_by,
        )
        saved_paths = []
        try:
            data_urls = []
            for file_storage in references:
                saved = self.storage.save_reference(file_storage)
                saved_paths.append(saved["asset_path"])
                self.repository.add_job_reference(job_id, saved)
                data_urls.append(
                    self.storage.reference_as_data_url(
                        saved["asset_path"], saved["mime_type"]
                    )
                )
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_image(
                step["rendered_prompt"],
                data_urls,
                aspect_ratio=step.get("aspect_ratio") or "16:9",
            )
            asset_url = self.storage.save_generated_base64(
                generated["b64_json"], generated.get("output_format", "png")
            )
            asset = self.repository.add_generated_asset(
                job_id,
                step_id,
                "image",
                asset_url,
                {"model": generated.get("model")},
            )
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {
                    "usage": generated.get("usage") or {},
                    **(generated.get("response_metadata") or {}),
                },
            )
            return {"job_id": job_id, "asset": asset}
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            for public_path in saved_paths:
                self.storage.delete(public_path)
            raise

    def generate_video_script(self, step_id, asset_ids, created_by=None):
        step_id = _integer(step_id, "Step")
        ids = [_integer(value, "Asset") for value in (asset_ids or [])]
        if len(ids) != 4 or len(set(ids)) != 4:
            raise ValueError("Selecione exatamente quatro imagens aprovadas.")
        assets = self.repository.get_assets(ids, approved_only=True)
        if len(assets) != 4:
            raise ValueError("As quatro imagens precisam estar aprovadas.")
        context = self.repository.get_step_context(step_id)
        if any(
            asset.get("campaign_id") not in (None, context["campaign_id"])
            for asset in assets
        ):
            raise ValueError("As imagens devem pertencer à mesma campanha.")
        step = context["step"]
        script_context = {
            "campaign": context["campaign_name"],
            "objective": context.get("objective"),
            "message": context.get("campaign_text"),
            "cta": context.get("cta_text"),
            "format": step["format_name"],
            "images": [
                {"position": index, "asset_url": asset["asset_url"]}
                for index, asset in enumerate(assets, start=1)
            ],
        }
        estimate = self._estimate("script")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "script",
            "openrouter",
            DEFAULT_TEXT_MODEL,
            estimate,
            request_payload=script_context,
            created_by=created_by,
        )
        try:
            self.repository.mark_job_generating(job_id)
            generated = self.generator.generate_script(script_context)
            script_text = json.dumps(
                generated["result"], ensure_ascii=False, indent=2
            )
            self.repository.update_step_script(step_id, script_text, "generated")
            actual = generated.get("actual_cost_usd")
            self.repository.complete_generation_job(
                job_id,
                estimate if actual is None else actual,
                {"usage": generated.get("usage") or {}},
                "review",
            )
            return {"job_id": job_id, "script": generated["result"]}
        except Exception as exc:
            self.repository.fail_generation_job(job_id, exc)
            raise

    def review_step_script(self, step_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        script_text = _text(
            payload.get("script"), "Roteiro", required=True, max_length=30000
        )
        return self.repository.update_step_script(
            _integer(step_id, "Step"),
            script_text,
            "approved" if payload.get("approved") is True else "reviewed",
        )

    def prepare_higgsfield(self, step_id, asset_ids, created_by=None):
        step_id = _integer(step_id, "Step")
        ids = [_integer(value, "Asset") for value in (asset_ids or [])]
        if len(ids) != 4 or len(set(ids)) != 4:
            raise ValueError("Selecione exatamente quatro imagens aprovadas.")
        assets = self.repository.get_assets(ids, approved_only=True)
        if len(assets) != 4:
            raise ValueError("As quatro imagens precisam estar aprovadas.")
        context = self.repository.get_step_context(step_id)
        if any(
            asset.get("campaign_id") not in (None, context["campaign_id"])
            for asset in assets
        ):
            raise ValueError("As imagens devem pertencer à mesma campanha.")
        step = context["step"]
        if step.get("script_status") != "approved":
            raise ValueError("Revise e aprove o roteiro antes de preparar o vídeo.")
        job_id = self.repository.create_generation_job(
            context["campaign_id"],
            step_id,
            step["format_template_id"],
            "video_payload",
            "higgsfield",
            "higgsfield-pending-configuration",
            Decimal("0"),
            script_text=step["script_text"],
            created_by=created_by,
        )
        payload = build_higgsfield_payload(
            job_id,
            step["script_text"],
            assets,
            step.get("aspect_ratio"),
            15,
        )
        self.repository.link_video_assets(job_id, assets)
        self.repository.complete_generation_job(
            job_id, Decimal("0"), payload, "ready_for_higgsfield"
        )
        return {"job_id": job_id, "payload": payload}

    def history(self, campaign_id=None):
        campaign = (
            _integer(campaign_id, "Campanha") if campaign_id not in (None, "") else None
        )
        return _serialize(self.repository.list_generation_jobs(campaign))

    def review_asset(self, asset_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        status = payload.get("status")
        if status not in ("approved", "rejected"):
            raise ValueError("Status do asset deve ser approved ou rejected.")
        return self.repository.set_asset_status(
            _integer(asset_id, "Asset"), status
        )

    def promote_format_reference(self, asset_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        slot = _integer(payload.get("slot"), "Slot")
        if slot > 4:
            raise ValueError("O slot deve estar entre 1 e 4.")
        reference_type = payload.get("reference_type", "full_mockup")
        if reference_type not in ("background", "full_mockup"):
            raise ValueError("Tipo de referência inválido.")
        assets = self.repository.get_assets(
            [_integer(asset_id, "Asset")], approved_only=True
        )
        if not assets:
            raise ValueError("Apenas assets aprovados podem virar referência.")
        asset = assets[0]
        format_id = _integer(
            payload.get("format_template_id"), "Formato"
        )
        prompt = _text(payload.get("prompt"), "Prompt", max_length=20000)
        return self.repository.upsert_format_reference(
            format_id,
            slot,
            reference_type,
            prompt,
            asset["asset_url"],
            asset["job_id"],
        )

    def campaign_assets(self, campaign_id):
        return _serialize(
            self.repository.list_campaign_assets(
                _integer(campaign_id, "Campanha")
            )
        )

    def reorder_campaign_assets(self, campaign_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        raw_ids = payload.get("asset_ids")
        if not isinstance(raw_ids, list):
            raise ValueError("asset_ids deve ser uma lista.")
        asset_ids = [_integer(value, "Asset") for value in raw_ids]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("A lista de assets contém itens duplicados.")
        self.repository.reorder_campaign_assets(
            _integer(campaign_id, "Campanha"), asset_ids
        )
        return {"asset_ids": asset_ids}

    def update_campaign_asset(self, campaign_id, asset_id, payload):
        payload = payload if isinstance(payload, dict) else {}
        return self.repository.update_campaign_asset(
            _integer(campaign_id, "Campanha"),
            _integer(asset_id, "Asset"),
            _text(payload.get("title"), "Título", max_length=200),
            _text(payload.get("caption"), "Descrição", max_length=4000),
        )

    def delete_campaign_asset(self, campaign_id, asset_id):
        path = self.repository.delete_campaign_asset(
            _integer(campaign_id, "Campanha"),
            _integer(asset_id, "Asset"),
        )
        self.storage.delete(path)

    def create_public_collection(self, campaign_id, payload, created_by=None):
        payload = payload if isinstance(payload, dict) else {}
        campaign_id = _integer(campaign_id, "Campanha")
        assets = self.repository.list_campaign_assets(campaign_id)
        requested = payload.get("asset_ids")
        if requested is None:
            asset_ids = [asset["id"] for asset in assets]
        elif isinstance(requested, list):
            asset_ids = [_integer(value, "Asset") for value in requested]
        else:
            raise ValueError("asset_ids deve ser uma lista.")
        if not asset_ids:
            raise ValueError("Adicione ao menos um criativo antes de compartilhar.")
        title = _text(
            payload.get("title"),
            "Título da apresentação",
            required=True,
            max_length=200,
        )
        description = _text(
            payload.get("description"), "Descrição", max_length=4000
        )
        token = secrets.token_urlsafe(32)
        collection = self.repository.create_public_collection(
            campaign_id,
            token,
            title,
            description,
            asset_ids,
            created_by,
        )
        return {
            **collection,
            "public_url": f"/criativos/publico/{token}",
            "asset_count": len(asset_ids),
        }

    def list_public_collections(self, campaign_id):
        rows = self.repository.list_public_collections(
            _integer(campaign_id, "Campanha")
        )
        for row in rows:
            row["public_url"] = f"/criativos/publico/{row['token']}"
        return _serialize(rows)

    def revoke_public_collection(self, campaign_id, collection_id):
        self.repository.revoke_public_collection(
            _integer(campaign_id, "Campanha"),
            _integer(collection_id, "Apresentação"),
        )

    def public_collection(self, token):
        token = _text(token, "Token", required=True, max_length=100)
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token):
            raise CreativeNotFoundError("Apresentação não encontrada ou revogada.")
        return _serialize(self.repository.get_public_collection(token))

    def public_collection_asset(self, token, asset_id):
        token = _text(token, "Token", required=True, max_length=100)
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,100}", token):
            raise CreativeNotFoundError(
                "Mídia não encontrada ou apresentação revogada."
            )
        return self.repository.get_public_collection_asset(
            token, _integer(asset_id, "Asset")
        )
