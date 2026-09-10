import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra.errors import HydraError
from hydra.overpower import tasks_from_overpower
from hydra.remote import plan_remote


class OverpowerParseTest(unittest.TestCase):
    def _plan(self, tmp: Path, body: str) -> Path:
        root = make_repo(tmp / "repo")
        (root / ".overpower").mkdir()
        (root / ".overpower" / "plan.md").write_text(textwrap.dedent(body), encoding="utf-8")
        return root

    def test_parses_tasks_files_and_deps(self):
        with TemporaryDirectory() as tmp:
            root = self._plan(Path(tmp), """
                # Plan

                ## Task 1 — Add slugify helper
                Files: src/slug.py, tests/test_slug.py
                Implement slugify().

                ## Task 2 — Add config loader
                Files: src/config.py
                Read TOML into a dataclass.

                ## Task 3 — Wire the endpoint
                Depends on: 1, 2
                Files:
                - src/api.py
                - tests/test_api.py
                GET /slug using slugify + config.
            """)
            tasks = tasks_from_overpower(root)
            self.assertEqual([t.id for t in tasks],
                             ["add-slugify-helper", "add-config-loader", "wire-the-endpoint"])
            self.assertEqual(tasks[0].files, ("src/slug.py", "tests/test_slug.py"))
            self.assertEqual(set(tasks[2].files), {"src/api.py", "tests/test_api.py"})
            self.assertEqual(set(tasks[2].depends_on),
                             {"add-slugify-helper", "add-config-loader"})
            self.assertIn("slugify", tasks[0].prompt)

    def test_missing_plan(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            with self.assertRaises(HydraError):
                tasks_from_overpower(root)

    def test_no_task_headings(self):
        with TemporaryDirectory() as tmp:
            root = self._plan(Path(tmp), "# Plan\n\nSome prose, no task sections.\n")
            with self.assertRaises(HydraError):
                tasks_from_overpower(root)


class RemotePlanTest(unittest.TestCase):
    def test_command_shapes(self):
        with TemporaryDirectory() as tmp:
            root = make_repo(Path(tmp) / "repo")
            p = plan_remote(root, "user@box", "tasks.toml", ["--max-agents", "4"])
            self.assertEqual(p.push[0], "rsync")
            self.assertIn("--exclude", p.push)
            self.assertEqual(p.execute[0], "ssh")
            self.assertIn("hydra run tasks.toml --max-agents 4", " ".join(p.execute))
            self.assertEqual(p.fetch[:3], ["git", "-C", str(root.resolve())])
            self.assertIn("refs/heads/hydra/*:refs/heads/hydra/*", p.fetch)


class UsingHydraSkillTest(unittest.TestCase):
    def test_skill_file_has_frontmatter(self):
        skill = (Path(__file__).resolve().parent.parent / "skills" / "using-hydra" / "SKILL.md"
                 ).read_text(encoding="utf-8")
        self.assertTrue(skill.startswith("---"))
        self.assertIn("name: using-hydra", skill)
        self.assertIn("--from-overpower", skill)


if __name__ == "__main__":
    unittest.main()
