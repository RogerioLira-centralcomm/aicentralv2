"""Simulações de anúncio por canal: a mesma lista alimenta a página (channels.py) e o gerador de imagens
(scripts/generate_channel_ad_variations.py). Marcas de exemplo giram entre os formatos de cada canal.

Cada item: (chave, orientação 'p'|'l', título, formato, descrição, cena em inglês para a imagem).
"""
BRANDS = [('Coca-Cola', 'the Coca-Cola brand (red, classic logo, a cold bottle)'),
          ('Dove', 'the Dove brand (white and soft blue, dove logo, a product bottle)'),
          ('Nescau', 'the Nescau brand (Nestlé chocolate drink, brown and yellow packaging)'),
          ('Itambé', 'the Itambé brand (dairy, blue packaging, milk and yogurt)'),
          ('Danone', 'the Danone brand (yogurt, blue and white, fresh fruit)'),
          ('Nespresso', 'the Nespresso brand (premium coffee capsules, dark and silver, an espresso cup)'),
          ('Havaianas', 'the Havaianas brand (colorful Brazilian flip-flops, summery, the brand logo on the strap)'),
          ('Unimed', 'the Unimed brand (Brazilian health plan, green identity, caring doctor and family)'),
          ('Netshoes', 'the Netshoes brand (sports retailer, sneakers and gear, bold dark purple identity)'),
          ('Mercado Livre', 'the Mercado Livre brand (e-commerce, yellow and blue identity, the handshake logo, parcels)'),
          ('Nike', 'the Nike brand (black and white, the swoosh logo, an athlete in motion, running shoes)')]
ROTATION = BRANDS[:5]  # the default brand cycle; OVERRIDES pins a brand to a specific ad where it fits better
OVERRIDES = {
    'twitch-pre-roll': 'Nike', 'twitch-overlay': 'Netshoes', 'youtube-shorts': 'Nike', 'youtube-tv': 'Havaianas',
    'instagram-feed': 'Havaianas', 'instagram-reels': 'Nike', 'instagram-stories': 'Nespresso',
    'tiktok-efeito': 'Havaianas', 'tiktok-desafio': 'Nike', 'linkedin-mensagem': 'Unimed', 'linkedin-lead-gen': 'Unimed',
    'linkedin-document-ad': 'Nespresso', 'amazon-ads-busca-patrocinada': 'Nespresso', 'amazon-ads-marca-loja-propria': 'Havaianas',
    'google-dv360-display-300x250': 'Mercado Livre', 'google-dv360-mobile-320x100': 'Netshoes', 'google-dv360-native': 'Unimed',
    'eletromidia-elevador': 'Unimed', 'eletromidia-shopping-totem': 'Netshoes', 'logan-aeroporto': 'Nespresso', 'logan-empena': 'Nike',
    'globoplay-pre-roll': 'Unimed', 'netflix-mobile': 'Mercado Livre', 'spotify-home-takeover': 'Nike', 'spotify-podcast': 'Nespresso',
    'samsung-tv-plus-home-banner': 'Mercado Livre', 'disney-plus-mobile': 'Havaianas',
}


def brand_for(slug, key, position):
    """(name, prompt text) of the brand shown in this ad."""
    named = OVERRIDES.get(f'{slug}-{key}')
    if named:
        return next(brand for brand in BRANDS if brand[0] == named)
    return ROTATION[(position + _offset(slug)) % len(ROTATION)]

CHANNEL_ADS = {
    'ifood': ('Visual language of a Brazilian food-delivery app, red (#EA1D2C) and white, rounded UI, no app logo.', [
        ('banner-home', 'p', 'Banner na home', 'Banner patrocinado · home', 'Topo da home, quando a pessoa escolhe o que pedir.', 'smartphone screen of the app home with a top sponsored banner'),
        ('restaurante-destaque', 'p', 'Marca em destaque nos restaurantes', 'Card patrocinado · lista', 'Posição de destaque na lista de restaurantes e mercados.', 'smartphone screen of a restaurant list with a highlighted sponsored product card'),
        ('cupom-checkout', 'p', 'Cupom no carrinho', 'Cupom · checkout', 'Oferta exibida no momento exato da compra.', 'smartphone checkout screen with a coupon card for the brand product'),
        ('busca-patrocinada', 'p', 'Resultado patrocinado na busca', 'Busca patrocinada', 'Aparece quando a pessoa pesquisa a categoria do produto.', 'smartphone search results with the first result a sponsored brand product'),
        ('notificacao-push', 'p', 'Notificação push', 'Push · tela bloqueada', 'Mensagem na tela bloqueada, no horário de maior pedido.', 'smartphone lock screen with a push notification from the app about the brand')]),
    'eletromidia': ('Out-of-home advertising photo in a Brazilian metropolis, sharp and premium.', [
        ('elevador', 'p', 'Tela no elevador', 'Mídia indoor · elevador', 'Atinge moradores e trabalhadores todos os dias, a poucos centímetros.', 'vertical digital screen inside a modern office elevator showing the ad'),
        ('painel-rua', 'l', 'Painel digital de rua', 'DOOH · painel urbano', 'Alto impacto em avenidas de grande fluxo.', 'large digital billboard on a busy São Paulo avenue at dusk'),
        ('abrigo-onibus', 'p', 'Abrigo de ônibus', 'Mobiliário urbano', 'Presença no trajeto diário de quem usa transporte.', 'bus shelter lightbox ad with people waiting'),
        ('metro-estacao', 'l', 'Estação de metrô', 'Mídia em transporte', 'Audiência cativa no tempo de espera.', 'subway platform digital panel with the ad'),
        ('shopping-totem', 'p', 'Totem de shopping', 'Totem digital', 'Perto do ponto de venda, com público em modo de compra.', 'digital totem in a mall corridor with the ad')]),
    'amazon-ads': ('Photorealistic e-commerce and streaming advertising mockups, Amazon-like orange and dark blue palette but no real Amazon logo.', [
        ('busca-patrocinada', 'p', 'Produto patrocinado na busca', 'Sponsored Products', 'Aparece nos resultados de busca de quem já quer comprar.', 'smartphone shopping app search results with a sponsored product listing'),
        ('banner-pagina-produto', 'l', 'Banner na página de produto', 'Display · página de produto', 'Reforça a marca perto da decisão de compra.', 'laptop screen of a product page with a display banner ad on the side'),
        ('video-ctv', 'l', 'Vídeo em streaming', 'Vídeo · CTV', 'Vídeo de 15 a 30 s em serviços de streaming.', 'living room TV showing a pre-roll video ad of the brand'),
        ('home-loja', 'p', 'Destaque na home da loja', 'Banner · home', 'Visibilidade para a marca logo na entrada.', 'smartphone shopping home with a hero brand banner'),
        ('marca-loja-propria', 'l', 'Loja da marca', 'Brand Store', 'Vitrine própria com todos os produtos da marca.', 'laptop showing a branded store page of the brand')]),
    'google-dv360': ('Programmatic display advertising mockups on real-looking news and content websites, clean.', [
        ('display-300x250', 'l', 'Display retângulo médio', 'Display · 300x250', 'O formato mais comprado, presente em milhares de sites.', 'news article webpage on a laptop with a 300x250 ad box in the sidebar'),
        ('display-970x250', 'l', 'Billboard no topo do site', 'Display · 970x250', 'Alto impacto no topo da página.', 'portal webpage with a wide 970x250 billboard ad at the top'),
        ('mobile-320x100', 'p', 'Banner mobile', 'Display · 320x100', 'Banner fixo em sites e apps no celular.', 'smartphone news article with a banner ad pinned at the bottom'),
        ('video-instream', 'l', 'Vídeo in-stream', 'Vídeo · in-stream', 'Anúncio de vídeo antes do conteúdo.', 'laptop video player with a pre-roll ad and a Skip button'),
        ('native', 'p', 'Anúncio nativo', 'Nativo · feed de conteúdo', 'Se integra ao estilo do conteúdo ao redor.', 'smartphone article feed with a native sponsored card among articles')]),
    'logan': ('Out-of-home advertising photo in Brazil, sharp and premium.', [
        ('frontlight', 'l', 'Outdoor de estrada', 'OOH · outdoor', 'Visibilidade em rodovias e grandes avenidas.', 'large roadside billboard along a highway at sunset'),
        ('led-avenida', 'l', 'Painel de LED', 'DOOH · LED', 'Troca de mensagem por horário e por dia.', 'large LED billboard on an urban avenue at night'),
        ('empena', 'p', 'Empena de prédio', 'OOH · empena', 'Grande formato que domina a paisagem.', 'giant building-side mural ad on a tall building'),
        ('mobiliario', 'p', 'Relógio de rua', 'Mobiliário urbano', 'Presença no caminho a pé.', 'street clock lightbox ad on a city sidewalk'),
        ('aeroporto', 'l', 'Aeroporto', 'OOH · aeroporto', 'Público de maior renda em viagem.', 'airport terminal large digital panel with the ad')]),
    'instagram': ('Visual language of a social media photo/video app: clean white UI, rounded corners, no app logo.', [
        ('feed', 'p', 'Post patrocinado no feed', 'Feed · imagem', 'Anúncio entre os posts de quem a pessoa segue.', 'smartphone social feed with a sponsored photo post of the brand and a Saiba mais button'),
        ('stories', 'p', 'Stories em tela cheia', 'Stories · 9:16', 'Tela cheia, vertical, com ação por deslize.', 'smartphone full-screen vertical story ad of the brand with a swipe-up cue'),
        ('reels', 'p', 'Reels', 'Reels · vídeo curto', 'Vídeo curto entre os Reels mais vistos.', 'smartphone reels video ad of the brand, a person enjoying the product'),
        ('carrossel', 'p', 'Carrossel', 'Carrossel · 1:1', 'Vários produtos ou ângulos no mesmo anúncio.', 'smartphone post with a carousel ad showing several brand products'),
        ('explorar', 'p', 'Aba Explorar', 'Explorar · grade', 'Descoberta de marcas por interesse.', 'smartphone explore grid with a sponsored brand tile')]),
    'kwai': ('Visual language of a short-video social app: dark UI, bright accents, no app logo.', [
        ('feed-video', 'p', 'Vídeo no feed', 'Vídeo · feed', 'Anúncio de vídeo entre vídeos curtos.', 'smartphone vertical short-video feed with a sponsored ad video of the brand'),
        ('abertura-app', 'p', 'Abertura do app', 'Brand takeover', 'Primeira tela vista ao abrir o app.', 'smartphone splash screen full ad of the brand'),
        ('desafio', 'p', 'Desafio de marca', 'Hashtag challenge', 'Convida os usuários a criar vídeos com a marca.', 'smartphone showing a branded hashtag challenge page with many user videos'),
        ('efeito', 'p', 'Efeito de marca', 'Efeito de câmera', 'Filtro com a marca para as pessoas usarem.', 'smartphone camera screen with a branded AR effect on a smiling person'),
        ('live-shop', 'p', 'Live com compra', 'Live shopping', 'Venda ao vivo com produto em destaque.', 'smartphone live stream with a product card of the brand and a buy button')]),
    'linkedin': ('Visual language of a professional network: clean blue and white UI, no app logo.', [
        ('sponsored-content', 'l', 'Conteúdo patrocinado', 'Feed · imagem', 'Post no feed de profissionais por cargo e setor.', 'laptop professional feed with a sponsored post of the brand'),
        ('mensagem', 'l', 'Mensagem patrocinada', 'Message Ad', 'Mensagem direta na caixa de entrada do decisor.', 'laptop inbox with a sponsored message from the brand'),
        ('video', 'p', 'Vídeo no feed', 'Vídeo · feed', 'Vídeo curto para quem decide compra.', 'smartphone professional feed with a sponsored video of the brand'),
        ('lead-gen', 'p', 'Formulário de lead', 'Lead Gen Form', 'Formulário já preenchido com dados do perfil.', 'smartphone lead-gen form prefilled with a sponsored brand header'),
        ('document-ad', 'l', 'Documento patrocinado', 'Document Ad', 'Material em páginas, lido dentro do feed.', 'laptop feed with a sponsored multi-page document carousel')]),
    'tiktok': ('Visual language of a short-video social app: dark UI, vertical video, no app logo.', [
        ('infeed', 'p', 'Anúncio In-Feed', 'In-Feed · 9:16', 'Vídeo vertical entre os vídeos Para você.', 'smartphone vertical video feed with a sponsored brand video and a Saiba mais button'),
        ('topview', 'p', 'TopView', 'TopView', 'Primeiro vídeo ao abrir o app, em tela cheia.', 'smartphone full-screen first video ad of the brand with sound icon'),
        ('desafio', 'p', 'Desafio patrocinado', 'Branded Hashtag Challenge', 'A marca lança um desafio e as pessoas participam.', 'smartphone hashtag challenge page of the brand with many user videos'),
        ('efeito', 'p', 'Efeito de marca', 'Branded Effect', 'Efeito de câmera com a marca.', 'smartphone camera with a branded AR effect on a smiling person'),
        ('spark', 'p', 'Spark Ads', 'Spark Ads', 'Impulsiona um vídeo orgânico de criador.', 'smartphone showing a creator video promoted as an ad for the brand')]),
    'twitch': ('Visual language of a game livestreaming platform: dark purple UI, no platform logo.', [
        ('pre-roll', 'l', 'Vídeo antes da live', 'Vídeo · pre-roll', 'Anúncio antes de a live começar.', 'laptop livestream player with a video ad before the stream'),
        ('overlay', 'l', 'Overlay na live', 'Overlay de transmissão', 'Marca dentro da tela do streamer.', 'game livestream screen with a branded overlay panel of the brand'),
        ('patrocinio-streamer', 'l', 'Patrocínio de streamer', 'Conteúdo patrocinado', 'O streamer usa e fala da marca.', 'streamer at a gaming desk drinking the brand product, sponsor banner on screen'),
        ('display-home', 'l', 'Banner na home', 'Display · home', 'Destaque na página inicial.', 'livestream platform homepage with a large display banner ad'),
        ('evento', 'l', 'Evento ao vivo', 'Ativação em evento', 'Presença em campeonato transmitido.', 'e-sports arena stage with giant screens branded with the brand')]),
    'youtube': ('Visual language of a video platform: white or dark UI, red progress bar, no platform logo.', [
        ('skippable', 'l', 'Vídeo com opção de pular', 'In-Stream · skippable', 'Anúncio antes ou durante o vídeo, pulável após 5 s.', 'laptop video player showing an ad of the brand with a Skip Ad button'),
        ('bumper', 'l', 'Bumper de 6 segundos', 'Bumper · 6 s', 'Mensagem curta e sem pular.', 'TV or laptop video player showing a short 6-second brand ad'),
        ('shorts', 'p', 'Shorts', 'Shorts · 9:16', 'Vertical entre vídeos curtos.', 'smartphone vertical shorts player with a brand ad'),
        ('masthead', 'l', 'Masthead', 'Masthead · home', 'Maior vitrine da home, por dia.', 'laptop video platform homepage with a huge masthead video banner of the brand'),
        ('tv', 'l', 'YouTube na TV', 'CTV · sala', 'Alcance em telas grandes, em família.', 'living room smart TV playing an ad of the brand')]),
    'amazon-music': ('Visual language of a music streaming app: dark UI with a bright blue accent, no app logo.', [
        ('audio-ad', 'p', 'Anúncio de áudio', 'Áudio · 30 s', 'Entre as músicas, com capa da marca na tela.', 'smartphone music player showing a sponsored audio ad cover of the brand'),
        ('banner-player', 'p', 'Banner no player', 'Display · player', 'Imagem clicável enquanto o áudio toca.', 'smartphone music player with a companion banner ad of the brand'),
        ('playlist-patrocinada', 'p', 'Playlist patrocinada', 'Playlist da marca', 'Playlist com o tom da marca.', 'smartphone showing a playlist page presented by the brand'),
        ('alexa', 'l', 'Em casa, no alto-falante', 'Áudio · smart speaker', 'Alcança a pessoa em casa, pela voz.', 'living room smart speaker with a subtle sound-wave graphic and the brand product on a table'),
        ('takeover', 'p', 'Takeover de sessão', 'Sessão patrocinada', 'Sem anúncios de concorrentes por um período.', 'smartphone app home with a full-page brand takeover')]),
    'deezer': ('Visual language of a music streaming app: dark UI with purple accent, no app logo.', [
        ('audio-ad', 'p', 'Anúncio de áudio', 'Áudio · 30 s', 'Entre as músicas, com capa da marca.', 'smartphone music player showing a sponsored audio ad of the brand'),
        ('banner-player', 'p', 'Banner no player', 'Display · player', 'Imagem clicável enquanto o áudio toca.', 'smartphone music player with a companion banner ad of the brand'),
        ('playlist', 'p', 'Playlist da marca', 'Playlist patrocinada', 'Curadoria no tom da marca.', 'smartphone playlist page presented by the brand'),
        ('home-takeover', 'p', 'Takeover na home', 'Display · home', 'Destaque total na entrada do app.', 'smartphone app home with a full-width brand takeover banner'),
        ('video-reward', 'p', 'Vídeo por recompensa', 'Video reward', 'A pessoa assiste e ganha tempo sem anúncios.', 'smartphone showing a video ad with a reward prompt for ad-free listening')]),
    'disney-plus': ('Visual language of a family streaming service: deep blue UI, no service logo.', [
        ('pre-roll', 'l', 'Vídeo antes do conteúdo', 'Pre-roll · CTV', 'Anúncio antes do filme ou série.', 'living room TV showing a pre-roll ad of the brand'),
        ('pause-ad', 'l', 'Anúncio na pausa', 'Pause Ad', 'Aparece quando a pessoa pausa o conteúdo.', 'TV paused on a movie with a small brand ad panel on screen'),
        ('home-banner', 'l', 'Banner na home', 'Display · home', 'Destaque na entrada do streaming.', 'smart TV streaming home with a sponsored brand tile'),
        ('mobile', 'p', 'No celular', 'Vídeo · mobile', 'Mesma mensagem fora da sala.', 'smartphone streaming app with a video ad of the brand'),
        ('patrocinio-colecao', 'l', 'Coleção patrocinada', 'Coleção patrocinada', 'Marca associada a uma seleção de títulos.', 'smart TV browsing a collection row presented by the brand')]),
    'globoplay': ('Visual language of a Brazilian streaming service: dark UI with red accents, no service logo.', [
        ('pre-roll', 'l', 'Vídeo antes do conteúdo', 'Pre-roll · CTV', 'Anúncio antes da novela, série ou filme.', 'living room TV showing a pre-roll ad of the brand'),
        ('mid-roll', 'l', 'Intervalo comercial', 'Mid-roll', 'Entre os blocos do conteúdo.', 'TV showing an ad break of the brand during a drama show'),
        ('home-takeover', 'l', 'Destaque na home', 'Display · home', 'Primeira tela do streaming.', 'smart TV streaming home with a large sponsored brand banner'),
        ('mobile', 'p', 'No celular', 'Vídeo · mobile', 'Assistir de qualquer lugar.', 'smartphone streaming app with a video ad of the brand'),
        ('patrocinio-evento', 'l', 'Patrocínio de evento ao vivo', 'Patrocínio', 'Marca em transmissões ao vivo.', 'TV showing a live event with a brand sponsor lower-third')]),
    'hbo-max': ('Visual language of a premium streaming service: deep purple/black UI, no service logo.', [
        ('pre-roll', 'l', 'Vídeo antes do conteúdo', 'Pre-roll · CTV', 'Anúncio antes da série ou filme.', 'living room TV showing a pre-roll ad of the brand'),
        ('pause-ad', 'l', 'Anúncio na pausa', 'Pause Ad', 'Aparece ao pausar o conteúdo.', 'TV paused on a movie with a small brand ad panel'),
        ('home-banner', 'l', 'Banner na home', 'Display · home', 'Destaque na entrada.', 'smart TV streaming home with a sponsored brand tile'),
        ('mobile', 'p', 'No celular', 'Vídeo · mobile', 'Assistir de qualquer lugar.', 'smartphone streaming app with a video ad of the brand'),
        ('mid-roll', 'l', 'Intervalo', 'Mid-roll', 'Entre os blocos do episódio.', 'TV showing an ad break of the brand in a series')]),
    'netflix': ('Visual language of a premium streaming service: black UI with red accents, no service logo.', [
        ('pre-roll', 'l', 'Vídeo antes do conteúdo', 'Pre-roll · CTV', 'Anúncio antes do título escolhido.', 'living room TV showing a pre-roll ad of the brand'),
        ('mid-roll', 'l', 'Intervalo', 'Mid-roll', 'Entre os blocos do episódio.', 'TV showing an ad break of the brand during a series episode'),
        ('pause-ad', 'l', 'Anúncio na pausa', 'Pause Ad', 'Aparece quando a pessoa pausa.', 'TV paused on a show with a small brand ad panel'),
        ('mobile', 'p', 'No celular', 'Vídeo · mobile', 'Assistir de qualquer lugar.', 'smartphone streaming app with a video ad of the brand'),
        ('tablet', 'l', 'No tablet', 'Vídeo · tablet', 'Uso em casa e em viagem.', 'tablet streaming app showing a video ad of the brand')]),
    'paramount-plus': ('Visual language of a streaming service: deep blue UI, no service logo.', [
        ('pre-roll', 'l', 'Vídeo antes do conteúdo', 'Pre-roll · CTV', 'Anúncio antes do filme ou série.', 'living room TV showing a pre-roll ad of the brand'),
        ('mid-roll', 'l', 'Intervalo', 'Mid-roll', 'Entre os blocos do conteúdo.', 'TV showing an ad break of the brand'),
        ('pause-ad', 'l', 'Anúncio na pausa', 'Pause Ad', 'Aparece ao pausar o conteúdo.', 'TV paused on a movie with a small brand ad panel'),
        ('mobile', 'p', 'No celular', 'Vídeo · mobile', 'Assistir de qualquer lugar.', 'smartphone streaming app with a video ad of the brand'),
        ('home-banner', 'l', 'Banner na home', 'Display · home', 'Destaque na entrada.', 'smart TV streaming home with a sponsored brand tile')]),
    'podcast-ads': ('Visual language of a podcast app: warm dark UI, no app logo.', [
        ('host-read', 'l', 'Lido pelo apresentador', 'Host-read · 30-60 s', 'A recomendação vem da voz que a pessoa já confia.', 'podcast studio with a host holding the brand product and a microphone'),
        ('pre-roll', 'p', 'Antes do episódio', 'Pre-roll · áudio', 'Mensagem curta no início.', 'smartphone podcast player showing a sponsored pre-roll with the brand cover'),
        ('mid-roll', 'p', 'No meio do episódio', 'Mid-roll · áudio', 'Maior atenção, no meio do conteúdo.', 'smartphone podcast player mid-episode with a sponsor card of the brand'),
        ('banner-app', 'p', 'Banner no app', 'Display · player', 'Imagem clicável enquanto o episódio toca.', 'smartphone podcast app with a companion banner of the brand'),
        ('serie-patrocinada', 'p', 'Série patrocinada', 'Naming de série', 'A marca apresenta uma série de episódios.', 'smartphone podcast series page presented by the brand')]),
    'prime-video': ('Visual language of a premium streaming service: dark navy UI with blue accent, no service logo.', [
        ('mid-roll', 'l', 'Intervalo', 'Mid-roll', 'Entre os blocos do episódio.', 'TV showing an ad break of the brand during a series'),
        ('pause-ad', 'l', 'Anúncio na pausa', 'Pause Ad', 'Aparece ao pausar o conteúdo.', 'TV paused on a movie with a small brand ad panel'),
        ('home-banner', 'l', 'Banner na home', 'Display · home', 'Destaque na entrada.', 'smart TV streaming home with a sponsored brand tile'),
        ('mobile', 'p', 'No celular', 'Vídeo · mobile', 'Assistir de qualquer lugar.', 'smartphone streaming app with a video ad of the brand'),
        ('compra-na-tv', 'l', 'Compra na TV', 'Anúncio interativo', 'O espectador adiciona o produto ao carrinho pela TV.', 'TV ad of the brand with an on-screen add-to-cart prompt')]),
    'samsung-tv-plus': ('Visual language of a free ad-supported smart TV channel guide: dark UI, no logo.', [
        ('canal-fast', 'l', 'Canal patrocinado', 'Canal FAST', 'A marca patrocina um canal linear gratuito.', 'smart TV channel guide with a brand-sponsored channel tile'),
        ('pre-roll', 'l', 'Vídeo no intervalo', 'Vídeo · intervalo', 'Anúncio entre os blocos do canal.', 'living room TV showing an ad break of the brand'),
        ('home-banner', 'l', 'Banner na home da TV', 'Display · home TV', 'Primeira tela da smart TV.', 'smart TV home screen with a large sponsored brand banner'),
        ('interativo', 'l', 'Anúncio interativo', 'Interativo · controle remoto', 'Responde ao controle remoto.', 'smart TV ad of the brand with an on-screen interactive prompt'),
        ('familia', 'l', 'Sala em família', 'Audiência em casa', 'Alcance de toda a casa.', 'family on a sofa watching an ad of the brand on TV')]),
    'spotify': ('Visual language of a music streaming app: black UI with green accent, no app logo.', [
        ('audio-ad', 'p', 'Anúncio de áudio', 'Áudio · 30 s', 'Entre as músicas, com capa da marca.', 'smartphone music player showing a sponsored audio ad cover of the brand'),
        ('video-takeover', 'p', 'Video Takeover', 'Vídeo · tela ativa', 'Vídeo que roda quando o app está aberto.', 'smartphone full-screen video ad of the brand within a music app'),
        ('home-takeover', 'p', 'Takeover na home', 'Display · home', 'Destaque total na entrada do app.', 'smartphone app home with a large brand banner'),
        ('playlist', 'p', 'Playlist patrocinada', 'Playlist da marca', 'Curadoria no tom da marca.', 'smartphone playlist page presented by the brand'),
        ('podcast', 'p', 'Em podcasts', 'Áudio · podcast', 'Mensagem dentro do episódio.', 'smartphone podcast page with a sponsor card of the brand')]),
}


def concepts(slug):
    """Page entries for one channel; image files are `{slug}-{key}.jpg` in static/images/channel-creatives."""
    items = CHANNEL_ADS.get(slug, (None, []))[1]
    return [{'image_url': f'/static/images/channel-creatives/{slug}-{key}.jpg', 'title': f'{brand_for(slug, key, index)[0]} · {title}',
             'format': fmt, 'description': text} for index, (key, _o, title, fmt, text, _s) in enumerate(items)]


def _offset(slug):
    return list(CHANNEL_ADS).index(slug) if slug in CHANNEL_ADS else 0
