# radio-cli

Internet radio in the terminal. Python stdlib only, plus `mpv` or `ffplay`. Interactive UI and plain commands.

## Install (macOS / Linux)

```sh
curl -fsSL https://raw.githubusercontent.com/USER/radio-cli/main/install.sh | bash
```

or from a clone: `./install.sh`. The script installs `mpv` if missing (brew/apt/dnf/pacman),
puts the program in `~/.local/share/radio-cli` and the `radio` command in `~/.local/bin`.

## Usage

```sh
radio                     # UI, see keys below
radio local               # Indonesian regions -> type a number
radio local bandung       # stations in Bandung -> number plays, s3 saves #3
radio tag dangdut         # stations by genre (news, jazz, quran, pop, ...)
radio search jazz         # global search (radio-browser.info)
radio play groove         # saved station: name, prefix (gr), number (1), or URL
radio list / add <name> <url> / rm <name>
```

UI keys: `⏎` play · `s` stop · `+`/`-` volume · `m` mute · `r` record · `/` search · `l` local ·
`t` tag · `a` add · `d` delete · `b` back · `q` quit.

Status line: `▶ name  ▃▅▂▇▄▆ 128 kb/s  vol 80  ● REC  Track title`. The title comes from ICY metadata
when the station sends it, and a desktop notification fires when it changes.
Recordings go to `~/Music/radio/` (override: `RADIO_REC`). Stations live in
`~/.config/radio/stations.json` (override: `RADIO_CONF`).

## Hacking

New command: write `cmd_<name>(st, *args)` in `radio.py` and register it in `CMDS`.
New UI key: one `elif` in `App.key` in `tui.py`. Check: `python3 test_radio.py`.
