#!/usr/bin/env python3
"""
joy_to_osc.py - DragonRise USB joysticks -> OSC, command-line version.
See joy_osc_app.py for the window version. Addresses are listed in joy_core.py.

Usage:  python joy_to_osc.py [--ip 127.0.0.1] [--port 7000] [--swap]
Install: pip install -r requirements.txt
"""
import argparse
import time

from joy_core import OscSender, start_controllers

ap = argparse.ArgumentParser()
ap.add_argument("--ip", default="127.0.0.1")
ap.add_argument("--port", type=int, default=7000)
ap.add_argument("--swap", action="store_true", help="reverse controller numbering")
args = ap.parse_args()

sender = OscSender(args.ip, args.port, on_send=lambda a, v: print(a, v))
ctrls = start_controllers(sender, args.swap)
if not ctrls:
    raise SystemExit("No joysticks found.")
print(f"Sending OSC to {args.ip}:{args.port} from {len(ctrls)} controller(s)  (Ctrl+C to quit)")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    for c in ctrls:
        c.stop()
