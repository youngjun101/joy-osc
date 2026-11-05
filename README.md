# Joy OSC

Turns DragonRise "Generic USB Joystick" controllers (VID 0x0079, PID 0x0006)
into OSC messages for TouchDesigner or any other OSC app, with a live preview
window. It supports several identical controllers at once.

## Download and run

| System | File | How to open |
|---|---|---|
| Windows 10/11 | `Joy-OSC-windows.exe` | Double-click it. No install needed. If Windows SmartScreen appears, click **More info → Run anyway**. |
| Mac (Apple Silicon: M1–M4…) | `Joy-OSC-mac-arm64.zip` | Unzip it, then drag **Joy OSC** into Applications. The first time, **right-click → Open**, then click **Open**. |
| Mac (Intel) | `Joy-OSC-mac-x86_64.zip` | Same as above. |

To check which Mac you have, open the Apple menu → About This Mac. "Chip: Apple M…" means Apple Silicon.

If macOS says the app "can't be opened", go to **System Settings → Privacy & Security**,
scroll down, and click **Open Anyway**. This happens because the app isn't signed
with a paid Apple developer certificate.

## Using it

1. Plug in the controllers, then open Joy OSC.
2. Each controller gets a panel showing its stick and buttons as you use them.
3. Set **Send to** to the TouchDesigner computer's IP (`127.0.0.1` if it's the same computer) and port, then click **Apply**.
4. In TouchDesigner, add an **OSC In CHOP** and set its **Network Port** to the same port (default 7000).

- **Swap 1↔2** switches the controller numbers.
- **Rescan** picks up controllers plugged in after the app started.
- **Send OSC** off means preview only.
- Settings are remembered between launches.

Controllers are numbered by the USB port they're plugged into, so keep each one in
the same port and the numbers stay the same.

## OSC messages

Sent only when a value changes. `N` is the controller number (1, 2, …).

| Address | Type | Value |
|---|---|---|
| `/joyN/x` | float | -1 left, 0 center, 1 right |
| `/joyN/y` | float | -1 down, 0 center, 1 up |
| `/joyN/b1` … `/joyN/b12` | int | 1 pressed, 0 released |

## Building the downloads

The Windows `.exe` must be built on Windows, and each Mac version on that kind of Mac.

- **All three at once (easiest):** put this folder in a GitHub repository. Open the **Actions** tab → **build** → **Run workflow**. The files appear under the finished run's *Artifacts*. Push a tag such as `v1.0` to also publish them as a GitHub Release.
- **Mac, locally:** run `./build_mac.sh`. Output: `releases/Joy-OSC-mac-<chip>.zip`.
- **Windows, locally:** double-click `build_windows.bat`. Output: `releases\Joy-OSC-windows.exe`.

Both scripts install everything they need (uv, Python 3.12, PyInstaller) on first run.

## Files

| File | What it is |
|---|---|
| `joy_osc_app.py` | The window app |
| `joy_to_osc.py` | Same thing without a window: `python joy_to_osc.py [--ip …] [--port …] [--swap]` |
| `joy_core.py` | Shared controller reading and OSC sending |
| `controller_probe.py` | Raw byte viewer for working out what a new controller sends |
