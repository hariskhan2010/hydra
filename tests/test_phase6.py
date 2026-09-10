import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from _gitrepo import make_repo

from hydra.config import load_config
from hydra.drivers import ClaudeDriver, GenericDriver
from hydra.errors import HydraError
from hydra.policy import Policy, check_declared
from hydra.routing import Routing
from hydra.tasks import Task

HYDRA = Path(__file__).resolve().parent.parent


class PolicyTest(unittest.TestCase):
    def test_allowed_and_forbidden(self):
        pol = Policy(allowed_paths=["src/**", "tests/**"],
                     forbidden_paths=["src/secrets/**"], max_files_per_task=2)
        ok = Task(id="a", title="a", prompt="p", files=("src/a.py", "tests/a.py"))
        self.assertEqual(check_declared([ok], pol), [])

        outside = Task(id="b", title="b", prompt="p", files=("infra/x.tf",))
        self.assertTrue(check_declared([outside], pol))

        forbidden = Task(id="c", title="c", prompt="p", files=("src/secrets/k.py",))
        self.assertTrue(any("forbidden" in v for v in check_declared([forbidden], pol)))

        toomany = Task(id="d", title="d", prompt="p",
                       files=("src/a.py", "src/b.py", "src/c.py"))
        self.assertTrue(any("max_files_per_task" in v for v in check_declared([toomany], pol)))

    def test_inactive_policy_passes_everything(self):
        self.assertEqual(check_declared([Task(id="x", title="x", prompt="p",
                                              files=("anything/goes.py",))], Policy()), [])


class RoutingTest(unittest.TestCase):
    def test_model_for_role_then_default(self):
        r = Routing(table={"default": "big", "docs": "small"})
        self.assertEqual(r.model_for(Task(id="a", title="a", prompt="p", role="docs")), "small")
        self.assertEqual(r.model_for(Task(id="b", title="b", prompt="p", role="coder")), "big")
        self.assertEqual(r.model_for(Task(id="c", title="c", prompt="p")), "big")

    def test_driver_model_flag(self):
        argv = ClaudeDriver().argv(model="claude-haiku-4-5")
        if argv:
            self.assertIn("--model", argv)
            self.assertIn("claude-haiku-4-5", argv)

    def test_generic_model_substitution(self):
        d = GenericDriver(template=["cli", "--model", "{model}"])
        self.assertEqual(d.argv(model="m")[-1], "m")


class ConfigPhase6Test(unittest.TestCase):
    def test_loads_policy_and_routing(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "hydra.toml").write_text(textwrap.dedent("""
                [policy]
                allowed_paths = ["src/**"]
                max_files_per_task = 5
                [routing]
                default = "sonnet"
                docs = "haiku"
            """), encoding="utf-8")
            c = load_config(tmp)
            self.assertEqual(c.policy.allowed_paths, ["src/**"])
            self.assertEqual(c.policy.max_files_per_task, 5)
            self.assertEqual(c.routing.table["docs"], "haiku")


class McpServerTest(unittest.TestCase):
    def _rpc(self, repo, *messages):
        proc = subprocess.run(
            [sys.executable, "-m", "hydra.cli", "serve", "--repo", repo],
            input="\n".join(json.dumps(m) for m in messages),
            capture_output=True, text=True, cwd=HYDRA, timeout=60)
        return [json.loads(ln) for ln in proc.stdout.splitlines() if ln.strip()]

    def test_initialize_and_tools_list(self):
        with TemporaryDirectory() as tmp:
            out = self._rpc(
                tmp,
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )
            self.assertEqual(out[0]["result"]["serverInfo"]["name"], "hydra")
            names = {t["name"] for t in out[1]["result"]["tools"]}
            self.assertIn("hydra_run", names)
            self.assertIn("hydra_plan", names)

    def test_tools_call_doctor(self):
        with TemporaryDirectory() as tmp:
            out = self._rpc(tmp, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                  "params": {"name": "hydra_doctor", "arguments": {}}})
            self.assertIn("MAX AGENTS", out[0]["result"]["content"][0]["text"])

    def test_unknown_method_returns_error(self):
        with TemporaryDirectory() as tmp:
            out = self._rpc(tmp, {"jsonrpc": "2.0", "id": 9, "method": "bogus/thing"})
            self.assertIn("error", out[0])


if __name__ == "__main__":
    unittest.main()
