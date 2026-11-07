#!/usr/bin/env python3
"""Fresnel probe: check every service, write site/status.json.

The browser cannot do this honestly — a cross-origin fetch without CORS on the
target tells you nothing. So the checking happens here, where it can actually
open a socket, and the page just reads the result.

    python3 tools/probe.py                 # one pass, writes site/status.json
    python3 tools/probe.py --interval 60   # loop forever, every 60s
    python3 tools/probe.py --timeout 4

Exit codes: 0 if every service answered, 1 if any did not.
"""

from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "site" / "services.json"
OUT = ROOT / "site" / "status.json"

UA = "fresnel-probe/1.0"


def check(url: str, timeout: float) -> dict:
    """A service is 'up' if it answers at all — any HTTP status counts.

    A 401 or a 404 is a live server. Only a connection failure, a DNS failure
    or a timeout means it is down, which is what people actually want to know.
    """
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # homelab certificates are usually self-signed
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            code = response.status
        state = "up"
        detail = f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        state, detail = "up", f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        state, detail = "down", str(exc.reason)[:80]
    except Exception as exc:  # noqa: BLE001 - a probe should never crash the pass
        state, detail = "down", type(exc).__name__

    return {
        "state": state,
        "ms": int((time.monotonic() - started) * 1000),
        "detail": detail,
    }


def one_pass(timeout: float, workers: int) -> int:
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    services = [s for c in data["categories"] for s in c["services"]]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda s: (s["name"], check(s["url"], timeout)), services))

    payload = {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "services": {name: result for name, result in results},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    down = [n for n, r in results if r["state"] != "up"]
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] probed {len(results)} services, {len(down)} down"
          + (f": {', '.join(down)}" if down else ""))
    return 0 if not down else 1


def main() -> int:
    args = sys.argv[1:]
    timeout = 4.0
    interval = None
    if "--timeout" in args:
        timeout = float(args[args.index("--timeout") + 1])
    if "--interval" in args:
        interval = float(args[args.index("--interval") + 1])

    if interval is None:
        return one_pass(timeout, workers=16)

    while True:
        one_pass(timeout, workers=16)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
