import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from aicentralv2.creative_media.studio_caption_style import catalog,normalize_style,caption_image
from aicentralv2.creative_media.studio_captions import render_captions
from aicentralv2.creative_media.studio_composition import normalize_composition

class CaptionStyleTest(unittest.TestCase):
    def test_ten_distinct_presets_and_fonts(self):
        self.assertEqual(len(catalog()['presets']),10)
        pictures=[caption_image('Sua legenda\nCom acentuação: ação',360,640,p['style']).tobytes() for p in catalog()['presets']]
        self.assertEqual(len(set(pictures)),10)
        for f in catalog()['fonts']:
            self.assertIsNotNone(caption_image('Olá!',360,640,{'font':f['id']}).getbbox())

    def test_style_bounds_and_roundtrip(self):
        s=normalize_style({'font':'../../bad','color':'red;bad','x':float('nan'),'size':100,'outline':-1})
        self.assertEqual(s['font'],'open');self.assertEqual(s['color'],'#ffffff')
        self.assertEqual(s['size'],.12);self.assertEqual(s['outline'],0)
        style=normalize_style({'preset':'box','x':.25,'y':.2,'size':.08,'font':'anton'})
        c=normalize_composition({'caption_style':style})
        self.assertEqual(c['caption_style'],style)

    def test_safe_bounds_and_explicit_line_breaks(self):
        for x,y in [(0,0),(1,1)]:
            image=caption_image('PalavraMuitoLongaSemEspaços'*3+'\nSegunda linha',360,640,{'size':.12,'x':x,'y':y,'preset':'box'})
            left,top,right,bottom=image.getbbox()
            self.assertGreater(left,0);self.assertGreater(top,0)
            self.assertLess(right,360);self.assertLess(bottom,640)

    def test_same_style_on_every_timed_caption(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.mp4';dest=root/'out.mp4'
            subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=black:s=180x320:r=24:d=3','-c:v','libx264',str(source)],check=True,capture_output=True)
            render_captions(source,dest,[{'start':0,'end':1,'text':'Primeira'},{'start':1,'end':2,'text':'Segunda'}],180,320,3,24,{'preset':'yellow','y':.2})
            def frame(at):
                raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(dest),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
                return Image.open(io.BytesIO(raw)).convert('RGB')
            for at in [.2,.8,1.2,1.8]:
                im=frame(at);coords=[(x,y) for y in range(320) for x in range(180) if (lambda c:c[0]>140 and c[1]>110 and c[2]<100)(im.getpixel((x,y)))]
                self.assertTrue(coords);self.assertLess(max(y for x,y in coords),160)
            self.assertLess(max(frame(2.5).getextrema()[0]),15)
