"""One Pillow renderer for layer previews and exports (no UI guides)."""
import io
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = Path(__file__).resolve().parents[1] / 'static/fonts/OpenSans-Regular.ttf'


def number(value, default, low, high):
    value = default if value is None else value
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Propriedade da camada fora do limite.')
    return value


def normalize(layers, store):
    if not isinstance(layers, list) or len(layers) > 100:
        raise ValueError('Use até 100 camadas.')
    result = []
    for layer in layers:
        if not isinstance(layer, dict) or layer.get('kind') not in {'image', 'text'}:
            raise ValueError('Camada inválida.')
        clean = {'id': str(layer.get('id') or '')[:64], 'kind': layer['kind'],
                 'visible': layer.get('visible') is not False, 'protected': layer.get('protected') is True,
                 'x': number(layer.get('x'), 0, -10000, 10000), 'y': number(layer.get('y'), 0, -10000, 10000),
                 'width': number(layer.get('width'), 100, 1, 8000), 'height': number(layer.get('height'), 100, 1, 8000),
                 'opacity': number(layer.get('opacity'), 1, 0, 1), 'shadow': number(layer.get('shadow'), 0, 0, 30),
                 'outline': number(layer.get('outline'), 0, 0, 20)}
        if clean['width'] * clean['height'] > 20_000_000:
            raise ValueError('Camada excede 20 megapixels.')
        if layer['kind'] == 'image':
            store.asset(layer.get('asset_id'))
            clean['asset_id'] = layer['asset_id']
        else:
            color = str(layer.get('color') or '#ffffff')
            if len(color) != 7 or color[0] != '#' or any(c not in '0123456789abcdefABCDEF' for c in color[1:]):
                raise ValueError('Cor inválida.')
            text = layer.get('text') or ''
            if not isinstance(text, str) or len(text) > 1000:
                raise ValueError('Texto excede 1000 caracteres.')
            clean.update(text=text, color=color, font='Open Sans', font_size=number(layer.get('font_size'), 48, 6, 500),
                         align=layer.get('align') if layer.get('align') in {'left','center','right'} else 'left',
                         spacing=number(layer.get('spacing'), 4, 0, 100))
        result.append(clean)
    return result


def render(store, base, layers):
    canvas = store.image(base)
    for layer in normalize(layers, store):
        if not layer['visible']:
            continue
        size = (round(layer['width']), round(layer['height']))
        if layer['kind'] == 'image':
            image = store.image(layer['asset_id']).resize(size, Image.Resampling.LANCZOS)
        else:
            image = Image.new('RGBA', size)
            draw = ImageDraw.Draw(image)
            font = ImageFont.truetype(str(FONT), round(layer['font_size']))
            x = {'left':0, 'center':size[0]/2, 'right':size[0]}[layer['align']]
            anchor = {'left':'la','center':'ma','right':'ra'}[layer['align']]
            draw.multiline_text((x, 0), layer['text'], font=font, fill=layer['color'], anchor=anchor,
                                align=layer['align'], spacing=round(layer['spacing']),
                                stroke_width=round(layer['outline']), stroke_fill='#000000')
        alpha = image.getchannel('A')
        image.putalpha(alpha.point(lambda p: round(p * layer['opacity'])))
        x, y = round(layer['x']), round(layer['y'])
        if layer['shadow']:
            shadow = Image.new('RGBA', size, '#000000')
            shadow.putalpha(image.getchannel('A').filter(ImageFilter.GaussianBlur(layer['shadow']/2)))
            canvas.alpha_composite(shadow, (x + round(layer['shadow']), y + round(layer['shadow'])))
        if layer['kind'] == 'image' and layer['outline']:
            outline = Image.new('RGBA', size, '#000000')
            outline.putalpha(alpha.filter(ImageFilter.MaxFilter(round(layer['outline'])*2+1)).point(lambda p: round(p*layer['opacity'])))
            canvas.alpha_composite(outline, (x, y))
        canvas.alpha_composite(image, (x, y))
    output = io.BytesIO(); canvas.save(output, 'PNG')
    return output.getvalue()
