import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra.config import Config
from hydra.drivers import GenericDriver
from hydra.runner import run
from hydra.runstate import DONE, FAILED, SKIPPED, RunState

FAKE = str(Path(__file__).resolve().parent / "_fakeagent.py")


def cfg() -> Config:
    return Config(agent_kind=None, agent_args=None, agent_template=[], timeout=60,
                  base_branch="HEAD", pricing=None, source=None)


def driver() -> GenericDriver:
    return GenericDriver(template=[sys.executable, FAKE])


def _tasks(tmp: Path, body: str) -> Path:
    p = tmp / "tasks.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class RunnerTest(unittest.TestCase):
    def test_full_run_all_succeed(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = _tasks(Path(tmp), """
                [[task]]
                id="slug"
                title="slug"
                prompt="make it"
                files=["src/slug.py"]
                [[task]]
                id="conf"
                title="conf"
                prompt="make it"
                files=["src/conf.py"]
                [[task]]
                id="api"
                title="api"
                prompt="make it"
                files=["src/api.py"]
                depends_on=["slug","conf"]
            """)
            out = run(root, tf, cfg(), driver(), max_agents=2)
            self.assertEqual(out.failed, 0)
            self.assertFalse(out.stopped_early)
            for tid in ("slug", "conf", "api"):
                self.assertEqual(out.state.tasks[tid].status, DONE)
                self.assertTrue(out.state.diff_path(root, tid).exists())
            # slug + conf share batch 0, api is batch 1
            self.assertEqual(out.state.tasks["slug"].batch, 0)
            self.assertEqual(out.state.tasks["api"].batch, 1)

    def test_failure_skips_dependents_and_stops(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = _tasks(Path(tmp), """
                [[task]]
                id="base"
                title="base FAIL"
                prompt="FAIL please"
                files=["src/base.py"]
                [[task]]
                id="child"
                title="child"
                prompt="make it"
                files=["src/child.py"]
                depends_on=["base"]
            """)
            out = run(root, tf, cfg(), driver())
            self.assertEqual(out.state.tasks["base"].status, FAILED)
            self.assertEqual(out.state.tasks["child"].status, SKIPPED)
            self.assertTrue(out.stopped_early)
            self.assertTrue((root / ".hydra" / "runs" / out.state.run_id / "FAILURES.md").exists())

    def test_resume_completes_the_rest(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = _tasks(Path(tmp), """
                [[task]]
                id="a"
                title="a FAIL"
                prompt="FAIL"
                files=["src/a.py"]
                [[task]]
                id="b"
                title="b"
                prompt="make it"
                files=["src/b.py"]
            """)
            out1 = run(root, tf, cfg(), driver())
            # a failed; b is independent so it still ran in the same batch
            self.assertEqual(out1.state.tasks["a"].status, FAILED)
            self.assertEqual(out1.state.tasks["b"].status, DONE)

            # now fix a: rewrite the task file so a no longer says FAIL
            _tasks(Path(tmp), """
                [[task]]
                id="a"
                title="a fixed"
                prompt="make it"
                files=["src/a.py"]
                [[task]]
                id="b"
                title="b"
                prompt="make it"
                files=["src/b.py"]
            """)
            out2 = run(root, tf, cfg(), driver(), resume=True,
                       resume_id=out1.state.run_id)
            self.assertEqual(out2.state.tasks["a"].status, DONE)
            self.assertEqual(out2.state.tasks["b"].status, DONE)

    def test_state_reloads_from_disk(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            tf = _tasks(Path(tmp), """
                [[task]]
                id="x"
                title="x"
                prompt="make it"
                files=["x.py"]
            """)
            out = run(root, tf, cfg(), driver())
            reloaded = RunState.load(root, out.state.run_id)
            self.assertEqual(reloaded.tasks["x"].status, DONE)
            self.assertIn("run ", reloaded.render_table())


if __name__ == "__main__":
    unittest.main()
