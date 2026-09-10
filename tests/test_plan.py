import unittest
from pathlib import Path

from hydra.planning import render_plan

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "tasks.toml"


class RenderPlanTest(unittest.TestCase):
    def test_example_plan(self):
        out = render_plan(EXAMPLE, max_agents=4)
        # slug + config are dependency- and file-independent -> same batch
        self.assertIn("4 task(s), 2 batch(es)", out)
        self.assertIn("batch 0  [parallel x2", out)
        self.assertIn("batch 1  [parallel x2", out)
        self.assertIn("token estimate (rough)", out)
        self.assertIn("critical path", out)
        self.assertIn("nothing dispatched", out)

    def test_governor_one_agent_downgrades_label(self):
        out = render_plan(EXAMPLE, max_agents=1)
        self.assertIn("governor runs 1 at a time", out)

    def test_all_serial_when_files_overlap(self):
        # a bespoke file where everything collides
        import tempfile, textwrap, pathlib
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "tasks.toml"
            p.write_text(textwrap.dedent("""
                [[task]]
                id="a"
                title="A"
                prompt="p"
                files=["src/big.py"]
                [[task]]
                id="b"
                title="B"
                prompt="p"
                files=["src/big.py"]
            """), encoding="utf-8")
            out = render_plan(p, max_agents=4)
            self.assertIn("2 batch(es)", out)
            self.assertIn("no parallelism available", out)

    def test_parallelism_speedup_reported_when_governor_allows(self):
        # the honest line depends on this box; either branch is acceptable
        out = render_plan(EXAMPLE, max_agents=4)
        self.assertTrue(
            ("% shorter than fully serial" in out) or ("no speedup here" in out),
            out,
        )

    def test_speedup_branch_with_a_generous_governor(self):
        # pin the governor high so the parallel-speedup rendering path is covered
        import hydra.planning as planning
        from hydra.governor import Budget

        real = planning.governor.compute
        planning.governor.compute = lambda configured_max=None: Budget(
            cores=8, free_gb=32.0, per_agent_gb=2.0, configured_max=configured_max,
            max_agents=4, reason="pinned for test")
        try:
            out = render_plan(EXAMPLE)
            self.assertIn("shorter than fully serial", out)
        finally:
            planning.governor.compute = real


if __name__ == "__main__":
    unittest.main()
