"""Inclui aeroportos, arenas, centros de eventos e hubs metroviários solicitados.

Os fluxos sem fonte pública comparável ficam explicitamente como estimativa ou
a validar. Uso: python -m migrations.add_places_transport_and_events
"""
from __future__ import annotations

from datetime import datetime, timezone

from aicentralv2 import create_app
from aicentralv2.places.audience import enrich_point_inventory, enrich_public_payload
from aicentralv2.places.repository import get_by_slug, insert_place, update_place
from aicentralv2.places.schema import CITY_LABELS, normalize_payload
from aicentralv2.places.share import make_preview_token


SOURCES = {
    "gru": ("GRU Airport — site oficial", "https://www.gru.com.br/pt"),
    "cmt": ("PAX Aeroportos — Campo de Marte", "https://paxaeroportos.com.br/campodemarte/"),
    "cat": ("São Paulo Catarina Aeroporto Executivo", "https://spcatarinaaeroporto.com.br/"),
    "jac": ("Agência Brasil — operação comercial em Jacarepaguá", "https://agenciabrasil.ebc.com.br/geral/noticia/2019-10/no-rio-aeroporto-de-jacarepagua-inicia-operacao-de-voos-comerciais"),
    "min": ("Portal Oficial de Belo Horizonte — Mineirão", "https://portalbelohorizonte.com.br/o-que-fazer/ao-ar-livre-e-esportes/futebol/estadio-mineirao"),
    "rio": ("Riocentro — site oficial", "https://riocentro.com.br/"),
    "pol": ("Rock in Rio — história e informações oficiais", "https://rockinrio.com/rio/pt-br/historia/"),
    "msp": ("Metrô de São Paulo — rede e estações", "https://www.metro.sp.gov.br/"),
    "mrj": ("MetrôRio — estações e rede", "https://www.metrorio.com.br/"),
}


def point(name, kind, lat, lng, commercial, *audiences):
    return {"id": name.lower().replace(" ", "-")[:32], "name": name, "kind": kind, "lat": lat, "lng": lng,
            "radius_m": 350 if kind != "halo" else 800, "reach": "A validar", "reach_status": "to_validate",
            "commercial": commercial, "defense": commercial, "audiences": list(audiences),
            "formats": ["Display no app", "Vídeo vertical", "Portais"]}


def record(slug, title, code, city, place_type, operator, lat, lng, source, profile, points, *, subtitle="", target=None, weekly=None):
    source_title, source_url = SOURCES[source]
    payload = {
        "geo": {"lat": lat, "lng": lng, "zoom": 14}, "points": points,
        "metrics": {"passengers": {"label": "A validar", "source": source_title, "source_status": "to_validate"},
                    "four_weeks": {"label": "A validar", "source": source_title, "source_status": "to_validate"},
                    "addressable": {"label": "A validar", "source": "Requer parceiro de location data", "source_status": "to_validate"}},
        "catchment": {"population": {"label": "A validar", "source_status": "to_validate"},
                       "density": {"label": "A validar", "source_status": "to_validate"}, "neighborhoods": [], "profile": profile},
        "target_audience": target or ["Mobilidade e deslocamento", "Trabalho e estudo", "Lazer e serviços", "Moradores do entorno"],
        "weekly_movement": {"values": weekly or [62, 72, 78, 82, 88, 100, 68], "source": "Curva de planejamento; validar com operador", "source_status": "estimate", "note": "Índice relativo, não contagem de pessoas."},
        "research": {"query": title, "notes": "Fontes públicas consultadas via Firecrawl; fluxo e audiência exigem validação comercial.", "sources": [{"title": source_title, "url": source_url}]},
        "offer": {"lead": "O recorte comercial é o ponto e sua ocasião de uso; não some os pontos.", "lines": []},
        "methodology": {"title": "Como ler este place", "body": "Fluxo físico não é audiência única. Toda estimativa deve ser validada com o operador e o parceiro de dados."},
    }
    payload = enrich_point_inventory(normalize_payload(payload), place_type=place_type, city=city, overwrite=True)
    payload = enrich_public_payload(payload, place_type=place_type, slug=slug, city_label=CITY_LABELS[city])
    return {"slug": slug, "title": title, "code": code, "city": city, "place_type": place_type, "operator": operator,
            "subtitle": subtitle or profile, "status": "published", "payload": normalize_payload(payload)}


PLACES = [
    record("guarulhos", "Aeroporto Internacional de São Paulo/Guarulhos", "GRU", "sp", "aeroporto", "GRU Airport", -23.4356, -46.4731, "gru", "Principal porta aérea internacional do país; viagem, conexão e serviços aeroportuários.", [point("Terminal 3", "terminal", -23.4345, -46.4746, "Embarque internacional, conexão e espera.", "Viajantes internacionais", "Alto tempo de permanência"), point("Terminal 2", "terminal", -23.4334, -46.4718, "Fluxo doméstico e conexão.", "Viajantes nacionais", "Famílias e trabalho"), point("Curbside e transporte", "mobilidade", -23.4365, -46.4750, "Chegada, retirada e apps de mobilidade.", "Motoristas", "Acompanhantes")], weekly=[74,82,86,89,95,100,82]),
    record("campo-de-marte", "Aeroporto Campo de Marte", "CMT", "sp", "aeroporto", "PAX Aeroportos", -23.5091, -46.6364, "cmt", "Aviação geral, executiva, helicópteros e operações na zona norte de São Paulo.", [point("Terminal executivo", "terminal", -23.5091, -46.6364, "Recepção e operação de aviação geral.", "Executivos", "Tripulações"), point("Heliponto e hangares", "premium", -23.5083, -46.6376, "Serviços e circulação ligada à aviação executiva.", "Aviação corporativa", "Serviços especializados")], target=["Executivos e tripulações", "Serviços corporativos", "Mobilidade na zona norte", "Aviação geral"]),
    record("catarina", "São Paulo Catarina Aeroporto Executivo", "CAT", "sp", "aeroporto", "JHSF / Catarina", -23.4256, -47.1558, "cat", "Aeroporto executivo integrado ao eixo de São Roque e ao complexo Catarina.", [point("Terminal executivo", "terminal", -23.4256, -47.1558, "Chegada e espera de passageiros de aviação executiva.", "Executivos", "Turismo de alta renda"), point("Catarina Fashion Outlet", "premium", -23.4198, -47.1509, "Compras, gastronomia e serviços do complexo.", "Compradores", "Famílias em lazer")]),
    record("jacarepagua", "Aeroporto de Jacarepaguá", "JAC", "rj", "aeroporto", "PAX Aeroportos", -22.9883, -43.3669, "jac", "Aviação geral e regional no eixo Barra–Jacarepaguá, próximo a produção audiovisual e serviços.", [point("Terminal", "terminal", -22.9883, -43.3669, "Chegada, embarque e espera.", "Viajantes regionais", "Tripulações"), point("Acesso Ayrton Senna", "mobilidade", -22.9891, -43.3655, "Deslocamento e conexão com a Barra.", "Motoristas", "Mobilidade")]),
    record("mineirao", "Mineirão", "MIN", "bh", "evento", "Minas Arena", -19.8659, -43.9711, "min", "Estádio da Pampulha com jogos, shows e grande variação de público por calendário.", [point("Esplanada", "terminal", -19.8659, -43.9711, "Concentração pré e pós-evento.", "Torcedores", "Público de shows"), point("Portões e arquibancadas", "premium", -19.8667, -43.9724, "Entrada e permanência em dia de evento.", "Público com ingresso", "Hospitalidade"), point("Entorno Pampulha", "halo", -19.8645, -43.9688, "Chegada e dispersão.", "Mobilidade", "Moradores")], weekly=[35,38,42,45,52,100,70]),
    record("riocentro", "Riocentro", "RIO", "rj", "evento", "GL events", -22.9781, -43.4103, "rio", "Centro de convenções na Barra; o fluxo depende da agenda de feiras, congressos e credenciamento.", [point("Pavilhões", "terminal", -22.9781, -43.4103, "Credenciamento e circulação de visitantes.", "Congressistas", "Expositores"), point("Entrada e transporte", "mobilidade", -22.9793, -43.4093, "Chegada por carro, táxi e apps.", "Mobilidade", "Prestadores"), point("Hotéis e Barra", "halo", -22.9820, -43.4070, "Hospedagem e serviços no entorno.", "Visitantes de fora", "Turismo de negócios")], weekly=[45,48,52,55,60,72,58]),
    record("parque-olimpico", "Parque Olímpico da Barra", "POL", "rj", "evento", "Prefeitura do Rio / produção do evento", -22.9765, -43.3949, "pol", "Complexo de entretenimento e esporte; em Rock in Rio a Cidade do Rock transforma o fluxo, a permanência e a mobilidade do entorno.", [point("Cidade do Rock", "terminal", -22.9765, -43.3949, "Palcos, ativações e longa permanência em edição do Rock in Rio.", "Público de festivais", "Jovens e grupos"), point("Acesso e transporte", "mobilidade", -22.9782, -43.3932, "Chegada, ônibus especiais e dispersão.", "Mobilidade", "Acompanhantes"), point("Vila Olímpica", "halo", -22.9742, -43.3925, "Serviços e circulação no entorno do complexo.", "Moradores", "Trabalhadores")], weekly=[30,34,38,42,48,58,44]),
]

for slug, title, code, city, lat, lng, source, line in [
    ("metro-se", "Metrô Sé", "MSE", "sp", -23.5504, -46.6340, "msp", "Maior conexão central entre linhas 1 e 3; comércio, trabalho e serviços."),
    ("metro-luz", "Metrô Luz", "MLZ", "sp", -23.5335, -46.6333, "msp", "Integração de metrô e trens, acesso ao centro histórico e equipamentos culturais."),
    ("metro-tatuape", "Metrô Tatuapé", "MTT", "sp", -23.5404, -46.5765, "msp", "Integração metroviária, ferroviária, shopping e deslocamento da zona leste."),
    ("metro-pinheiros", "Metrô Pinheiros", "MPN", "sp", -23.5660, -46.7010, "msp", "Conexão de metrô, trem e Faria Lima; trabalho, estudo e vida noturna."),
    ("metro-paulista-consolacao", "Metrô Paulista/Consolação", "MPC", "sp", -23.5554, -46.6608, "msp", "Conexão na Paulista entre trabalho, cultura, turismo e comércio."),
    ("metro-carioca", "Metrô Carioca", "MCA", "rj", -22.9030, -43.1772, "mrj", "Hub do Centro com trabalho, serviços públicos e conexões de ônibus."),
    ("metro-central-rj", "Metrô Central", "MCR", "rj", -22.9038, -43.1871, "mrj", "Integração com trens, VLT e ônibus no principal nó de mobilidade do Rio."),
    ("metro-botafogo", "Metrô Botafogo", "MBF", "rj", -22.9517, -43.1838, "mrj", "Estação de bairro com trabalho, serviços, praias e vida noturna."),
    ("metro-maracana", "Metrô Maracanã", "MMR", "rj", -22.9122, -43.2302, "mrj", "Porta de jogos, eventos e campus universitário."),
    ("metro-jardim-oceanico", "Metrô Jardim Oceânico", "MJO", "rj", -23.0067, -43.3074, "mrj", "Integração Barra, BRT, praia, moradia e serviços."),
]:
    PLACES.append(record(slug, title, code, city, "evento", "Metrô de São Paulo" if city == "sp" else "MetrôRio", lat, lng, source, line,
        [point("Plataformas e mezanino", "terminal", lat, lng, "Espera, troca de linha e fluxo de passageiros.", "Commuters", "Estudantes e trabalhadores"), point("Acessos e entorno", "mobilidade", lat + .0007, lng + .0007, "Chegada a pé, ônibus, táxi e aplicativos.", "Mobilidade", "Comércio local")], weekly=[72,100,98,96,94,62,48]))


def run():
    app = create_app()
    with app.app_context():
        for item in PLACES:
            existing = get_by_slug(item["slug"])
            record = {**item, "preview_token": (existing or {}).get("preview_token") or make_preview_token(), "published_at": (existing or {}).get("published_at") or datetime.now(timezone.utc), "created_by": (existing or {}).get("created_by")}
            if existing:
                record["id"] = existing["id"]
                update_place(existing["id"], record)
            else:
                insert_place(record)
    return len(PLACES)


if __name__ == "__main__":
    print(f"{run()} novos Places inseridos ou atualizados.")
