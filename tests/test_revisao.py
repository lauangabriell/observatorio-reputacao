from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revisao import sinalizar


def previsao(p=.1, n=.1, neg=.8):
    scores = {"positivo": p, "neutro": n, "negativo": neg}
    return {"sentimento": max(scores, key=scores.get), **{f"escore_{k}": v for k, v in scores.items()}}


class Revisao(unittest.TestCase):
    def test_caso_do_candidato(self):
        r = sinalizar("desgraça de itau aplicativo horrivel e nojento, retiro oq eu disse da nubank.", "Nubank", previsao(.256, .360, .384))
        for motivo in ["escores_proximos", "multiplas_empresas_detectadas", "possivel_referencia_a_fala_anterior"]:
            self.assertIn(motivo, r["motivos_revisao"])
        self.assertTrue(r["revisao_necessaria"])
        self.assertEqual(r["sentimento_empresa"], "nao_determinado_automaticamente")

    def test_marca_unica_sem_alerta_nao_significa_alvo_resolvido(self):
        r = sinalizar("Nubank é ruim", "Nubank", previsao())
        self.assertFalse(r["revisao_necessaria"])
        self.assertEqual(r["sentimento_empresa"], "nao_determinado_automaticamente")

    def test_alvo_ausente(self):
        self.assertIn("empresa_alvo_nao_detectada", sinalizar("Itaú é ruim", "Nubank", previsao())["motivos_revisao"])

    def test_limite_de_palavra(self):
        r = sinalizar("nubankinho", "Nubank", previsao())
        self.assertIn("empresa_alvo_nao_detectada", r["motivos_revisao"])

    def test_dominio_novo(self):
        self.assertIn("empresa_fora_do_dominio", sinalizar("iFood é bom", "iFood", previsao(.8, .1, .1))["motivos_revisao"])

    def test_rejeita_escores_invalidos(self):
        with self.assertRaises(ValueError):
            sinalizar("Nubank", "Nubank", previsao(.9, .9, .9))
