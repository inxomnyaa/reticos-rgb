# reticos-rgb: project context

Owner: inxomnyaa (hobbyist; Bazzite Linux with GNOME/Wayland/NVIDIA, plus Windows).
Goal: control the lighting of a Speedlink Reticos mouse and a Das Keyboard 4Q without vendor software, ideally by adding support to OpenRGB so others benefit.

## Working rules
- Ask before expensive analysis or big changes; say what you will do first.
- Use "color", never "colour".
- Show output inline, not as downloadable archives.
- Verify command and parameter usage before giving it. Do not invent flags or env vars.
- Dry run by default. Anything that writes to the mouse needs `--apply`, and the user confirms visually that the mouse changed.
- Do not probe the interface 0 hidraw node (that is the mouse itself).

## Device 1: Speedlink Reticos (SL-680011-BK, rev "V3")
- USB 258a:003b, "SINOWEALTH Wired Gaming Mouse", generic Sinowealth "BY-COMBO2" OEM device.
- Config is HID feature reports on interface 1:
  - Report 5 (6 bytes) = command channel.
  - Report 4 (520 bytes) = profile.
  - The mouse answers a report 4 read according to the last report 5 command.
- Handshake:
  1. `05 01` answers `05 01 39 36 31 30` ("9610").
  2. `05 02`.
  3. `05 11`, then read report 4 (131 bytes, starts `04 11`).
- Write: send the whole profile as 520 bytes with b[3]=0x7b and b[6]=b[7]=0 (read-modify-write), then re-read and compare `q[8:] == new[8:]`.
- Byte map: EFFECT at 53 (1-based, 0 = none), LIGHTS on/off at 130, color-stream slots start at 86 (8 slots, 5 are real LEDs, slots 6-8 are dead). Bytes 61, 85 and 116 are unknown and never change.
- The setting survives reboot and is visible from BIOS on. Whether repeated writes wear flash is unknown, so rate-limit writes.
- LEDs: 1 is front, 2 is behind the scroll wheel, and 6-8 do nothing.

## Files
- `replicator.py`: read/write tool.
  - No args prints a read-only color tree.
  - Also: `show FILE.bin`, `set KEY=VALUE ... [--apply]`, `restore FILE.bin [--apply]`, plus `--plain` and `--save`.
  - Keys: effect, lights (on|off|toggle), poll, dpiN, dpiN.color, dpiN.enabled, dpi.enabled, dpi.active, stream.speed, stream.dir, steady.color, steady.brightness, breathing.speed, breathing.colors, tail.speed, neon.speed, stars.speed, wave.speed, flicker.colors, cs.colors.
  - `--apply` saves `reticos_backup_*.bin` first.
- `selftest.py`: 33 guided hardware tests. It restores the original profile at the end. All passed on Windows and Linux.
- `linux/hid.py`: hidraw-based stand-in for the `hid` module (ioctl HIDIOCSFEATURE nr 6, HIDIOCGFEATURE nr 7). Linux only, never put it on Windows.
- `diag.py`: Linux hidraw diagnostic.
- `70-reticos.rules`: `TAG+="uaccess"` udev rule.
- Run on Linux: `sudo env PYTHONPATH=linux python3 replicator.py`. On Windows: `pip install hidapi`.

## Open items
- Polling-rate accuracy: a browser tester reads about 350 at 500 Hz and about 520 at 1000 Hz, probably under-reporting.
- Unknown bytes 61, 85 and 116, and the `04 12` write.
- DPI step behavior between 5000 and 7000 is inferred from few data points. The slider runs 200-10000 in steps of 100 (500 above some point).
- The repo still needs `LICENSE` (MIT), `70-reticos.rules` and a first commit.

## Next step: OpenRGB controller for the Reticos
- Plan: 5 zones, OpenRGB modes mapped to the mouse's effects. DPI and polling rate stay in the Python script.
- Rate-limit writes, since flash wear is unknown.
- First check whether OpenRGB already has a Sinowealth controller to build on (OpenRGB lives on GitLab).
- Open question: can OpenRGB be built on Bazzite, for example in a distrobox?

## Device 2: Das Keyboard 4Q (later)
- Vendor 0x24F0. Keep the Q software only for firmware flashing.
- OpenRGB's `RGBController_DasKeyboard.cpp` has 131 LEDs. The special keys (sleep, Q button, brightness, play/pause, next) are LEDs 126-130, so nothing is missing.
- The user already submitted OpenRGB MR !3787 (a name fix).
- Wanted effects: the Das clock plugin, and a red/green mute indicator on the Q button via the OpenRGB SDK. Mode-change handling still needs checking.