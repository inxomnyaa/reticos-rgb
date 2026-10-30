#!/usr/bin/env python3
"""Guided hardware test for replicator.py. Put it in the same folder as replicator.py.
Close the Reticos app first. For every test it writes one change to the mouse, you look at the
mouse and answer, and at the end your original profile is written back.

  python selftest.py                run all tests
  python selftest.py tail wave      only tests whose name contains one of these words
  python selftest.py --list         just list the tests

Answer each question with:  y = it did what was expected   n = it did not   s = skip   q = quit
You can add a note after the letter, e.g.   n only the front LED changed
"""
import sys, time
import replicator as rep

# (name, settings, what you should see, chain)   chain=True -> start from the previous test's state
TESTS = [
    ("lights off",            ["lights=toggle"], "all lights go dark", False),
    ("lights on again",       ["lights=toggle"], "lights come back", True),
    ("effect none only",      ["effect=none"], "lights go off? (answer y if they do: then byte 130 is not needed)", False),
    ("effect none + off",     ["effect=none", "lights=off"], "lights go dark", False),
    ("steady red 100%",       ["effect=steady", "steady.color=ff0000", "steady.brightness=100"], "all LEDs solid bright red", False),
    ("steady red 25%",        ["effect=steady", "steady.color=ff0000", "steady.brightness=25"], "same red but clearly dimmer", False),
    ("steady blue",           ["effect=steady", "steady.color=0000ff", "steady.brightness=100"], "all LEDs solid blue", False),
    ("cs five colors",        ["effect=cs", "cs.colors=ff0000,00ff00,0000ff,ffff00,ffffff"], "front red, behind wheel green, next blue, rear yellow, logo white (positions 4/5 may be swapped)", False),
    ("cs all white",          ["effect=cs", "cs.colors=ffffff,ffffff,ffffff,ffffff,ffffff,ffffff,ffffff,ffffff"], "all 5 zones white", False),
    ("streaming speed 1 up",  ["effect=streaming", "stream.speed=1", "stream.dir=up"], "rainbow flowing slowly in one direction", False),
    ("streaming speed 3 up",  ["effect=streaming", "stream.speed=3", "stream.dir=up"], "same direction but faster", False),
    ("streaming dir toggle",  ["stream.dir=toggle"], "flows the opposite way now", True),
    ("breathing speed 1",     ["effect=breathing", "breathing.speed=1"], "slow breathing", False),
    ("breathing speed 3",     ["effect=breathing", "breathing.speed=3"], "faster breathing", False),
    ("breathing 7 colors",    ["effect=breathing", "breathing.colors=ff0000,00ff00,0000ff,ffff00,ff00ff,00ffff,ffffff"], "breathes through red, green, blue, yellow, magenta, cyan, white", False),
    ("tail speed 1",          ["effect=tail", "tail.speed=1"], "slow tail effect", False),
    ("tail speed 3",          ["effect=tail", "tail.speed=3"], "faster tail effect", False),
    ("neon speed 1",          ["effect=neon", "neon.speed=1"], "slow neon effect", False),
    ("neon speed 3",          ["effect=neon", "neon.speed=3"], "faster neon effect", False),
    ("flicker green+purple",  ["effect=flicker", "flicker.colors=00ff00,ff00ff"], "flickers between green and magenta", False),
    ("stars speed 1",         ["effect=stars", "stars.speed=1"], "slow twinkling", False),
    ("stars speed 3",         ["effect=stars", "stars.speed=3"], "faster twinkling", False),
    ("wave speed 1",          ["effect=wave", "wave.speed=1"], "slow wave", False),
    ("wave speed 3",          ["effect=wave", "wave.speed=3"], "faster wave", False),
    ("poll 125",              ["poll=125"], "open a mouse polling-rate test page: it reads about 125 Hz", False),
    ("poll 500",              ["poll=500"], "polling-rate test page reads about 500 Hz", False),
    ("poll 1000",             ["poll=1000"], "polling-rate test page reads about 1000 Hz", False),
    ("dpi 3 levels",          ["dpi.enabled=1,2,3", "dpi.active=1"], "press the DPI button repeatedly: it cycles through only 3 levels", False),
    ("dpi level 3 off",       ["dpi3.enabled=toggle"], "now it cycles through only 2 levels", True),
    ("dpi colors",            ["dpi.enabled=1,2", "dpi.active=1", "dpi1.color=ffffff", "dpi2.color=ff00ff"], "press the DPI button: the indicator flashes white and magenta", False),
    ("dpi 400 only",          ["dpi.enabled=1", "dpi.active=1", "dpi1=400"], "pointer is very slow", False),
    ("dpi 10000 only",        ["dpi.enabled=1", "dpi.active=1", "dpi1=10000"], "pointer is extremely fast", False),
    ("dpi active level 2",    ["dpi.enabled=1,2,3", "dpi.active=2"], "informational: press the DPI button once and note which level/color you get (level 3 expected if the mouse took level 2 as active)", False),
]

def main():
    args = sys.argv[1:]
    rep.PLAIN = "--plain" in args
    words = [a.lower() for a in args if not a.startswith("--")]
    tests = [t for t in TESTS if not words or any(w in t[0].lower() for w in words)]
    if "--list" in args:
        for i, t in enumerate(tests, 1): print(f"{i:2d}. {t[0]:24s} {' '.join(t[1])}")
        return
    import hid
    h5, h4 = rep.find(hid)
    if not (h5 and h4): sys.exit("Did not find the mouse handles (is the Reticos app closed?)")
    p0 = rep.read_profile(h5, h4)
    rep.save(p0)
    log, cur = [], p0

    def write(new):
        h4.send_feature_report(list(rep.build_write(new))); time.sleep(0.2)
        q = rep.read_profile(h5, h4)
        return q, q[8:] == new[8:]

    print(f"\n{len(tests)} tests. Your current profile is saved and will be restored at the end.")
    input("Press Enter to start... ")
    try:
        for i, (name, items, expect, chain) in enumerate(tests, 1):
            try: new = rep.apply_settings(cur if chain else p0, items)
            except ValueError as e:
                log.append((name, "ERROR", str(e))); print(f"\n[{i}/{len(tests)}] {name}: script error: {e}"); continue
            if new == cur:
                log.append((name, "SKIP", "mouse already in this state")); print(f"\n[{i}/{len(tests)}] {name}: already in this state, skipped"); continue
            print(f"\n[{i}/{len(tests)}] {name}\n  sets:   {' '.join(items)}\n  expect: {expect}")
            cur, ok = write(new)
            ans = input(f"  written ({'verify OK' if ok else 'VERIFY MISMATCH'}). Did it match? [y/n/s/q + note]: ").strip()
            a, note = (ans[:1].lower(), ans[1:].strip())
            if a == "q": log.append((name, "QUIT", "")); break
            log.append((name, {"y": "PASS", "n": "FAIL", "s": "SKIP"}.get(a, "?"), ("" if ok else "verify mismatch; ") + note))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        _, ok = write(p0)
        print(f"\nOriginal profile written back ({'verify OK' if ok else 'VERIFY MISMATCH - use: replicator.py restore the backup file --apply'}).")
    print("\n=== RESULTS (paste this to Claude) ===")
    for name, res, note in log: print(f"{res:5s} {name}" + (f"  -- {note}" if note else ""))

if __name__ == "__main__": main()