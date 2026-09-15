import base64
import io
import shutil
import subprocess
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from flask import Flask

from aicentralv2.creative_media.geometry import prepare_frame, infer_reference_aspect
from aicentralv2.creative_media.repository import MemoryMediaRepository, utc_now
from aicentralv2.creative_media.worker import AnimateWorker
from aicentralv2.creative_media.validation import validate_delivery
from aicentralv2.creative_media.public import job_payload
from aicentralv2.creative_media.queue_worker import drain_exports
from aicentralv2.creative_media.studio import normalize_edit, _write


class GeometryTest(unittest.TestCase):
    def test_vertical_reference_never_stretches_into_horizontal(self):
        source=Image.new('RGB',(90,160),'red');buf=io.BytesIO();source.save(buf,format='PNG')
        result=Image.open(io.BytesIO(prepare_frame(buf.getvalue(),'16:9','720p')))
        self.assertEqual(result.size,(1280,720))
        self.assertLess(result.getpixel((0,360))[0],20)
        self.assertGreater(result.getpixel((640,360))[0],240)
        self.assertEqual(infer_reference_aspect('data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()),'9:16')

    def test_terminal_and_recently_claimed_jobs_cannot_run_twice(self):
        repo=MemoryMediaRepository();row=repo.create_job({'client_id':1,'user_id':2})
        self.assertIsNotNone(repo.claim_job(row['public_id']))
        self.assertIsNone(repo.claim_job(row['public_id']))
        repo.update_job(row['public_id'],status='ready',locked_at=None)
        self.assertIsNone(repo.claim_job(row['public_id']))
        self.assertEqual(repo.list_jobs(2,2),[])
        self.assertEqual(repo.list_jobs(1,3),[])

    def test_public_progress_does_not_leak_reference_payload(self):
        result=job_payload({'public_id':'a','plan_json':{'source':{'mode':'storyboard','references':['data:SECRET'],'ref_ids':['1']}}})
        self.assertNotIn('SECRET',str(result))
        self.assertEqual(result['plan']['source']['ref_ids'],['1'])

    def test_ambiguous_submission_is_not_repeated(self):
        repo=MemoryMediaRepository();row=repo.create_job({'plan_json':{}})
        repo.update_job(row['public_id'],stage='submit',attempt=1)
        submit=Mock();worker=AnimateWorker(repo,video={'submit':submit})
        with self.assertRaisesRegex(RuntimeError,'cobrança duplicada'):
            worker.run(row['public_id'])
        submit.assert_not_called()


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class DeliveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        cls.video=cls.root/'vertical.mp4'
        subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=red:s=72x128:d=1:r=24','-c:v','libx264','-pix_fmt','yuv420p',str(cls.video)],check=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_actual_dimensions_and_audio_override_requested_flags(self):
        data=validate_delivery(self.video.read_bytes(),{'piece_ratio':'9:16','duration':1})
        self.assertEqual((data['width'],data['height']),(72,128));self.assertFalse(data['has_audio'])
        with self.assertRaisesRegex(ValueError,'exige 16:9'):
            validate_delivery(self.video.read_bytes(),{'piece_ratio':'16:9','duration':1})
        with self.assertRaises(ValueError):validate_delivery(b'broken',{'piece_ratio':'9:16'})

    def test_recovery_reuses_provider_id_without_new_generation(self):
        repo=MemoryMediaRepository()
        plan={'width':72,'height':128,'piece_ratio':'9:16','aspect_ratio':'9:16','duration':1,'audio_mode':'silence'}
        row=repo.create_job({'plan_json':plan});repo.update_job(row['public_id'],status='provider_pending',provider_job_id='provider-1')
        submit=Mock();worker=AnimateWorker(repo,video={'submit':submit,'poll':lambda *a,**kw:{'status':'completed'},'download':lambda *a:self.video.read_bytes()})
        app=Flask(__name__,instance_path=str(self.root/'instance'))
        with app.app_context(),patch('aicentralv2.creative_media.worker.POLL_INTERVAL',0):
            result=worker.run(row['public_id'])
        submit.assert_not_called();self.assertEqual(result['status'],'ready')
        self.assertEqual(result['version_payload']['aspect_ratio'],'9:16')
        self.assertEqual(result['version_payload']['width'],72)
        self.assertEqual(worker.run(row['public_id'])['status'],'ready')

    def test_export_queue_can_be_reopened_by_another_worker(self):
        root=self.root/'queue';scope=root/'studio'/'brand';scope.mkdir(parents=True,exist_ok=True)
        ident='a'*32;_write(scope/f'export-{ident}.json',{'id':ident,'status':'queued','work':{'source':str(self.video),'sound':'','edit':normalize_edit({})}})
        self.assertEqual(drain_exports(root),1)
        import json
        self.assertEqual(json.loads((scope/f'export-{ident}.json').read_text())['status'],'ready')
        self.assertEqual(drain_exports(root),0)
