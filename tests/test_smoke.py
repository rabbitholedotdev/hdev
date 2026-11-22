"""Smoke do Stop: importa o núcleo. A suíte inteira roda no hdev fechar."""
import unittest

from hdev import check, stop


class Smoke(unittest.TestCase):
    def test_lista_fechada_e_tetos(self):
        self.assertEqual(stop.classify("pediram 2FA"), "2fa")
        self.assertIsNone(stop.classify("nome do arquivo"))
        self.assertEqual(check.HOOKS_EXPECTED, 5)
        self.assertEqual(check.AGENTS_MAX, 60)


if __name__ == "__main__":
    unittest.main()
