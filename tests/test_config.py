import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hydra.config import load_config
from hydra.errors import HydraError


class ConfigTest(unittest.TestCase):
    def test_defaults_when_absent(self):
        with TemporaryDirectory() as tmp:
            c = load_config(tmp)
            self.assertIsNone(c.agent_kind)
            self.assertEqual(c.base_branch, "HEAD")
            self.assertEqual(c.timeout, 900)
            self.assertIsNone(c.pricing)

    def test_parses_a_full_file(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "hydra.toml").write_text(textwrap.dedent("""
                [agent]
                kind = "generic"
                template = ["mycli", "--stdin"]
                args = ["-x"]
                timeout = 120

                [run]
                base_branch = "develop"

                [pricing]
                input_per_mtok = 3.0
                output_per_mtok = 15.0
            """), encoding="utf-8")
            c = load_config(tmp)
            self.assertEqual(c.agent_kind, "generic")
            self.assertEqual(c.agent_template, ["mycli", "--stdin"])
            self.assertEqual(c.agent_args, ["-x"])
            self.assertEqual(c.timeout, 120)
            self.assertEqual(c.base_branch, "develop")
            self.assertEqual(c.pricing, (3.0, 15.0))

    def test_bad_toml_raises(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "hydra.toml").write_text("[agent\n", encoding="utf-8")
            with self.assertRaises(HydraError):
                load_config(tmp)

    def test_generic_kind_without_agent_cli_raises_on_driver(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "hydra.toml").write_text(
                '[agent]\nkind="generic"\ntemplate=[]\n', encoding="utf-8")
            c = load_config(tmp)
            # building the driver is fine; it's just unavailable
            d = c.driver()
            self.assertFalse(d.available())


if __name__ == "__main__":
    unittest.main()
