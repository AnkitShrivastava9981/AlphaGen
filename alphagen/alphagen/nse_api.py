"""Browser-like access to nseindia.com JSON APIs.

NSE sits behind Akamai, which rejects plain Python TLS fingerprints on many /api/ routes
(that is why the old bulk-deals call failed). curl_cffi impersonates Chrome's TLS handshake;
if it is not installed we fall back to requests. Every call re-warms cookies once on 401/403.
"""
import time

from .common import UA, http_session, log

BASE = "https://www.nseindia.com"
API_HEADERS = {"Accept": "application/json, text/plain, */*", "Referer": BASE + "/"}


class NseApi:
    def __init__(self, pause=0.35):
        self.pause = pause
        self.calls = 0
        self._new_session()

    def _new_session(self):
        try:
            from curl_cffi import requests as creq  # type: ignore
            self.s = creq.Session(impersonate="chrome")
            self.kind = "curl_cffi"
        except Exception:
            self.s = http_session()
            self.kind = "requests"
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        for url in (BASE, BASE + "/option-chain"):
            try:
                self.s.get(url, timeout=20)
            except Exception:
                pass

    def json(self, path_or_url, tries=3, referer=None):
        url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
        headers = dict(API_HEADERS)
        if referer:
            headers["Referer"] = referer
        last = ""
        for i in range(tries):
            time.sleep(self.pause)
            self.calls += 1
            try:
                r = self.s.get(url, headers=headers, timeout=30)
                if r.status_code == 200:
                    try:
                        return r.json()
                    except ValueError:
                        last = f"non-JSON body ({len(r.text)} chars)"
                elif r.status_code == 404:
                    return None
                else:
                    last = f"HTTP {r.status_code}"
                if r.status_code in (401, 403, 429, 503) or last.startswith("non-JSON"):
                    time.sleep(2 * (i + 1))
                    self._new_session()
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
                time.sleep(2 * (i + 1))
        raise RuntimeError(f"{url} -> {last} [{self.kind}]")

    def raw(self, url, tries=3):
        """Download a file (e.g. an XBRL document on nsearchives)."""
        last = ""
        for i in range(tries):
            time.sleep(self.pause)
            self.calls += 1
            try:
                r = self.s.get(url, timeout=40)
                if r.status_code == 200 and r.content:
                    return r.content
                if r.status_code == 404:
                    return None
                last = f"HTTP {r.status_code}"
            except Exception as e:
                last = f"{type(e).__name__}: {e}"
            time.sleep(2 * (i + 1))
        log.warning("raw download failed %s: %s", url, last)
        return None
