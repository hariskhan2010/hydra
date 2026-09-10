import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hydra.errors import HydraError
from hydra.tasks import load_tasks


def _write(tmp: str, body: str) -> Path:
    p = Path(tmp) / "tasks.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class LoadTasksTest(unittest.TestCase):
    def test_loads_a_valid_file(self):
        with TemporaryDirectory() as tmp:
            p = _write(tmp, """
                [[task]]
                id = "a"
                title = "A"
                prompt = "do a"
                files = ["src/a.py", "./tests/test_a.py"]

                [[task]]
                id = "b"
                title = "B"
                prompt = "do b"
                depends_on = ["a"]
            """)
            tasks = load_tasks(p)
            self.assertEqual([t.id for t in tasks], ["a", "b"])
            self.assertEqual(tasks[0].files, ("src/a.py", "tests/test_a.py"))
            self.assertEqual(tasks[1].depends_on, ("a",))

    def test_missing_file(self):
        with self.assertRaises(HydraError):
            load_tasks("nope/tasks.toml")

    def test_no_tasks(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(HydraError):
                load_tasks(_write(tmp, "title = 'x'\n"))

    def test_missing_required_key(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(HydraError):
                load_tasks(_write(tmp, '[[task]]\nid="a"\ntitle="A"\n'))

    def test_unknown_key(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(HydraError):
                load_tasks(_write(tmp, '[[task]]\nid="a"\ntitle="A"\nprompt="p"\nbogus=1\n'))

    def test_duplicate_id(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(HydraError):
                load_tasks(_write(tmp, """
                    [[task]]
                    id="a"
                    title="A"
                    prompt="p"
                    [[task]]
                    id="a"
                    title="A2"
                    prompt="p"
                """))

    def test_unknown_dependency(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(HydraError):
                load_tasks(_write(tmp, '[[task]]\nid="a"\ntitle="A"\nprompt="p"\ndepends_on=["ghost"]\n'))


if __name__ == "__main__":
    unittest.main()
