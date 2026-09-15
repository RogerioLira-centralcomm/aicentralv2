import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from aicentralv2.creative_media.studio_composition import normalize_composition,render_composition
from aicentralv2.creative_media.validation import inspect_video


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class CompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.video=cls.root/'clip.mp4';cls.image=cls.root/'image.jpg';cls.sound=cls.root/'sound.wav'
        subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=blue:s=72x128:d=1.5:r=24','-c:v','libx264','-pix_fmt','yuv420p',str(cls.video)],check=True)
        subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1.5',str(cls.sound)],check=True)
        Image.new('RGB',(90,160),'red').save(cls.image)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_video_image_transition_two_audio_tracks_text_and_captions(self):
        c=normalize_composition({'ratio':'9:16','fps':24,'items':[
            {'kind':'video','in':.2,'out':1.2,'transition':'fade','transition_duration':.2},
            {'kind':'image','duration':1,'motion':'zoom'}],
            'audio':[{'sound_id':'a','duration':1.5,'volume':.2,'fade_in':.1},{'sound_id':'b','start':.3,'duration':.8,'muted':True}],
            'layers':[{'text':'OFERTA','start':.2,'end':1,'size':.08,'animation':'fade'}],
            'captions':[{'start':.4,'end':1.5,'text':'Conheça a oferta'}]})
        output=self.root/'composed.mp4'
        render_composition(c,[self.video,self.image],[self.sound,self.sound],output)
        meta=inspect_video(output.read_bytes())
        self.assertEqual((meta['width'],meta['height']),(720,1280))
        self.assertAlmostEqual(meta['duration'],1.8,delta=.15)
        self.assertTrue(meta['has_audio'])
        pixel=subprocess.check_output(['ffmpeg','-v','error','-ss','1.6','-i',str(output),'-vf','scale=1:1','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        self.assertGreater(pixel[0],pixel[2])

    def test_cut_and_muted_original_do_not_lose_duration(self):
        c=normalize_composition({'ratio':'1:1','items':[{'kind':'video','in':0,'out':.5,'volume':0},{'kind':'image','duration':.5}]})
        output=self.root/'cut.mp4';render_composition(c,[self.video,self.image],[],output)
        self.assertAlmostEqual(inspect_video(output.read_bytes())['duration'],1,delta=.15)

    def test_image_keyframes_preserve_output_geometry(self):
        c=normalize_composition({'ratio':'9:16','fps':24,'items':[{'kind':'image','duration':.5,'keyframes':[{'time':0,'scale':.5,'rotation':0,'opacity':1},{'time':.5,'scale':.8,'rotation':30,'opacity':.5}]}]})
        output=self.root/'keyframes.mp4'
        try:render_composition(c,[self.image],[],output)
        except subprocess.CalledProcessError as e:self.fail(e.stderr.decode())
        meta=inspect_video(output.read_bytes());self.assertEqual((meta['width'],meta['height']),(720,1280))
        self.assertAlmostEqual(meta['duration'],.5,delta=.1)

    def test_reject_invalid_trim(self):
        c=normalize_composition({'items':[{'kind':'video','in':1.2,'out':.5}]})
        with self.assertRaises(ValueError):render_composition(c,[self.video],[],self.root/'bad.mp4')
