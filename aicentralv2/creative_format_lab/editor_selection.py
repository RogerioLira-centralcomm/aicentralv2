"""Conservative point suggestions using Camadas' existing color-contour engine.

This is not semantic SAM segmentation. Reject an empty or full-frame result and
keep manual refinement available. Work at bounded resolution to avoid expensive
Python flood fills on full-resolution assets.
"""
import io
import math
from PIL import Image, ImageChops

from ..camadas.segmentation.interactive import flood_from_points
from ..camadas.segmentation.quality import assess_mask


def suggest(store, payload):
    base = payload.get('base_asset')
    source = store.image(base)
    point = payload.get('point')
    if not isinstance(point, dict) or any(type(point.get(k)) not in (float,int) or not math.isfinite(point[k]) or not 0 <= point[k] <= 1 for k in ('x','y')):
        raise ValueError('Ponto de seleção inválido.')
    mode = payload.get('mode')
    if mode not in {'include','exclude'}:
        raise ValueError('Modo de seleção inválido.')
    tolerance = payload.get('tolerance', 48)
    if type(tolerance) not in (int, float) or not math.isfinite(tolerance) or not 1 <= tolerance <= 120:
        raise ValueError('Tolerância deve estar entre 1 e 120.')
    reduced = source.copy(); reduced.thumbnail((512,512))
    region = flood_from_points(reduced, [point], threshold=tolerance)
    quality = assess_mask(region,reduced,'click') if region is not None else {'reason':'empty'}
    if region is None or quality.get('reason') in {'empty','full-frame'}:
        raise ValueError('Não foi possível sugerir um contorno confiável aqui. Use o pincel para selecionar manualmente.')
    region = region.resize(source.size, Image.Resampling.NEAREST)
    old = payload.get('mask_asset')
    if old:
        mask = store.image(old).convert('L')
        if mask.size != source.size or payload.get('mask_base') != base:
            raise ValueError('A base mudou. Revise a máscara.')
    else:
        mask = Image.new('L',source.size)
    result = ImageChops.lighter(mask,region) if mode=='include' else ImageChops.subtract(mask,region)
    buffer=io.BytesIO();result.save(buffer,'PNG')
    asset=store.upload(buffer.getvalue(),'Contorno por ponto.png')
    region_fraction = sum(region.histogram()[1:]) / (source.width * source.height)
    histogram = result.histogram()
    coverage = sum(histogram[1:]) / (source.width * source.height)
    warning = 'A seleção cobre mais de 35% da imagem. Confira se incluiu outros artistas, textos ou o fundo; reduza a tolerância ou use o laço.' if coverage > .35 else None
    if region_fraction < .001:
        warning = 'O clique alcançou apenas uma pequena área, não necessariamente o elemento inteiro. Amplie para revisar e complete com laço ou pincel.'
    return {'mask_asset':asset['id'],'base_asset':base,'engine':'color-contour','review_required':True,
            'coverage':round(coverage, 4),'warning':warning}
