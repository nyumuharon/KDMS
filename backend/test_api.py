"""Quick API test suite for KDMS — run from backend directory."""
import urllib.request
import urllib.error
import json
import sys

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0

def req(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code
    except Exception as e:
        return {"error": str(e)}, 0

def test(name, method, path, body=None, expect_keys=None, min_len=None):
    global PASS, FAIL
    data, status = req(method, path, body)
    ok = status in (200, 201)
    if ok and expect_keys:
        ok = all(k in data for k in expect_keys)
    if ok and min_len is not None:
        ok = isinstance(data, list) and len(data) >= min_len
    symbol = "✅ PASS" if ok else "❌ FAIL"
    if PASS == 0 and FAIL == 0:
        print(f"\n{'='*55}")
        print(f"  KDMS API Test Suite — {BASE}")
        print(f"{'='*55}\n")
    print(f"  {symbol}  {method} {path}")
    if not ok:
        print(f"         status={status}  data={str(data)[:80]}")
    (PASS if ok else FAIL).__class__  # trick to force increment
    if ok: PASS += 1
    else:   FAIL += 1
    return data

# ── GET endpoints ─────────────────────────────────────────────────────────────
stats    = test("Stats summary",          "GET",  "/stats",
                expect_keys=["active_disasters","counties_monitored","total_affected"])
disasters= test("List all disasters",     "GET",  "/disasters",          min_len=1)
active   = test("Active disasters only",  "GET",  "/disasters?status=active", min_len=1)
counties = test("County risk scores",     "GET",  "/counties/risk",      min_len=47)
workers  = test("Workers list",           "GET",  "/workers",            min_len=5)
alerts   = test("Alert history",          "GET",  "/alerts")

# ── POST endpoints ────────────────────────────────────────────────────────────
report   = test("Submit field report",    "POST", "/report",
                body={"type":"Flood","severity":"High","location":"Test County",
                      "lat":-1.0,"lng":36.5,"affected_people":200,
                      "description":"API test disaster report"},
                expect_keys=["success","disaster_id"])

# Get a valid disaster_id for the next tests
dis_id = active[0]["id"] if active else 1
alert_r= test("Send AI SMS alert",       "POST", "/alert/send",
                body={"disaster_id": dis_id},
                expect_keys=["success","message_en","message_sw"])

dispatch=test("Dispatch worker",          "POST", "/dispatch",
                body={"worker_id":2,"disaster_id":dis_id},
                expect_keys=["success"])

# ── Summary ───────────────────────────────────────────────────────────────────
total = PASS + FAIL
print(f"\n{'='*55}")
print(f"  Results: {PASS}/{total} passed  ({FAIL} failed)")
print(f"{'='*55}\n")

# Print SMS preview if available
if isinstance(alert_r, dict) and alert_r.get("message_en"):
    print("  SMS Preview (English):", alert_r["message_en"][:90])
    print("  SMS Preview (Swahili):", alert_r.get("message_sw","")[:90])
    print()

sys.exit(0 if FAIL == 0 else 1)
