"""
joy_core.py - read DragonRise USB joysticks and send them as OSC.

Shared by joy_to_osc.py (command line) and joy_osc_app.py (window).

OSC addresses (N = controller number 1, 2, ...), sent on change:
  /joyN/x              float  -1 left .. 1 right
  /joyN/y              float  -1 down .. 1 up
  /joyN/b1../joyN/b12  int    1 pressed, 0 released
"""
import plistlib
import subprocess
import sys
import threading

import hid
from pythonosc.udp_client import SimpleUDPClient

VID, PID = 0x0079, 0x0006
NUM_BUTTONS = 12


def _mac_usb_locations():
    """macOS: HID registry id -> USB port LocationID, for stable numbering."""
    try:
        out = subprocess.run(["ioreg", "-r", "-c", "IOHIDDevice", "-a"],
                             capture_output=True, check=True).stdout
        return {d["IORegistryEntryID"]: d.get("LocationID", 0)
                for d in plistlib.loads(out) if "IORegistryEntryID" in d}
    except Exception:
        return {}


def _sort_key(d, locs):
    # macOS paths look like "DevSrvsID:4295007337"; Windows paths include the
    # USB instance id, which follows the port, so sorting by path works there.
    path = d["path"].decode(errors="replace")
    reg_id = int(path.split(":")[1]) if path.startswith("DevSrvsID:") else 0
    return (locs.get(reg_id, 0), path)


def find_joysticks(swap=False):
    locs = _mac_usb_locations() if sys.platform == "darwin" else {}
    devs = [d for d in hid.enumerate(VID, PID) if d["usage_page"] == 0x01]
    return sorted(devs, key=lambda d: _sort_key(d, locs), reverse=swap)


def axis(v):
    return max(-1.0, min(1.0, round((v - 127) / 127, 3)))  # 0/127/255 -> -1/0/1


class Controller:
    """One joystick. Reads in a background thread; `state` is the latest input."""

    def __init__(self, num, info, sender):
        self.num = num
        self.info = info
        self.sender = sender
        self.prefix = f"/joy{num}"
        self.state = {"x": 0.0, "y": 0.0, "buttons": [0] * NUM_BUTTONS}
        self.connected = False
        self.error = None
        self._last = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def _send(self, addr, value):
        if self._last.get(addr) != value:
            self._last[addr] = value
            self.sender.send(self.prefix + addr, value)

    def _run(self):
        dev = hid.device()
        try:
            dev.open_path(self.info["path"])
        except OSError as e:
            self.error = str(e)
            return
        self.connected = True
        try:
            while not self._stop.is_set():
                r = dev.read(64, timeout_ms=200)
                if len(r) < 7:
                    continue
                x = axis(r[0])
                y = -axis(r[1]) or 0.0  # byte goes up when stick goes down
                bits = (r[5] >> 4) | (r[6] << 4)  # buttons 1-4 in byte 5, 5-12 in byte 6
                buttons = [(bits >> i) & 1 for i in range(NUM_BUTTONS)]
                self.state = {"x": x, "y": y, "buttons": buttons}
                self._send("/x", x)
                self._send("/y", y)
                for i, b in enumerate(buttons):
                    self._send(f"/b{i + 1}", b)
        except OSError:
            self.error = "disconnected"
        finally:
            self.connected = False
            dev.close()

    def resend_all(self):
        """Forget what was sent so every value goes out again."""
        self._last.clear()


class OscSender:
    def __init__(self, ip="127.0.0.1", port=7000, enabled=True, on_send=None):
        self.enabled = enabled
        self.on_send = on_send
        self.count = 0
        self._lock = threading.Lock()
        self.set_target(ip, port)

    def set_target(self, ip, port):
        with self._lock:
            self.ip, self.port = ip, port
            self._client = SimpleUDPClient(ip, port)

    def send(self, addr, value):
        with self._lock:
            if not self.enabled:
                return
            try:
                self._client.send_message(addr, value)
            except OSError:
                return
            self.count += 1
        if self.on_send:
            self.on_send(addr, value)


def start_controllers(sender, swap=False):
    ctrls = [Controller(n, d, sender) for n, d in enumerate(find_joysticks(swap), 1)]
    for c in ctrls:
        c.start()
    return ctrls
