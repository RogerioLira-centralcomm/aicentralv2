"""Persistência PostgreSQL da Modelagem de Criativos."""

from contextlib import contextmanager
from decimal import Decimal

from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Json


class CreativeNotFoundError(LookupError):
    pass


class CreativeConflictError(ValueError):
    pass


def scene_count_for_format(format_row):
    behavior = format_row.get("behavior_spec") or {}
    return (
        1
        if behavior.get("type") == "static"
        and format_row.get("mechanic") == "static_display"
        else 4
    )


class CreativeModelingRepository:
    def __init__(self, connection=None):
        self._connection = connection

    @property
    def conn(self):
        if self._connection is not None:
            return self._connection
        from . import db

        return db.get_db()

    @contextmanager
    def _write(self):
        try:
            with self.conn.cursor() as cursor:
                yield cursor
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def list_formats(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.id, f.slug, f.name_pt, f.name_en, f.mechanic,
                       f.media_type, f.engine, f.aspect_ratio, f.default_size,
                       f.safe_area, f.responsive_rules,
                       f.background_guidance, f.foreground_guidance,
                       f.max_reference_variants,
                       f.layers, f.required_fields, f.optional_fields,
                       f.forbidden_elements, f.use_cases_by_market, f.status,
                       f.placement_spec, f.behavior_spec,
                       f.default_viewer_profile_id,
                       COALESCE(cat.slug, 'programatica') AS category,
                       ch.slug AS channel, ch.name AS channel_name,
                       ch.screen_context_template, ch.partner_primary_color,
                       ch.partner_secondary_color, ch.brand_guidelines,
                       COALESCE(
                           (SELECT jsonb_agg(to_jsonb(ref) ORDER BY ref.slot)
                              FROM cx_format_references ref
                             WHERE ref.format_template_id = f.id
                               AND ref.status = 'approved'),
                           '[]'::jsonb
                       ) AS references
                  FROM cx_format_templates f
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_format_categories cat ON cat.id = ch.category_id
                 WHERE f.is_active = TRUE
                 ORDER BY COALESCE(cat.slug, 'programatica'), f.name_pt
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_viewer_profiles(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, name, viewer_kind, source_url, logo_asset_ref,
                       palette, shell_spec, disclaimer
                  FROM cx_creative_viewer_profiles
                 WHERE is_active = TRUE
                 ORDER BY viewer_kind, name
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_viewer_profile(self, profile_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, slug, name, viewer_kind, source_url, logo_asset_ref,
                       palette, shell_spec, disclaimer
                  FROM cx_creative_viewer_profiles
                 WHERE id = %s AND is_active = TRUE
                """,
                (profile_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Ambiente de mídia não encontrado.")
        return dict(row)

    def get_format(self, format_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT f.*, COALESCE(cat.slug, 'programatica') AS category,
                       ch.slug AS channel, ch.name AS channel_name,
                       ch.screen_context_template, ch.partner_primary_color,
                       ch.partner_secondary_color, ch.brand_guidelines
                  FROM cx_format_templates f
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_format_categories cat ON cat.id = ch.category_id
                 WHERE f.id = %s AND f.is_active = TRUE
                """,
                (format_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Formato não encontrado.")
        return dict(row)

    def update_format_modeling(self, format_id, data):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_templates
                   SET safe_area = %s,
                       responsive_rules = %s,
                       background_guidance = %s,
                       foreground_guidance = %s,
                       placement_spec = %s,
                       behavior_spec = %s,
                       default_viewer_profile_id = %s
                 WHERE id = %s
                RETURNING id
                """,
                (
                    Json(data.get("safe_area") or {}),
                    data.get("responsive_rules"),
                    data.get("background_guidance"),
                    data.get("foreground_guidance"),
                    Json(data.get("placement_spec") or {}),
                    Json(data.get("behavior_spec") or {}),
                    data.get("default_viewer_profile_id"),
                    format_id,
                ),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Formato não encontrado.")

    def list_clients(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, sector, tone_of_voice, logo_url,
                       logo_upload_path, primary_color, secondary_color,
                       website_url, brand_profile, analysis_metadata,
                       price_policy, created_at
                  FROM cx_clients
                 ORDER BY created_at DESC, id DESC
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def list_campaign_clients(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT cx.id AS profile_id, crm.id_cliente AS crm_client_id,
                       'crm:' || crm.id_cliente::text AS selection_key,
                       'crm' AS source,
                       CASE WHEN cx.id IS NULL THEN 'minimal' ELSE 'ready' END
                           AS profile_status,
                       COALESCE(
                           cx.name, crm.nome_fantasia, crm.razao_social,
                           'Cliente #' || crm.id_cliente::text
                       )
                           AS name,
                       cx.sector, cx.tone_of_voice, cx.logo_url,
                       cx.logo_upload_path, cx.primary_color,
                       cx.secondary_color, cx.website_url,
                       COALESCE(cx.brand_profile, '{}'::jsonb) AS brand_profile,
                       COALESCE(cx.analysis_metadata, '{}'::jsonb)
                           AS analysis_metadata,
                       COALESCE(cx.price_policy, 'hide_price') AS price_policy
                  FROM tbl_cliente crm
                  LEFT JOIN cx_clients cx ON cx.crm_client_id = crm.id_cliente
                 WHERE crm.status = TRUE
                UNION ALL
                SELECT cx.id AS profile_id, NULL::integer AS crm_client_id,
                       'profile:' || cx.id::text AS selection_key,
                       'creative' AS source, 'ready' AS profile_status,
                       cx.name, cx.sector, cx.tone_of_voice, cx.logo_url,
                       cx.logo_upload_path, cx.primary_color,
                       cx.secondary_color, cx.website_url,
                       cx.brand_profile, cx.analysis_metadata, cx.price_policy
                  FROM cx_clients cx
                 WHERE cx.crm_client_id IS NULL
                 ORDER BY name
                """
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_client(self, client_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, sector, tone_of_voice, logo_url,
                       logo_upload_path, primary_color, secondary_color,
                       website_url, brand_profile, analysis_metadata,
                       price_policy, created_at
                  FROM cx_clients
                 WHERE id = %s
                """,
                (client_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Cliente não encontrado.")
        return dict(row)

    def create_client(self, data):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_clients (
                    name, sector, tone_of_voice, logo_url, primary_color,
                    secondary_color, website_url, brand_profile,
                    analysis_metadata, price_policy
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["name"],
                    data.get("sector"),
                    data.get("tone_of_voice"),
                    data.get("logo_url"),
                    data.get("primary_color"),
                    data.get("secondary_color"),
                    data.get("website_url"),
                    Json(data.get("brand_profile") or {}),
                    Json(data.get("analysis_metadata") or {}),
                    data["price_policy"],
                ),
            )
            return cursor.fetchone()["id"]

    def set_client_logo(self, client_id, public_path):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_clients
                   SET logo_upload_path = %s
                 WHERE id = %s
                RETURNING logo_upload_path
                """,
                (public_path, client_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Cliente não encontrado.")

    def delete_client(self, client_id):
        try:
            with self._write() as cursor:
                cursor.execute(
                    "DELETE FROM cx_clients WHERE id = %s RETURNING id",
                    (client_id,),
                )
                if not cursor.fetchone():
                    raise CreativeNotFoundError("Cliente não encontrado.")
        except ForeignKeyViolation as exc:
            raise CreativeConflictError(
                "Cliente vinculado a campanhas não pode ser removido."
            ) from exc

    def create_campaign_with_variation_a(self, data):
        with self._write() as cursor:
            client_source = data.get("client_source", "creative")
            source_client_id = data["client_id"]
            if client_source == "crm":
                cursor.execute(
                    """
                    SELECT id_cliente,
                           COALESCE(
                               nome_fantasia, razao_social,
                               'Cliente #' || id_cliente::text
                           ) AS name
                      FROM tbl_cliente
                     WHERE id_cliente = %s AND status = TRUE
                    """,
                    (source_client_id,),
                )
                crm_client = cursor.fetchone()
                if not crm_client:
                    raise CreativeNotFoundError("Cliente do CRM não encontrado.")
                cursor.execute(
                    """
                    INSERT INTO cx_clients (
                        crm_client_id, name, brand_profile,
                        analysis_metadata, price_policy
                    )
                    VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'hide_price')
                    ON CONFLICT (crm_client_id)
                        WHERE crm_client_id IS NOT NULL
                    DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    (source_client_id, crm_client["name"]),
                )
                client_id = cursor.fetchone()["id"]
            else:
                cursor.execute(
                    "SELECT id FROM cx_clients WHERE id = %s",
                    (source_client_id,),
                )
                client = cursor.fetchone()
                if not client:
                    raise CreativeNotFoundError("Perfil de marca não encontrado.")
                client_id = client["id"]

            first_step = data["first_step"]
            cursor.execute(
                """
                SELECT id, engine
                  FROM cx_format_templates
                 WHERE id = %s AND is_active = TRUE
                """,
                (first_step["format_template_id"],),
            )
            format_row = cursor.fetchone()
            if not format_row:
                raise CreativeNotFoundError("Formato inicial não encontrado.")
            cursor.execute(
                """
                INSERT INTO cx_campaigns (
                    client_id, name, objective, campaign_text, cta_text,
                    show_price, budget_usd, creative_brief
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    client_id,
                    data["name"],
                    data.get("objective"),
                    data.get("campaign_text"),
                    data.get("cta_text"),
                    data.get("show_price", False),
                    data.get("budget_usd", 0),
                    Json(data.get("creative_brief") or {}),
                ),
            )
            campaign_id = cursor.fetchone()["id"]
            cursor.execute(
                """
                INSERT INTO cx_campaign_variations (campaign_id, label)
                VALUES (%s, 'A')
                RETURNING id
                """,
                (campaign_id,),
            )
            variation_id = cursor.fetchone()["id"]
            cursor.execute(
                """
                INSERT INTO cx_variation_steps (
                    variation_id, position, format_template_id,
                    mockup, scene_description, engine
                )
                VALUES (%s, 1, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    variation_id,
                    format_row["id"],
                    first_step["mockup"],
                    first_step.get("scene_description"),
                    format_row["engine"],
                ),
            )
            step_id = cursor.fetchone()["id"]
        return {
            "id": campaign_id,
            "variation_id": variation_id,
            "step_id": step_id,
        }

    def create_campaign_with_productions(self, data):
        """Cria campanha, uma produção por formato e suas cenas atomicamente."""
        with self._write() as cursor:
            client_source = data.get("client_source", "creative")
            source_client_id = data["client_id"]
            if client_source == "crm":
                cursor.execute(
                    """
                    SELECT id_cliente,
                           COALESCE(
                               nome_fantasia, razao_social,
                               'Cliente #' || id_cliente::text
                           ) AS name
                      FROM tbl_cliente
                     WHERE id_cliente = %s AND status = TRUE
                    """,
                    (source_client_id,),
                )
                crm_client = cursor.fetchone()
                if not crm_client:
                    raise CreativeNotFoundError("Cliente do CRM não encontrado.")
                cursor.execute(
                    """
                    INSERT INTO cx_clients (
                        crm_client_id, name, brand_profile,
                        analysis_metadata, price_policy
                    )
                    VALUES (%s, %s, '{}'::jsonb, '{}'::jsonb, 'hide_price')
                    ON CONFLICT (crm_client_id)
                        WHERE crm_client_id IS NOT NULL
                    DO UPDATE SET name = EXCLUDED.name
                    RETURNING id
                    """,
                    (source_client_id, crm_client["name"]),
                )
                client_id = cursor.fetchone()["id"]
            else:
                cursor.execute(
                    "SELECT id FROM cx_clients WHERE id = %s",
                    (source_client_id,),
                )
                client = cursor.fetchone()
                if not client:
                    raise CreativeNotFoundError("Perfil de marca não encontrado.")
                client_id = client["id"]

            format_ids = [item["format_template_id"] for item in data["productions"]]
            cursor.execute(
                """
                SELECT id, mechanic, media_type, behavior_spec
                  FROM cx_format_templates
                 WHERE id = ANY(%s) AND is_active = TRUE
                """,
                (format_ids,),
            )
            formats = {row["id"]: dict(row) for row in cursor.fetchall()}
            if set(format_ids) != set(formats):
                raise CreativeNotFoundError(
                    "Um ou mais formatos não foram encontrados."
                )
            if any(row["media_type"] == "video" for row in formats.values()):
                raise CreativeConflictError(
                    "Vídeo está indisponível para novas produções."
                )

            cursor.execute(
                """
                INSERT INTO cx_campaigns (
                    client_id, name, objective, campaign_text, cta_text,
                    show_price, budget_usd
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    client_id,
                    data["name"],
                    data.get("objective"),
                    data.get("campaign_text"),
                    data.get("cta_text"),
                    data.get("show_price", False),
                    data.get("budget_usd", 0),
                ),
            )
            campaign_id = cursor.fetchone()["id"]
            productions = []
            for requested in data["productions"]:
                format_id = requested["format_template_id"]
                format_row = formats[format_id]
                scene_count = scene_count_for_format(format_row)
                cursor.execute(
                    """
                    INSERT INTO cx_creative_productions (
                        campaign_id, format_template_id
                    )
                    VALUES (%s, %s)
                    RETURNING id
                    """,
                    (campaign_id, format_id),
                )
                production_id = cursor.fetchone()["id"]
                descriptions = requested.get("scene_descriptions") or []
                scene_ids = []
                for position in range(1, scene_count + 1):
                    description = (
                        descriptions[position - 1]
                        if position <= len(descriptions)
                        else data.get("campaign_text")
                    )
                    cursor.execute(
                        """
                        INSERT INTO cx_creative_scenes (
                            production_id, position, description, status
                        )
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            production_id,
                            position,
                            description,
                            "ready" if position == 1 else "blocked",
                        ),
                    )
                    scene_ids.append(cursor.fetchone()["id"])
                productions.append(
                    {
                        "id": production_id,
                        "format_template_id": format_id,
                        "scene_ids": scene_ids,
                    }
                )
        return {"id": campaign_id, "productions": productions}

    def get_production(self, production_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.campaign_id, p.format_template_id, p.status,
                       p.selected_asset_id, p.created_at, p.updated_at,
                       c.name AS campaign_name, f.slug AS format_slug,
                       f.name_pt AS format_name, f.mechanic, f.media_type,
                       f.aspect_ratio, f.default_size, f.placement_spec,
                       f.behavior_spec
                  FROM cx_creative_productions p
                  JOIN cx_campaigns c ON c.id = p.campaign_id
                  JOIN cx_format_templates f ON f.id = p.format_template_id
                 WHERE p.id = %s
                """,
                (production_id,),
            )
            production = cursor.fetchone()
            if not production:
                raise CreativeNotFoundError("Produção não encontrada.")
            cursor.execute(
                """
                SELECT s.id, s.production_id, p.format_template_id,
                       s.position, s.description, s.prompt,
                       s.prompt AS rendered_prompt, s.prompt_status,
                       s.status, s.approved_asset_id, s.preview_asset_id,
                       s.created_at, s.updated_at,
                       COALESCE(
                           (
                               SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at)
                                 FROM cx_generated_assets a
                                WHERE a.scene_id = s.id
                           ),
                           '[]'::jsonb
                       ) AS assets
                  FROM cx_creative_scenes s
                  JOIN cx_creative_productions p ON p.id = s.production_id
                 WHERE s.production_id = %s
                 ORDER BY s.position
                """,
                (production_id,),
            )
            result = dict(production)
            result["scenes"] = [dict(row) for row in cursor.fetchall()]
            return result

    def get_scene_context(self, scene_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.production_id, s.position, s.description,
                       s.prompt, s.prompt_status, s.status, p.campaign_id,
                       p.format_template_id, p.status AS production_status,
                       (
                           SELECT COUNT(*)::integer
                             FROM cx_creative_scenes sequence_scene
                            WHERE sequence_scene.production_id = s.production_id
                       ) AS scene_count,
                       c.name AS campaign_name, c.objective, c.campaign_text,
                       c.cta_text, c.show_price, c.creative_brief,
                       (
                           SELECT jsonb_agg(
                               jsonb_build_object(
                                   'position', sequence_scene.position,
                                   'description', sequence_scene.description
                               )
                               ORDER BY sequence_scene.position
                           )
                             FROM cx_creative_scenes sequence_scene
                            WHERE sequence_scene.production_id = s.production_id
                       ) AS storyboard,
                       (
                           SELECT previous_asset.asset_url
                             FROM cx_creative_scenes previous_scene
                             JOIN cx_generated_assets previous_asset
                               ON previous_asset.id = previous_scene.approved_asset_id
                            WHERE previous_scene.production_id = s.production_id
                              AND previous_scene.position < s.position
                            ORDER BY previous_scene.position DESC
                            LIMIT 1
                       ) AS previous_approved_asset_url,
                       cl.name AS client_name, cl.sector AS client_sector,
                       cl.tone_of_voice, cl.logo_url, cl.logo_upload_path,
                       cl.primary_color, cl.secondary_color, cl.brand_profile,
                       f.name_pt AS format_name, f.mechanic, f.media_type,
                       f.engine, f.aspect_ratio, f.default_size, f.safe_area,
                       f.background_guidance, f.foreground_guidance,
                       f.layers, f.forbidden_elements, f.placement_spec,
                       f.behavior_spec, ch.name AS channel_name
                  FROM cx_creative_scenes s
                  JOIN cx_creative_productions p ON p.id = s.production_id
                  JOIN cx_campaigns c ON c.id = p.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                  JOIN cx_format_templates f ON f.id = p.format_template_id
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE s.id = %s
                """,
                (scene_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Cena não encontrada.")
        return dict(row)

    def update_scene_prompt(self, scene_id, prompt, status):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_creative_scenes
                   SET prompt = %s, prompt_status = %s, updated_at = NOW()
                 WHERE id = %s AND status IN ('ready', 'failed')
                RETURNING id, prompt, prompt AS rendered_prompt, prompt_status
                """,
                (prompt, status, scene_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeConflictError(
                    "Cena não está disponível para editar a direção."
                )
            return dict(row)

    def list_campaigns(self, limit=50):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.name, c.client_id, cl.name AS client,
                       c.objective, c.campaign_text, c.cta_text, c.show_price,
                       c.status, c.budget_usd, c.reserved_usd, c.spent_usd,
                       (c.budget_usd - c.reserved_usd - c.spent_usd) AS balance_usd,
                       c.created_at,
                       COUNT(v.id)::integer AS variation_count
                  FROM cx_campaigns c
                  JOIN cx_clients cl ON cl.id = c.client_id
                  LEFT JOIN cx_campaign_variations v ON v.campaign_id = c.id
                 GROUP BY c.id, cl.name
                 ORDER BY c.created_at DESC, c.id DESC
                 LIMIT %s
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_campaign(self, campaign_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.name, c.client_id, c.objective,
                       c.campaign_text, c.cta_text, c.show_price,
                       c.creative_brief, c.status,
                       c.budget_usd, c.reserved_usd, c.spent_usd,
                       (c.budget_usd - c.reserved_usd - c.spent_usd) AS balance_usd,
                       c.created_at, cl.name AS client_name,
                       cl.sector AS client_sector,
                       cl.tone_of_voice AS client_tone_of_voice,
                       cl.logo_url AS client_logo_url,
                       cl.logo_upload_path AS client_logo_upload_path,
                       cl.primary_color AS client_primary_color,
                       cl.secondary_color AS client_secondary_color,
                       cl.website_url AS client_website_url,
                       cl.brand_profile AS client_brand_profile,
                       cl.price_policy AS client_price_policy
                  FROM cx_campaigns c
                  JOIN cx_clients cl ON cl.id = c.client_id
                 WHERE c.id = %s
                """,
                (campaign_id,),
            )
            campaign = cursor.fetchone()
            if not campaign:
                raise CreativeNotFoundError("Campanha não encontrada.")
            cursor.execute(
                """
                SELECT id, campaign_id, label, notes, created_at
                  FROM cx_campaign_variations
                 WHERE campaign_id = %s
                 ORDER BY label
                """,
                (campaign_id,),
            )
            variations = [dict(row) for row in cursor.fetchall()]
            variation_ids = [row["id"] for row in variations]
            steps_by_variation = {variation_id: [] for variation_id in variation_ids}
            if variation_ids:
                cursor.execute(
                    """
                    SELECT s.id, s.variation_id, s.position,
                           s.format_template_id, s.mockup,
                           s.scene_description, s.rendered_prompt, s.engine,
                           s.prompt_status, s.script_text, s.script_status,
                           s.asset_url, s.asset_status, s.created_at,
                           f.slug AS format_slug, f.name_pt AS format_name,
                           f.media_type, f.aspect_ratio, f.default_size,
                           COALESCE(
                               (SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at DESC)
                                  FROM cx_generated_assets a
                                 WHERE a.step_id = s.id),
                               '[]'::jsonb
                           ) AS assets
                      FROM cx_variation_steps s
                      JOIN cx_format_templates f ON f.id = s.format_template_id
                     WHERE s.variation_id = ANY(%s)
                     ORDER BY s.variation_id, s.position
                    """,
                    (variation_ids,),
                )
                for row in cursor.fetchall():
                    step = dict(row)
                    steps_by_variation[step["variation_id"]].append(step)

        result = dict(campaign)
        result["client"] = {
            "id": result.pop("client_id"),
            "name": result.pop("client_name"),
            "sector": result.pop("client_sector"),
            "tone_of_voice": result.pop("client_tone_of_voice"),
            "logo_url": result.pop("client_logo_url"),
            "logo_upload_path": result.pop("client_logo_upload_path"),
            "primary_color": result.pop("client_primary_color"),
            "secondary_color": result.pop("client_secondary_color"),
            "website_url": result.pop("client_website_url"),
            "brand_profile": result.pop("client_brand_profile") or {},
            "price_policy": result.pop("client_price_policy"),
        }
        for variation in variations:
            variation["steps"] = steps_by_variation[variation["id"]]
        result["variations"] = variations
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                  FROM cx_creative_productions
                 WHERE campaign_id = %s
                 ORDER BY created_at, id
                """,
                (campaign_id,),
            )
            production_ids = [row["id"] for row in cursor.fetchall()]
        result["productions"] = [
            self.get_production(production_id) for production_id in production_ids
        ]
        result["production"] = (
            result["productions"][0] if result["productions"] else None
        )
        return result

    def create_variation(self, campaign_id, notes=None):
        labels = ("A", "B", "C", "D")
        try:
            with self._write() as cursor:
                cursor.execute(
                    "SELECT id FROM cx_campaigns WHERE id = %s FOR UPDATE",
                    (campaign_id,),
                )
                if not cursor.fetchone():
                    raise CreativeNotFoundError("Campanha não encontrada.")
                cursor.execute(
                    """
                    SELECT label
                      FROM cx_campaign_variations
                     WHERE campaign_id = %s
                     ORDER BY label
                    """,
                    (campaign_id,),
                )
                used = {row["label"] for row in cursor.fetchall()}
                label = next((item for item in labels if item not in used), None)
                if not label:
                    raise CreativeConflictError(
                        "A campanha já possui o máximo de 4 variações."
                    )
                cursor.execute(
                    """
                    INSERT INTO cx_campaign_variations (
                        campaign_id, label, notes
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id, label
                    """,
                    (campaign_id, label, notes),
                )
                return dict(cursor.fetchone())
        except UniqueViolation as exc:
            raise CreativeConflictError(
                "Não foi possível reservar a próxima variação."
            ) from exc

    def save_variation(self, variation_id, notes, steps):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id
                  FROM cx_campaign_variations
                 WHERE id = %s
                 FOR UPDATE
                """,
                (variation_id,),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Variação não encontrada.")

            cursor.execute(
                """
                SELECT id, format_template_id, mockup, scene_description
                  FROM cx_variation_steps
                 WHERE variation_id = %s
                """,
                (variation_id,),
            )
            existing = {row["id"]: dict(row) for row in cursor.fetchall()}
            incoming_ids = {step["id"] for step in steps if step.get("id")}
            invalid_ids = incoming_ids - set(existing)
            if invalid_ids:
                raise CreativeConflictError(
                    "Um ou mais steps não pertencem à variação."
                )

            format_ids = sorted({step["format_template_id"] for step in steps})
            formats = {}
            if format_ids:
                cursor.execute(
                    """
                    SELECT id, engine
                      FROM cx_format_templates
                     WHERE id = ANY(%s) AND is_active = TRUE
                    """,
                    (format_ids,),
                )
                formats = {row["id"]: row["engine"] for row in cursor.fetchall()}
            if set(format_ids) != set(formats):
                raise CreativeNotFoundError(
                    "Um ou mais formatos não foram encontrados."
                )

            cursor.execute(
                "UPDATE cx_campaign_variations SET notes = %s WHERE id = %s",
                (notes, variation_id),
            )
            cursor.execute(
                """
                UPDATE cx_variation_steps
                   SET position = position + 1000
                 WHERE variation_id = %s
                """,
                (variation_id,),
            )
            if existing:
                omitted = set(existing) - incoming_ids
                if omitted:
                    cursor.execute(
                        "DELETE FROM cx_variation_steps WHERE id = ANY(%s)",
                        (sorted(omitted),),
                    )

            saved = []
            for position, step in enumerate(steps, start=1):
                format_id = step["format_template_id"]
                values = (
                    position,
                    format_id,
                    step["mockup"],
                    step.get("scene_description"),
                    formats[format_id],
                )
                step_id = step.get("id")
                if step_id:
                    before = existing[step_id]
                    changed = (
                        before["format_template_id"] != format_id
                        or before["mockup"] != step["mockup"]
                        or (before.get("scene_description") or "")
                        != (step.get("scene_description") or "")
                    )
                    cursor.execute(
                        """
                        UPDATE cx_variation_steps
                           SET position = %s,
                               format_template_id = %s,
                               mockup = %s,
                               scene_description = %s,
                               engine = %s,
                               rendered_prompt = CASE
                                   WHEN %s THEN NULL ELSE rendered_prompt
                               END,
                               asset_status = CASE
                                   WHEN %s THEN 'pending' ELSE asset_status
                               END
                         WHERE id = %s
                        RETURNING id, position
                        """,
                        values + (changed, changed, step_id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO cx_variation_steps (
                            variation_id, position, format_template_id,
                            mockup, scene_description, engine
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id, position
                        """,
                        (variation_id,) + values,
                    )
                saved.append(dict(cursor.fetchone()))
            return saved

    def delete_variation(self, variation_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT campaign_id
                  FROM cx_campaign_variations
                 WHERE id = %s
                """,
                (variation_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Variação não encontrada.")
            cursor.execute(
                """
                SELECT COUNT(*) AS total
                  FROM cx_campaign_variations
                 WHERE campaign_id = %s
                """,
                (row["campaign_id"],),
            )
            if cursor.fetchone()["total"] <= 1:
                raise CreativeConflictError(
                    "A campanha precisa manter ao menos uma variação."
                )
            cursor.execute(
                "DELETE FROM cx_campaign_variations WHERE id = %s",
                (variation_id,),
            )

    def get_variation_context(self, variation_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT v.id, v.label, v.notes, c.id AS campaign_id,
                       c.name AS campaign_name, c.objective,
                       c.campaign_text, c.cta_text, c.show_price,
                       c.budget_usd, c.reserved_usd, c.spent_usd,
                       cl.name AS client_name, cl.sector AS client_sector,
                       cl.tone_of_voice, cl.logo_url, cl.logo_upload_path,
                       cl.primary_color, cl.secondary_color,
                       cl.website_url, cl.brand_profile
                  FROM cx_campaign_variations v
                  JOIN cx_campaigns c ON c.id = v.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                 WHERE v.id = %s
                """,
                (variation_id,),
            )
            variation = cursor.fetchone()
            if not variation:
                raise CreativeNotFoundError("Variação não encontrada.")
            cursor.execute(
                """
                SELECT s.id, s.position, s.mockup, s.scene_description,
                       s.rendered_prompt, s.prompt_status, s.script_text,
                       s.script_status,
                       f.id AS format_template_id, f.slug AS format_slug,
                       f.name_pt AS format_name, f.mechanic, f.media_type,
                       f.engine, f.layers, f.forbidden_elements,
                       f.aspect_ratio, f.default_size, f.safe_area,
                       f.responsive_rules, f.background_guidance,
                       f.foreground_guidance,
                       ch.name AS channel_name, ch.screen_context_template,
                       ch.partner_primary_color, ch.partner_secondary_color,
                       ch.brand_guidelines
                  FROM cx_variation_steps s
                  JOIN cx_format_templates f ON f.id = s.format_template_id
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE s.variation_id = %s
                 ORDER BY s.position
                """,
                (variation_id,),
            )
            result = dict(variation)
            result["steps"] = [dict(row) for row in cursor.fetchall()]
            return result

    def get_step_context(self, step_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT variation_id FROM cx_variation_steps WHERE id = %s",
                (step_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Step não encontrado.")
        context = self.get_variation_context(row["variation_id"])
        step = next(item for item in context["steps"] if item["id"] == step_id)
        context["step"] = step
        return context

    def save_rendered_prompts(self, prompts):
        with self._write() as cursor:
            for item in prompts:
                cursor.execute(
                    """
                    UPDATE cx_variation_steps
                       SET rendered_prompt = %s, prompt_status = 'generated',
                           asset_status = 'pending'
                     WHERE id = %s
                    """,
                    (item["prompt"], item["step_id"]),
                )

    def update_step_prompt(self, step_id, prompt, status="reviewed"):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_variation_steps
                   SET rendered_prompt = %s, prompt_status = %s
                 WHERE id = %s
                RETURNING id, rendered_prompt, prompt_status
                """,
                (prompt, status, step_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Step não encontrado.")
            return dict(row)

    def update_step_script(self, step_id, script_text, status="reviewed"):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_variation_steps
                   SET script_text = %s, script_status = %s
                 WHERE id = %s
                RETURNING id, script_text, script_status
                """,
                (script_text, status, step_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Step não encontrado.")
            return dict(row)

    def create_generation_job(
        self,
        campaign_id,
        step_id,
        format_template_id,
        job_type,
        provider,
        model,
        estimated_cost_usd,
        prompt=None,
        script_text=None,
        request_payload=None,
        created_by=None,
        scene_id=None,
        reserve_scene=False,
    ):
        estimate = Decimal(str(estimated_cost_usd or 0))
        with self._write() as cursor:
            if scene_id is not None:
                cursor.execute(
                    """
                    SELECT s.id, s.position, s.status, p.status AS production_status
                      FROM cx_creative_scenes s
                      JOIN cx_creative_productions p ON p.id = s.production_id
                     WHERE s.id = %s
                     FOR UPDATE OF s, p
                    """,
                    (scene_id,),
                )
                scene = cursor.fetchone()
                if not scene:
                    raise CreativeNotFoundError("Cena não encontrada.")
                if scene["production_status"] != "active":
                    raise CreativeConflictError("Produção não está ativa.")
                cursor.execute(
                    """
                    SELECT COUNT(*) AS pending_previous
                      FROM cx_creative_scenes current_scene
                      JOIN cx_creative_scenes previous
                        ON previous.production_id = current_scene.production_id
                       AND previous.position < current_scene.position
                     WHERE current_scene.id = %s
                       AND previous.status <> 'approved'
                    """,
                    (scene_id,),
                )
                if cursor.fetchone()["pending_previous"]:
                    raise CreativeConflictError(
                        "A cena anterior precisa ser aprovada primeiro."
                    )
                if scene["status"] not in ("ready", "failed"):
                    raise CreativeConflictError(
                        "Cena não está disponível para geração."
                    )
            cursor.execute(
                """
                SELECT budget_usd, reserved_usd, spent_usd
                  FROM cx_campaigns
                 WHERE id = %s
                 FOR UPDATE
                """,
                (campaign_id,),
            )
            campaign = cursor.fetchone()
            if not campaign:
                raise CreativeNotFoundError("Campanha não encontrada.")
            balance = (
                campaign["budget_usd"]
                - campaign["reserved_usd"]
                - campaign["spent_usd"]
            )
            if estimate > balance:
                raise CreativeConflictError(
                    f"Saldo insuficiente. Disponível: US$ {balance:.4f}."
                )
            cursor.execute(
                """
                INSERT INTO cx_generation_jobs (
                    campaign_id, step_id, scene_id, format_template_id, job_type,
                    provider, model, status, prompt, script_text,
                    request_payload, estimated_cost_usd, created_by
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, 'queued',
                    %s, %s, %s, %s, %s
                )
                RETURNING id
                """,
                (
                    campaign_id,
                    step_id,
                    scene_id,
                    format_template_id,
                    job_type,
                    provider,
                    model,
                    prompt,
                    script_text,
                    Json(request_payload or {}),
                    estimate,
                    created_by,
                ),
            )
            job_id = cursor.fetchone()["id"]
            if scene_id is not None and reserve_scene:
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'generating', prompt = %s, updated_at = NOW()
                     WHERE id = %s
                    """,
                    (prompt, scene_id),
                )
            cursor.execute(
                """
                UPDATE cx_campaigns
                   SET reserved_usd = reserved_usd + %s
                 WHERE id = %s
                """,
                (estimate, campaign_id),
            )
            cursor.execute(
                """
                INSERT INTO cx_generation_cost_ledger (
                    campaign_id, job_id, entry_type, amount_usd
                )
                VALUES (%s, %s, 'reservation', %s)
                """,
                (campaign_id, job_id, estimate),
            )
            return job_id

    def mark_job_generating(self, job_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_generation_jobs
                   SET status = 'generating', updated_at = NOW()
                 WHERE id = %s AND status = 'queued'
                RETURNING id
                """,
                (job_id,),
            )
            if not cursor.fetchone():
                raise CreativeConflictError("Job não está disponível para execução.")

    def complete_generation_job(
        self, job_id, actual_cost_usd, response_metadata, status="done"
    ):
        actual = Decimal(str(actual_cost_usd or 0))
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id, campaign_id, estimated_cost_usd, status
                  FROM cx_generation_jobs
                 WHERE id = %s
                 FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if not job:
                raise CreativeNotFoundError("Job não encontrado.")
            if job["status"] in ("done", "failed", "ready_for_higgsfield"):
                raise CreativeConflictError("Job já foi finalizado.")
            cursor.execute(
                """
                UPDATE cx_campaigns
                   SET reserved_usd = GREATEST(0, reserved_usd - %s),
                       spent_usd = spent_usd + %s
                 WHERE id = %s
                """,
                (job["estimated_cost_usd"], actual, job["campaign_id"]),
            )
            cursor.execute(
                """
                UPDATE cx_generation_jobs
                   SET status = %s, actual_cost_usd = %s,
                       response_metadata = %s, updated_at = NOW()
                 WHERE id = %s
                """,
                (status, actual, Json(response_metadata or {}), job_id),
            )
            cursor.executemany(
                """
                INSERT INTO cx_generation_cost_ledger (
                    campaign_id, job_id, entry_type, amount_usd
                )
                VALUES (%s, %s, %s, %s)
                """,
                [
                    (
                        job["campaign_id"],
                        job_id,
                        "release",
                        job["estimated_cost_usd"],
                    ),
                    (job["campaign_id"], job_id, "charge", actual),
                ],
            )

    def fail_generation_job(self, job_id, error_message):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT campaign_id, estimated_cost_usd, status, scene_id, job_type
                  FROM cx_generation_jobs
                 WHERE id = %s
                 FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if not job:
                raise CreativeNotFoundError("Job não encontrado.")
            if job["status"] in ("done", "failed", "ready_for_higgsfield"):
                return
            cursor.execute(
                """
                UPDATE cx_campaigns
                   SET reserved_usd = GREATEST(0, reserved_usd - %s)
                 WHERE id = %s
                """,
                (job["estimated_cost_usd"], job["campaign_id"]),
            )
            cursor.execute(
                """
                UPDATE cx_generation_jobs
                   SET status = 'failed', error_message = %s, updated_at = NOW()
                 WHERE id = %s
                """,
                (str(error_message)[:4000], job_id),
            )
            if job.get("scene_id") and job.get("job_type") == "image":
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'failed', updated_at = NOW()
                     WHERE id = %s AND status = 'generating'
                    """,
                    (job["scene_id"],),
                )
            cursor.execute(
                """
                INSERT INTO cx_generation_cost_ledger (
                    campaign_id, job_id, entry_type, amount_usd
                )
                VALUES (%s, %s, 'release', %s)
                """,
                (job["campaign_id"], job_id, job["estimated_cost_usd"]),
            )

    def add_job_reference(self, job_id, reference):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(MAX(position), 0) + 1 AS next_position
                  FROM cx_generation_references
                 WHERE job_id = %s
                """,
                (job_id,),
            )
            position = cursor.fetchone()["next_position"]
            if position > 2:
                raise CreativeConflictError(
                    "Cada geração aceita no máximo duas referências."
                )
            cursor.execute(
                """
                INSERT INTO cx_generation_references (
                    job_id, position, asset_path, original_name, mime_type
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, position
                """,
                (
                    job_id,
                    position,
                    reference["asset_path"],
                    reference.get("original_name"),
                    reference.get("mime_type"),
                ),
            )
            return dict(cursor.fetchone())

    def add_generated_asset(
        self, job_id, step_id, asset_type, asset_url, metadata=None, scene_id=None
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_generated_assets (
                    job_id, step_id, scene_id, asset_type, asset_url,
                    metadata, position
                )
                SELECT %s, %s, %s, %s, %s, %s,
                       COALESCE(MAX(a.position), 0) + 1
                  FROM cx_generation_jobs target
                  LEFT JOIN cx_generation_jobs sibling
                    ON sibling.campaign_id = target.campaign_id
                  LEFT JOIN cx_generated_assets a ON a.job_id = sibling.id
                 WHERE target.id = %s
                 GROUP BY target.id
                RETURNING id, asset_url, status, position
                """,
                (
                    job_id,
                    step_id,
                    scene_id,
                    asset_type,
                    asset_url,
                    Json(metadata or {}),
                    job_id,
                ),
            )
            asset = dict(cursor.fetchone())
            if step_id:
                cursor.execute(
                    """
                    UPDATE cx_variation_steps
                       SET asset_url = %s, asset_status = 'done'
                     WHERE id = %s
                    """,
                    (asset_url, step_id),
                )
            if scene_id:
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'review', updated_at = NOW()
                     WHERE id = %s
                    """,
                    (scene_id,),
                )
            return asset

    def review_scene_asset(self, scene_id, asset_id, status):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT s.id, s.production_id, s.status AS scene_status,
                       a.id AS asset_id
                  FROM cx_creative_scenes s
                  JOIN cx_generated_assets a
                    ON a.scene_id = s.id AND a.id = %s
                 WHERE s.id = %s
                 FOR UPDATE OF s, a
                """,
                (asset_id, scene_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset da cena não encontrado.")
            if row["scene_status"] != "review":
                raise CreativeConflictError("Cena não está aguardando revisão.")
            if status == "approved":
                cursor.execute(
                    """
                    UPDATE cx_generated_assets
                       SET status = CASE
                           WHEN id = %s THEN 'approved' ELSE 'rejected'
                       END
                     WHERE scene_id = %s
                    """,
                    (asset_id, scene_id),
                )
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'approved', approved_asset_id = %s,
                           preview_asset_id = %s,
                           updated_at = NOW()
                     WHERE id = %s
                    RETURNING position
                    """,
                    (asset_id, asset_id, scene_id),
                )
                position = cursor.fetchone()["position"]
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'ready', updated_at = NOW()
                     WHERE production_id = %s AND position = %s
                       AND status = 'blocked'
                    """,
                    (row["production_id"], position + 1),
                )
                cursor.execute(
                    """
                    UPDATE cx_creative_productions p
                       SET status = CASE
                               WHEN NOT EXISTS (
                                   SELECT 1
                                     FROM cx_creative_scenes s
                                    WHERE s.production_id = p.id
                                      AND s.status <> 'approved'
                               ) THEN 'completed'
                               ELSE 'active'
                           END,
                           updated_at = NOW()
                     WHERE p.id = %s
                    """,
                    (row["production_id"],),
                )
            else:
                cursor.execute(
                    "UPDATE cx_generated_assets SET status = 'rejected' WHERE id = %s",
                    (asset_id,),
                )
                cursor.execute(
                    """
                    UPDATE cx_creative_scenes
                       SET status = 'ready', approved_asset_id = NULL,
                           updated_at = NOW()
                     WHERE id = %s
                    """,
                    (scene_id,),
                )
            return {
                "scene_id": scene_id,
                "asset_id": asset_id,
                "status": status,
            }

    def set_scene_preview_asset(self, scene_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                 WHERE a.id = %s AND a.scene_id = %s AND a.status = 'approved'
                """,
                (asset_id, scene_id),
            )
            if not cursor.fetchone():
                raise CreativeConflictError(
                    "Escolha um asset aprovado desta cena."
                )
            cursor.execute(
                """
                UPDATE cx_creative_scenes
                   SET preview_asset_id = %s, updated_at = NOW()
                 WHERE id = %s
                RETURNING id, preview_asset_id
                """,
                (asset_id, scene_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Cena não encontrada.")
            return dict(row)

    def select_production_asset(self, production_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                  JOIN cx_creative_scenes s ON s.id = a.scene_id
                 WHERE a.id = %s
                   AND s.production_id = %s
                   AND a.status = 'approved'
                """,
                (asset_id, production_id),
            )
            if not cursor.fetchone():
                raise CreativeConflictError(
                    "Escolha um asset aprovado desta produção."
                )
            cursor.execute(
                """
                UPDATE cx_creative_productions
                   SET selected_asset_id = %s, updated_at = NOW()
                 WHERE id = %s
                RETURNING id, selected_asset_id
                """,
                (asset_id, production_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Produção não encontrada.")
            return dict(row)

    def get_assets(self, asset_ids, approved_only=True):
        ids = sorted({_id for _id in asset_ids})
        if not ids:
            return []
        with self.conn.cursor() as cursor:
            query = """
                SELECT a.id, a.job_id, a.step_id, a.scene_id,
                       a.asset_type, a.asset_url,
                       a.status, a.metadata, j.campaign_id,
                       COALESCE(j.format_template_id, s.format_template_id)
                           AS format_template_id,
                       f.aspect_ratio, f.media_type, f.mechanic
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                 WHERE a.id = ANY(%s)
            """
            if approved_only:
                query += " AND a.status = 'approved'"
            cursor.execute(query, (ids,))
            rows = {row["id"]: dict(row) for row in cursor.fetchall()}
        return [rows[_id] for _id in asset_ids if _id in rows]

    def set_asset_status(self, asset_id, status):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_generated_assets
                   SET status = %s
                 WHERE id = %s
                RETURNING id, job_id, step_id, asset_url, asset_type, status
                """,
                (status, asset_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset não encontrado.")
            if row.get("step_id"):
                cursor.execute(
                    """
                    UPDATE cx_variation_steps
                       SET asset_status = %s
                     WHERE id = %s
                    """,
                    (status, row["step_id"]),
                )
            return dict(row)

    def link_video_assets(self, job_id, assets):
        with self._write() as cursor:
            for position, asset in enumerate(assets, start=1):
                cursor.execute(
                    """
                    INSERT INTO cx_video_input_assets (job_id, position, asset_id)
                    VALUES (%s, %s, %s)
                    """,
                    (job_id, position, asset["id"]),
                )

    def list_generation_jobs(self, campaign_id=None, limit=100):
        params = []
        where = ""
        if campaign_id:
            where = "WHERE j.campaign_id = %s"
            params.append(campaign_id)
        params.append(limit)
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT j.*, c.name AS campaign_name,
                       v.label AS variation_label, s.position AS step_position,
                       f.name_pt AS format_name,
                       COALESCE(
                           (SELECT jsonb_agg(to_jsonb(a) ORDER BY a.created_at)
                              FROM cx_generated_assets a WHERE a.job_id = j.id),
                           '[]'::jsonb
                       ) AS assets
                  FROM cx_generation_jobs j
                  JOIN cx_campaigns c ON c.id = j.campaign_id
                  LEFT JOIN cx_variation_steps s ON s.id = j.step_id
                  LEFT JOIN cx_campaign_variations v ON v.id = s.variation_id
                  LEFT JOIN cx_format_templates f ON f.id = j.format_template_id
                  {where}
                 ORDER BY j.created_at DESC
                 LIMIT %s
                """,
                params,
            )
            return [dict(row) for row in cursor.fetchall()]

    def create_format_modeling_job(
        self,
        format_template_id,
        client_id,
        parent_job_id,
        slot,
        reference_type,
        model,
        prompt,
        input_references,
        estimated_cost_usd,
        refinement_instruction=None,
        created_by=None,
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_format_modeling_jobs (
                    format_template_id, client_id, parent_job_id, slot,
                    reference_type, model, prompt, refinement_instruction,
                    input_references, estimated_cost_usd, created_by
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    format_template_id,
                    client_id,
                    parent_job_id,
                    slot,
                    reference_type,
                    model,
                    prompt,
                    refinement_instruction,
                    Json(input_references or []),
                    Decimal(str(estimated_cost_usd or 0)),
                    created_by,
                ),
            )
            return cursor.fetchone()["id"]

    def mark_format_modeling_job_generating(self, job_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'generating', updated_at = NOW()
                 WHERE id = %s AND status = 'queued'
                RETURNING id
                """,
                (job_id,),
            )
            if not cursor.fetchone():
                raise CreativeConflictError("Job de modelagem indisponível.")

    def complete_format_modeling_job(
        self, job_id, asset_url, actual_cost_usd, response_metadata
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'review', asset_url = %s,
                       actual_cost_usd = %s, response_metadata = %s,
                       updated_at = NOW()
                 WHERE id = %s AND status = 'generating'
                RETURNING id, format_template_id, client_id, parent_job_id,
                          slot, reference_type, model, status, prompt,
                          refinement_instruction, input_references, asset_url,
                          estimated_cost_usd, actual_cost_usd,
                          response_metadata, created_at, updated_at
                """,
                (
                    asset_url,
                    Decimal(str(actual_cost_usd or 0)),
                    Json(response_metadata or {}),
                    job_id,
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeConflictError("Job de modelagem não está gerando.")
            return dict(row)

    def fail_format_modeling_job(self, job_id, error_message):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'failed', error_message = %s, updated_at = NOW()
                 WHERE id = %s AND status IN ('queued', 'generating')
                """,
                (str(error_message)[:4000], job_id),
            )

    def get_format_modeling_job(self, job_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT j.*, f.name_pt AS format_name, f.aspect_ratio,
                       f.default_size, f.placement_spec, f.behavior_spec,
                       c.name AS client_name, c.logo_url, c.logo_upload_path,
                       c.primary_color, c.secondary_color, c.tone_of_voice
                  FROM cx_format_modeling_jobs j
                  JOIN cx_format_templates f ON f.id = j.format_template_id
                  LEFT JOIN cx_clients c ON c.id = j.client_id
                 WHERE j.id = %s
                """,
                (job_id,),
            )
            row = cursor.fetchone()
        if not row:
            raise CreativeNotFoundError("Job de modelagem não encontrado.")
        return dict(row)

    def list_format_modeling_jobs(self, format_template_id, limit=40):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT j.id, j.format_template_id, j.client_id, j.parent_job_id,
                       j.slot, j.reference_type, j.model, j.status, j.prompt,
                       j.refinement_instruction, j.asset_url,
                       j.estimated_cost_usd, j.actual_cost_usd, j.error_message,
                       j.created_at, j.updated_at, c.name AS client_name
                  FROM cx_format_modeling_jobs j
                  LEFT JOIN cx_clients c ON c.id = j.client_id
                 WHERE j.format_template_id = %s
                   AND j.status <> 'archived'
                 ORDER BY j.created_at DESC, j.id DESC
                 LIMIT %s
                """,
                (format_template_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def approve_format_modeling_job(self, job_id, slot):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id, format_template_id, reference_type, prompt, asset_url
                  FROM cx_format_modeling_jobs
                 WHERE id = %s AND status IN ('review', 'approved')
                 FOR UPDATE
                """,
                (job_id,),
            )
            job = cursor.fetchone()
            if not job or not job.get("asset_url"):
                raise CreativeConflictError("Gere o mockup antes de aprová-lo.")
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = CASE WHEN id = %s THEN 'approved' ELSE status END,
                       slot = CASE WHEN id = %s THEN %s ELSE slot END,
                       updated_at = NOW()
                 WHERE id = %s
                """,
                (job_id, job_id, slot, job_id),
            )
            cursor.execute(
                """
                INSERT INTO cx_format_references (
                    format_template_id, slot, reference_type, prompt, asset_url,
                    status, source_modeling_job_id
                )
                VALUES (%s, %s, %s, %s, %s, 'approved', %s)
                ON CONFLICT (format_template_id, slot) DO UPDATE SET
                    reference_type = EXCLUDED.reference_type,
                    prompt = EXCLUDED.prompt,
                    asset_url = EXCLUDED.asset_url,
                    status = 'approved',
                    source_job_id = NULL,
                    source_modeling_job_id = EXCLUDED.source_modeling_job_id,
                    created_at = NOW()
                RETURNING id, slot, asset_url, status
                """,
                (
                    job["format_template_id"],
                    slot,
                    job["reference_type"],
                    job["prompt"],
                    job["asset_url"],
                    job_id,
                ),
            )
            return dict(cursor.fetchone())

    def archive_format_modeling_job(self, job_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_format_modeling_jobs
                   SET status = 'archived', updated_at = NOW()
                 WHERE id = %s AND status <> 'approved'
                RETURNING id, asset_url, input_references
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeConflictError(
                    "Referências aprovadas devem ser substituídas antes de arquivar."
                )
            return dict(row)

    def upsert_format_reference(
        self, format_template_id, slot, reference_type, prompt, asset_url, job_id
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                INSERT INTO cx_format_references (
                    format_template_id, slot, reference_type, prompt,
                    asset_url, status, source_job_id
                )
                VALUES (%s, %s, %s, %s, %s, 'approved', %s)
                ON CONFLICT (format_template_id, slot) DO UPDATE SET
                    reference_type = EXCLUDED.reference_type,
                    prompt = EXCLUDED.prompt,
                    asset_url = EXCLUDED.asset_url,
                    status = 'approved',
                    source_job_id = EXCLUDED.source_job_id,
                    created_at = NOW()
                RETURNING id, slot
                """,
                (
                    format_template_id,
                    slot,
                    reference_type,
                    prompt,
                    asset_url,
                    job_id,
                ),
            )
            return dict(cursor.fetchone())

    def list_campaign_assets(self, campaign_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.job_id, a.step_id, a.scene_id,
                       a.asset_type, a.asset_url,
                       a.position, a.title, a.caption, a.status, a.metadata,
                       j.campaign_id, j.prompt, j.script_text, j.model,
                       j.actual_cost_usd, j.created_at,
                       v.label AS variation_label, s.position AS step_position,
                       f.id AS format_template_id, f.name_pt AS format_name,
                       f.mechanic, f.media_type, f.aspect_ratio, f.default_size,
                       f.placement_spec, f.default_viewer_profile_id,
                       ch.name AS channel_name
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_campaign_variations v ON v.id = s.variation_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                 WHERE j.campaign_id = %s
                 ORDER BY a.position, a.created_at, a.id
                """,
                (campaign_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def reorder_campaign_assets(self, campaign_id, asset_ids):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                 WHERE j.campaign_id = %s
                 FOR UPDATE
                """,
                (campaign_id,),
            )
            available = {row["id"] for row in cursor.fetchall()}
            if set(asset_ids) != available or len(asset_ids) != len(available):
                raise CreativeConflictError(
                    "A ordenação deve conter todos os assets da campanha uma vez."
                )
            cursor.execute(
                """
                UPDATE cx_generated_assets a
                   SET position = position + 1000
                  FROM cx_generation_jobs j
                 WHERE a.job_id = j.id AND j.campaign_id = %s
                """,
                (campaign_id,),
            )
            for position, asset_id in enumerate(asset_ids, start=1):
                cursor.execute(
                    """
                    UPDATE cx_generated_assets
                       SET position = %s
                     WHERE id = %s
                    """,
                    (position, asset_id),
                )

    def delete_campaign_asset(self, campaign_id, asset_id):
        with self._write() as cursor:
            cursor.execute(
                """
                DELETE FROM cx_generated_assets a
                 USING cx_generation_jobs j
                 WHERE a.id = %s
                   AND a.job_id = j.id
                   AND j.campaign_id = %s
                RETURNING a.asset_url
                """,
                (asset_id, campaign_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset não encontrado na campanha.")
            return row["asset_url"]

    def update_campaign_asset(self, campaign_id, asset_id, title, caption):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_generated_assets a
                   SET title = %s, caption = %s
                  FROM cx_generation_jobs j
                 WHERE a.id = %s
                   AND a.job_id = j.id
                   AND j.campaign_id = %s
                RETURNING a.id, a.title, a.caption
                """,
                (title, caption, asset_id, campaign_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError("Asset não encontrado na campanha.")
            return dict(row)

    def create_public_collection(
        self, campaign_id, token, title, description, asset_ids,
        viewer_profiles, created_by
    ):
        with self._write() as cursor:
            cursor.execute(
                """
                SELECT id FROM cx_campaigns WHERE id = %s FOR UPDATE
                """,
                (campaign_id,),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Campanha não encontrada.")
            cursor.execute(
                """
                SELECT a.id
                  FROM cx_generated_assets a
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                 WHERE j.campaign_id = %s AND a.id = ANY(%s)
                """,
                (campaign_id, asset_ids),
            )
            found = {row["id"] for row in cursor.fetchall()}
            if found != set(asset_ids):
                raise CreativeConflictError(
                    "Um ou mais assets não pertencem à campanha."
                )
            cursor.execute(
                """
                INSERT INTO cx_public_creative_collections (
                    campaign_id, token, title, description, created_by
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, token
                """,
                (campaign_id, token, title, description, created_by),
            )
            collection = dict(cursor.fetchone())
            for position, asset_id in enumerate(asset_ids, start=1):
                cursor.execute(
                    """
                    INSERT INTO cx_public_collection_assets (
                        collection_id, asset_id, position, viewer_profile_id
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        collection["id"], asset_id, position,
                        viewer_profiles.get(asset_id),
                    ),
                )
            return collection

    def list_public_collections(self, campaign_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.id, c.campaign_id, c.token, c.title, c.description,
                       c.is_active, c.created_at, c.revoked_at,
                       COUNT(a.asset_id)::integer AS asset_count
                  FROM cx_public_creative_collections c
                  LEFT JOIN cx_public_collection_assets a
                    ON a.collection_id = c.id
                 WHERE c.campaign_id = %s
                 GROUP BY c.id
                 ORDER BY c.created_at DESC
                """,
                (campaign_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def revoke_public_collection(self, campaign_id, collection_id):
        with self._write() as cursor:
            cursor.execute(
                """
                UPDATE cx_public_creative_collections
                   SET is_active = FALSE, revoked_at = NOW()
                 WHERE id = %s AND campaign_id = %s AND is_active = TRUE
                RETURNING id
                """,
                (collection_id, campaign_id),
            )
            if not cursor.fetchone():
                raise CreativeNotFoundError("Link público ativo não encontrado.")

    def get_public_collection(self, token):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT pc.id, pc.campaign_id, pc.title, pc.description,
                       pc.created_at, c.name AS campaign_name,
                       cl.name AS client_name, cl.logo_url,
                       cl.logo_upload_path, cl.primary_color, cl.secondary_color
                  FROM cx_public_creative_collections pc
                  JOIN cx_campaigns c ON c.id = pc.campaign_id
                  JOIN cx_clients cl ON cl.id = c.client_id
                 WHERE pc.token = %s AND pc.is_active = TRUE
                """,
                (token,),
            )
            collection = cursor.fetchone()
            if not collection:
                raise CreativeNotFoundError("Apresentação não encontrada ou revogada.")
            cursor.execute(
                """
                SELECT a.id, a.asset_type, a.asset_url, a.title, a.caption,
                       a.status, ca.position, j.prompt, j.script_text,
                       f.slug AS format_slug, f.name_pt AS format_name,
                       f.mechanic, f.media_type,
                       f.aspect_ratio, f.default_size, ch.name AS channel_name,
                       v.label AS variation_label, s.position AS step_position,
                       vp.id AS viewer_profile_id, vp.slug AS viewer_slug,
                       vp.name AS viewer_name, vp.viewer_kind,
                       vp.logo_asset_ref AS viewer_logo_asset_ref,
                       vp.palette AS viewer_palette,
                       vp.shell_spec AS viewer_shell_spec,
                       vp.disclaimer AS viewer_disclaimer
                  FROM cx_public_collection_assets ca
                  JOIN cx_generated_assets a ON a.id = ca.asset_id
                  JOIN cx_generation_jobs j ON j.id = a.job_id
                  LEFT JOIN cx_variation_steps s ON s.id = a.step_id
                  LEFT JOIN cx_campaign_variations v ON v.id = s.variation_id
                  LEFT JOIN cx_format_templates f
                    ON f.id = COALESCE(j.format_template_id, s.format_template_id)
                  LEFT JOIN cx_channels ch ON ch.id = f.channel_id
                  LEFT JOIN cx_creative_viewer_profiles vp
                    ON vp.id = COALESCE(
                        ca.viewer_profile_id,
                        f.default_viewer_profile_id,
                        (
                            SELECT fallback.id
                              FROM cx_creative_viewer_profiles fallback
                             WHERE fallback.slug = CASE
                                 WHEN f.placement_spec->>'context' = 'tv'
                                 THEN 'netflix'
                                 ELSE 'g1'
                             END
                               AND fallback.is_active = TRUE
                             LIMIT 1
                        )
                    )
                 WHERE ca.collection_id = %s
                 ORDER BY ca.position
                """,
                (collection["id"],),
            )
            result = dict(collection)
            result["assets"] = [dict(row) for row in cursor.fetchall()]
            return result

    def get_public_collection_asset(self, token, asset_id):
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.id, a.asset_url, a.asset_type
                  FROM cx_public_creative_collections pc
                  JOIN cx_public_collection_assets ca
                    ON ca.collection_id = pc.id
                  JOIN cx_generated_assets a ON a.id = ca.asset_id
                 WHERE pc.token = %s
                   AND pc.is_active = TRUE
                   AND a.id = %s
                """,
                (token, asset_id),
            )
            row = cursor.fetchone()
            if not row:
                raise CreativeNotFoundError(
                    "Mídia não encontrada ou apresentação revogada."
                )
            return dict(row)
