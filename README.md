# 3D Flowers (Python Turtle)

An interactive 3D flower viewer built in pure Python (`turtle` + `tkinter`) with **zero external dependencies**.

> **Note:** The whole project was fully made with **Antigravity**.

## What's Inside

- **5 Flower Species** — Rose, Tulip, Lotus, Sunflower, and Sakura, each with an opening bloom animation and multiple color varieties (cultivars).
- **4 Lighting Moods** — Daylight, Golden, Sage, and Twilight (dark mode).
- **Interactive Motion** — Toggleable gentle wind breeze, live **Speed** and **Bloom** sliders, and smooth mouse orbit and zoom.
- **Detail Modes** — Switch between **Standard** (60 FPS) and **Lush** (higher detail) anytime.
- **On-Screen HUD** — Clickable pills and sliders styled with bundled `Google Sans` fonts and `Material Symbols` icons, plus a custom window icon.

## Run

Requires **Python 3.10+** with standard `tkinter`/`turtle` support (no `pip install` needed):

```bash
python flowers_3d.py
```

On Windows, the app automatically detaches via `pythonw.exe` so no terminal window stays open behind it (pass `--no-detach` to keep console output).

## Controls

Click the on-screen HUD buttons/sliders directly, or use keyboard and mouse shortcuts:

| Input | Action |
| --- | --- |
| **Mouse Drag** / **Arrow Keys** | Orbit and tilt camera |
| **Mouse Wheel** / **`+`** **`-`** | Zoom in and out |
| **Speed / Bloom Sliders** | Adjust spin speed (`1.0x`–`5.0x`) or bloom (`0%`–`100%`) |
| **`Shift + Scroll`** | Adjust bloom openness (`±5%`) |
| **`1`–`5`** / **`F`** | Pick or cycle flower (Rose, Tulip, Lotus, Sunflower, Sakura) |
| **`C`** | Cycle color variety (cultivar) |
| **`M`** | Cycle lighting mood (Daylight, Golden, Sage, Twilight) |
| **`W`** | Toggle wind breeze |
| **`D`** | Toggle Standard / Lush detail |
| **`Space`** | Pause / resume auto-rotation |
| **`B`** / **`R`** | Replay bloom (`B`) or reset view (`R`) |
| **`F11`** / **`Esc`** | Toggle fullscreen (`F11`) or exit (`Esc`) |

## Project Structure

```text
Draw-a-flower/
├── flowers_3d.py        # 3D flower geometry, lighting, animation, HUD & app loop
├── README.md            # Project guide
├── .gitignore           # Ignores __pycache__ and compiled Python files
└── assets/
    ├── rose_icon.png    # App icon (PNG)
    ├── rose_icon.ico    # Windows window & taskbar icon
    ├── fonts/           # Bundled Google Sans fonts & OFL.txt
    └── icons/           # 13 HUD icons & Apache-2.0 LICENSE
```

## Credits

- **Antigravity**: This whole project was fully made with Antigravity.
- **Fonts & Icons**: `Google Sans` ([`OFL.txt`](assets/fonts/OFL.txt)) and `Google Material Symbols` ([`LICENSE`](assets/icons/LICENSE)).
