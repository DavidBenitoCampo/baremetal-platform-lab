#!/usr/bin/env python3
"""Send short sequential requests and print one JSON evidence record per request."""

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen2.5:0.5b")
    parser.add_argument("--count", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--timeout", type=float, default=180,
                        help="Socket timeout in seconds, not a wall-clock deadline")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    def call(path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            args.url.rstrip("/") + path, data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            return response.status, json.load(response)

    prompt = "Explain a Kubernetes readiness probe in one short sentence."
    payload = {
        "model": args.model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "num_ctx": 2048, "num_predict": 64,
            "num_thread": 2, "num_gpu": 0, "temperature": 0, "seed": 7,
        },
    }
    for sample in range(1, args.count + 1):
        record = {
            "sample": sample,
            "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "model": args.model,
            "prompt": prompt,
            "options": payload["options"],
            "keep_alive": payload["keep_alive"],
            "stream": False,
            "socket_timeout_seconds": args.timeout,
        }
        started = None
        try:
            _, version = call("/api/version")
            _, tags = call("/api/tags")
            _, running = call("/api/ps")
            named_model = next((model for model in tags.get("models", [])
                                if model.get("name") == args.model), {})
            record["server_version"] = version.get("version")
            record["model_digest"] = named_model.get("digest")
            record["loaded_before"] = any(
                model.get("name") == args.model
                for model in running.get("models", [])
            )
            started = time.monotonic()
            status, body = call("/api/generate", payload)
            record["wall_seconds"] = round(time.monotonic() - started, 4)
            record["http_status"] = status
            if body.get("error"):
                raise ValueError(body["error"])
            if body.get("done") is not True or not body.get("response", "").strip():
                raise ValueError("No completed, non-empty response")
            generation_ns = body.get("eval_duration", 0)
            tokens = body.get("eval_count", 0)
            record.update({
                "ok": True,
                "response": body["response"],
                "done_reason": body.get("done_reason"),
                "generated_tokens": tokens,
                "generation_seconds": generation_ns / 1e9,
                "generation_tokens_per_second": (
                    round(tokens * 1e9 / generation_ns, 3)
                    if generation_ns > 0 else None
                ),
                "load_seconds": body.get("load_duration", 0) / 1e9,
                "server_total_seconds": body.get("total_duration", 0) / 1e9,
            })
        except urllib.error.HTTPError as error:
            record.update(ok=False, http_status=error.code,
                          error=error.read(1024).decode("utf-8", errors="replace"))
        except (OSError, ValueError, TypeError, AttributeError) as error:
            record.update(ok=False, error=str(error))
        if not record.get("ok") and started is not None:
            record["wall_seconds"] = round(time.monotonic() - started, 4)
        print(json.dumps(record), flush=True)
        if not record.get("ok"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
