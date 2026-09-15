"""Editorial import → inspection → audio extraction → text export, with real media."""
import io
from unittest.mock import Mock, patch
from flask import jsonify, request
import unittest
from tests import test_video_studio as fixtures
from aicentralv2.creative_media.studio import normalize_edit, probe
from aicentralv2.creative_media.studio_layers import normalize_layers, render_layers
from aicentralv2.creative_media.studio_media import public_sounds
from aicentralv2.creative_media.planner import build_plan


@unittest.skipUnless(fixtures.shutil.which("ffmpeg") and fixtures.shutil.which("ffprobe"), "FFmpeg required")
class EditorMediaTest(unittest.TestCase):
    setUpClass = classmethod(fixtures.MediaTest.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.MediaTest.tearDownClass.__func__)
    app = fixtures.MediaTest.app
    def test_import_inspect_extract_and_brand_boundary(self):
        app=self.app();client=app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=7,user_type='admin',trocr_csrf_token='token')
        def execute(fn):
            try:return fn()
            except ValueError as error:return jsonify(success=False,error=str(error)),400
        http=(execute,lambda:request.get_json(),lambda data:jsonify(success=True,data=data),lambda:Mock())
        base='/parametros/api/format-lab/studio';headers={'X-Trocr-CSRF-Token':'token'}
        with patch('aicentralv2.creative_format_lab.swap_routes._http',return_value=http):
            result=client.post(base+'/clips',data={'client_id':'31','file':(io.BytesIO(self.voiced.read_bytes()),'test.mp4')},headers=headers)
            self.assertEqual(result.status_code,200,result.json)
            row=result.json['data'];self.assertTrue(row['has_audio'])
            body={'client_id':31,'clip_id':row['id']}
            meta=client.post(base+'/inspect',json=body,headers=headers)
            self.assertEqual(meta.status_code,200,meta.json)
            self.assertEqual(len(meta.json['data']['frames']),8)
            self.assertTrue(meta.json['data']['waveform'])
            with client.get(meta.json['data']['frames'][0]['url']) as frame:self.assertEqual(frame.status_code,200)
            self.assertEqual(client.post(base+'/inspect',json={**body,'client_id':32},headers=headers).status_code,400)
            extracted=client.post(base+'/extract-audio',json=body,headers=headers)
            self.assertEqual(extracted.status_code,200,extracted.json)
            from aicentralv2.creative_media import studio
            export_body={**body,'request_id':'b'*32,'edit':{'output_ratio':'9:16','start':.2,'end':2,'original_volume':0,'sound_id':public_sounds()[1][0]['id'],'loop':True,'layers':[{'text':'Oferta','start':0,'end':1.5,'animation':'fade'}]}}
            with patch.object(studio._POOL,'submit',side_effect=lambda fn,*args:fn(*args)):
                exported=client.post(base+'/exports',json=export_body,headers=headers)
            self.assertEqual(exported.status_code,200,exported.json)
            status=client.get(base+'/exports/'+'b'*32+'?client_id=31')
            self.assertEqual(status.json['data']['status'],'ready',status.json)
            with client.get(base+'/exports/'+'b'*32+'/content?client_id=31') as video:
                self.assertEqual(video.status_code,200)
                output=self.root/'import-export.mp4';output.write_bytes(video.data)
            self.assertIn('audio',probe(output)[1])
            from aicentralv2.creative_media.validation import inspect_video
            dimensions=inspect_video(output.read_bytes())
            self.assertEqual((dimensions['width'],dimensions['height']),(720,1280))
            self.assertAlmostEqual(probe(output)[0],1.8,delta=.15)
            with client.get(extracted.json['data']['url']) as audio:self.assertEqual(audio.status_code,200)
            bad=client.post(base+'/clips',data={'client_id':'31','file':(io.BytesIO(b'not a movie'),'bad.mp4')},headers=headers)
            self.assertEqual(bad.status_code,400)
            archived=client.post(base+'/archive-clip',json=body,headers=headers)
            self.assertEqual(archived.status_code,200)
            listing=client.get(base+'/clips?client_id=31').json['data']['items']
            self.assertNotIn(row['id'],[item['id'] for item in listing])

    def test_public_catalog_has_real_licensed_files(self):
        root,rows=public_sounds()
        self.assertGreaterEqual(len(rows),30)
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        for row in rows:
            self.assertTrue((root/row['filename']).is_file())
            self.assertEqual(row['license'],'CC0 1.0')
            self.assertGreater(row['duration'],0)

    def test_text_layers_render_with_audio_and_duration(self):
        import subprocess
        output=self.root/'layers.mp4'
        layers=normalize_layers([{'text':'TESTE','start':.3,'end':1.8,'x':.5,'y':.5,'size':.2,'animation':'fade'}])
        render_layers(self.voiced,output,layers)
        self.assertIn('audio',probe(output)[1]);self.assertAlmostEqual(probe(output)[0],2.4,delta=.15)
        def frame(at):
            return subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(output),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
        self.assertNotEqual(frame(.1),frame(1))
        self.assertEqual(normalize_edit({'layers':layers})['layers'],layers)

    def test_storyboard_transition_reaches_generation_prompt(self):
        plan=build_plan({'source':{'mode':'storyboard','ref_ids':['a','b']},'script':{'beats':[{'visual':'Produto na mesa','motion':'Zoom lento','transition':'cross dissolve'}]}})
        self.assertIn('cross dissolve',plan['prompt'])
        self.assertIn('Produto na mesa',plan['prompt'])

    def test_per_clip_edits_survive_project_normalization(self):
        from aicentralv2.creative_format_lab.swap_session import normalize_video_project
        result=normalize_video_project({'clip_edits':{'upload:abc':{'start':1,'layers':[{'text':'Título'}]}}})
        self.assertEqual(result['clip_edits']['upload:abc']['start'],1)
        self.assertEqual(result['clip_edits']['upload:abc']['layers'][0]['text'],'Título')
