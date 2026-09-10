import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra import gitutil, worktree
from hydra.errors import HydraError


class WorktreeTest(unittest.TestCase):
    def test_create_capture_remove(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")

            wt = worktree.create(root, "task-a", base="HEAD")
            self.assertTrue(wt.path.is_dir())
            self.assertEqual(wt.branch, "hydra/task-a")
            self.assertTrue((root / ".hydra" / ".gitignore").exists())

            # simulate an agent editing + adding files
            (wt.path / "src" / "new.py").write_text("y = 2\n", encoding="utf-8")
            (wt.path / "src" / "seed.py").write_text("x = 99\n", encoding="utf-8")

            diff = worktree.capture_diff(wt)
            self.assertIn("src/new.py", diff)
            self.assertIn("x = 99", diff)

            worktree.remove(root, "task-a")
            self.assertFalse(wt.path.exists())
            branches = gitutil.git(["branch", "--list", "hydra/task-a"], cwd=root)
            self.assertEqual(branches.strip(), "")

    def test_recreate_over_stale(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            worktree.create(root, "t", base="HEAD")
            wt2 = worktree.create(root, "t", base="HEAD")  # must not raise
            self.assertTrue(wt2.path.is_dir())
            worktree.remove(root, "t")

    def test_needs_a_commit(self):
        with TemporaryDirectory() as tmp:
            bare = Path(tmp) / "empty"
            bare.mkdir()
            gitutil.git(["init", "-q"], cwd=bare)
            with self.assertRaises(HydraError):
                worktree.create(bare, "t", base="HEAD")


if __name__ == "__main__":
    unittest.main()
