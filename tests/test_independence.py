import unittest

from hydra.errors import HydraError
from hydra.independence import plan_waves, specs_overlap
from hydra.tasks import Task


def T(id, files=(), deps=()):
    return Task(id=id, title=id, prompt=f"do {id}", files=tuple(files), depends_on=tuple(deps))


class SpecsOverlapTest(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(specs_overlap("src/a.py", "src/a.py"))
        self.assertFalse(specs_overlap("src/a.py", "src/b.py"))

    def test_dir_prefix(self):
        self.assertTrue(specs_overlap("src/**", "src/a.py"))
        self.assertTrue(specs_overlap("src/**", "src/deep/x.py"))
        self.assertFalse(specs_overlap("src/**", "tests/a.py"))
        self.assertTrue(specs_overlap("src/**", "src/sub/**"))
        self.assertFalse(specs_overlap("src/**", "lib/**"))

    def test_unprovable_glob_is_conservative(self):
        self.assertTrue(specs_overlap("*.py", "src/a.py"))
        self.assertTrue(specs_overlap("src/*/x.py", "src/a.py"))


class PlanWavesTest(unittest.TestCase):
    def test_disjoint_no_deps_parallelise(self):
        wp = plan_waves([T("a", ["src/a.py"]), T("b", ["src/b.py"])])
        self.assertEqual(len(wp.batches), 1)
        self.assertEqual(sorted(wp.batches[0].task_ids), ["a", "b"])
        self.assertTrue(wp.parallelizable)

    def test_file_overlap_serialises(self):
        wp = plan_waves([T("a", ["src/shared.py"]), T("b", ["src/shared.py"])])
        self.assertEqual(len(wp.batches), 2)
        self.assertFalse(wp.parallelizable)

    def test_dependency_serialises(self):
        wp = plan_waves([T("a", ["src/a.py"]), T("b", ["src/b.py"], deps=["a"])])
        self.assertEqual([b.task_ids for b in wp.batches], [["a"], ["b"]])

    def test_layered_mix(self):
        # a,b parallel -> then c (needs both, own file) alongside d (own file)
        wp = plan_waves([
            T("a", ["src/a.py"]),
            T("b", ["src/b.py"]),
            T("c", ["src/c.py"], deps=["a", "b"]),
            T("d", ["docs/x.md"], deps=["a", "b"]),
        ])
        self.assertEqual(sorted(wp.batches[0].task_ids), ["a", "b"])
        self.assertEqual(sorted(wp.batches[1].task_ids), ["c", "d"])

    def test_cycle_detected(self):
        with self.assertRaises(HydraError):
            plan_waves([T("a", deps=["b"]), T("b", deps=["a"])])

    def test_no_declared_files_are_kept_apart(self):
        # independence is unprovable without a declared touch-set -> serialise
        wp = plan_waves([T("a"), T("b")])
        self.assertEqual(len(wp.batches), 2)
        self.assertFalse(wp.parallelizable)
        # one side undeclared is still unprovable
        wp2 = plan_waves([T("a", ["x.py"]), T("b")])
        self.assertEqual(len(wp2.batches), 2)


if __name__ == "__main__":
    unittest.main()
