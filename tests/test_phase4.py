import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra import hooks
from hydra.config import Config
from hydra.drivers import GenericDriver
from hydra.errors import HydraError
from hydra.roles import BUILTIN, load_role
from hydra.runner import run
from hydra.sharedmem import SharedContext

FAKE = str(Path(__file__).resolve().parent / "_fakeagent.py")


def cfg():
    return Config(agent_kind=None, agent_args=None, agent_template=[], timeout=60,
                  base_branch="HEAD", pricing=None, source=None)


def driver():
    return GenericDriver(template=[sys.executable, FAKE])


class RolesTest(unittest.TestCase):
    def test_builtins_load(self):
        for name in BUILTIN:
            self.assertTrue(load_role(".", name).strip())

    def test_repo_override_wins(self):
        with TemporaryDirectory() as tmp:
            d = Path(tmp) / ".hydra" / "roles"
            d.mkdir(parents=True)
            (d / "coder.md").write_text("CUSTOM CODER", encoding="utf-8")
            self.assertEqual(load_role(tmp, "coder"), "CUSTOM CODER")

    def test_unknown_role(self):
        with self.assertRaises(HydraError):
            load_role(".", "wizard")


class SharedContextTest(unittest.TestCase):
    def test_append_current_search(self):
        with TemporaryDirectory() as tmp:
            sc = SharedContext(tmp)
            sc.append("slug", "Added slugify()", ["src/slug.py"], "lowercases only")
            sc.append("conf", "Added config loader", ["src/conf.py"])
            self.assertIn("slugify", sc.current())
            hits = sc.search("slugify")
            self.assertTrue(hits and "slug" in hits[0])
            self.assertEqual(sc.search("nonexistentterm"), [])
            sc.close()


class HooksTest(unittest.TestCase):
    def test_missing_hook_is_ok(self):
        with TemporaryDirectory() as tmp:
            ok, out = hooks.run_hook(tmp, "pre-task", {"task": "x"})
            self.assertTrue(ok)
            self.assertEqual(out, "")

    def test_py_hook_runs_with_env(self):
        with TemporaryDirectory() as tmp:
            hd = Path(tmp) / ".hydra" / "hooks"
            hd.mkdir(parents=True)
            (hd / "pre-task.py").write_text(
                "import os,sys; sys.stdout.write(os.environ['HYDRA_TASK']); "
                "sys.exit(0 if os.environ['HYDRA_TASK']!='bad' else 1)",
                encoding="utf-8")
            ok, out = hooks.run_hook(tmp, "pre-task", {"task": "good"})
            self.assertTrue(ok)
            self.assertEqual(out, "good")
            ok2, _ = hooks.run_hook(tmp, "pre-task", {"task": "bad"})
            self.assertFalse(ok2)


class RunnerIntegrationTest(unittest.TestCase):
    def test_shared_memory_accumulates_across_batches(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = Path(tmp) / "tasks.toml"
            tf.write_text(textwrap.dedent("""
                [[task]]
                id="a"
                title="make A"
                prompt="make it"
                files=["src/a.py"]
                role="coder"
                [[task]]
                id="b"
                title="make B on A"
                prompt="make it"
                files=["src/b.py"]
                depends_on=["a"]
            """), encoding="utf-8")
            out = run(root, tf, cfg(), driver())
            self.assertEqual(out.failed, 0)
            ctx = (root / ".hydra" / "runs" / out.state.run_id / "context.md").read_text(encoding="utf-8")
            self.assertIn("## a", ctx)
            self.assertIn("## b", ctx)

    def test_pre_task_hook_can_abort(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            hd = root / ".hydra" / "hooks"
            hd.mkdir(parents=True)
            (hd / "pre-task.py").write_text("import sys; sys.exit(1)", encoding="utf-8")
            tf = Path(tmp) / "tasks.toml"
            tf.write_text('[[task]]\nid="x"\ntitle="x"\nprompt="p"\nfiles=["x.py"]\n',
                          encoding="utf-8")
            with self.assertRaises(HydraError):
                run(root, tf, cfg(), driver())


if __name__ == "__main__":
    unittest.main()
