import base64
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from tests import test_video_studio as fixtures
from aicentralv2.creative_media.studio_keyframes import normalize_keyframes,value_at
from aicentralv2.creative_media.studio_layers import normalize_layers,render_layers
from aicentralv2.creative_media.studio_push import validate_subscription


class AnimationContractTest(unittest.TestCase):
    def test_interpolation_bounds_and_duplicates(self):
        frames=normalize_keyframes([{'time':0,'x':0,'ease':'ease'},{'time':2,'x':1},{'time':2,'x':.8},{'time':'nan'}])
        self.assertEqual(len(frames),2)
        self.assertAlmostEqual(value_at(frames,'x',1),.4)
        self.assertAlmostEqual(value_at(frames,'x',.5),.125)
        self.assertEqual(value_at(frames,'x',3),.8)
        frames[0]['ease']='hold';self.assertEqual(value_at(frames,'x',1),0)

    def test_push_rejects_arbitrary_network_destinations(self):
        keys={'p256dh':base64.urlsafe_b64encode(b'x'*65).decode(),'auth':base64.urlsafe_b64encode(b'x'*16).decode()}
        for endpoint in ['http://localhost/x','https://127.0.0.1/x','https://fcm.googleapis.com.evil.test/x','https://fcm.googleapis.com:8443/x']:
            with self.assertRaises(ValueError):validate_subscription({'endpoint':endpoint,'keys':keys})
        self.assertEqual(validate_subscription({'endpoint':'https://fcm.googleapis.com/fcm/send/test','keys':keys})['keys'],keys)


class MediaCompletionTest(unittest.TestCase):
    setUpClass=classmethod(fixtures.MediaTest.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.MediaTest.tearDownClass.__func__)
    app=fixtures.MediaTest.app

    def test_animated_text_moves_in_real_export(self):
        from PIL import Image
        import io
        output=self.root/'moving-text.mp4'
        layers=normalize_layers([{'text':'MOVE','start':0,'end':2.4,'size':.15,'keyframes':[{'time':0,'x':.2,'y':.5},{'time':2.4,'x':.8,'y':.5}]}])
        try:render_layers(self.voiced,output,layers)
        except subprocess.CalledProcessError as e:self.fail(e.stderr.decode())
        centers=[]
        for at in (.2,2.):
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(at),'-i',str(output),'-frames:v','1','-f','image2pipe','-vcodec','png','-'])
            image=Image.open(io.BytesIO(raw)).convert('RGB');points=[]
            for y in range(image.height):
                for x in range(image.width):
                    r,g,b=image.getpixel((x,y))
                    if min(r,g,b)>220:points.append(x)
            self.assertTrue(points);centers.append(sum(points)/len(points))
        self.assertGreater(centers[1]-centers[0],self.width*.3 if hasattr(self,'width') else 40)

    def test_preparation_task_survives_worker_restart(self):
        from aicentralv2.creative_media.queue_worker import drain_tasks
        from aicentralv2.creative_media.studio import _write
        app=self.app();ident='d'*32
        with app.app_context():
            from aicentralv2.creative_media.storage import media_root
            root=media_root();folder=root/'studio'/'31';folder.mkdir(parents=True,exist_ok=True)
            path=folder/f'task-{ident}.json'
            _write(path,{'id':ident,'kind':'extract','client_id':31,'user_id':7,'status':'processing','created_at':0,'work':{'source':str(self.voiced)}})
            self.assertEqual(drain_tasks(root),1)
            result=json.loads(path.read_text());self.assertEqual(result['status'],'ready',result)
            self.assertTrue((folder/f'{ident}.m4a').exists());self.assertEqual(drain_tasks(root),0)

    def test_http_task_is_persisted_and_scoped_to_user(self):
        from flask import request,jsonify
        from aicentralv2.creative_media.queue_worker import drain_tasks
        app=self.app();app.config['MEDIA_WORKER_MODE']='supervised';client=app.test_client()
        with client.session_transaction() as sess:sess.update(user_id=7,user_type='admin',trocr_csrf_token='token')
        def execute(fn):
            try:return fn()
            except ValueError as error:return jsonify(success=False,error=str(error)),400
        http=(execute,lambda:request.get_json(),lambda data:jsonify(success=True,data=data),lambda:Mock())
        with patch('aicentralv2.creative_format_lab.swap_routes._http',return_value=http),patch('aicentralv2.creative_media.studio_media.resolve_clip',return_value=self.voiced):
            response=client.post('/parametros/api/format-lab/studio/tasks',json={'client_id':31,'kind':'extract','clip_id':'known'},headers={'X-Trocr-CSRF-Token':'token'})
            self.assertEqual(response.status_code,200,response.json);task=response.json['data'];self.assertNotIn('work',task);self.assertEqual(task['status'],'queued')
            url=f"/parametros/api/format-lab/studio/tasks/{task['id']}?client_id=31"
            with app.app_context():
                from aicentralv2.creative_media.storage import media_root
                drain_tasks(media_root())
            self.assertEqual(client.get(url).json['data']['status'],'ready')
            with client.session_transaction() as sess:sess['user_id']=8
            self.assertEqual(client.get(url).status_code,400)

    def test_transcription_groups_timed_words(self):
        from types import SimpleNamespace as NS
        import tempfile,os,sys
        from aicentralv2.creative_media.studio_tasks import transcribe
        words=[NS(start=0,end=1,word=' Olá'),NS(start=1,end=2,word=' mundo'),NS(start=5,end=6,word=' Agora')]
        fake=Mock();fake.WhisperModel.return_value.transcribe.return_value=([NS(words=words)],NS(language='pt'))
        with tempfile.TemporaryDirectory() as model,patch.dict(os.environ,{'MEDIA_TRANSCRIBE_MODEL_PATH':model}),patch.dict(sys.modules,{'faster_whisper':fake}):
            result=transcribe(self.voiced)
        self.assertEqual(result['captions'],[{'start':0,'end':2,'text':'Olá mundo'},{'start':5,'end':6,'text':'Agora'}])

    def test_push_completion_sent_once(self):
        import tempfile,time,sys
        from aicentralv2.creative_media.studio import _write
        from aicentralv2.creative_media.studio_push import deliver
        fake=Mock();fake.WebPushException=type('PushError',(Exception,),{})
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'studio'/'31';folder.mkdir(parents=True)
            _write(folder/('push-'+'a'*32+'.json'),{'id':'a'*32,'user_id':7,'client_id':31,'enabled':True,'created_at':0,'subscription':{},'origin':'https://studio.example'})
            _write(folder/('export-'+'b'*32+'.json'),{'id':'b'*32,'user_id':7,'status':'ready','created_at':time.time()})
            repo=Mock();repo.list_jobs.return_value=[]
            with patch.dict(sys.modules,{'pywebpush':fake}),patch('aicentralv2.creative_media.studio_push.keys',return_value=(Path('/tmp/test.pem'),'public')):
                self.assertEqual(deliver(root,repo),1);self.assertEqual(deliver(root,repo),0)
            fake.webpush.assert_called_once()
