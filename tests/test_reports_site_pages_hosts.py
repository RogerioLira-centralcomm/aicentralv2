import unittest
from unittest import mock

from flask import Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_site_pages


class HostParamTests(unittest.TestCase):
    def call(self, query):
        app = Flask(__name__)
        with app.test_request_context(query), mock.patch.object(reports_site_pages, 'client_hosts', return_value=['cliente.com.br', 'loja.cliente.com.br']):
            return reports_site_pages._host_param(1)

    def test_www_is_the_same_site(self):
        self.assertEqual(self.call('/?host=www.cliente.com.br')[0], 'cliente.com.br')

    def test_unknown_domain_is_refused(self):
        with self.assertRaises(BadRequest):
            self.call('/?host=outro.com')

    def test_default_is_the_first_site(self):
        self.assertEqual(self.call('/')[0], 'cliente.com.br')


if __name__ == '__main__':
    unittest.main()
