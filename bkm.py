#!/usr/bin/env python3
"""Read a Speedlink Reticos vendor profile (.bkm, exported by the Reticos software) and print the
settings plus the matching replicator.py command. Read-only, no mouse needed.

  python bkm.py FILE.bkm            decode and print the replicator.py command
  python bkm.py FILE.bkm --plain    same, without color blocks

Layout (little-endian 32-bit values) of the block at PROFILE:
  +0x00 polling rate (1-4)   +0x0C active DPI level? (not used)
  +0x10 8 DPI levels, 16 bytes each: disabled flag, DPI X, DPI Y, color R G B 0
  +0xC0 active effect, 0-based (0 = Colorful streaming ... 8 = Wave)
  +0xC4 effect records, 60 bytes each, record i = effect i+1:
        speed, brightness (1-4), unknown, unknown, 8 colors (R G B 0), color mask, 0, 0
"""
import struct, sys

PROFILE = 0x83D4
RECORD, RECORD_SIZE = 0xC4, 60
EFFECTS = ["streaming", "steady", "breathing", "tail", "neon", "cs", "flicker", "stars", "wave"]
PLAIN = "--plain" in sys.argv

def sw(c):
    block = "" if PLAIN else f"\x1b[38;2;{int(c[0:2], 16)};{int(c[2:4], 16)};{int(c[4:6], 16)}m██\x1b[0m "
    return f"{block}#{c}"

def parse(data):
    b = data[PROFILE:PROFILE + 0x400]
    u = lambda o: struct.unpack_from("<I", b, o)[0]
    col = lambda o: b[o:o + 3].hex()
    p = {"poll": {1: 125, 2: 250, 3: 500, 4: 1000}.get(u(0x00)), "effect": u(0xC0) + 1, "dpi": [], "rec": []}
    for i in range(8):
        o = 0x10 + 16 * i
        p["dpi"].append({"enabled": u(o) == 0, "dpi": u(o + 4), "color": col(o + 12)})
    for i in range(len(EFFECTS)):
        o = RECORD + RECORD_SIZE * i
        p["rec"].append({"speed": u(o), "brightness": u(o + 4), "colors": [col(o + 16 + 4 * k) for k in range(8)]})
    return p

def command(p):
    r = {name: p["rec"][i] for i, name in enumerate(EFFECTS)}
    args = [f"effect={EFFECTS[p['effect'] - 1]}" if 1 <= p["effect"] <= 9 else f"effect={p['effect']}"]
    args.append("lights=on")
    if p["poll"]: args.append(f"poll={p['poll']}")
    for i, d in enumerate(p["dpi"]):
        args += [f"dpi{i+1}={d['dpi']}", f"dpi{i+1}.color={d['color']}"]
    args.append("dpi.enabled=" + ",".join(str(i + 1) for i, d in enumerate(p["dpi"]) if d["enabled"]))
    args += [f"stream.speed={r['streaming']['speed']}",
             f"steady.color={r['steady']['colors'][0]}",
             f"steady.brightness={25 * r['steady']['brightness']}",
             f"breathing.speed={r['breathing']['speed']}",
             "breathing.colors=" + ",".join(r["breathing"]["colors"][:7]),
             f"tail.speed={r['tail']['speed']}", f"neon.speed={r['neon']['speed']}",
             "cs.colors=" + ",".join(r["cs"]["colors"]),
             "flicker.colors=" + ",".join(r["flicker"]["colors"][:2]),
             f"stars.speed={r['stars']['speed']}", f"wave.speed={r['wave']['speed']}"]
    return args

def main():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(files) != 1:
        print(__doc__); sys.exit(1)
    data = open(files[0], "rb").read()
    name = data[0x214:0x254].decode("utf-16-le", "replace").split("\0")[0]
    p = parse(data)
    print(f"Profile '{name}' ({files[0]})")
    print(f"  effect      {p['effect']} ({EFFECTS[p['effect'] - 1] if 1 <= p['effect'] <= 9 else '?'})")
    print(f"  poll        {p['poll']} Hz")
    for i, d in enumerate(p["dpi"]):
        print(f"  dpi{i+1}        {d['dpi']:>5}  {sw(d['color'])}  {'enabled' if d['enabled'] else 'disabled'}")
    for i, name in enumerate(EFFECTS):
        r = p["rec"][i]
        print(f"  {name:<11} speed {r['speed']}  brightness {r['brightness']}  " + " ".join(sw(c) for c in r["colors"]))
    print("\nreplicator.py command (dry run; add --apply to write):")
    print("  python3 replicator.py set " + " ".join(command(p)))

if __name__ == "__main__":
    main()
