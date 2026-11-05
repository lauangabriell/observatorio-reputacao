import unittest
from assuntos import identificar, ranking, OUTROS


class AssuntosTest(unittest.TestCase):
    def test_acentos_e_multiplos(self):
        self.assertEqual(identificar('O aplicativo é bom, mas o atendimento é péssimo'), ['Atendimento', 'Aplicativo'])
        self.assertIn('Cartão e limite', identificar('CARTÃO com limite'))

    def test_fronteiras_e_outros(self):
        self.assertEqual(identificar('felizmente aconteceu'), [OUTROS])
        self.assertEqual(identificar(None), [OUTROS])

    def test_contagem_por_id_e_denominador(self):
        r = ranking([{'comment_id': '1', 'texto': 'app app atendimento'},
                     {'comment_id': '1', 'texto': 'app'},
                     {'comment_id': '2', 'texto': 'oi'}])
        self.assertEqual(len(r), 3)
        self.assertTrue(all(x['Comentários'] == 1 and x['Percentual'] == 50 for x in r))

    def test_vazio(self):
        self.assertEqual(ranking([]), [])

    def test_nao_atribui_sentimento(self):
        self.assertEqual(identificar('atendimento bom'), identificar('atendimento ruim'))


if __name__ == '__main__':
    unittest.main()
