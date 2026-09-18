import io
import tempfile
import unittest
from PIL import Image

from aicentralv2.creative_format_lab.editor_workspace import Workspace, Conflict


def png(color, size=(16, 12)):
    image = Image.new('RGB', size, color)
    out = io.BytesIO()
    image.save(out, 'PNG')
    return out.getvalue()


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Workspace(self.temp.name)
        self.base = self.store.upload(png('red'))['id']
        self.ref = self.store.upload(png('blue'))['id']
        image = Image.new('L', (16, 12))
        for x in range(3, 7):
            for y in range(2, 6):
                image.putpixel((x, y), 255)
        out = io.BytesIO(); image.save(out, 'PNG')
        self.mask = self.store.upload(out.getvalue())['id']

    def operation(self, action='replace'):
        return {'base_asset':self.base,'mask_asset':self.mask,'reference_asset':self.ref if action=='replace' else None,
                'role':'person','action':action,'instruction':'Trocar a pessoa'}

    def enqueue(self, operations=None):
        return self.store.enqueue({'operation_id':'a'*32,'base_asset':self.base,'operations':operations or [self.operation()]})

    def test_composition_preserves_every_pixel_outside_mask_and_records_reference(self):
        job=self.enqueue()
        calls=[]
        def generate(prompt, **kwargs):
            calls.append(kwargs['input_references'])
            return png('green')
        self.store.run(job['id'],generate)
        result=self.store.get('jobs',job['id'])
        self.assertEqual(result['status'],'succeeded')
        self.assertEqual(len(calls[0]),2)
        self.assertEqual(calls[0][0],self.store.reference(self.base))
        self.assertEqual(calls[0][1],self.store.reference(self.ref))
        image=self.store.image(result['result_asset'])
        original=self.store.image(self.base)
        mask=self.store.image(self.mask).convert('L')
        for x in range(16):
            for y in range(12):
                if mask.getpixel((x,y))==0:
                    self.assertEqual(image.getpixel((x,y)),original.getpixel((x,y)))
        self.assertEqual(result['results'][0]['operation']['reference_asset'],self.ref)
        self.assertTrue(result['results'][0]['qa']['outside_mask_preserved'])

    def test_multiple_operations_use_previous_result_and_do_not_duplicate(self):
        job=self.enqueue([self.operation(),self.operation('erase')])
        calls=[]
        def generate(prompt,**kwargs):
            calls.append(kwargs['input_references']);return png('green')
        self.store.run(job['id'],generate)
        self.store.run(job['id'],generate)
        result=self.store.get('jobs',job['id'])
        self.assertEqual(len(calls),2)
        self.assertEqual(len(calls[1]),1)
        self.assertEqual(calls[1][0],self.store.reference(result['results'][0]['result_asset']))
        self.assertEqual(self.enqueue([self.operation(),self.operation('erase')])['id'],job['id'])
        with self.assertRaises(Conflict):self.enqueue([self.operation('erase')])

    def test_failed_operation_keeps_inputs_and_partial_results(self):
        job=self.enqueue([self.operation(),self.operation('erase')])
        def generate(prompt,**kwargs):
            if len(kwargs['input_references'])==1:raise ValueError('rede interrompida')
            return png('green')
        self.store.run(job['id'],generate)
        result=self.store.get('jobs',job['id'])
        self.assertEqual(result['status'],'failed')
        self.assertEqual(len(result['results']),1)
        self.assertEqual(result['operations'][0]['reference_asset'],self.ref)
        self.assertEqual(Workspace(self.temp.name).get('jobs',job['id']),result)

    def test_revision_history_survives_reload_and_conflicts(self):
        first=self.store.save('documents','piece',{'base_asset':self.base,'ui':{'tolerance':20}},0)
        self.store.save('documents','piece',{**first,'ui':{'tolerance':80}},1)
        with self.assertRaises(Conflict):self.store.save('documents','piece',first,1)
        self.assertEqual(Workspace(self.temp.name).revisions('piece'),[first])
        self.assertEqual(self.store.revisions('other'),[])

    def test_format_rejects_protected_regions_before_generation(self):
        with self.assertRaisesRegex(ValueError,'protegidas'):
            self.store.enqueue({'operation_id':'c'*32,'base_asset':self.base,'protected_masks':[self.mask],
              'operations':[{'base_asset':self.base,'action':'format','role':'background','aspect_ratio':'4:5'}]})

    def test_cancellation_stops_pending_steps(self):
        job=self.enqueue([self.operation(),self.operation()])
        def generate(prompt,**kwargs):
            self.store.cancel(job['id']);return png('green')
        self.store.run(job['id'],generate)
        result=self.store.get('jobs',job['id'])
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(len(result['results']),1)

    def test_documents_conflict_campaigns_and_legacy_group(self):
        campaign=self.store.save('campaigns','campaign',{'name':'Lançamento'},0)
        doc=self.store.save('documents','old-run',{'base_asset':self.base,'campaign_id':None},0)
        self.assertIsNone(doc['campaign_id'])
        updated=self.store.save('documents','old-run',{**doc,'campaign_id':campaign['id']},doc['revision'])
        with self.assertRaises(Conflict):self.store.save('documents','old-run',doc,doc['revision'])
        self.assertEqual(self.store.get('documents','old-run'),updated)
        archived=self.store.save('campaigns','campaign',{**campaign,'archived':True},1)
        self.assertTrue(archived['archived'])
        self.assertFalse(self.store.save('campaigns','campaign',{**archived,'archived':False},2)['archived'])

    def test_rejects_wrong_base_empty_mask_and_bad_files(self):
        for override in ({'base_asset':self.ref},{'mask_asset':self.store.upload(png('black'))['id']}):
            with self.assertRaises(ValueError):self.enqueue([{**self.operation(),**override}])
        with self.assertRaises(ValueError):self.store.upload(b'not an image')
        with self.assertRaises(ValueError):self.store.asset('../secret')

    def test_retry_continues_after_last_completed_step(self):
        job=self.enqueue([self.operation(),self.operation('erase')])
        calls=[]
        def fail_second(prompt,**kwargs):
            calls.append(kwargs)
            if len(calls)==2:raise ValueError('offline')
            return png('green')
        self.store.run(job['id'],fail_second)
        self.store.retry(job['id'])
        self.store.run(job['id'],lambda prompt,**kwargs: calls.append(kwargs) or png('yellow'))
        self.assertEqual(len(calls),3)
        self.assertEqual(self.store.get('jobs',job['id'])['status'],'succeeded')

    def test_extracted_layer_is_transparent_and_document_renders_identically(self):
        from aicentralv2.creative_format_lab.editor_layers import render
        job=self.enqueue([self.operation('extract')])
        self.store.run(job['id'],lambda prompt,**kwargs:png('blue'))
        result=self.store.get('jobs',job['id'])
        layer=result['results'][0]['layer']
        self.assertEqual((layer['x'],layer['y'],layer['width'],layer['height']),(3,2,4,4))
        doc=self.store.save('documents','layers',{'base_asset':self.base,'layers':[layer]},0)
        first=render(self.store,result['result_asset'],doc['layers'])
        second=render(self.store,result['result_asset'],self.store.get('documents','layers')['layers'])
        self.assertEqual(first,second)
        image=Image.open(io.BytesIO(first))
        self.assertEqual(image.getpixel((4,3)),(255,0,0,255))
        self.assertEqual(image.getpixel((0,0)),(255,0,0,255))

    def test_formats_have_independent_bases_and_dimensions(self):
        ops=[{'base_asset':self.base,'role':'background','action':'format','aspect_ratio':r} for r in ['1:1','9:16']]
        job=self.enqueue(ops);calls=[]
        self.store.run(job['id'],lambda prompt,**kwargs:calls.append(kwargs) or png('blue'))
        result=self.store.get('jobs',job['id'])
        self.assertEqual(result['status'],'succeeded')
        self.assertEqual(calls[0]['input_references'],calls[1]['input_references'])
        self.assertEqual(self.store.image(result['results'][0]['result_asset']).size,(1080,1080))
        self.assertEqual(self.store.image(result['results'][1]['result_asset']).size,(1080,1920))

    def test_text_renderer_checks_properties_and_preserves_hidden_layer(self):
        from aicentralv2.creative_format_lab.editor_layers import render
        layer={'kind':'text','id':'t','text':'Teste','font_size':8,'width':16,'height':12,'visible':False}
        image=Image.open(io.BytesIO(render(self.store,self.base,[layer])))
        self.assertEqual(list(image.getdata()),list(self.store.image(self.base).getdata()))
        with self.assertRaises(ValueError):render(self.store,self.base,[{**layer,'width':float('nan')}])
        layer['visible']=True
        self.assertTrue(render(self.store,self.base,[layer]))

    def test_cutout_is_transparent_and_does_not_call_image_model(self):
        operation={**self.operation('erase'),'action':'cutout','reference_asset':None,'role':'product'}
        job=self.enqueue([operation]);calls=[]
        self.store.run(job['id'],lambda *_a,**_k:calls.append(1) or png('blue'))
        result=self.store.get('jobs',job['id'])
        image=self.store.image(result['result_asset'])
        self.assertEqual(calls,[])
        self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertEqual(image.getpixel((4,3)),(255,0,0,255))

    def test_solid_background_is_deterministic_and_preserves_outside_mask(self):
        operation={**self.operation('erase'),'action':'fill','reference_asset':None,'role':'background','background_color':'#123456'}
        job=self.enqueue([operation]);calls=[]
        self.store.run(job['id'],lambda *_a,**_k:calls.append(1) or png('blue'))
        image=self.store.image(self.store.get('jobs',job['id'])['result_asset'])
        self.assertEqual(calls,[])
        self.assertEqual(image.getpixel((4,3)),(18,52,86,255))
        self.assertEqual(image.getpixel((0,0)),(255,0,0,255))

    def test_similarity_uses_two_role_scoped_inputs(self):
        operation={'base_asset':self.base,'mask_asset':None,'reference_asset':self.ref,
                   'role':'background','action':'similarity','instruction':'Mais editorial'}
        job=self.store.enqueue({'operation_id':'d'*32,'base_asset':self.base,
                                'protected_masks':[{'mask_asset':self.mask,'role':'logo','label':'Logo'}],'operations':[operation]});calls=[]
        def generate(prompt,**kwargs):
            calls.append((prompt,kwargs));return png('green')
        self.store.run(job['id'],generate)
        prompt,kwargs=calls[0]
        self.assertEqual(len(kwargs['input_references']),2)
        self.assertIn('FIRST image remains the source of truth',prompt)
        self.assertEqual(self.store.get('jobs',job['id'])['operations'][0]['reference_role'],'similarity_reference')
        self.assertEqual(self.store.get('jobs',job['id'])['results'][0]['qa']['protected_regions'],1)

    def test_similarity_requires_brand_protection(self):
        operation={'base_asset':self.base,'mask_asset':None,'reference_asset':self.ref,
                   'role':'background','action':'similarity','instruction':'Mais editorial'}
        with self.assertRaisesRegex(ValueError,'proteja'):
            self.enqueue([operation])
        with self.assertRaisesRegex(ValueError,'classifique'):
            self.store.enqueue({'operation_id':'f'*32,'base_asset':self.base,
                'protected_masks':[{'mask_asset':self.mask,'role':'person'}],'operations':[operation]})

    def test_logo_mutation_requires_explicit_confirmation(self):
        operation={**self.operation(),'role':'logo'}
        with self.assertRaisesRegex(ValueError,'explicitamente'):
            self.enqueue([operation])
        job=self.enqueue([{**operation,'explicit_brand_change':True}])
        self.assertTrue(job['operations'][0]['explicit_brand_change'])

    def test_rejects_incompatible_action_and_role(self):
        operation={**self.operation('erase'),'action':'fill','role':'person','background_color':'#ffffff'}
        with self.assertRaisesRegex(ValueError,'compatível'):
            self.enqueue([operation])

    def test_background_preset_is_catalogued_and_normalized(self):
        operation={**self.operation('erase'),'action':'recreate','reference_asset':None,
                   'role':'background','instruction':'','background_preset':'paper'}
        job=self.enqueue([operation])
        normalized=self.store.get('jobs',job['id'])['operations'][0]
        self.assertEqual(normalized['background_preset'],'paper')
        self.assertIn('paper texture',normalized['instruction'])
        with self.assertRaisesRegex(ValueError,'Preset'):
            self.store.enqueue({'operation_id':'e'*32,'base_asset':self.base,
                'operations':[{**operation,'background_preset':'inventado'}]})


class WorkspaceHttpTest(unittest.TestCase):
    def test_auth_csrf_and_private_asset_roundtrip(self):
        from unittest.mock import patch
        from flask import Flask, Blueprint
        from aicentralv2.creative_format_lab import editor_routes
        with tempfile.TemporaryDirectory() as root:
            store=Workspace(root)
            app=Flask(__name__);app.secret_key='test-only'
            bp=Blueprint('test_editor',__name__)
            editor_routes.register_editor_routes(bp);app.register_blueprint(bp)
            client=app.test_client();path='/api/format-lab/swap/editor/assets?client_id=1'
            self.assertEqual(client.post(path).status_code,401)
            with client.session_transaction() as session:
                session['user_id']=1;session['user_type']='admin';session['trocr_csrf_token']='csrf'
            self.assertEqual(client.post(path).status_code,403)
            with patch.object(editor_routes,'workspace',lambda:store):
                response=client.post(path,headers={'X-Trocr-CSRF-Token':'csrf'},data={'file':(io.BytesIO(png('red')),'base.png')})
                self.assertEqual(response.status_code,200)
                ident=response.json['data']['id']
                content=client.get(f'/api/format-lab/swap/editor/assets/{ident}/content?client_id=1')
                self.assertEqual(content.status_code,200)
                self.assertIn('private',content.headers['Cache-Control'])
                content.close()
                self.assertEqual(client.get('/api/format-lab/swap/editor/assets/bad/content?client_id=1').status_code,404)


class SelectionTest(unittest.TestCase):
    def test_color_contour_requires_review_and_is_bound_to_base(self):
        from aicentralv2.creative_format_lab.editor_selection import suggest
        with tempfile.TemporaryDirectory() as root:
            store=Workspace(root)
            image=Image.new('RGB',(100,100),'white')
            from PIL import ImageDraw
            ImageDraw.Draw(image).ellipse((20,20,70,70),fill='blue')
            output=io.BytesIO();image.save(output,'PNG')
            base=store.upload(output.getvalue())['id']
            result=suggest(store,{'base_asset':base,'point':{'x':.45,'y':.45},'mode':'include'})
            self.assertEqual(result['engine'],'color-contour')
            self.assertTrue(result['review_required'])
            self.assertGreater(result['coverage'],0)
            self.assertIsNone(result['warning'])
            mask=store.image(result['mask_asset']).convert('L')
            self.assertEqual(mask.getpixel((45,45)),255)
            self.assertEqual(mask.getpixel((0,0)),0)
            with self.assertRaises(ValueError):
                suggest(store,{'base_asset':base,'mask_asset':result['mask_asset'],'mask_base':'other','point':{'x':.45,'y':.45},'mode':'include'})

    def test_tolerance_controls_adjacent_tones_and_rejects_invalid_values(self):
        from aicentralv2.creative_format_lab.editor_selection import suggest
        from PIL import ImageDraw
        with tempfile.TemporaryDirectory() as root:
            store=Workspace(root)
            image=Image.new('RGB',(100,100),'white')
            draw=ImageDraw.Draw(image)
            draw.rectangle((20,20,40,70),fill=(0,0,100))
            draw.rectangle((41,20,70,70),fill=(0,0,150))
            output=io.BytesIO();image.save(output,'PNG')
            base=store.upload(output.getvalue())['id']
            payload={'base_asset':base,'point':{'x':.3,'y':.4},'mode':'include'}
            for tolerance,expected in [(20,0),(80,255)]:
                result=suggest(store,{**payload,'tolerance':tolerance})
                self.assertEqual(store.image(result['mask_asset']).convert('L').getpixel((60,40)),expected)
            draw.rectangle((10,10,85,85),fill=(0,0,100))
            output=io.BytesIO();image.save(output,'PNG')
            large=store.upload(output.getvalue())['id']
            broad=suggest(store,{**payload,'base_asset':large})
            self.assertGreater(broad['coverage'],.35)
            self.assertIn('35%',broad['warning'])
            for value in [0,121,True,float('nan'),'48']:
                with self.assertRaises(ValueError):suggest(store,{**payload,'tolerance':value})

    def test_tiny_point_region_warns_instead_of_claiming_full_element(self):
        from aicentralv2.creative_format_lab.editor_selection import suggest
        with tempfile.TemporaryDirectory() as root:
            store=Workspace(root)
            image=Image.new('RGB',(100,100),'white');image.putpixel((50,50),(0,0,0))
            out=io.BytesIO();image.save(out,'PNG')
            base=store.upload(out.getvalue())['id']
            result=suggest(store,{'base_asset':base,'point':{'x':.5,'y':.5},'mode':'include'})
            self.assertIn('pequena área',result['warning'])
            self.assertTrue(result['review_required'])

    def test_protection_preserves_pixels_even_inside_edit_region(self):
        with tempfile.TemporaryDirectory() as root:
            store=Workspace(root)
            base=store.upload(png('red'))['id']
            mask=store.upload(png('white'))['id']
            protected=Image.new('L',(16,12));protected.putpixel((8,6),255)
            output=io.BytesIO();protected.save(output,'PNG');protection=store.upload(output.getvalue())['id']
            job=store.enqueue({'operation_id':'b'*32,'base_asset':base,'protected_masks':[{'mask_asset':protection,'role':'logo'}],
                'operations':[{'base_asset':base,'mask_asset':mask,'role':'product','action':'erase'}]})
            store.run(job['id'],lambda prompt,**kwargs:png('blue'))
            result=store.image(store.get('jobs',job['id'])['result_asset'])
            self.assertEqual(result.getpixel((8,6)),(255,0,0,255))
            self.assertEqual(result.getpixel((0,0)),(0,0,255,255))
