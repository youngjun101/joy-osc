#!/usr/bin/env python3
"""
joy_osc_app.py - window app: preview DragonRise USB joysticks and send them as OSC.

Shows each controller's stick and buttons live while sending the same OSC
messages as joy_to_osc.py (addresses listed in joy_core.py).
Settings are remembered in ~/.joy_osc.json.
"""
import collections
import json
import os
import tkinter as tk
from tkinter import ttk

from joy_core import NUM_BUTTONS, OscSender, start_controllers

SETTINGS = os.path.join(os.path.expanduser("~"), ".joy_osc.json")
DEFAULTS = {"ip": "127.0.0.1", "port": 7000, "swap": False, "send": True}

BG, PANEL, LINE, DIM, TEXT, ON = "#1e1f22", "#2b2d31", "#4a4d55", "#80848e", "#e6e6e6", "#4fd18b"
PAD_SIZE = 150


def load_settings():
    try:
        with open(SETTINGS) as f:
            return {**DEFAULTS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_settings(s):
    try:
        with open(SETTINGS, "w") as f:
            json.dump(s, f)
    except OSError:
        pass


class ControllerPanel:
    """Stick pad + button lights for one controller."""

    def __init__(self, parent, ctrl):
        self.ctrl = ctrl
        self.frame = tk.Frame(parent, bg=PANEL, padx=14, pady=12)
        tk.Label(self.frame, text=f"joy{ctrl.num}", bg=PANEL, fg=TEXT,
                 font=("Helvetica", 16, "bold")).pack(anchor="w")
        self.status = tk.Label(self.frame, text="", bg=PANEL, fg=DIM, font=("Helvetica", 11))
        self.status.pack(anchor="w")

        s = PAD_SIZE
        self.pad = tk.Canvas(self.frame, width=s, height=s, bg=BG, highlightthickness=0)
        self.pad.pack(pady=(8, 4))
        self.pad.create_rectangle(2, 2, s - 2, s - 2, outline=LINE)
        self.pad.create_line(s / 2, 2, s / 2, s - 2, fill=LINE, dash=(2, 3))
        self.pad.create_line(2, s / 2, s - 2, s / 2, fill=LINE, dash=(2, 3))
        self.dot = self.pad.create_oval(0, 0, 0, 0, fill=ON, outline="")

        self.xy = tk.Label(self.frame, text="", bg=PANEL, fg=TEXT, font=("Menlo", 12))
        self.xy.pack()

        self.btns = tk.Canvas(self.frame, width=6 * 30, height=2 * 30, bg=PANEL, highlightthickness=0)
        self.btns.pack(pady=(8, 0))
        self.lights = []
        for i in range(NUM_BUTTONS):
            cx, cy = 15 + (i % 6) * 30, 15 + (i // 6) * 30
            o = self.btns.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, outline=LINE, fill=BG)
            t = self.btns.create_text(cx, cy, text=str(i + 1), fill=DIM, font=("Helvetica", 10))
            self.lights.append((o, t))
        self._shown = None

    def update(self):
        c = self.ctrl
        st = c.state
        if c.error:
            status = f"⚠ {c.error}"
        else:
            status = "connected" if c.connected else "opening…"
        key = (status, st["x"], st["y"], tuple(st["buttons"]))
        if key == self._shown:
            return
        self._shown = key
        self.status.config(text=status)

        s, r = PAD_SIZE, 10
        px = s / 2 + st["x"] * (s / 2 - r - 4)
        py = s / 2 - st["y"] * (s / 2 - r - 4)
        self.pad.coords(self.dot, px - r, py - r, px + r, py + r)
        self.xy.config(text=f"x {st['x']:+.2f}   y {st['y']:+.2f}")
        for (o, t), b in zip(self.lights, st["buttons"]):
            self.btns.itemconfig(o, fill=ON if b else BG, outline=ON if b else LINE)
            self.btns.itemconfig(t, fill=BG if b else DIM)


class App:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.log = collections.deque(maxlen=200)
        self.sender = OscSender(self.settings["ip"], self.settings["port"],
                                enabled=self.settings["send"], on_send=self._on_send)
        self.ctrls, self.panels = [], []
        self.error = None

        root.title("Joy OSC")
        root.configure(bg=BG)
        root.minsize(420, 360)
        # "clam" looks the same on macOS and Windows and takes custom colors
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, bordercolor=LINE,
                        lightcolor=PANEL, darkcolor=PANEL, focuscolor=LINE)
        style.configure("TButton", background=PANEL, padding=(10, 3))
        style.map("TButton", background=[("active", LINE)])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT)
        style.configure("TCheckbutton", indicatorbackground=PANEL, indicatorforeground=ON)
        style.map("TCheckbutton", background=[("active", BG)],
                  indicatorbackground=[("selected", PANEL)])

        bar = tk.Frame(root, bg=BG, padx=12, pady=10)
        bar.pack(fill="x")
        tk.Label(bar, text="Send to", bg=BG, fg=TEXT).pack(side="left")
        self.ip = tk.StringVar(value=self.settings["ip"])
        self.port = tk.StringVar(value=str(self.settings["port"]))
        ttk.Entry(bar, textvariable=self.ip, width=14).pack(side="left", padx=(6, 2))
        tk.Label(bar, text=":", bg=BG, fg=TEXT).pack(side="left")
        ttk.Entry(bar, textvariable=self.port, width=6).pack(side="left", padx=(2, 6))
        ttk.Button(bar, text="Apply", command=self.apply_target).pack(side="left")

        self.send = tk.BooleanVar(value=self.settings["send"])
        self.swap = tk.BooleanVar(value=self.settings["swap"])
        ttk.Checkbutton(bar, text="Send OSC", variable=self.send,
                        command=self.toggle_send).pack(side="left", padx=(14, 0))
        ttk.Checkbutton(bar, text="Swap 1↔2", variable=self.swap,
                        command=self.rescan).pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="Rescan", command=self.rescan).pack(side="left", padx=(8, 0))

        self.status = tk.Label(root, text="", bg=BG, fg=DIM, anchor="w", padx=12)
        self.status.pack(fill="x")

        self.area = tk.Frame(root, bg=BG, padx=12, pady=10)
        self.area.pack(fill="both", expand=True)
        self.empty = tk.Label(self.area, bg=BG, fg=DIM, font=("Helvetica", 13), justify="center",
                              text="No joysticks found.\nPlug them in and press Rescan.")

        tk.Label(root, text="Last OSC messages", bg=BG, fg=DIM, anchor="w", padx=12).pack(fill="x")
        self.logbox = tk.Text(root, height=6, bg=PANEL, fg=TEXT, relief="flat",
                              font=("Menlo", 11), padx=8, pady=6, state="disabled",
                              highlightthickness=0)
        self.logbox.pack(fill="x", padx=12, pady=(2, 6))
        tk.Label(root, text="TouchDesigner: add an OSC In CHOP and set its Network Port to the port above.",
                 bg=BG, fg=DIM, anchor="w", padx=12).pack(fill="x", pady=(0, 10))

        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.rescan()
        self.tick()

    def _on_send(self, addr, value):
        self.log.append(f"{addr} {value}")  # called from reader threads

    def apply_target(self):
        try:
            port = int(self.port.get())
            if not 0 < port < 65536:
                raise ValueError
        except ValueError:
            self.error = "Port must be a number from 1 to 65535."
            return
        ip = self.ip.get().strip() or "127.0.0.1"
        try:
            self.sender.set_target(ip, port)
        except OSError as e:
            self.error = f"Can't send to {ip}: {e}"
            return
        self.error = None
        self.settings.update(ip=ip, port=port)
        save_settings(self.settings)
        for c in self.ctrls:
            c.resend_all()

    def toggle_send(self):
        self.sender.enabled = self.send.get()
        self.settings["send"] = self.sender.enabled
        save_settings(self.settings)
        for c in self.ctrls:
            c.resend_all()

    def rescan(self):
        for c in self.ctrls:
            c.stop()
        for p in self.panels:
            p.frame.destroy()
        self.empty.pack_forget()
        self.settings["swap"] = self.swap.get()
        save_settings(self.settings)

        self.ctrls = start_controllers(self.sender, self.swap.get())
        self.panels = [ControllerPanel(self.area, c) for c in self.ctrls]
        for i, p in enumerate(self.panels):
            p.frame.grid(row=i // 2, column=i % 2, padx=6, pady=6, sticky="n")
        if not self.ctrls:
            self.empty.pack(expand=True)

    def tick(self):
        for p in self.panels:
            p.update()
        if self.sender.enabled:
            msg = f"Sending to {self.sender.ip}:{self.sender.port}"
        else:
            msg = "Preview only (Send OSC is off)"
        if self.error:
            self.status.config(text=self.error, fg="#f07070")
        else:
            self.status.config(text=f"{msg}   ·   {len(self.ctrls)} controller(s)   ·   "
                                    f"{self.sender.count} messages", fg=DIM)
        if self.log:
            lines = []
            while self.log:
                lines.append(self.log.popleft())
            self.logbox.config(state="normal")
            self.logbox.insert("end", "\n".join(lines) + "\n")
            self.logbox.delete("1.0", "end-60l")
            self.logbox.see("end")
            self.logbox.config(state="disabled")
        self.root.after(30, self.tick)

    def quit(self):
        for c in self.ctrls:
            c.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
