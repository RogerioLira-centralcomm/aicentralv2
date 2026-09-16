import io
from unittest import TestCase
from PIL import Image
from werkzeug.datastructures import FileStorage
from aicentralv2.cadu_connect.import_inbox import validate_inbox_upload


class ImportInboxTests(TestCase):
    def test_validates_standalone_import_without_campaign(self):
        data=io.BytesIO(); Image.new('RGB',(10,10)).save(data,'PNG'); data.seek(0)
        item=validate_inbox_upload(FileStorage(stream=data,filename='meta.png'),{'supplier':'Meta Ads'})
        self.assertEqual(item['supplier'],'Meta Ads')
        self.assertEqual(item['mime_type'],'image/png')
