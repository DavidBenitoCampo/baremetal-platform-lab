#!/usr/bin/env python3
"""Run scheduled Ollama requests and expose their results to Prometheus."""

import argparse
import collections
import datetime
import http.client
import json
import math
import os
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


RESULTS = ("success", "http_error", "timeout", "transport_error", "invalid_response")
BUCKETS = (0.25, 0.5, 1, 2, 4, 8, 15, 30, 60)
MAX_RESPONSE_BYTES = 65536


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


def check_model(url, model, timeout):
    """Measure one non-streaming request, including failures."""
    started = time.monotonic()
    result = {"result": "invalid_response", "http_status": 0, "generated_tokens": 0}
    payload = {
        "model": model,
        "prompt": "Reply with the word ready.",
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "num_ctx": 2048, "num_predict": 16, "num_thread": 2,
            "num_gpu": 0, "temperature": 0, "seed": 7,
        },
    }
    request = urllib.request.Request(
        url.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    # Internal cluster requests should not use a workstation or proxy setting.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            result["http_status"] = response.status
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("Response exceeds 64 KiB")
        body = json.loads(raw)
        if (
            not isinstance(body, dict)
            or body.get("done") is not True
            or not isinstance(body.get("response"), str)
            or not body["response"].strip()
            or body.get("error")
        ):
            raise ValueError("No completed, non-empty response")
        tokens = body.get("eval_count", 0)
        if type(tokens) is not int or tokens < 0:
            raise ValueError("Invalid generated-token count")
        if result["http_status"] != 200:
            result.update(result="http_error", error=f'HTTP {result["http_status"]}')
        else:
            result.update(result="success", generated_tokens=tokens)
    except urllib.error.HTTPError as error:
        result.update(result="http_error", http_status=error.code,
                      error=f"HTTP {error.code}")
        error.close()
    except urllib.error.URLError as error:
        kind = "timeout" if isinstance(error.reason, TimeoutError) else "transport_error"
        result.update(result=kind, error=str(error.reason)[:256])
    except TimeoutError:
        result.update(result="timeout", error="Socket timeout")
    except OSError as error:
        result.update(result="transport_error", error=str(error)[:256])
    except http.client.HTTPException as error:
        result.update(result="transport_error", error=str(error)[:256])
    except (ValueError, TypeError) as error:
        result.update(result="invalid_response", error=str(error)[:256])
    result["duration_seconds"] = time.monotonic() - started
    return result


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.started = time.time()
        self.last_check = 0.0
        self.success = -1
        self.duration = 0.0
        self.http_status = 0
        self.counts = collections.Counter({name: 0 for name in RESULTS})
        self.generated_tokens = 0
        self.buckets = {boundary: 0 for boundary in BUCKETS}
        self.duration_sum = 0.0

    def record(self, result):
        with self.lock:
            self.last_check = time.time()
            self.success = int(result["result"] == "success")
            self.duration = result["duration_seconds"]
            self.http_status = result["http_status"]
            self.counts[result["result"]] += 1
            self.generated_tokens += result["generated_tokens"]
            self.duration_sum += self.duration
            for boundary in BUCKETS:
                if self.duration <= boundary:
                    self.buckets[boundary] += 1

    def render(self):
        with self.lock:
            lines = []

            def scalar(name, kind, description, value):
                lines.extend((f"# HELP {name} {description}", f"# TYPE {name} {kind}",
                              f"{name} {value}"))

            scalar("ollama_probe_success", "gauge",
                   "Last check: 1 success, 0 failure, -1 no completed check.", self.success)
            scalar("ollama_probe_last_check_timestamp_seconds", "gauge",
                   "Unix time of the last completed check, or 0 before the first.",
                   self.last_check)
            scalar("ollama_probe_started_timestamp_seconds", "gauge",
                   "Unix time when this probe process started.", self.started)
            scalar("ollama_probe_duration_seconds", "gauge",
                   "Duration of the last completed check, including failed checks.",
                   self.duration)
            scalar("ollama_probe_http_status", "gauge",
                   "HTTP status of the last check, or 0 without an HTTP response.",
                   self.http_status)
            scalar("ollama_probe_generated_tokens_total", "counter",
                   "Tokens generated by successful scheduled checks.", self.generated_tokens)
            lines.extend((
                "# HELP ollama_probe_requests_total Completed scheduled checks by result.",
                "# TYPE ollama_probe_requests_total counter",
            ))
            for name in RESULTS:
                lines.append(f'ollama_probe_requests_total{{result="{name}"}} {self.counts[name]}')
            lines.extend((
                "# HELP ollama_probe_request_duration_seconds Duration of completed checks.",
                "# TYPE ollama_probe_request_duration_seconds histogram",
            ))
            for boundary in BUCKETS:
                lines.append(
                    f'ollama_probe_request_duration_seconds_bucket{{le="{boundary:g}"}} '
                    f"{self.buckets[boundary]}"
                )
            count = sum(self.counts.values())
            lines.extend((
                f'ollama_probe_request_duration_seconds_bucket{{le="+Inf"}} {count}',
                f"ollama_probe_request_duration_seconds_sum {self.duration_sum}",
                f"ollama_probe_request_duration_seconds_count {count}",
            ))
            return ("\n".join(lines) + "\n").encode("utf-8")


def make_server(address, port, metrics, worker):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def do_GET(self):
            if self.path == "/metrics":
                status, body = 200, metrics.render()
                content_type = "text/plain; version=0.0.4; charset=utf-8"
            elif self.path in ("/-/healthy", "/-/ready"):
                # A failed model check must leave the metrics endpoint available.
                status = 200 if worker.is_alive() else 503
                body = b"Probe worker is running.\n" if status == 200 else b"Worker stopped.\n"
                content_type = "text/plain; charset=utf-8"
            else:
                status, body = 404, b"Not found.\n"
                content_type = "text/plain; charset=utf-8"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((address, port), Handler)


def run_checks(stop, metrics, url, model, timeout, interval):
    while not stop.is_set():
        result = check_model(url, model, timeout)
        metrics.record(result)
        print(json.dumps({
            "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "model": model, **result,
        }), flush=True)
        stop.wait(max(0, interval - result["duration_seconds"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ollama-url", default=os.environ.get(
        "OLLAMA_URL", "http://ollama.ai-lab.svc.cluster.local:11434"))
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b"))
    parser.add_argument("--interval", type=float,
                        default=os.environ.get("PROBE_INTERVAL_SECONDS", "60"))
    parser.add_argument("--timeout", type=float,
                        default=os.environ.get("PROBE_TIMEOUT_SECONDS", "15"),
                        help="Socket timeout, not an overall server-processing deadline")
    parser.add_argument("--listen-address", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9189)
    args = parser.parse_args()
    parsed_url = urllib.parse.urlsplit(args.ollama_url)
    if (parsed_url.scheme not in ("http", "https") or not parsed_url.hostname
            or parsed_url.username or parsed_url.password or parsed_url.query
            or parsed_url.fragment):
        parser.error("--ollama-url must be an HTTP(S) base URL without credentials")
    if not args.model.strip():
        parser.error("--model must not be empty")
    if not math.isfinite(args.interval) or args.interval < 5:
        parser.error("--interval must be finite and at least five seconds")
    if not math.isfinite(args.timeout) or not 0 < args.timeout < args.interval:
        parser.error("--timeout must be finite, positive, and below --interval")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    stop, metrics = threading.Event(), Metrics()
    worker = threading.Thread(target=run_checks, args=(
        stop, metrics, args.ollama_url, args.model, args.timeout, args.interval,
    ), daemon=True)
    server = make_server(args.listen_address, args.port, metrics, worker)
    http_thread = threading.Thread(target=server.serve_forever, daemon=True)
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    worker.start()
    http_thread.start()
    try:
        stop.wait()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=args.timeout + 1)


if __name__ == "__main__":
    main()
