import tempfile
import subprocess
import unittest
from pathlib import Path
from aicentralv2.creative_media.studio_autocut import analyze, options, silences
from aicentralv2.creative_media.studio_audio import filters
from aicentralv2.creative_media.studio_composition import normalize_composition

class AutoCutTest(unittest.TestCase):
    def test_words_protected_and_modes(self):
        words=[{'start':0,'end':.2,'text':'Olá'},{'start':2,'end':3,'text':'mundo'}]
        moderate=analyze(4,words,[(.3,.85),(1,1.9),(2.1,2.9)],{'enabled':True})
        aggressive=analyze(4,words,[(.3,.85),(1,1.9),(2.1,2.9)],{'enabled':True,'mode':'aggressive'})
        self.assertEqual(len(moderate['cuts']),1)
        self.assertEqual(len(aggressive['cuts']),2)
        self.assertFalse(any(c['in']<3 and c['out']>2 for c in aggressive['cuts']))

    def test_short_dissolve_is_preserved_by_normalizer(self):
        c=normalize_composition({'items':[{'kind':'video','out':1,'transition':'fade','transition_duration':.05}]})
        self.assertEqual(c['items'][0]['transition_duration'],.05)

    def test_no_speech_preserves_original(self):
        self.assertEqual(analyze(10,[],[(0,10)],{'enabled':True})['cuts'],[])

    def test_limit_and_review(self):
        words=[{'start':0,'end':.2,'text':'Sim'},{'start':.3,'end':.5,'text':'sim'}]
        result=analyze(100,words,[(i*3+1,i*3+2) for i in range(32)],{'max_cuts':30})
        self.assertEqual(len(result['cuts']),30)
        self.assertEqual(len(result['review']),1)
        self.assertEqual(options({'max_cuts':'nan'})['max_cuts'],30)

    def test_composition_does_not_truncate_31_segments(self):
        c=normalize_composition({'items':[{'id':str(i),'kind':'video','out':1,'voice':{'preset':'warm'}} for i in range(31)]})
        self.assertEqual(len(c['items']),31)
        self.assertEqual(c['items'][0]['voice']['preset'],'warm')

    def test_audio_filters_render_and_preserve_duration(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'clean.wav'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=200:duration=2','-af',filters({'preset':'warm'}),str(dest)],check=True,capture_output=True)
            seconds=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(dest)]))
            self.assertAlmostEqual(seconds,2,places=2)
            self.assertEqual(silences(dest,2,'moderate'),[])
