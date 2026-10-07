#!/usr/bin/env python3
"""Measure serial HTTP attempts. Uses only Python's standard library."""
import argparse
import datetime
import http.client
import json
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('url')
parser.add_argument('--host', default=None)
parser.add_argument('--count', type=int, default=600)
parser.add_argument('--interval', type=float, default=1.0)
parser.add_argument('--timeout', type=float, default=0.8)
args = parser.parse_args()
if args.count < 1 or args.interval <= 0 or not 0 < args.timeout < args.interval:
    parser.error('Use count >= 1 and 0 < timeout < interval.')

headers = {'Host': args.host} if args.host else {}
request = urllib.request.Request(args.url, headers=headers)
# No redirect handler: retain an unexpected 3xx status as a failed attempt.
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None
opener = urllib.request.build_opener(NoRedirect)
start = time.monotonic()
latencies, failures, status_counts = [], 0, {}
max_lateness = 0.0
for index in range(args.count):
    scheduled = start + index * args.interval
    time.sleep(max(0, scheduled - time.monotonic()))
    before = time.monotonic()
    lateness = max(0, before - scheduled)
    max_lateness = max(max_lateness, lateness)
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status, error = None, None
    try:
        with opener.open(request, timeout=args.timeout) as response:
            status = response.status
            response.read(65536)
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = exc.reason
        exc.close()
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        error = str(exc)
    elapsed = (time.monotonic() - before) * 1000
    ok = status is not None and 200 <= status < 300
    failures += int(not ok)
    latencies.append(elapsed)
    key = str(status) if status is not None else 'transport_error'
    status_counts[key] = status_counts.get(key, 0) + 1
    print(json.dumps({'type': 'sample', 'index': index, 'utc': timestamp,
                      'status': status, 'ok': ok, 'latency_ms': round(elapsed, 2),
                      'schedule_delay_ms': round(lateness * 1000, 2),
                      'error': error}), flush=True)

latencies.sort()
p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)]
print(json.dumps({'type': 'summary', 'url': args.url, 'host': args.host,
                  'attempts': args.count, 'failures': failures,
                  'status_counts': status_counts, 'interval_s': args.interval,
                  'timeout_s': args.timeout, 'elapsed_s': round(time.monotonic() - start, 2),
                  'p95_attempt_latency_ms': round(p95, 2),
                  'max_schedule_delay_ms': round(max_lateness * 1000, 2)}))
