import unittest

from aicentralv2.services.brevo_contatos_sync import Desejado, montar_plano


def _d(email, segmento, executivo):
    return Desejado(email=email, nome="X", segmento=segmento, executivo=executivo)


class MontarPlanoTest(unittest.TestCase):
    def test_cliente_vai_para_21_e_lista_do_executivo(self):
        plano = montar_plano({"a@x.com": _d("a@x.com", "clientes", "João Figueiredo")}, {})
        self.assertEqual(plano.incluir[0]["listas"], [21, 35])

    def test_lead_vai_so_para_lista_de_leads(self):
        plano = montar_plano({"a@x.com": _d("a@x.com", "leads", "Demetrius D")}, {})
        self.assertEqual(plano.incluir[0]["listas"], [32])

    def test_quem_ja_esta_na_lista_nao_e_reenviado(self):
        plano = montar_plano({"a@x.com": _d("a@x.com", "leads", "João")}, {34: {"a@x.com"}})
        self.assertEqual(plano.incluir, [])

    def test_lead_que_virou_cliente_sai_da_lista_de_leads(self):
        membros = {32: {"a@x.com"}, 33: {"a@x.com"}, 21: {"a@x.com"}}
        plano = montar_plano({"a@x.com": _d("a@x.com", "clientes", "Demetrius")}, membros)
        self.assertEqual(plano.incluir, [])
        self.assertEqual(plano.remover, {32: ["a@x.com"]})

    def test_troca_de_executivo_move_de_lista(self):
        plano = montar_plano({"a@x.com": _d("a@x.com", "leads", "João")}, {36: {"a@x.com"}})
        self.assertEqual(plano.incluir[0]["listas"], [34])
        self.assertEqual(plano.remover, {36: ["a@x.com"]})

    def test_executivo_sem_lista_nao_importa_nem_remove(self):
        plano = montar_plano({"a@x.com": _d("a@x.com", "clientes", "Rogério Lira")}, {35: {"a@x.com"}})
        self.assertEqual(plano.incluir, [])
        self.assertEqual(plano.remover, {})
        self.assertEqual(plano.sem_lista, {"Rogério": 1})

    def test_email_que_so_existe_na_brevo_fica(self):
        plano = montar_plano({}, {35: {"manual@x.com"}})
        self.assertEqual(plano.remover, {})


if __name__ == "__main__":
    unittest.main()
