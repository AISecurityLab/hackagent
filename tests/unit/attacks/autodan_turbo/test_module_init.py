import unittest

import hackagent.attacks.techniques.autodan_turbo as autodan_pkg


class TestAutoDANModuleInit(unittest.TestCase):
    def test_exports_attack_class(self):
        self.assertIn("AutoDANTurboAttack", autodan_pkg.__all__)
        self.assertTrue(hasattr(autodan_pkg, "AutoDANTurboAttack"))


if __name__ == "__main__":
    unittest.main()
