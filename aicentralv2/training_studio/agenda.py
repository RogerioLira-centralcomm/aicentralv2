"""Grade da Imersão em Mídias Complexas — especialistas."""

from .content import atencao, cadu, canais, coffee, dinamica, lucas, max, places

CHANNELS = [
    {"key": "linkedin", "name": "LinkedIn", "site": "https://www.linkedin.com"},
    {"key": "instagram", "name": "Instagram", "site": "https://www.instagram.com"},
    {"key": "tiktok", "name": "TikTok", "site": "https://www.tiktok.com"},
    {"key": "g1", "name": "g1", "site": "https://g1.globo.com"},
    {"key": "cnn", "name": "CNN Brasil", "site": "https://www.cnnbrasil.com.br"},
    {"key": "sbt", "name": "SBT", "site": "https://www.sbt.com.br"},
    {"key": "serasa", "name": "Serasa", "site": "https://www.serasa.com.br"},
    {"key": "uber", "name": "Uber", "site": "https://www.uber.com"},
    {"key": "99", "name": "99", "site": "https://99app.com"},
    {"key": "ifood", "name": "iFood", "site": "https://www.ifood.com.br"},
    {"key": "amazon", "name": "Amazon", "site": "https://www.amazon.com.br"},
    {"key": "spotify", "name": "Spotify", "site": "https://www.spotify.com"},
    {"key": "netflix", "name": "Netflix", "site": "https://www.netflix.com"},
    {"key": "prime", "name": "Prime Video", "site": "https://www.primevideo.com"},
    {"key": "disney", "name": "Disney+", "site": "https://www.disneyplus.com"},
    {"key": "hbo", "name": "Max / HBO", "site": "https://www.max.com"},
]

OBSOLETE_SLUGS = ("mercado-canais",)

ILLUSTRATION_SESSIONS = (
    "atencao-mercado",
    "mapa-canais",
    "ia-cadu",
    "max-formatos",
    "lucas-interativos",
    "lucas-programatica",
    "dinamica-planos",
)


SESSIONS = [
    {
        "slug": "atencao-mercado",
        "ordem": 1,
        "titulo": "Comprem atenção, não impressão",
        "horario_inicio": "09:30",
        "horario_fim": "09:45",
        "facilitadores": ["Alexandre Borges", "Apolo Lira"],
        "tipo": "bloco",
        "html": atencao.html,
        "notas_instrutor": atencao.NOTAS,
        "fontes": atencao.FONTES,
        "illustration": (
            "Minimal corporate illustration, navy and mint, empty attention "
            "currency — a scale weighing a screen against a clock, no text, no logos."
        ),
    },
    {
        "slug": "mapa-canais",
        "ordem": 2,
        "titulo": "De onde sai a verba",
        "horario_inicio": "09:45",
        "horario_fim": "10:00",
        "facilitadores": ["Alexandre Borges", "Apolo Lira"],
        "tipo": "bloco",
        "html": canais.html,
        "notas_instrutor": canais.NOTAS,
        "fontes": canais.FONTES,
        "illustration": (
            "Four quiet inventory blocks on a dark navy desk, mint accent, "
            "flat corporate, no logos, no text, no brand marks."
        ),
    },
    {
        "slug": "dooh-places",
        "ordem": 3,
        "titulo": "O lugar não é a audiência",
        "horario_inicio": "10:00",
        "horario_fim": "10:20",
        "facilitadores": ["Apolo Lira", "Alexandre Borges"],
        "tipo": "bloco",
        "html": places.html,
        "notas_instrutor": places.NOTAS,
        "fontes": places.FONTES,
        "illustration": None,
    },
    {
        "slug": "ia-cadu",
        "ordem": 4,
        "titulo": "Cadu começa na restrição",
        "horario_inicio": "10:20",
        "horario_fim": "10:35",
        "facilitadores": ["Apolo Lira"],
        "tipo": "bloco",
        "html": cadu.html,
        "notas_instrutor": cadu.NOTAS,
        "fontes": cadu.FONTES,
        "illustration": (
            "A planner desk with five ordered steps as mint marks on navy paper, "
            "no text, no screenshots, no logos."
        ),
    },
    {
        "slug": "coffee",
        "ordem": 5,
        "titulo": "Intervalo · escolher a moeda",
        "horario_inicio": "10:35",
        "horario_fim": "10:45",
        "facilitadores": [],
        "tipo": "intervalo",
        "html": coffee.html,
        "notas_instrutor": coffee.NOTAS,
        "fontes": coffee.FONTES,
        "illustration": None,
    },
    {
        "slug": "max-formatos",
        "ordem": 6,
        "titulo": "O plano quebra no formato",
        "horario_inicio": "10:45",
        "horario_fim": "11:20",
        "facilitadores": ["Max III"],
        "tipo": "bloco",
        "html": max.html,
        "notas_instrutor": max.NOTAS,
        "fontes": max.FONTES,
        "illustration": (
            "A campaign structure cracking at the format layer, navy and mint, "
            "minimal, no text, no logos."
        ),
    },
    {
        "slug": "lucas-interativos",
        "ordem": 7,
        "titulo": "O gesto prova a first-wave",
        "horario_inicio": "11:20",
        "horario_fim": "11:35",
        "facilitadores": ["Lucas Facchini"],
        "tipo": "bloco",
        "html": lucas.html_interativos,
        "notas_instrutor": lucas.NOTAS_INTERATIVOS,
        "fontes": lucas.FONTES_INTERATIVOS,
        "illustration": (
            "A hand choosing one of three silent panels, mint highlight, navy ground, "
            "no UI, no logos, no text."
        ),
    },
    {
        "slug": "lucas-programatica",
        "ordem": 8,
        "titulo": "Aberto não é qualquer impressão",
        "horario_inicio": "11:35",
        "horario_fim": "11:50",
        "facilitadores": ["Lucas Facchini"],
        "tipo": "bloco",
        "html": lucas.html_programatica,
        "notas_instrutor": lucas.NOTAS_PROGRAMATICA,
        "fontes": lucas.FONTES_PROGRAMATICA,
        "illustration": (
            "A clean inventory grid with one premium cell lit mint, rest navy, "
            "no logos, no text."
        ),
    },
    {
        "slug": "dinamica-planos",
        "ordem": 9,
        "titulo": "Banca: moeda, família, first-wave",
        "horario_inicio": "11:50",
        "horario_fim": "12:30",
        "facilitadores": ["Time"],
        "tipo": "bloco",
        "html": dinamica.html,
        "notas_instrutor": dinamica.NOTAS,
        "fontes": dinamica.FONTES,
        "illustration": (
            "Three sealed briefing envelopes on a dark table, mint edge, "
            "corporate, no text, no logos."
        ),
    },
]


def session_html(item):
    builder = item.get("html")
    return builder() if callable(builder) else str(builder or "")
