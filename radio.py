#!/usr/bin/env python3
"""radio — internet radio from the terminal. Stdlib only; plays via mpv or ffplay."""
import json, os, shutil, subprocess, sys, urllib.parse, urllib.request

CONF = os.path.expanduser(os.environ.get("RADIO_CONF", "~/.config/radio/stations.json"))
DEFAULTS = {
    "groove": "https://ice1.somafm.com/groovesalad-128-mp3",
    "drone": "https://ice1.somafm.com/dronezone-128-mp3",
    "lush": "https://ice1.somafm.com/lush-128-mp3",
    "paradise": "https://stream.radioparadise.com/mp3-128",
}
PLAYERS = {  # first one found wins; vol 0-100
    "mpv": lambda vol: ["mpv", "--no-video", "--really-quiet", "--display-tags=icy-title", f"--volume={vol}"],
    "ffplay": lambda vol: ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(vol)],
}
API = "https://de1.api.radio-browser.info/json/stations/search?limit=15&hidebroken=true&order=votes&reverse=true&name="


def load():
    try:
        with open(CONF) as f:
            return json.load(f)
    except FileNotFoundError:
        return dict(DEFAULTS)


def save(st):
    os.makedirs(os.path.dirname(CONF), exist_ok=True)
    with open(CONF, "w") as f:
        json.dump(st, f, indent=2)


def resolve(st, key):
    """name | 1-based index | prefix | raw url -> url"""
    if "://" in key:
        return key
    if key.isdigit() and 0 < int(key) <= len(st):
        return list(st.values())[int(key) - 1]
    if key in st:
        return st[key]
    hits = [n for n in st if n.startswith(key)]
    if len(hits) == 1:
        return st[hits[0]]
    sys.exit(f"unknown station '{key}'" + (f" (ambiguous: {', '.join(hits)})" if hits else ""))


def player(vol=100):
    for name, cmd in PLAYERS.items():
        if shutil.which(name):
            return cmd(vol)
    sys.exit("need mpv or ffplay installed")


# ---- commands: add a function here + an entry in CMDS, that's it ----
def cmd_list(st, *_):
    for i, (n, u) in enumerate(st.items(), 1):
        print(f"{i:>2}  {n:<16} {u}")


def cmd_add(st, name=None, url=None, *_):
    if not (name and url):
        sys.exit("usage: radio add <name> <url>")
    st[name] = url
    save(st)
    print(f"added {name}")


def cmd_rm(st, name=None, *_):
    if name not in st:
        sys.exit(f"unknown station '{name}'")
    del st[name]
    save(st)
    print(f"removed {name}")


def search(q):
    """global search -> [(name, info, url)]"""
    return [(s["name"], s.get("countrycode", ""), s["url_resolved"])
            for s in _get(API + urllib.parse.quote(q))]


def local(q=""):
    """q empty -> [(region, count, '')]; else Indonesian stations matching substring in state/name"""
    base = "https://de1.api.radio-browser.info/json/"
    if not q:
        return [(s["name"], str(s["stationcount"]), "") for s in
                sorted(_get(base + "states/Indonesia/"), key=lambda s: -s["stationcount"]) if s["stationcount"] > 1]
    q = q.lower()
    # ponytail: fetches all ID stations each call (~300 rows); cache if it feels slow
    return [(s["name"], s.get("state", ""), s["url_resolved"])
            for s in _get(base + "stations/bycountrycodeexact/ID?hidebroken=true&order=votes&reverse=true")
            if q in s.get("state", "").lower() or q in s["name"].lower()]


def tag(q):
    """global stations by tag/genre (dangdut, news, jazz, quran, ...)"""
    url = f"https://de1.api.radio-browser.info/json/stations/bytag/{urllib.parse.quote(q.lower())}?limit=30&hidebroken=true&order=votes&reverse=true"
    return [(s["name"], s.get("countrycode", ""), s["url_resolved"]) for s in _get(url)]


def _pick(st, rows):
    """numbered list; on a tty ask: <n> play, s<n> save, Enter cancel"""
    for i, (n, info, u) in enumerate(rows, 1):
        print(f"{i:>3}  {n[:34]:<34} {info[:18]}")
    if not rows or not sys.stdin.isatty():
        return
    try:
        ans = input(f"\nnumber to play, s<number> to save, Enter to cancel> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    save_it = ans.startswith("s")
    num = ans.lstrip("s")
    if not num.isdigit() or not 0 < int(num) <= len(rows):
        return
    name, info, url = rows[int(num) - 1]
    if not url:  # region row -> show its stations
        return _pick(st, local(name))
    if save_it:
        key = input(f"save as [{name}]: ").strip() or name
        cmd_add(st, key, url)
    else:
        cmd_play(st, url, name)


def cmd_play(st, key=None, label=None, *_):
    if not key:
        sys.exit("usage: radio play <name|index|url>")
    url = resolve(st, key)
    print(f"▶ {label or key}  ({url})   Ctrl-C to stop")
    try:
        subprocess.run(player() + [url])
    except KeyboardInterrupt:
        pass


def cmd_search(st, *words):
    if not words:
        sys.exit("usage: radio search <query>")
    _pick(st, search(" ".join(words)))


def cmd_tag(st, *words):
    if not words:
        sys.exit("usage: radio tag <genre>   (dangdut, news, jazz, quran, pop, ...)")
    _pick(st, tag(" ".join(words)))


def cmd_local(st, *words):
    """radio local -> Indonesian regions; radio local <region> -> stations there"""
    _pick(st, local(" ".join(words)))


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "radio-cli"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


CMDS = {"local": cmd_local, "tag": cmd_tag, "list": cmd_list, "ls": cmd_list, "play": cmd_play, "add": cmd_add, "rm": cmd_rm, "search": cmd_search}


def main(argv=sys.argv[1:]):
    if not argv and sys.stdout.isatty():
        import tui; return tui.run()
    if not argv or argv[0] not in CMDS:
        sys.exit("usage: radio (ui) | list | play <name|#|url> | local [region] | tag <genre> | search <query> | add <name> <url> | rm <name>")
    CMDS[argv[0]](load(), *argv[1:])


if __name__ == "__main__":
    main()
