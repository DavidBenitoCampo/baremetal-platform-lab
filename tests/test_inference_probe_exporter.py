"""Exercise the probe against a local fake Ollama HTTP server."""

import json
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROBE_DIRECTORY = Path(__file__).resolve().parents[1] / "kubernetes/ai/inference-probe"
sys.path.insert(0, str(PROBE_DIRECTORY))
import probe


class FakeOllama(BaseHTTPRequestHandler):
    def do_POST(self):
        self.server.requests.append(json.loads(
            self.rfile.read(int(self.headers["Content-Length"]))
        ))
        mode = self.server.mode
        if mode == "bad_http":
            self.connection.sendall(b"NOT HTTP\r\n\r\n")
            self.close_connection = True
            return
        status = 404 if mode == "missing" else 200
        if mode == "slow":
            self.server.request_started.set()
            self.server.release.wait(2)
        if mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "/redirected")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        data = json.dumps({"done": True, "response": "ready", "eval_count": 2}).encode()
        if mode == "missing":
            data = b'{"error":"model not found"}'
        elif mode == "invalid_json":
            data = b"not JSON"
        elif mode == "incomplete":
            data = b'{"done":false,"response":"ready"}'
        elif mode == "empty":
            data = b'{"done":true,"response":" "}'
        elif mode == "oversized":
            data = b"x" * (probe.MAX_RESPONSE_BYTES + 1)
        elif mode == "invalid_tokens":
            data = b'{"done":true,"response":"ready","eval_count":-1}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.ollama = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        self.ollama.mode = "success"
        self.ollama.requests = []
        self.ollama.request_started = threading.Event()
        self.ollama.release = threading.Event()
        self.ollama_thread = threading.Thread(
            target=self.ollama.serve_forever, daemon=True,
        )
        self.ollama_thread.start()
        self.url = f"http://127.0.0.1:{self.ollama.server_port}"
        self.addCleanup(self.close_ollama)

    def close_ollama(self):
        self.ollama.release.set()
        self.ollama.shutdown()
        self.ollama.server_close()
        self.ollama_thread.join(2)

    def test_success_sends_bounded_non_streaming_request(self):
        result = probe.check_model(self.url, "test-model", 1)
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["generated_tokens"], 2)
        sent = self.ollama.requests[0]
        self.assertEqual(sent["model"], "test-model")
        self.assertFalse(sent["stream"])
        self.assertEqual(sent["options"]["num_predict"], 16)
        self.assertEqual(sent["options"]["num_gpu"], 0)

    def test_missing_model_records_404(self):
        self.ollama.mode = "missing"
        result = probe.check_model(self.url, "not-installed", 1)
        self.assertEqual(result["result"], "http_error")
        self.assertEqual(result["http_status"], 404)
        self.assertEqual(result["generated_tokens"], 0)

    def test_socket_timeout_is_distinct_from_transport_failure(self):
        self.ollama.mode = "slow"
        result = probe.check_model(self.url, "test-model", 0.05)
        self.assertEqual(result["result"], "timeout")
        self.assertEqual(result["http_status"], 0)
        self.assertGreaterEqual(result["duration_seconds"], 0.04)

    def test_closed_port_is_a_transport_failure(self):
        self.ollama.shutdown()
        self.ollama.server_close()
        result = probe.check_model(self.url, "test-model", 1)
        self.assertEqual(result["result"], "transport_error")
        self.assertEqual(result["http_status"], 0)

    def test_redirect_does_not_turn_model_request_into_another_request(self):
        self.ollama.mode = "redirect"
        result = probe.check_model(self.url, "test-model", 1)
        self.assertEqual(result["result"], "http_error")
        self.assertEqual(result["http_status"], 302)
        self.assertEqual(len(self.ollama.requests), 1)

    def test_malformed_http_is_recorded_instead_of_stopping_worker(self):
        self.ollama.mode = "bad_http"
        result = probe.check_model(self.url, "test-model", 1)
        self.assertEqual(result["result"], "transport_error")
        self.assertEqual(result["http_status"], 0)

    def test_bad_bodies_never_report_a_successful_model_check(self):
        for mode in ("invalid_json", "incomplete", "empty", "oversized", "invalid_tokens"):
            with self.subTest(mode=mode):
                self.ollama.mode = mode
                result = probe.check_model(self.url, "test-model", 1)
                self.assertEqual(result["result"], "invalid_response")
                self.assertEqual(result["http_status"], 200)
                self.assertEqual(result["generated_tokens"], 0)

    def test_recovery_updates_last_result_and_preserves_failure_count(self):
        metrics = probe.Metrics()
        self.ollama.mode = "missing"
        metrics.record(probe.check_model(self.url, "test-model", 1))
        self.assertIn(b"ollama_probe_success 0\n", metrics.render())
        self.ollama.mode = "success"
        metrics.record(probe.check_model(self.url, "test-model", 1))
        text = metrics.render().decode()
        self.assertIn("ollama_probe_success 1\n", text)
        self.assertIn('ollama_probe_requests_total{result="http_error"} 1\n', text)
        self.assertIn('ollama_probe_requests_total{result="success"} 1\n', text)
        self.assertIn("ollama_probe_generated_tokens_total 2\n", text)
        self.assertIn('ollama_probe_request_duration_seconds_bucket{le="+Inf"} 2\n', text)

    def test_initial_state_is_unknown_and_all_result_counters_exist(self):
        text = probe.Metrics().render().decode()
        self.assertIn("ollama_probe_success -1\n", text)
        self.assertIn("ollama_probe_last_check_timestamp_seconds 0.0\n", text)
        for result in probe.RESULTS:
            self.assertIn(f'ollama_probe_requests_total{{result="{result}"}} 0\n', text)

    def test_metrics_and_health_remain_responsive_during_a_slow_request(self):
        metrics, stop = probe.Metrics(), threading.Event()
        self.ollama.mode = "slow"
        worker = threading.Thread(target=probe.run_checks, args=(
            stop, metrics, self.url, "test-model", 1, 60,
        ), daemon=True)
        server = probe.make_server("127.0.0.1", 0, metrics, worker)
        http_thread = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        http_thread.start()
        try:
            self.assertTrue(self.ollama.request_started.wait(1))
            for endpoint in ("/metrics", "/-/ready", "/-/healthy"):
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}{endpoint}", timeout=0.5,
                ) as response:
                    self.assertEqual(response.status, 200)
            self.ollama.release.set()
            deadline = time.monotonic() + 2
            while metrics.last_check == 0 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertGreater(metrics.last_check, 0)
        finally:
            stop.set()
            self.ollama.release.set()
            worker.join(2)
            server.shutdown()
            server.server_close()
            http_thread.join(2)

    def test_failed_model_check_keeps_exporter_ready(self):
        metrics, stop = probe.Metrics(), threading.Event()
        self.ollama.mode = "missing"
        metrics.record(probe.check_model(self.url, "test-model", 1))
        worker = threading.Thread(target=stop.wait, daemon=True)
        worker.start()
        server = probe.make_server("127.0.0.1", 0, metrics, worker)
        http_thread = threading.Thread(target=server.serve_forever, daemon=True)
        http_thread.start()
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/-/ready", timeout=1,
            ) as response:
                self.assertEqual(response.status, 200)
            with urllib.request.urlopen(
                f"http://127.0.0.1:{server.server_port}/metrics", timeout=1,
            ) as response:
                self.assertIn(b"ollama_probe_success 0\n", response.read())
            stop.set()
            worker.join(1)
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{server.server_port}/-/healthy", timeout=1,
                )
            self.assertEqual(error.exception.code, 503)
        finally:
            stop.set()
            worker.join(1)
            server.shutdown()
            server.server_close()
            http_thread.join(2)

    def test_invalid_configuration_exits_before_starting_checks(self):
        for args in (
            ["--timeout", "nan"], ["--timeout", "60"], ["--interval", "inf"],
            ["--model", ""], ["--ollama-url", "http://user:password@example.test"],
        ):
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, str(PROBE_DIRECTORY / "probe.py"), *args],
                    capture_output=True, timeout=3,
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
