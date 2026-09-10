"""The hardware governor must never propose more agents than the machine can
bear, and `--max-agents` must only ever lower the ceiling.
"""
import unittest

from hydra import governor


class GovernorTest(unittest.TestCase):
    def test_ceiling_is_at_least_one(self):
        b = governor.compute()
        self.assertGreaterEqual(b.max_agents, 1)

    def test_ceiling_never_exceeds_cores_minus_one_floor_one(self):
        b = governor.compute()
        self.assertLessEqual(b.max_agents, max(1, b.cores - 1))

    def test_configured_max_can_only_lower(self):
        base = governor.compute().max_agents
        lowered = governor.compute(configured_max=1).max_agents
        self.assertEqual(lowered, 1)
        raised = governor.compute(configured_max=999).max_agents
        self.assertEqual(raised, base, "a huge configured max must not raise the ceiling")

    def test_configured_max_below_one_is_clamped(self):
        self.assertGreaterEqual(governor.compute(configured_max=0).max_agents, 1)

    def test_reason_is_populated(self):
        self.assertIn("min(", governor.compute().reason)


if __name__ == "__main__":
    unittest.main()
