#!/usr/bin/env python3
"""Linux diagnostic for the Reticos: shows every hidraw node, and what each probe returns.
Read-only (it only asks the mouse for report 5 / report 4, like the driver's first steps).
Needs hid.py next to it.   sudo python3 diag.py"""
import glob, os, re, sys
import hid

print("python", sys.version.split()[0], "| hid module:", getattr(hid, "__file__", "?"))
print("kernel:", os.uname().release)

def attempt(label, fn):
    try:
        r = fn()
        print(f"    {label}: OK", (bytes(r).hex()[:60] + ("..." if len(bytes(r)) > 30 else "")) if isinstance(r, (list, bytes, bytearray)) else r)
        return r
    except Exception as e:
        print(f"    {label}: FAILED {type(e).__name__}: {e}")

print("\nall hidraw nodes:")
for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
    try: u = open(node + "/device/uevent").read()
    except OSError as e: print(" ", node, "unreadable", e); continue
    m = re.search(r"HID_ID=(\S+)", u); n = re.search(r"HID_NAME=(.*)", u)
    try: iface = open(node + "/device/../bInterfaceNumber").read().strip()
    except OSError: iface = "?"
    try: desc = open(node + "/device/report_descriptor", "rb").read()
    except OSError: desc = b""
    print(f"  {os.path.basename(node)}: {m.group(1) if m else '?'}  iface={iface}  name={n.group(1) if n else '?'}  descriptor={len(desc)} bytes")

print("\nReticos nodes (258A:003B):")
devs = hid.enumerate(0x258A, 0x003B)
if not devs: print("  none found by hid.enumerate()")
for d in devs:
    print(" ", d["path"], "iface", d["interface_number"])
    h = hid.device()
    if attempt("open", lambda: h.open_path(d["path"])) is None and h.fd is None: continue
    attempt("set report 5 cmd 01", lambda: h.send_feature_report([5, 1, 0, 0, 0, 0]))
    attempt("get report 5 (6)", lambda: h.get_feature_report(5, 6))
    for size in (520, 131, 130):
        attempt(f"get report 4 ({size})", lambda: h.get_feature_report(4, size))
    h.close()
    try:
        desc = open("/sys/class/hidraw/" + os.path.basename(d["path"]) + "/device/report_descriptor", "rb").read()
        print("    report descriptor:", desc.hex())
    except OSError: pass