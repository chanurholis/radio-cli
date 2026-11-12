import radio
st = {"groove": "u1", "drone": "u2"}
assert radio.resolve(st, "groove") == "u1"
assert radio.resolve(st, "2") == "u2"
assert radio.resolve(st, "dr") == "u2"
assert radio.resolve(st, "http://x/y") == "http://x/y"
for bad in ("nope", "9"):
    try: radio.resolve(st, bad); assert False
    except SystemExit: pass
print("ok")

# TUI smoke: run in a pty, move down, back, quit; must exit cleanly within 10s
import os, pty, select, subprocess, time
m, sl = pty.openpty()
env = dict(os.environ, RADIO_CONF="/nonexistent/st.json", TERM="xterm", LINES="24", COLUMNS="80")
p = subprocess.Popen(["python3", "tui.py"], stdin=sl, stdout=sl, stderr=sl, env=env, close_fds=True)
os.close(sl)
out = b""
for ch in (b"", b"j", b"b", b"q"):
    time.sleep(0.5); os.write(m, ch)
    while select.select([m], [], [], 0.3)[0]:
        try: d = os.read(m, 4096)
        except OSError: d = b""
        if not d: break
        out += d
try:
    rc = p.wait(timeout=10)
except subprocess.TimeoutExpired:
    p.kill(); rc = "timeout"
assert rc == 0 and b"saved" in out and b"groove" in out and b"Traceback" not in out, (rc, out[-800:])
print("tui ok")

# now-playing file: written on play/title change, removed on stop
import tui
tui.NOW_FILE = "/tmp/radio-test-now"
tui.now_playing("x · y"); assert open(tui.NOW_FILE).read() == "x · y"
tui.now_playing(""); assert not os.path.exists(tui.NOW_FILE)
tui.now_playing("")  # idempotent
print("now ok")
