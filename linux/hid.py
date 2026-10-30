"""Tiny Linux-only stand-in for the `hid` (hidapi) module, using /dev/hidraw* directly.
Save it as hid.py next to replicator.py and selftest.py on Linux. No pip install needed.
Only implements what replicator.py uses: enumerate(), device().open_path/send_feature_report/
get_feature_report/close."""
import fcntl, glob, os, re

SYSFS = "/sys/class/hidraw"

def _ioc(nr, size):                          # _IOC(_IOC_WRITE|_IOC_READ, 'H', nr, size)
    return (3 << 30) | (size << 16) | (ord("H") << 8) | nr

def HIDIOCSFEATURE(size): return _ioc(0x06, size)
def HIDIOCGFEATURE(size): return _ioc(0x07, size)

def enumerate(vid=0, pid=0):
    out = []
    for node in sorted(glob.glob(SYSFS + "/hidraw*")):
        try: uevent = open(node + "/device/uevent").read()
        except OSError: continue
        m = re.search(r"HID_ID=([0-9A-Fa-f]+):([0-9A-Fa-f]+):([0-9A-Fa-f]+)", uevent)
        if not m: continue
        v, p = int(m.group(2), 16), int(m.group(3), 16)
        if (vid and v != vid) or (pid and p != pid): continue
        try: iface = int(open(node + "/device/../bInterfaceNumber").read().strip(), 16)
        except (OSError, ValueError): iface = None
        out.append({"path": "/dev/" + os.path.basename(node), "vendor_id": v, "product_id": p,
                    "interface_number": iface, "usage_page": 0, "usage": 0})
    return out

class device:
    def __init__(self): self.fd = None

    def open_path(self, path):
        if isinstance(path, bytes): path = path.decode()
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)

    def close(self):
        if self.fd is not None: os.close(self.fd); self.fd = None

    def send_feature_report(self, data):     # data[0] is the report ID, like hidapi
        buf = bytearray(data)
        return fcntl.ioctl(self.fd, HIDIOCSFEATURE(len(buf)), buf, True)

    def get_feature_report(self, report_id, max_length):
        buf = bytearray(max_length); buf[0] = report_id
        n = fcntl.ioctl(self.fd, HIDIOCGFEATURE(max_length), buf, True)
        return list(buf[:n])