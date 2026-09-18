import io
import json
import shutil
import unittest
from unittest.mock import Mock,patch
from flask import jsonify,request
from tests import test_video_studio as fixtures
from aicentralv2.creative_media.studio_delivery import slug,filename


class DeliveryTest(unittest.TestCase):
    setUpClass=classmethod(fixtures.MediaTest.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.MediaTest.tearDownClass.__func__)
    app=fixtures.MediaTest.app

    def test_safe_descriptive_filename(self):
        self.assertEqual(filename({'brand':'Vivára / Brasil','creative':'Oferta especial!','version':3,'ratio':'9:16','format':'mp4'},720,1280),'vivara_brasil_v003_oferta_especial_9x16_720x1280.mp4')
        self.assertEqual(slug('../../','criativo'),'criativo')

    def test_formats_download_and_anonymous_html(self):
        from aicentralv2.creative_media import studio
        app=self.app();client=app.test_client();anonymous=app.test_client();service=Mock();service.get_client.return_value={'name':'Marca Ágil'}
        with client.session_transaction() as sess:sess.update(user_id=7,user_type='admin',studio_csrf_token='token')
        def execute(fn):
            try:return fn()
            except ValueError as error:return jsonify(success=False,error=str(error)),400
        http=(execute,lambda:request.get_json(),lambda data:jsonify(success=True,data=data),lambda:service)
        base='/parametros/api/format-lab/studio';headers={'X-Trocr-CSRF-Token':'token'}
        with patch('aicentralv2.creative_media.studio._http',return_value=http),patch('aicentralv2.creative_media.studio_media.resolve_clip',return_value=self.voiced),patch.object(studio._POOL,'submit',side_effect=lambda fn,*args:fn(*args)):
            for index,kind in enumerate(['mp4','gif','html'],1):
                ident=str(index)*32
                payload={'client_id':31,'clip_id':'clip','request_id':ident,'edit':{'start':0,'end':.5,'output_ratio':'9:16'},'delivery':{'format':kind,'brand':'Wrong name','creative':'Oferta de verão'}}
                response=client.post(base+'/exports',json=payload,headers=headers);self.assertEqual(response.status_code,200,response.json)
                status=client.get(base+'/exports/'+ident+'?client_id=31').json['data'];self.assertEqual(status['status'],'ready',status)
                self.assertTrue(status['filename'].startswith(f'marca_agil_v{index:03}_oferta_de_verao_9x16_'),status)
                download_url = status.get('download_url') or f"{base}/exports/{ident}/content?client_id=31&format={kind}"
                with client.get(download_url) as result:
                    self.assertEqual(result.status_code,200);self.assertIn(status['filename'],result.headers['Content-Disposition']);data=result.data
                    if kind=='gif':self.assertTrue(data.startswith(b'GIF89a'));self.assertIn('360x640.gif',status['filename'])
                    if kind=='html':self.assertIn(b'<video controls',data);self.assertNotIn(b'<script',data)
                duplicate=client.post(base+'/exports',json=payload,headers=headers);self.assertEqual(duplicate.json['data']['filename'],status['filename'])
                if kind=='html':
                    url=status['public_url']
                    with anonymous.get(url) as page:self.assertEqual(page.status_code,200);self.assertIn(b'Oferta de ver',page.data)
                    with anonymous.get(url+'/video',headers={'Range':'bytes=0-63'}) as video:self.assertEqual(video.status_code,206);self.assertEqual(len(video.data),64)
                    self.assertEqual(anonymous.get('/parametros/studio/public/'+'0'*48).status_code,404)
                    self.assertNotEqual(anonymous.get(download_url).status_code,200)
                else:self.assertEqual(status['public_url'],'')
