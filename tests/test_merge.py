import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra import gitutil
from hydra.config import Config
from hydra.drivers import GenericDriver
from hydra.merge import merge_run
from hydra.runner import run

FAKE = str(Path(__file__).resolve().parent / "_fakeagent.py")


def cfg():
    return Config(agent_kind=None, agent_args=None, agent_template=[], timeout=60,
                  base_branch="HEAD", pricing=None, source=None)


def driver():
    return GenericDriver(template=[sys.executable, FAKE])


def tasks_file(tmp: Path, body: str) -> Path:
    p = tmp / "tasks.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class MergeTest(unittest.TestCase):
    def test_happy_path_merges_all(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = tasks_file(Path(tmp), """
                [[task]]
                id="slug"
                title="slug"
                prompt="make it"
                files=["src/slug.py"]
                [[task]]
                id="api"
                title="api"
                prompt="make it"
                files=["src/api.py"]
                depends_on=["slug"]
            """)
            out = run(root, tf, cfg(), driver())
            by_id = {t.id: t for t in __import__("hydra.tasks", fromlist=["load_tasks"]).load_tasks(tf)}

            m = merge_run(root, out.state, by_id)
            self.assertTrue(m.ok, (m.blocked, m.conflicted))
            self.assertEqual(sorted(m.merged), ["api", "slug"])

            # the integration branch has both files
            show = gitutil.git(["ls-tree", "-r", "--name-only", m.integration_branch], cwd=root)
            self.assertIn("src/slug.py", show)
            self.assertIn("src/api.py", show)
            # target branch untouched
            self.assertNotIn("src/slug.py",
                             gitutil.git(["ls-tree", "-r", "--name-only", "HEAD"], cwd=root))

    def test_scope_breach_blocks_merge_when_another_task_owns_the_file(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            # task `t` will be tampered to touch src/owned.py, which task `o` declares
            tf = tasks_file(Path(tmp), """
                [[task]]
                id="t"
                title="t"
                prompt="make it"
                files=["src/t.py"]
                [[task]]
                id="o"
                title="o"
                prompt="make it"
                files=["src/owned.py"]
            """)
            out = run(root, tf, cfg(), driver())
            dp = out.state.diff_path(root, "t")
            dp.write_text(dp.read_text(encoding="utf-8") + textwrap.dedent("""
                diff --git a/src/owned.py b/src/owned.py
                --- a/src/owned.py
                +++ b/src/owned.py
                @@ -1 +1,2 @@
                 x
                +sneaky
            """), encoding="utf-8")
            by_id = {t.id: t for t in __import__("hydra.tasks", fromlist=["load_tasks"]).load_tasks(tf)}
            m = merge_run(root, out.state, by_id)
            self.assertFalse(m.ok)
            self.assertTrue(m.blocked)

    def test_undeclared_shared_file_does_not_block(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = tasks_file(Path(tmp), """
                [[task]]
                id="t"
                title="t"
                prompt="make it"
                files=["src/t.py"]
            """)
            out = run(root, tf, cfg(), driver())
            dp = out.state.diff_path(root, "t")
            dp.write_text(dp.read_text(encoding="utf-8") + textwrap.dedent("""
                diff --git a/conftest.py b/conftest.py
                new file mode 100644
                --- /dev/null
                +++ b/conftest.py
                @@ -0,0 +1 @@
                +import sys
            """), encoding="utf-8")
            by_id = {t.id: t for t in __import__("hydra.tasks", fromlist=["load_tasks"]).load_tasks(tf)}
            m = merge_run(root, out.state, by_id)
            self.assertTrue(m.ok, (m.blocked, m.conflicted))


if __name__ == "__main__":
    unittest.main()
