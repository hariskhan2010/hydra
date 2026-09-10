import sys
import unittest

from hydra.drivers import (ClaudeDriver, GenericDriver, QwenDriver, build_driver)
from hydra.errors import HydraError


class DriverArgvTest(unittest.TestCase):
    def test_claude_argv_shape(self):
        d = ClaudeDriver()
        argv = d.argv()
        if argv:  # claude may or may not be on PATH
            self.assertIn("-p", argv)
            self.assertIn("--permission-mode", argv)

    def test_qwen_argv_shape(self):
        d = QwenDriver()
        argv = d.argv()
        if argv:
            self.assertIn("-p", argv)

    def test_extra_args_override(self):
        d = build_driver("claude", extra_args=["--foo"])
        if d.argv():
            self.assertIn("--foo", d.argv())
            self.assertNotIn("--permission-mode", d.argv())

    def test_unknown_kind(self):
        with self.assertRaises(HydraError):
            build_driver("nope")

    def test_generic_missing_template_unavailable(self):
        self.assertFalse(GenericDriver().available())


class DriverRunTest(unittest.TestCase):
    def test_generic_driver_runs_a_process(self):
        # a fake "agent": read the prompt from stdin, write a file in cwd
        script = ("import sys,pathlib;"
                  "p=sys.stdin.read();"
                  "pathlib.Path('agent_out.txt').write_text(p[:20])")
        d = GenericDriver(template=[sys.executable, "-c", script])
        import tempfile
        with tempfile.TemporaryDirectory() as cwd:
            res = d.run("hello prompt", cwd, timeout=30)
            self.assertTrue(res.ok, res.error)
            import pathlib
            self.assertEqual((pathlib.Path(cwd) / "agent_out.txt").read_text(),
                             "hello prompt")

    def test_missing_exe_is_a_clean_result_not_a_crash(self):
        d = GenericDriver(template=["definitely-not-a-real-binary-xyz"])
        res = d.run("p", ".", timeout=5)
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.error)


if __name__ == "__main__":
    unittest.main()
