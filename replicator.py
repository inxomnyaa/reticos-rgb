#!/usr/bin/env python3
"""Speedlink Reticos (Sinowealth 258a:003b): show / change the profile stored on the mouse.
Protocol taken from a USB capture of the vendor driver. Close the Reticos software first.
pip install hidapi

  python replicator.py                          show the profile stored on the mouse (read-only)
  python replicator.py show FILE.bin            decode a saved profile, no mouse needed
  python replicator.py set KEY=VALUE [...]      change settings (dry run; add --apply to write)
  python replicator.py restore FILE.bin         write a saved profile back (dry run; --apply)
  flags: --apply  --plain (no color blocks)  --save (save a backup of the read)

Keys for "set" (several at once are fine, they go out as one write):
  effect=none|streaming|steady|breathing|tail|neon|cs|flicker|stars|wave   (or 0-9)
  lights=on|off|toggle                  global on/off, keeps the effect
  poll=125|250|500|1000
  dpi1=800 ... dpi8=9000                200-5000 in steps of 100, 5500-10000 in steps of 500
  dpi1.color=ff0000 ... dpi8.color=...
  dpi3.enabled=on|off|toggle            switch a single level on or off
  dpi.enabled=1,2,4                     set the whole list of enabled levels
  dpi.active=4                          active level (untested whether the mouse applies this)
  stream.speed=1-3  stream.dir=up|down|toggle  steady.color=RRGGBB  steady.brightness=25|50|75|100
  breathing.speed=1-3  breathing.colors=RRGGBB,... (up to 7)  tail.speed  neon.speed
  stars.speed  wave.speed  flicker.colors=RRGGBB,RRGGBB
  cs.colors=RRGGBB,...                  Colorful steady; only slots 1-5 are lit on this mouse
Example: python replicator.py set effect=cs cs.colors=ff0000,ff8000,ffff00,00ff00,00ffff --apply
"""
import os, re, sys, time

VID, PID = 0x258A, 0x003B
FULL = 520                                   # report 4 as sent by the driver
EFFECT, LIGHTS = 53, 130                     # LIGHTS: 0 = on, 3 = off (seen with effect None)
CS_OFF, CS_SLOTS = 86, 8
EFFECTS = {0: "None", 1: "Colorful streaming", 2: "Steady", 3: "Breathing", 4: "Tail",
           5: "Neon", 6: "Colorful steady", 7: "Flicker", 8: "Stars twinkle", 9: "Wave"}
EFFECT_NAMES = {"none": 0, "streaming": 1, "steady": 2, "breathing": 3, "tail": 4, "neon": 5,
                "cs": 6, "flicker": 7, "stars": 8, "wave": 9}
PLAIN = False

# ---------------------------------------------------------------- pretty printing
def paint(text, code):
    return text if PLAIN else f"\x1b[{code}m{text}\x1b[0m"

def sw(rgb):
    r, g, b = rgb[0], rgb[1], rgb[2]
    block = "██" if PLAIN else f"\x1b[38;2;{r};{g};{b}m██\x1b[0m"
    return f"{block} #{r:02x}{g:02x}{b:02x}"

def pick(options, cur):
    return " | ".join(paint(f"[{o}]", "1;32") if o == cur else str(o) for o in options)

def speed(b):  return pick([1, 2, 3], b & 3) if 0x41 <= b <= 0x43 else f"raw {b:#04x}"
def cols(p, off, n, label="color"): return [(f"{label} {i+1}  {sw(p[off+3*i:off+3*i+3])}", []) for i in range(n)]

def render(nodes, prefix=""):
    for i, (text, kids) in enumerate(nodes):
        last = i == len(nodes) - 1
        print(prefix + ("└─ " if last else "├─ ") + text)
        render(kids, prefix + ("   " if last else "│  "))

def dpi_value(v):                            # 100 steps up to 5000 (0x31), then 500 steps
    return (v + 1) * 100 if v <= 0x31 else 5000 + (v - 0x31) * 500

def dpi_state(p):                            # -> (enabled level indexes, active level index)
    enabled = [i for i in range(8) if not (p[12] >> i) & 1]
    hi = p[11] >> 4
    active = enabled[hi - 1] if 1 <= hi <= len(enabled) else (enabled[0] if enabled else 0)
    return enabled, active

def decode(p):
    eff = p[EFFECT]
    poll = {1: 125, 2: 250, 3: 500, 4: 1000}
    enabled, active = dpi_state(p)
    dpi = []
    for i in range(8):
        val = f"{dpi_value(p[13+i]):>5} DPI"
        if i == active and i in enabled: mark, val = paint("●", "1;36"), paint(val, "1;36")
        elif i in enabled: mark = paint("✓", "32")
        else: mark = paint("✗", "31")
        dpi.append((f"{i+1} {mark} {val}  {sw(p[29+3*i:32+3*i])}", []))
    note = "" if (p[11] & 15) == len(enabled) else f"   (count byte says {p[11] & 15}!)"
    brightness = {1: 25, 2: 50, 3: 75, 4: 100}.get(p[56] >> 4, f"raw {p[56]:#04x}")
    def e(n, kids): return (("▶ " if eff == n else "  ") + f"{n} {EFFECTS[n]}" + ("   <- active" if eff == n else ""), kids)
    unused = [(f"slot {i+1} (unused)  {sw(p[CS_OFF+3*i:CS_OFF+3*i+3])}", []) for i in range(5, 8)]
    effects = [
        e(1, [("speed      " + speed(p[54]), []), ("direction  " + pick(["down", "up"], "up" if p[55] else "down"), [])]),
        e(2, [("brightness " + pick([25, 50, 75, 100], brightness), []), ("color      " + sw(p[57:60]), [])]),
        e(3, [("speed      " + speed(p[60]), [])] + cols(p, 62, 7)),
        e(4, [("speed      " + speed(p[83]), [])]),
        e(5, [("speed      " + speed(p[84]), [])]),
        e(6, cols(p, CS_OFF, 5, "slot") + unused),
        e(7, cols(p, 117, 2)),
        e(8, [("speed      " + speed(p[123]), [])]),
        e(9, [("speed      " + speed(p[124]), [])]),
        e(0, []),
    ]
    tree = [
        ("Lights         " + (paint("ON", "1;32") if p[LIGHTS] == 0 else paint(f"OFF (byte 130 = {p[LIGHTS]})", "31")), []),
        ("Polling rate   " + pick([125, 250, 500, 1000], poll.get(p[10], f"raw {p[10]}")) + " Hz", []),
        ("DPI levels     (● active, ✓ enabled, ✗ disabled)" + note, dpi),
        (f"Lighting effect: {EFFECTS.get(eff, '?')}", effects),
        (f"Not decoded   b61={p[61]:02x} b85={p[85]:02x} b116={p[116]:02x}", []),
    ]
    print("Reticos profile stored on the mouse")
    render(tree)

# ---------------------------------------------------------------- changing settings
def rgb(s):
    s = s.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s): raise ValueError(f"'{s}' is not an RRGGBB color")
    return bytes.fromhex(s)

def one_of(v, options, what):
    if v not in options: raise ValueError(f"{what} must be one of {list(options)}")
    return options[v] if isinstance(options, dict) else v

def _speed(off):
    def f(b, v):
        if v not in ("1", "2", "3"): raise ValueError("speed must be 1, 2 or 3")
        b[off] = 0x40 + int(v)
    return f

def _colors(off, n):
    def f(b, v):
        c = [rgb(x) for x in v.split(",")]
        if not 1 <= len(c) <= n: raise ValueError(f"give 1 to {n} colors")
        for i, x in enumerate(c): b[off+3*i:off+3*i+3] = x
    return f

def _effect(b, v):
    n = int(v) if v.isdigit() else one_of(v.lower(), EFFECT_NAMES, "effect")
    if n not in EFFECTS: raise ValueError("effect must be 0-9")
    b[EFFECT] = n

def _lights(b, v):
    b[LIGHTS] = {"on": 0, "off": 3}.get(v, (0 if b[LIGHTS] else 3) if v == "toggle" else None)
    if b[LIGHTS] is None: raise ValueError("lights must be on, off or toggle")

def _direction(b, v):
    b[55] = (0 if b[55] else 1) if v == "toggle" else one_of(v, {"down": 0, "up": 1}, "stream.dir")

def _poll(b, v):
    b[10] = one_of(v, {"125": 1, "250": 2, "500": 3, "1000": 4}, "poll")

def _brightness(b, v):
    step = one_of(v, {"25": 1, "50": 2, "75": 3, "100": 4}, "steady.brightness")
    b[56] = 0x0F + 0x10 * step

def encode_dpi(d):
    if 200 <= d <= 5000 and d % 100 == 0: return d // 100 - 1
    if 5000 < d <= 10000 and d % 500 == 0: return 0x31 + (d - 5000) // 500
    raise ValueError("DPI must be 200-5000 in steps of 100, or 5500-10000 in steps of 500")

SETTERS = {
    "effect": _effect, "lights": _lights, "poll": _poll,
    "stream.speed": _speed(54), "stream.dir": _direction,
    "steady.color": _colors(57, 1), "steady.brightness": _brightness,
    "breathing.speed": _speed(60), "breathing.colors": _colors(62, 7),
    "tail.speed": _speed(83), "neon.speed": _speed(84), "stars.speed": _speed(123), "wave.speed": _speed(124),
    "cs.colors": _colors(CS_OFF, CS_SLOTS), "flicker.colors": _colors(117, 2),
}

def apply_settings(p, items):
    b = bytearray(p)
    enabled, active = dpi_state(b)
    touch_dpi = active_given = False
    for item in items:
        if "=" not in item: raise ValueError(f"'{item}' is not KEY=VALUE")
        k, v = item.split("=", 1); k = k.lower()
        m = re.fullmatch(r"dpi([1-8])(\.color|\.enabled)?", k)
        n = int(m.group(1)) - 1 if m else None
        if k in SETTERS: SETTERS[k](b, v)
        elif m and m.group(2) == ".color": b[29+3*n:32+3*n] = rgb(v)
        elif m and m.group(2) == ".enabled":
            want = {"on": True, "off": False, "toggle": n not in enabled}.get(v)
            if want is None: raise ValueError("use on, off or toggle")
            enabled = sorted((set(enabled) | {n}) if want else (set(enabled) - {n})); touch_dpi = True
        elif m: b[13 + n] = encode_dpi(int(v))
        elif k == "dpi.enabled":
            enabled = sorted({int(x) - 1 for x in v.split(",")}); touch_dpi = True
            if not all(0 <= i < 8 for i in enabled): raise ValueError("dpi.enabled needs levels 1-8")
        elif k == "dpi.active":
            active, active_given, touch_dpi = int(v) - 1, True, True
        else: raise ValueError(f"unknown key '{k}' (see the top of the script)")
    if touch_dpi:
        if not enabled: raise ValueError("at least one DPI level must stay enabled")
        if active not in enabled:
            if active_given: raise ValueError("dpi.active must be one of the enabled levels")
            active = enabled[0]
        b[12] = sum(1 << i for i in range(8) if i not in enabled)
        b[11] = ((enabled.index(active) + 1) << 4) | len(enabled)
    return bytes(b)

# ---------------------------------------------------------------- device access
def cmd5(h5, c):                             # 6-byte command on report 5
    h5.send_feature_report([5, c, 0, 0, 0, 0]); time.sleep(0.03)
    return bytes(h5.get_feature_report(5, 6))

def find(hid):
    """report 5 (commands) and report 4 (profile) may be on one handle (Linux) or two (Windows).
    The mouse answers a report 4 read according to the last report-5 command, so select the
    profile (05 02, 05 11) before trying report 4, like the driver does."""
    handles, h5 = [], None
    for d in hid.enumerate(VID, PID):
        if d.get("interface_number") == 0: continue          # the mouse interface has no feature reports
        h = hid.device()
        try: h.open_path(d["path"])
        except Exception: continue
        handles.append(h)
        if h5 is None:
            try:
                if cmd5(h, 1) == bytes([5, 1, 0x39, 0x36, 0x31, 0x30]): h5 = h   # handshake answers "9610"
            except Exception: pass
    h4 = None
    if h5:
        try: cmd5(h5, 2); h5.send_feature_report([5, 0x11, 0, 0, 0, 0]); time.sleep(0.05)
        except Exception: pass
        for h in handles:
            try:
                r = bytes(h.get_feature_report(4, FULL))
                if len(r) >= 131 and r[:2] == b"\x04\x11": h4 = h; break
            except Exception: pass
    for h in handles:
        if h is not h5 and h is not h4:
            try: h.close()
            except Exception: pass
    return h5, h4

def read_profile(h5, h4):
    cmd5(h5, 2)
    h5.send_feature_report([5, 0x11, 0, 0, 0, 0]); time.sleep(0.05)
    r = bytes(h4.get_feature_report(4, FULL))
    assert len(r) >= 131 and r[:2] == b"\x04\x11", "unexpected profile read: " + r[:16].hex()
    return r[:131]

def build_write(read):                       # driver sets b[3]=0x7b, b[6]=b[7]=0 and pads to 520 bytes
    b = bytearray(read).ljust(FULL, b"\0"); b[3] = 0x7B; b[6] = 0; b[7] = 0
    return bytes(b)

def save(p):
    name = time.strftime("reticos_backup_%Y%m%d_%H%M%S.bin"); open(name, "wb").write(p); print("backup saved:", name)

def main():
    global PLAIN
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    os.system("")                            # enables ANSI colors in the Windows console
    a = sys.argv[1:]
    apply, PLAIN, want_save = "--apply" in a, "--plain" in a, "--save" in a
    a = [x for x in a if not x.startswith("--")]
    if a and a[0] == "show":
        decode(open(a[1], "rb").read()[:131]); return
    import hid
    h5, h4 = find(hid)
    if not (h5 and h4): sys.exit("Did not find both the report-5 and report-4 handles (is the Reticos software closed?)")
    p = read_profile(h5, h4); decode(p)
    if want_save or (apply and a): save(p)
    if not a: return
    try:
        if a[0] == "set": new = apply_settings(p, a[1:])
        elif a[0] == "restore": new = open(a[1], "rb").read()[:131]
        else: sys.exit("unknown command")
    except ValueError as err: sys.exit(f"error: {err}")
    if new == p: print("\nnothing would change"); return
    print("\nwould write:"); decode(new)
    if not apply: print("\ndry run - add --apply to write"); return
    n = h4.send_feature_report(list(build_write(new))); print("\nwrote, return value:", n)
    time.sleep(0.2); q = read_profile(h5, h4); decode(q)
    print("verify:", "OK" if q[8:] == new[8:] else "MISMATCH (compare the two trees above)")

if __name__ == "__main__": main()