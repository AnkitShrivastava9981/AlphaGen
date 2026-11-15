"""Shared helpers: paths, HTTP session, retries, dates and the run-status tracker."""
import datetime as dt
import json
import logging
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("alphagen")


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def today_ist() -> dt.date:
    return now_ist().date()


def ensure(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"})
    return s


def get_with_retry(session, url, tries=3, timeout=30, **kw):
    """GET with retries. Returns the response, None on 404 (e.g. market holiday), raises otherwise."""
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=timeout, **kw)
            if r.status_code == 200 and r.content:
                return r
            if r.status_code == 404:
                return None
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url} -> {last}")


def recent_weekdays(n_days=8, end=None):
    end = end or today_ist()
    days = [end - dt.timedelta(days=k) for k in range(n_days)]
    return sorted(d for d in days if d.weekday() < 5)


def first_week_of_month() -> bool:
    """Used to trigger a full monthly refresh (catches splits/bonuses that rewrite history)."""
    return today_ist().day <= 7


class Status:
    def __init__(self):
        self.started = now_ist()
        self.steps = {}

    def record(self, name, ok, rows=0, note=""):
        self.steps[name] = {"ok": bool(ok), "rows": int(rows or 0), "note": str(note)[:300]}
        log.info("STEP %s ok=%s rows=%s %s", name, ok, rows, note)

    def write(self):
        finished = now_ist()
        payload = {
            "started_ist": self.started.isoformat(timespec="seconds"),
            "finished_ist": finished.isoformat(timespec="seconds"),
            "steps": self.steps,
        }
        ensure(DATA / "_status.json").write_text(json.dumps(payload, indent=2))
        lines = [
            "# Data collection status",
            "",
            f"Last run: {finished:%a %d %b %Y, %H:%M} IST",
            "",
            "| Step | Result | Rows | Note |",
            "|---|---|---|---|",
        ]
        for name, s in self.steps.items():
            mark = "OK" if s["ok"] else "FAILED"
            lines.append(f"| {name} | {mark} | {s['rows']:,} | {s['note']} |")
        ensure(DATA / "STATUS.md").write_text("\n".join(lines) + "\n")
