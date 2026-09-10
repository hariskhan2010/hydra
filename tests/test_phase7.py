import json
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra.config import Config
from hydra.drivers import GenericDriver
from hydra.reflect import gather_failures, reflect
from hydra.roles import load_role
from hydra.runner import run

FAKE = str(Path(__file__).resolve().parent / "_fakeagent.py")


def cfg():
    return Config(agent_kind=None, agent_args=None, agent_template=[], timeout=60,
                  base_branch="HEAD", pricing=None, source=None)


def driver():
    return GenericDriver(template=[sys.executable, FAKE])


class ReflectTest(unittest.TestCase):
    def _repo_with_a_failed_run(self, tmp: Path):
        root = make_repo(tmp / "repo")
        tf = tmp / "tasks.toml"
        tf.write_text(textwrap.dedent("""
            [[task]]
            id="a"
            title="a FAIL"
            prompt="FAIL please"
            files=["src/a.py"]
            role="coder"
        """), encoding="utf-8")
        run(root, tf, cfg(), driver())
        return root

    def test_gather_failures_groups_by_role(self):
        with TemporaryDirectory() as tmp:
            root = self._repo_with_a_failed_run(Path(tmp))
            f = gather_failures(root)
            self.assertIn("coder", f)
            self.assertTrue(f["coder"])

    def test_reflect_writes_lessons_and_load_role_uses_them(self):
        with TemporaryDirectory() as tmp:
            root = self._repo_with_a_failed_run(Path(tmp))
            written = reflect(root)  # no driver -> raw list
            self.assertIn("coder", written)
            self.assertTrue(written["coder"].exists())

            role_text = load_role(root, "coder")
            self.assertIn("Lessons for the coder role", role_text)
            self.assertIn("You are the **coder**", role_text)  # base still there

    def test_reflect_noop_when_no_failures(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            self.assertEqual(reflect(root), {})


class EvalHarnessTest(unittest.TestCase):
    def test_two_helpers_case_files_are_valid(self):
        import tomllib
        case = Path(__file__).resolve().parent.parent / "eval" / "cases" / "two-helpers"
        spec = tomllib.loads((case / "case.toml").read_text(encoding="utf-8"))
        self.assertIn("check", spec)
        self.assertTrue((case / spec["tasks"]).exists())
        self.assertTrue((case / "repo").is_dir())
        from hydra.tasks import load_tasks
        tasks = load_tasks(case / spec["tasks"])
        self.assertEqual({t.id for t in tasks}, {"slug", "upper", "consume"})


if __name__ == "__main__":
    unittest.main()
