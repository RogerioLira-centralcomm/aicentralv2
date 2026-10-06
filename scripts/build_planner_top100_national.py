"""Gera tmp/planner-portais-top100-nacionais.csv: curadoria inicial dos grandes portais nacionais.

A lista é uma seleção editorial (sem ranking e sem métricas): audiência, acessos e tempo
médio só entram com fonte pública. Domínios sem DNS público são descartados e listados.
"""
import csv
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NOTICIAS, ECON, ESP, ENT = 'Notícias gerais', 'Economia e negócios', 'Esportes', 'Entretenimento e celebridades'
TEC, MULHER, SAUDE, AUTO = 'Tecnologia e games', 'Mulher, estilo e casa', 'Saúde e bem-estar', 'Automotivo'
VIAGEM, EDU, PORTAL, MUSICA = 'Viagem e turismo', 'Ciência e educação', 'Portais e serviços', 'Música e cultura'

PORTAIS = [
    ('g1.globo.com', 'G1', NOTICIAS), ('oglobo.globo.com', 'O Globo', NOTICIAS), ('folha.uol.com.br', 'Folha de S.Paulo', NOTICIAS),
    ('estadao.com.br', 'Estadão', NOTICIAS), ('cnnbrasil.com.br', 'CNN Brasil', NOTICIAS), ('r7.com', 'R7', NOTICIAS),
    ('metropoles.com', 'Metrópoles', NOTICIAS), ('correiobraziliense.com.br', 'Correio Braziliense', NOTICIAS),
    ('gauchazh.clicrbs.com.br', 'GZH', NOTICIAS), ('gazetadopovo.com.br', 'Gazeta do Povo', NOTICIAS),
    ('em.com.br', 'Estado de Minas', NOTICIAS), ('otempo.com.br', 'O Tempo', NOTICIAS), ('atarde.com.br', 'A Tarde', NOTICIAS),
    ('folhape.com.br', 'Folha de Pernambuco', NOTICIAS), ('opovo.com.br', 'O Povo', NOTICIAS),
    ('diariodonordeste.verdesmares.com.br', 'Diário do Nordeste', NOTICIAS), ('correio24horas.com.br', 'Correio', NOTICIAS),
    ('band.uol.com.br', 'Band', NOTICIAS), ('brasil247.com', 'Brasil 247', NOTICIAS), ('cartacapital.com.br', 'CartaCapital', NOTICIAS),
    ('veja.abril.com.br', 'Veja', NOTICIAS), ('istoe.com.br', 'IstoÉ', NOTICIAS), ('poder360.com.br', 'Poder360', NOTICIAS),
    ('jovempan.com.br', 'Jovem Pan', NOTICIAS), ('agenciabrasil.ebc.com.br', 'Agência Brasil', NOTICIAS),
    ('correiodopovo.com.br', 'Correio do Povo', NOTICIAS), ('agazeta.com.br', 'A Gazeta', NOTICIAS),
    ('tribunaonline.com.br', 'Tribuna Online', NOTICIAS), ('opopular.com.br', 'O Popular', NOTICIAS), ('uai.com.br', 'UAI', NOTICIAS),
    ('brasildefato.com.br', 'Brasil de Fato', NOTICIAS), ('nexojornal.com.br', 'Nexo Jornal', NOTICIAS),
    ('ndmais.com.br', 'ND+', NOTICIAS), ('nsctotal.com.br', 'NSC Total', NOTICIAS), ('terra.com.br', 'Terra', PORTAL),
    ('uol.com.br', 'UOL', PORTAL), ('ig.com.br', 'iG', PORTAL), ('globo.com', 'Globo.com', PORTAL), ('bol.uol.com.br', 'BOL', PORTAL),
    ('climatempo.com.br', 'Climatempo', PORTAL), 
    ('infomoney.com.br', 'InfoMoney', ECON), ('valor.globo.com', 'Valor Econômico', ECON), ('exame.com', 'Exame', ECON),
    ('br.investing.com', 'Investing.com Brasil', ECON), ('moneytimes.com.br', 'Money Times', ECON), ('seudinheiro.com', 'Seu Dinheiro', ECON),
    ('forbes.com.br', 'Forbes Brasil', ECON), ('neofeed.com.br', 'NeoFeed', ECON), ('istoedinheiro.com.br', 'IstoÉ Dinheiro', ECON),
    ('bloomberglinea.com.br', 'Bloomberg Línea', ECON), ('meioemensagem.com.br', 'Meio & Mensagem', ECON),
    ('ge.globo.com', 'ge', ESP), ('espn.com.br', 'ESPN Brasil', ESP), ('lance.com.br', 'Lance!', ESP), ('gazetaesportiva.com', 'Gazeta Esportiva', ESP),
    ('torcedores.com', 'Torcedores.com', ESP), 
    
    ('gshow.globo.com', 'Gshow', ENT), ('ofuxico.com.br', 'OFuxico', ENT), ('purepeople.com.br', 'Purepeople', ENT), ('contigo.com.br', 'Contigo', ENT),
    ('caras.com.br', 'Caras', ENT), ('quem.globo.com', 'Quem', ENT), ('omelete.com.br', 'Omelete', ENT), ('adorocinema.com', 'AdoroCinema', ENT),
    ('minhaserie.com.br', 'Minha Série', ENT), 
    ('jovemnerd.com.br', 'Jovem Nerd', ENT), ('cinepop.com.br', 'Cinepop', ENT), 
    ('hugogloss.uol.com.br', 'Hugo Gloss', ENT), ('vagalume.com.br', 'Vagalume', MUSICA),
    ('letras.mus.br', 'Letras.mus.br', MUSICA), ('cifraclub.com.br', 'Cifra Club', MUSICA), ('rollingstone.uol.com.br', 'Rolling Stone Brasil', MUSICA),
    ('tecmundo.com.br', 'TecMundo', TEC), ('olhardigital.com.br', 'Olhar Digital', TEC), ('canaltech.com.br', 'Canaltech', TEC),
    ('tecnoblog.net', 'Tecnoblog', TEC), ('techtudo.com.br', 'TechTudo', TEC), ('showmetech.com.br', 'Showmetech', TEC),
    ('adrenaline.com.br', 'Adrenaline', TEC), ('tudocelular.com', 'TudoCelular', TEC), 
    ('vogue.globo.com', 'Vogue Brasil', MULHER), ('marieclaire.globo.com', 'Marie Claire', MULHER), ('elle.com.br', 'Elle Brasil', MULHER),
    ('tudogostoso.com.br', 'TudoGostoso', MULHER), ('casaejardim.globo.com', 'Casa e Jardim', MULHER), ('revistacrescer.globo.com', 'Crescer', MULHER),
    ('claudia.abril.com.br', 'Claudia', MULHER), ('drauziovarella.uol.com.br', 'Drauzio Varella', SAUDE), ('minhavida.com.br', 'Minha Vida', SAUDE),
    ('tuasaude.com', 'Tua Saúde', SAUDE), ('autoesporte.globo.com', 'Auto Esporte', AUTO), ('quatrorodas.abril.com.br', 'Quatro Rodas', AUTO),
    ('motor1.com', 'Motor1 Brasil', AUTO), ('melhoresdestinos.com.br', 'Melhores Destinos', VIAGEM),
    ('viagemeturismo.abril.com.br', 'Viagem e Turismo', VIAGEM), ('super.abril.com.br', 'Superinteressante', EDU),
    ('nationalgeographicbrasil.com', 'National Geographic Brasil', EDU), ('brasilescola.uol.com.br', 'Brasil Escola', EDU),
    ('mundoeducacao.uol.com.br', 'Mundo Educação', EDU), ('todamateria.com.br', 'Toda Matéria', EDU),
]


def resolves(domain):
    try:
        socket.getaddrinfo(domain, 443)
        return True
    except OSError:
        return False


def main(out='tmp/planner-portais-top100-nacionais.csv', dry=False):
    with ThreadPoolExecutor(12) as pool:
        alive = list(pool.map(lambda item: resolves(item[0]), PORTAIS))
    dead = [item[0] for item, ok in zip(PORTAIS, alive) if not ok]
    keep = [item for item, ok in zip(PORTAIS, alive) if ok]
    print(f'{len(PORTAIS)} candidatos; {len(keep)} com DNS público; sem DNS: {dead}')
    if dry:
        return
    attrs = lambda: json.dumps([
        {'atributo': 'status_curadoria', 'valor': 'curadoria_inicial_sem_metricas'},
        {'atributo': 'escopo', 'valor': 'Premium nacional (seleção editorial inicial, sem ranking)'}], ensure_ascii=False)
    with open(out, 'w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['name', 'domain', 'category', 'description', 'audience_estimate', 'audience_period',
                         'audience_source_url', 'audience_checked_at', 'public_attributes', 'featured_rank', 'scope'])
        for domain, name, category in keep:
            writer.writerow([name, domain, category, f'Portal nacional de {category.lower()}.', '', '', '', '', attrs(), '', 'nacional_premium'])


if __name__ == '__main__':
    main()
