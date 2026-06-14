#!/usr/bin/env python3
"""Verify the native host: message framing round-trips and macOS detection
functions actually execute on this machine (no live call required)."""
import io, json, struct, sys, os, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
HOST = os.path.join(HERE, "..", "native", "call_detector.py")

spec = importlib.util.spec_from_file_location("cd", HOST)
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)

fail = 0
def ok(c, m):
    global fail
    print(("ok:   " if c else "FAIL: ") + m)
    if not c: fail += 1

# 1. send_msg framing (4-byte LE length prefix + JSON)
buf = io.BytesIO()
real = sys.stdout
class W:  # minimal stand-in exposing .buffer
    buffer = buf
sys.stdout = W()
cd.send_msg({"event": "pong"})
sys.stdout = real
framed = buf.getvalue()
length = struct.unpack("<I", framed[:4])[0]
body = json.loads(framed[4:].decode())
ok(length == len(framed) - 4, "send_msg length prefix correct")
ok(body == {"event": "pong"}, "send_msg JSON payload correct")

# 2. read_msg parses a framed message from stdin
payload = json.dumps({"cmd": "ping"}).encode()
instream = io.BytesIO(struct.pack("<I", len(payload)) + payload)
class R:
    buffer = instream
real_in = sys.stdin
sys.stdin = R()
got = cd.read_msg()
sys.stdin = real_in
ok(got == {"cmd": "ping"}, "read_msg parses framed input")

# 3. detection functions run on this Mac without throwing
try:
    apps = cd.running_apps()
    ok(isinstance(apps, set), f"running_apps() executes (found: {sorted(apps) or 'none active'})")
except Exception as e:
    ok(False, "running_apps() raised: " + str(e))

try:
    label = cd.active_call_label()
    ok(label is None or isinstance(label, str), f"active_call_label() executes (now: {label or 'no active call'})")
except Exception as e:
    ok(False, "active_call_label() raised: " + str(e))

# 4. APP_PROCS map + markdown writer shape
ok("zoom.us" in cd.APP_PROCS and cd.APP_PROCS["FaceTime"] == "FaceTime", "app detection map present")

print("\n" + ("%d native check(s) failed" % fail if fail else "ALL NATIVE CHECKS PASSED"))
sys.exit(1 if fail else 0)
