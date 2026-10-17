"""Exercise Pi helpers with fake command-line tools and isolated config files."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FAKE_TOOL = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["ACCESS_CALLS"], "a") as log:
    log.write(json.dumps({"tool": name, "args": args}) + "\n")
if name == "systemctl":
    sys.exit(3 if os.environ.get("ACCESS_SERVICE") == "inactive" else 0)
if name == "curl":
    if os.environ.get("ACCESS_HTTP_ERROR"):
        sys.exit(7)
    print(os.environ.get("ACCESS_HTTP_STATUS", "200"), end="")
elif name == "kubectl":
    if "config" in args:
        config = args[args.index("--kubeconfig") + 1]
        print(json.loads(Path(config).read_text())["clusters"][0]["cluster"]["server"], end="")
    elif "get" in args and "--raw=/readyz" in args:
        sys.exit(1 if os.environ.get("ACCESS_API_ERROR") else 0)
    elif "node" in args:
        print(os.environ.get("ACCESS_NODE_READY", "True"), end="")
'''


class WorkstationAccessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for tool in ("systemctl", "kubectl", "flux", "curl"):
            path = self.bin / tool
            path.write_text(FAKE_TOOL)
            path.chmod(0o755)
        self.config = self.root / "pi-vpn.yaml"
        self.write_config("https://127.0.0.1:16443")
        self.calls_file = self.root / "calls.jsonl"
        self.env = os.environ.copy()
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + self.env["PATH"],
            "PI_LAB_KUBECONFIG": str(self.config),
            "KUBECONFIG": str(self.root / "wrong-default.yaml"),
            "ACCESS_CALLS": str(self.calls_file),
        })

    def write_config(self, server):
        self.config.write_text(json.dumps({"clusters": [{"cluster": {"server": server}}]}))

    def run_helper(self, helper, *args):
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / helper), *args],
            env=self.env, capture_output=True, text=True, timeout=5,
        )

    def calls(self):
        if not self.calls_file.exists():
            return []
        return [json.loads(line) for line in self.calls_file.read_text().splitlines()]

    def test_pi_commands_override_a_different_terminal_kubeconfig(self):
        for helper, tool in (("pi-kubectl.sh", "kubectl"), ("pi-flux.sh", "flux")):
            with self.subTest(helper=helper):
                result = self.run_helper(helper, "get", "nodes")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.calls()[-1], {
                    "tool": tool,
                    "args": ["--kubeconfig", str(self.config), "get", "nodes"],
                })

    def test_missing_config_stops_before_invoking_kubernetes(self):
        self.config.unlink()
        result = self.run_helper("pi-kubectl.sh", "get", "nodes")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing or unreadable", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_success_requires_api_node_and_http_checks(self):
        result = self.run_helper("pi-lab-check.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Access checks passed", result.stdout)
        request = next(call["args"] for call in self.calls() if call["tool"] == "curl")
        self.assertEqual(request[request.index("--noproxy") + 1], "127.0.0.1")
        self.assertEqual(request[request.index("--header") + 1], "Host: podinfo.lab.test")

    def test_wrong_api_endpoint_is_rejected_before_network_checks(self):
        self.write_config("https://0.0.0.0:38217")
        result = self.run_helper("pi-lab-check.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected Pi API endpoint", result.stderr)
        self.assertFalse(any("get" in call["args"] for call in self.calls()))
        self.assertFalse(any(call["tool"] == "curl" for call in self.calls()))

    def test_inactive_tunnel_stops_before_network_checks(self):
        self.env["ACCESS_SERVICE"] = "inactive"
        result = self.run_helper("pi-lab-check.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("journalctl", result.stderr)
        self.assertEqual([call["tool"] for call in self.calls()], ["systemctl"])

    def test_unreachable_api_stops_before_http_check(self):
        self.env["ACCESS_API_ERROR"] = "1"
        result = self.run_helper("pi-lab-check.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Pi API readiness check failed", result.stderr)
        self.assertFalse(any(call["tool"] == "curl" for call in self.calls()))

    def test_unready_node_fails_the_check(self):
        self.env["ACCESS_NODE_READY"] = "False"
        result = self.run_helper("pi-lab-check.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Node pi-lab is not Ready", result.stderr)

    def test_http_transport_error_is_not_a_success(self):
        self.env["ACCESS_HTTP_ERROR"] = "1"
        result = self.run_helper("pi-lab-check.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Podinfo HTTP check failed", result.stderr)
        self.assertNotIn("Access checks passed", result.stdout)

    def test_http_redirect_is_not_a_success(self):
        self.env["ACCESS_HTTP_STATUS"] = "302"
        result = self.run_helper("pi-lab-check.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("HTTP 302 instead of 200", result.stderr)


if __name__ == "__main__":
    unittest.main()
