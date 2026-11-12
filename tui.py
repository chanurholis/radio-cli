"""radio TUI (curses). keys: ↑↓/jk move · Enter play · s stop · +/- volume · m mute · r record · / search · l local · t tag · a add · d delete · b back · q quit"""
import curses, os, random, shutil, subprocess, threading, time, urllib.request
import radio

BARS = "▁▂▃▄▅▆▇█"
REC_DIR = os.path.expanduser(os.environ.get("RADIO_REC", "~/Music/radio"))
NOW_FILE = os.path.expanduser("~/.cache/radio/now")  # "station · title" for status lines (nvim, tmux, ...)


def now_playing(text):
    """publish what plays to NOW_FILE; empty text removes it"""
    try:
        if not text:
            return os.remove(NOW_FILE)
        os.makedirs(os.path.dirname(NOW_FILE), exist_ok=True)
        with open(NOW_FILE, "w") as f:
            f.write(text)
    except OSError:
        pass


def notify(title, body):
    """desktop notification; silently skipped when no tool is available"""
    if shutil.which("osascript"):
        esc = lambda t: t.replace("\\", "\\\\").replace('"', '\\"')
        cmd = ["osascript", "-e", f'display notification "{esc(body)}" with title "{esc(title)}"']
    elif shutil.which("notify-send"):
        cmd = ["notify-send", title, body]
    else:
        return
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Stream(threading.Thread):
    """read the stream ourselves and pipe to the player: gives bytes/sec + ICY title"""
    def __init__(self, url, vol=100):
        super().__init__(daemon=True)
        self.url, self.kbps, self.title, self.err = url, 0.0, "", ""
        self.ext, self.rec = "mp3", None
        self.proc = self._player(vol)
        self.stop = threading.Event()
        self.start()

    def _player(self, vol):
        return subprocess.Popen(radio.player(vol) + ["-"], stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def set_volume(self, vol):
        # ponytail: restart player with new volume flag (~0.5s gap); use mpv IPC for seamless
        old, self.proc = self.proc, self._player(vol)
        old.terminate()

    def record(self, name):
        """toggle recording to REC_DIR/<name>-<time>.<ext>; returns path, or None when stopped"""
        if self.rec:
            self.rec.close(); self.rec = None
            return None
        os.makedirs(REC_DIR, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip()
        path = os.path.join(REC_DIR, f"{safe}-{time.strftime('%Y%m%d-%H%M%S')}.{self.ext}")
        self.rec = open(path, "wb")
        return path

    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"Icy-MetaData": "1", "User-Agent": "radio-cli"})
            r = urllib.request.urlopen(req, timeout=10)
            metaint = int(r.headers.get("icy-metaint") or 0)
            ct = r.headers.get("content-type", "")
            self.ext = "aac" if "aac" in ct else "ogg" if "ogg" in ct else "mp3"
            n, t0 = 0, time.time()
            while not self.stop.is_set():
                chunk = r.read(metaint or 4096)
                if not chunk:
                    break
                self.proc.stdin.write(chunk)
                if self.rec:
                    self.rec.write(chunk)
                n += len(chunk)
                if metaint:  # metadata block: 1 length byte (/16), then "StreamTitle='...';"
                    ln = r.read(1)
                    if ln and ln[0]:
                        meta = r.read(ln[0] * 16).decode("utf-8", "ignore")
                        if "StreamTitle='" in meta:
                            self.title = meta.split("StreamTitle='", 1)[1].split("';", 1)[0]
                if time.time() - t0 >= 1:
                    self.kbps, n, t0 = n * 8 / 1000 / (time.time() - t0), 0, time.time()
        except Exception as e:  # disconnect/404/broken pipe: show it, never crash
            self.err = str(e)
        finally:
            self.kbps = 0
            self.proc.terminate()
            if self.rec:
                self.rec.close(); self.rec = None

    def close(self):
        self.stop.set()
        self.proc.terminate()


HELP = "⏎ play  s stop  +/- vol  m mute  r rec  / search  l local  t tag  a add  d del  b back  q quit"


class App:
    def __init__(self, scr):
        self.scr, self.st = scr, radio.load()
        self.stream = self.now = None
        self.mode, self.sel, self.msg = "saved", 0, ""
        self.bars = [0] * 12
        self.vol, self.muted, self.last_title = 100, False, ""
        self.rows = self.saved()

    def saved(self):
        return [(n, "", u) for n, u in self.st.items()]

    # ---- playback ----
    def play(self, name, url):
        self.stop()
        self.stream, self.now = Stream(url, 0 if self.muted else self.vol), name
        self.last_title = ""
        now_playing(name)

    def stop(self):
        if self.stream:
            self.stream.close()
            self.stream = self.now = None
            now_playing("")

    def volume(self, delta=None, mute=None):
        if mute is not None:
            self.muted = not self.muted
        else:
            self.vol, self.muted = max(0, min(100, self.vol + delta)), False
        if self.stream:
            self.stream.set_volume(0 if self.muted else self.vol)

    def status(self):
        if not self.stream:
            return f"■ nothing playing   vol {self.vol}"
        s = self.stream
        if s.title and s.title != self.last_title:  # track changed -> desktop notification
            self.last_title = s.title
            notify(f"radio: {self.now}", s.title)
            now_playing(f"{self.now} · {s.title}")
        # ponytail: bars driven by throughput (random while data flows), not real audio amplitude
        self.bars = self.bars[1:] + [random.randint(2, 7) if s.kbps else 0]
        sig = "".join(BARS[b] for b in self.bars)
        vol = "MUTE" if self.muted else f"vol {self.vol}"
        rec = "  ● REC" if s.rec else ""
        return f"▶ {self.now}  {sig} {s.kbps:4.0f} kb/s  {vol}{rec}  {s.title or s.err}"

    # ---- ui ----
    def ask(self, label, default=""):
        h, w = self.scr.getmaxyx()
        self.scr.move(h - 1, 0); self.scr.clrtoeol()
        self.scr.addstr(h - 1, 0, f"{label}: {default}"[: w - 1]); curses.echo(); curses.curs_set(1); self.scr.timeout(-1)
        try:
            s = self.scr.getstr(h - 1, len(label) + 2, w - len(label) - 3).decode(errors="ignore").strip()
        except KeyboardInterrupt:
            s = ""
        curses.noecho(); curses.curs_set(0); self.scr.timeout(200)
        return s or default

    def fetch(self, fn, *a):
        self.msg = "loading…"; self.draw()
        try:
            return fn(*a)
        except Exception as e:  # network/API error: show it, never crash
            self.msg = f"failed: {e}"
            return None

    def draw(self):
        scr, (h, w) = self.scr, self.scr.getmaxyx()
        scr.erase()
        scr.addstr(0, 0, f" radio · {self.mode} ({len(self.rows)}) ".ljust(w - 1), curses.A_REVERSE)
        top = max(0, self.sel - (h - 5))
        for i, (n, info, u) in enumerate(self.rows[top: top + h - 4]):
            line = f"{n[:32]:<32} {info[:16]:<16} {u}"[: w - 2]
            scr.addstr(i + 1, 1, line, curses.A_REVERSE if i + top == self.sel else 0)
        scr.addstr(h - 3, 0, self.status()[: w - 1], curses.A_BOLD)
        scr.addstr(h - 2, 0, (self.msg or HELP)[: w - 1])
        scr.refresh()

    def set_rows(self, rows, mode):
        if rows is not None:
            self.rows, self.mode, self.sel, self.msg = rows, mode, 0, ""

    def cur(self):
        return self.rows[self.sel] if self.rows else None

    def key(self, k):
        c = self.cur()
        if k in ("q",):
            return False
        if k in ("KEY_DOWN", "j"): self.sel = min(self.sel + 1, len(self.rows) - 1)
        elif k in ("KEY_UP", "k"): self.sel = max(self.sel - 1, 0)
        elif k == "\n" and c:
            if c[2]: self.play(c[0], c[2])
            else: self.set_rows(self.fetch(radio.local, c[0]), f"local {c[0]}")  # region row -> its stations
        elif k == "s": self.stop()
        elif k in ("+", "="): self.volume(+10)
        elif k == "-": self.volume(-10)
        elif k == "m": self.volume(mute=True)
        elif k == "r" and self.stream:
            path = self.stream.record(self.now)
            self.msg = f"recording to {path}" if path else "recording saved"
        elif k == "t":
            q = self.ask("tag/genre (dangdut, news, jazz, quran...)")
            if q: self.set_rows(self.fetch(radio.tag, q), f"tag {q}")
        elif k == "/":
            q = self.ask("search")
            if q: self.set_rows(self.fetch(radio.search, q), f"search {q}")
        elif k == "l":
            q = self.ask("region (empty = list)")
            self.set_rows(self.fetch(radio.local, q), f"local {q}" if q else "regions")
        elif k == "a":
            if self.mode == "saved":
                name, url = self.ask("name"), self.ask("url")
            elif c and c[2]:
                name, url = self.ask("save as", c[0]), c[2]
            else:
                return True
            if name and url:
                self.st[name] = url; radio.save(self.st); self.msg = f"saved: {name}"
        elif k == "d" and self.mode == "saved" and c:
            del self.st[c[0]]; radio.save(self.st); self.rows = self.saved(); self.sel = min(self.sel, len(self.rows) - 1)
        elif k == "b": self.set_rows(self.saved(), "saved")
        return True

    def loop(self):
        curses.curs_set(0)
        self.scr.timeout(200)  # redraw every 200ms for bars/bandwidth
        self.draw()
        try:
            while True:
                try:
                    k = self.scr.getkey()
                except curses.error:  # timeout
                    self.draw(); continue
                if not self.key(k):
                    break
                self.draw()
        finally:
            self.stop()  # also on a crash, so NOW_FILE never goes stale


def run():
    curses.wrapper(lambda scr: App(scr).loop())


if __name__ == "__main__":
    run()
