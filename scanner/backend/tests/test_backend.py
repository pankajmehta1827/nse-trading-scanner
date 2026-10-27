import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(BACKEND, "..", ".."))
FIXTURE = os.path.join(REPO, ".claude", "skills", "nse-swing", "tests", "fixture.json")
sys.path.insert(0, BACKEND)

from fastapi.testclient import TestClient  # noqa: E402

import app as api  # noqa: E402
import tradingview as tv  # noqa: E402


def raw_payload(rows, columns):
    """Shape fixture rows like the live screener: {"data": [{"s", "d": [...]}]}."""
    data = []
    for r in rows:
        norm = {tv.norm_key(k): v for k, v in r.items()}
        data.append({"s": norm["symbol"], "d": [norm.get(tv.norm_key(c)) for c in columns]})
    return {"totalCount": len(data), "data": data}


REGIME_DOWN = {"NSE:CNX500": {"close": 21668, "SMA50": 22664, "SMA200": 22808, "RSI": 38.8},
               "NSE:NIFTY": {"close": 24000, "SMA50": 24500, "SMA200": 24400}}


class Base(unittest.TestCase):
    def setUp(self):
        api.CACHE._store.clear()
        self.client = TestClient(api.app)


class Live(Base):
    """TradingView calls mocked at the HTTP layer."""

    def setUp(self):
        super().setUp()
        with open(FIXTURE) as f:
            self.rows = json.load(f)["data"]
        self.calls = []

        def fake_post(url, body):
            self.calls.append(body)
            if "symbols" in body:   # regime request
                return {"data": [{"s": t, "d": [v.get(c) for c in tv.REGIME_COLUMNS]}
                                 for t, v in REGIME_DOWN.items()]}
            start = body["range"][0]
            return raw_payload(self.rows if start == 0 else [], body["columns"])

        patcher = mock.patch.object(tv, "_post", side_effect=fake_post)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("NSE_SCANNER_OFFLINE", None)

    def test_rows_from_scan_maps_columns(self):
        rows = tv.rows_from_scan({"data": [{"s": "NSE:X", "d": [1, 2]}]}, ["close", "SMA50"])
        self.assertEqual(rows, [{"close": 1, "sma50": 2, "symbol": "NSE:X"}])

    def test_scan_end_to_end(self):
        r = self.client.post("/api/scan", json={"min_score": 0})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["mode"], "live")
        self.assertEqual(body["passed_filters"], 3)
        self.assertEqual(body["picks"][0]["symbol"], "GOODCO")
        self.assertTrue(body["regime"]["risk_off"])
        self.assertEqual(body["cutoff"], 10)            # min_score 0 + 10 risk-off
        self.assertTrue(body["sectors"])

    def test_scan_request_shape(self):
        self.client.post("/api/scan", json={})
        scans = [c for c in self.calls if "range" in c]
        self.assertEqual([c["range"] for c in scans], [[0, 500], [500, 900]])
        self.assertEqual(scans[0]["filter"][0]["right"], "NSE")
        self.assertIn("indexes", scans[0]["columns"])

    def test_risk_mode_override(self):
        body = self.client.post("/api/scan", json={"min_score": 50, "risk_mode": "on"}).json()
        self.assertEqual(body["cutoff"], 50)

    def test_cache_reused_until_refresh(self):
        self.client.post("/api/scan", json={})
        n = len(self.calls)
        self.client.post("/api/scan", json={})
        self.assertEqual(len(self.calls), n)
        self.client.post("/api/scan", json={"refresh": True})
        self.assertGreater(len(self.calls), n)

    def test_user_limits_reach_the_plan(self):
        body = self.client.post("/api/scan", json={"min_score": 0, "max_loss": 5000, "capital": 1000000}).json()
        plan = body["picks"][0]["plan"]
        self.assertLessEqual(plan["loss_at_stop"], 5000)
        self.assertGreater(plan["shares"], 0)

    def test_top_limits_picks_but_counts_all(self):
        body = self.client.post("/api/scan", json={"min_score": 0, "top": 1}).json()
        self.assertEqual(len(body["picks"]), 1)
        self.assertEqual(body["total_picks"], 3)

    def test_bad_universe(self):
        self.assertEqual(self.client.post("/api/scan", json={"universe": "XYZ"}).status_code, 400)

    def test_bad_limits(self):
        self.assertEqual(self.client.post("/api/scan", json={"max_loss": -1}).status_code, 422)

    def test_tradingview_down_is_502(self):
        with mock.patch.object(tv, "_post", side_effect=tv.TradingViewError("boom")):
            r = self.client.post("/api/scan", json={})
        self.assertEqual(r.status_code, 502)

    def test_regime_endpoint(self):
        body = self.client.get("/api/regime").json()
        self.assertEqual(body["status"], "risk-off")


class Offline(Base):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(REGIME_DOWN, self.tmp)
        self.tmp.close()
        patcher = mock.patch.dict(os.environ, {"NSE_SCANNER_OFFLINE": FIXTURE,
                                               "NSE_SCANNER_OFFLINE_REGIME": self.tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(os.unlink, self.tmp.name)

    def test_offline_scan_needs_no_network(self):
        with mock.patch.object(tv, "_post", side_effect=AssertionError("network used")):
            body = self.client.post("/api/scan", json={"min_score": 0}).json()
        self.assertEqual(body["mode"], "offline")
        self.assertEqual(body["picks"][0]["symbol"], "GOODCO")
        self.assertEqual(body["regime"]["status"], "risk-off")

    def test_health_and_news(self):
        self.assertEqual(self.client.get("/api/health").json()["mode"], "offline")
        self.assertEqual(self.client.get("/api/news/GOODCO").json()["items"], [])
        self.assertEqual(self.client.get("/api/news/BAD;SYM").status_code, 400)

    def test_universes(self):
        ids = [u["id"] for u in self.client.get("/api/universes").json()]
        self.assertIn("CNX500", ids)


def http_error(code, retry_after=None):
    import email.message
    import urllib.error
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://scanner.tradingview.com/india/scan", code, "Too Many Requests", headers, None)


URL = "https://scanner.tradingview.com/india/scan"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RateLimits(Base):
    """TradingView answering 429 Too Many Requests, as seen from Render."""

    def setUp(self):
        super().setUp()
        os.environ.pop("NSE_SCANNER_OFFLINE", None)
        self.sleeps = []
        for target, attr in ((tv.time, "sleep"),):
            p = mock.patch.object(target, attr, side_effect=lambda s: self.sleeps.append(s))
            p.start()
            self.addCleanup(p.stop)
        with open(FIXTURE) as f:
            self.rows = json.load(f)["data"]

    def urlopen(self, outcomes):
        """Each call pops the next outcome: an exception to raise or a payload to return."""
        calls = []

        def fake(req, timeout=None):
            calls.append(json.loads(req.data))
            out = outcomes.pop(0) if outcomes else {"data": []}
            if isinstance(out, Exception):
                raise out
            return FakeResponse(out)
        p = mock.patch.object(tv.urllib.request, "urlopen", side_effect=fake)
        p.start()
        self.addCleanup(p.stop)
        return calls

    def test_retries_then_succeeds(self):
        payload = raw_payload(self.rows, tv.COLUMNS)
        calls = self.urlopen([http_error(429), http_error(429), payload])
        self.assertEqual(len(tv._post(tv.SCAN_URL.format(market="india"), {"range": [0, 1]})["data"]), len(self.rows))
        self.assertEqual(len(calls), 3)
        self.assertIn(2, self.sleeps)        # first back-off
        self.assertIn(5, self.sleeps)        # second back-off

    def test_honours_retry_after_but_caps_it(self):
        self.urlopen([http_error(429, retry_after=7), http_error(429, retry_after=999), {"data": []}])
        tv._post(URL, {})
        self.assertIn(7.0, self.sleeps)
        self.assertIn(float(tv.MAX_RETRY_WAIT), self.sleeps)
        self.assertNotIn(999.0, self.sleeps)

    def test_gives_up_with_rate_limited(self):
        calls = self.urlopen([http_error(429)] * 10)
        with self.assertRaises(tv.RateLimited):
            tv._post(URL, {})
        self.assertEqual(len(calls), len(tv.RETRY_WAITS) + 1)

    def test_other_http_errors_not_retried(self):
        calls = self.urlopen([http_error(403)] * 3)
        with self.assertRaises(tv.TradingViewError) as ctx:
            tv._post(URL, {})
        self.assertNotIsInstance(ctx.exception, tv.RateLimited)
        self.assertEqual(len(calls), 1)

    def test_scan_rate_limited_without_cache_is_friendly_503(self):
        self.urlopen([http_error(429)] * 40)
        r = self.client.post("/api/scan", json={"universe": "NIFTY"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("Wait a minute", r.json()["detail"])

    def test_scan_falls_back_to_last_good_data(self):
        outcomes = [raw_payload(self.rows, tv.COLUMNS), {"data": []}, {"data": []}]
        self.urlopen(outcomes)                       # page 1, page 2, regime
        ok = self.client.post("/api/scan", json={"min_score": 0}).json()
        self.assertIsNone(ok["stale_note"])
        outcomes.extend([http_error(429)] * 40)      # TradingView now refuses everything
        r = self.client.post("/api/scan", json={"min_score": 0, "refresh": True})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("last good scan", body["stale_note"])
        self.assertEqual(body["picks"][0]["symbol"], "GOODCO")

    def test_min_gap_between_requests(self):
        self.urlopen([{"data": []}, {"data": []}])
        tv._last_call[0] = 0.0
        tv._post(URL, {})
        tv._post(URL, {})
        self.assertTrue(any(0 < s <= tv.MIN_GAP for s in self.sleeps))


class Password(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ, {"NSE_SCANNER_PASSWORD": "s3cret", "NSE_SCANNER_OFFLINE": FIXTURE})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_open_without_password_env(self):
        with mock.patch.dict(os.environ, {"NSE_SCANNER_PASSWORD": ""}):
            self.assertEqual(self.client.get("/api/universes").status_code, 200)

    def test_blocks_without_credentials(self):
        r = self.client.get("/api/universes")
        self.assertEqual(r.status_code, 401)
        self.assertIn("Basic", r.headers["www-authenticate"])

    def test_wrong_password(self):
        self.assertEqual(self.client.get("/api/universes", auth=("me", "nope")).status_code, 401)

    def test_right_password_any_user(self):
        self.assertEqual(self.client.get("/api/universes", auth=("anyone", "s3cret")).status_code, 200)
        r = self.client.post("/api/scan", json={"min_score": 0}, auth=("me", "s3cret"))
        self.assertEqual(r.status_code, 200)

    def test_health_stays_open(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_garbage_header(self):
        r = self.client.get("/api/universes", headers={"Authorization": "Basic !!!notbase64"})
        self.assertEqual(r.status_code, 401)


if __name__ == "__main__":
    unittest.main()
