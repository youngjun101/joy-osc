#!/usr/bin/env python3
"""
controller_probe.py - see what a USB joystick / button console sends.

Two modes:
  raw   (default)  Reads raw HID reports with hidapi and prints every byte.
                   Bytes that changed since the last report are highlighted,
                   so you can press one button at a time and see which
                   byte/bit it flips.
  game             Uses pygame (SDL) to show decoded axes / buttons / hats,
                   the way a game or app would see it.

Usage:
  python controller_probe.py --list              # list HID devices
  python controller_probe.py                     # auto-pick a joystick, raw mode
  python controller_probe.py --vid 0x0079 --pid 0x0006
  python controller_probe.py --mode game
  python controller_probe.py --log out.csv       # also save reports to CSV

Install:  pip install hidapi pygame
"""
import argparse
import csv
import sys
import time

# HID usage page 0x01 (Generic Desktop), usage 0x04 joystick / 0x05 gamepad
JOYSTICK_USAGES = {0x04, 0x05, 0x08}

HL = "\033[1;33;41m"  # highlight changed bytes
DIM = "\033[2m"
RST = "\033[0m"


def list_devices():
    import hid
    devs = hid.enumerate()
    if not devs:
        print("No HID devices found.")
        return
    print(f"{'VID':>6} {'PID':>6}  {'page':>6} {'usage':>5}  product / manufacturer")
    for d in devs:
        tag = "  <-- joystick/gamepad" if (
            d["usage_page"] == 0x01 and d["usage"] in JOYSTICK_USAGES) else ""
        print(f"0x{d['vendor_id']:04x} 0x{d['product_id']:04x}  "
              f"0x{d['usage_page']:04x} 0x{d['usage']:02x}   "
              f"{d['product_string'] or '?'} / {d['manufacturer_string'] or '?'}{tag}")


def pick_device(vid, pid):
    import hid
    devs = hid.enumerate(vid or 0, pid or 0)
    if not vid:
        devs = [d for d in devs
                if d["usage_page"] == 0x01 and d["usage"] in JOYSTICK_USAGES]
    if not devs:
        sys.exit("No matching joystick/gamepad found. Try --list, then --vid/--pid.")
    d = devs[0]
    print(f"Using: {d['product_string']} ({d['manufacturer_string']}) "
          f"VID=0x{d['vendor_id']:04x} PID=0x{d['product_id']:04x}")
    return d


def bits(b):
    return format(b, "08b")


HATS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def decode_dragonrise(r):
    """Common layout for DragonRise 0x0079 'Generic USB Joystick' encoders
    (8-byte report). Verify against the raw view - some boards differ."""
    if len(r) < 7:
        return None
    axes = " ".join(f"a{i}={r[i]:3}" for i in range(5))
    hat = r[5] & 0x0F
    hat_s = HATS[hat] if hat < 8 else "-"
    pressed = [i + 1 for i in range(4) if r[5] & (0x10 << i)]
    pressed += [i + 5 for i in range(8) if r[6] & (1 << i)]
    return f"  decoded: {axes}  hat={hat_s}  buttons={pressed or '-'}"


def run_raw(args):
    import hid
    info = pick_device(args.vid, args.pid)
    dev = hid.device()
    try:
        dev.open_path(info["path"])
    except OSError as e:
        sys.exit(f"Could not open device: {e}\n"
                 "On macOS you may need to allow Input Monitoring for your terminal "
                 "(System Settings > Privacy & Security > Input Monitoring).")
    dev.set_nonblocking(False)

    writer = None
    if args.log:
        f = open(args.log, "w", newline="")
        writer = csv.writer(f)
        writer.writerow(["time_s", "report_hex"])

    print("Move the stick / press buttons one at a time. Ctrl+C to quit.")
    print("Changed bytes are highlighted; the bit row shows exactly which bit flipped.\n")

    # axis bytes jitter by a count or two at rest; only report bigger moves
    axis_bytes = set(range(5)) if info["vendor_id"] == 0x0079 else set()

    def significant(data, prev):
        if prev is None or len(data) != len(prev):
            return True
        for i, (a, b) in enumerate(zip(data, prev)):
            if a == b:
                continue
            if i in axis_bytes and abs(a - b) <= args.noise:
                continue
            return True
        return False

    prev = None
    t0 = time.time()
    try:
        while True:
            data = dev.read(64, timeout_ms=1000)
            if not data:
                continue
            if not args.all and not significant(data, prev):
                continue

            t = time.time() - t0
            idx = " ".join(f"{i:>3}" for i in range(len(data)))
            hexs, bitl = [], []
            for i, b in enumerate(data):
                changed = prev is not None and (i >= len(prev) or prev[i] != b)
                hexs.append(f"{HL}{b:>3}{RST}" if changed else f"{b:>3}")
                if changed:
                    bitl.append(f"  byte {i}: {bits(prev[i]) if i < len(prev) else '--------'}"
                                f" -> {bits(b)}  ({prev[i] if i < len(prev) else '-'} -> {b})")
            print(f"{DIM}[{t:8.3f}s] idx {idx}{RST}")
            print(f"            val {' '.join(hexs)}")
            for line in bitl:
                print(line)
            if info["vendor_id"] == 0x0079:
                print(decode_dragonrise(data))
            print()

            if writer:
                writer.writerow([f"{t:.4f}", bytes(data).hex(" ")])
            prev = data
    except KeyboardInterrupt:
        pass
    finally:
        dev.close()
        if writer:
            f.close()
            print(f"Saved log to {args.log}")


def run_game(args):
    import os
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    pygame.init()
    # pygame needs a display on macOS for joystick events to arrive
    pygame.display.set_mode((240, 60))
    pygame.display.set_caption("controller_probe")
    clock = pygame.time.Clock()

    # joysticks are announced via JOYDEVICEADDED after the event loop starts
    deadline = time.time() + 3
    while pygame.joystick.get_count() <= args.index and time.time() < deadline:
        pygame.event.pump()
        clock.tick(30)
    if pygame.joystick.get_count() <= args.index:
        sys.exit("pygame sees no joystick. Use raw mode instead.")
    js = pygame.joystick.Joystick(args.index)
    js.init()
    print(f"Using: {js.get_name()}  axes={js.get_numaxes()} "
          f"buttons={js.get_numbuttons()} hats={js.get_numhats()}")
    print("Ctrl+C to quit.\n")
    try:
        while True:
            for e in pygame.event.get():
                if e.type == pygame.JOYAXISMOTION:
                    if abs(e.value) > args.deadzone or abs(e.value) < 0.01:
                        print(f"axis {e.axis}: {e.value:+.3f}")
                elif e.type == pygame.JOYBUTTONDOWN:
                    print(f"button {e.button}: DOWN")
                elif e.type == pygame.JOYBUTTONUP:
                    print(f"button {e.button}: up")
                elif e.type == pygame.JOYHATMOTION:
                    print(f"hat {e.hat}: {e.value}")
            clock.tick(250)
    except KeyboardInterrupt:
        pass
    finally:
        pygame.quit()


def parse_int(s):
    return int(s, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list HID devices and exit")
    ap.add_argument("--mode", choices=["raw", "game"], default="raw")
    ap.add_argument("--vid", type=parse_int, help="vendor id, e.g. 0x0079")
    ap.add_argument("--pid", type=parse_int, help="product id, e.g. 0x0006")
    ap.add_argument("--all", action="store_true", help="raw: print every report, not only changes")
    ap.add_argument("--log", help="raw: save reports to this CSV file")
    ap.add_argument("--noise", type=int, default=3,
                    help="raw: ignore axis changes this small (default 3)")
    ap.add_argument("--index", type=int, default=0, help="game: joystick index")
    ap.add_argument("--deadzone", type=float, default=0.05, help="game: axis noise filter")
    args = ap.parse_args()

    if args.list:
        list_devices()
    elif args.mode == "raw":
        run_raw(args)
    else:
        run_game(args)


if __name__ == "__main__":
    main()
