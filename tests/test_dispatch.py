import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra.dispatch import dispatch_one
from hydra.drivers import GenericDriver
from hydra.tasks import Task


def _fake_agent(*, touch: str, body: str = "# generated\n") -> GenericDriver:
    script = (f"import sys,pathlib;sys.stdin.read();"
              f"pathlib.Path({touch!r}).parent.mkdir(parents=True,exist_ok=True);"
              f"pathlib.Path({touch!r}).write_text({body!r})")
    return GenericDriver(template=[sys.executable, "-c", script])


class DispatchTest(unittest.TestCase):
    def test_dispatch_produces_a_diff(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            task = Task(id="add-mod", title="add a module",
                        prompt="make src/mod.py", files=("src/mod.py",))
            res = dispatch_one(root, task, _fake_agent(touch="src/mod.py"), base="HEAD")
            self.assertTrue(res.ok, res.error)
            self.assertIn("src/mod.py", res.diff)
            self.assertEqual(res.files_changed, 1)
            # worktree cleaned up by default
            self.assertFalse((root / ".hydra" / "wt" / "add-mod").exists())

    def test_agent_that_changes_nothing_is_a_failure(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            noop = GenericDriver(template=[sys.executable, "-c", "import sys;sys.stdin.read()"])
            task = Task(id="noop", title="do nothing", prompt="…")
            res = dispatch_one(root, task, noop, base="HEAD")
            self.assertFalse(res.ok)
            self.assertIn("changed no files", res.error)

    def test_agent_crash_is_reported_not_raised(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            boom = GenericDriver(template=[sys.executable, "-c", "import sys;sys.exit(3)"])
            task = Task(id="boom", title="crash", prompt="…")
            res = dispatch_one(root, task, boom, base="HEAD")
            self.assertFalse(res.ok)
            self.assertIn("exited 3", res.error)

    def test_keep_worktree(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            task = Task(id="k", title="k", prompt="p", files=("a.txt",))
            res = dispatch_one(root, task, _fake_agent(touch="a.txt"),
                               base="HEAD", keep_worktree=True)
            self.assertTrue(res.worktree_path.exists())
            from hydra import worktree
            worktree.remove(root, "k")


if __name__ == "__main__":
    unittest.main()
