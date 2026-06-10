import tempfile
import unittest
from pathlib import Path

from modelctl_core import detect_from_ini, plan_delete_model


class ImportAutodetectSafetyTests(unittest.TestCase):
    def test_import_autodetects_generic_ini_without_modifying_it_and_warns_multi_alias_delete(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            models = root / "models"
            models.mkdir()
            shared = models / "shared-model.Q4_K_M.gguf"
            solo = models / "solo-model.Q8_0.gguf"
            shared.write_bytes(b"shared")
            solo.write_bytes(b"solo")

            router_ini = root / "any-router.ini"
            original_ini = """
# arbitrary preamble should be preserved
[alpha]
model = {shared}
ctx-size = 4096

[models.beta]
model = {shared}
ctx-size = 8192

# [disabled.gamma]
# model = {solo}
# ctx-size = 2048

[not-a-model]
foo = bar
""".format(shared=shared, solo=solo).lstrip()
            router_ini.write_text(original_ini, encoding="utf-8")

            imported = detect_from_ini(router_ini)

            self.assertEqual(imported["router_ini"], str(router_ini))
            self.assertEqual(imported["download_dir"], str(models))
            self.assertEqual(
                sorted(alias["section"] for alias in imported["aliases"]),
                ["alpha", "disabled.gamma", "models.beta"],
            )
            self.assertEqual(
                {alias["section"]: alias["enabled"] for alias in imported["aliases"]},
                {"alpha": True, "models.beta": True, "disabled.gamma": False},
            )

            plan = plan_delete_model(imported, str(shared))

            self.assertEqual(plan["action"], "delete_model")
            self.assertEqual(plan["model_path"], str(shared))
            self.assertEqual(plan["aliases_impacted"], ["alpha", "models.beta"])
            self.assertEqual(plan["files_to_delete"], [str(shared)])
            self.assertTrue(plan["requires_confirmation"])
            self.assertIn("multiple aliases", plan["warnings"][0])

            # The test must never modify the user's/router config; even fixture ini stays byte-identical.
            self.assertEqual(router_ini.read_text(encoding="utf-8"), original_ini)
            self.assertTrue(shared.exists())
            self.assertTrue(solo.exists())


if __name__ == "__main__":
    unittest.main()
