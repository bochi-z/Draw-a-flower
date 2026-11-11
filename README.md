# 3D Rotating Rose (Python Turtle)

An interactive 3D layered scarlet rose rendered using Python's standard-library `turtle` module with zero external runtime dependencies.

> **Note:** The whole project was fully made with **Antigravity**.

## Features

- **3D Botanical Rose Geometry**:
  - 26 overlapping cupped petals arranged along a golden-angle phyllotaxis spiral (`137.5°`).
  - Floral receptacle, 5 reflexed calyx sepals, curved stem, 3 thorns, and 3 V-folded leaves attached directly to the stem.
- **Overhead Startup Bloom & Camera Tween**: Starts looking down into the opening rosebud over ~2.6 seconds, then smoothly glides down to a 3/4 view over ~1.6 seconds.
- **Smooth 3D Shading & 60 FPS Pooled Rendering**:
  - Double-sided petal lighting with wrapped diffuse illumination, soft cream bounce light, velvety specular sheen, and inner-petal ambient occlusion.
  - Back-to-front depth sorting (`build_draw_list`) rendered into a reusable `turtle` polygon pool locked to 60 FPS onto a `600×600` soft-cream canvas (`#FAF5EC`).
- **Translucent HUD, Speed Slider & FPS Counter (`Google Sans` + `Material Symbols`)**:
  - Top-left FPS badge, bottom translucent frosted control pill, and an interactive **Speed** slider pill stacked directly above the controls HUD (`1.0x`–`5.0x` rotation speed) rendered with bundled `Google Sans` fonts (`assets/fonts/`) and `Google Material Symbols` icons (`assets/icons/`).
  - HUD controls start dimmed/locked during the intro bloom & camera tween and fade smoothly to warm cream once interactive.
- **Custom 1:1 Window & Taskbar Icon**:
  - Minimalist scarlet rose squircle icon saved in `assets/rose_icon.png` (`1024×1024` master PNG) and `assets/rose_icon.ico` (multi-resolution Windows icon), wired into `rose_3d.py` via `wm_iconbitmap` (with Windows AppUserModelID) and `wm_iconphoto` fallback.
- **Interactive Camera & Playback Controls**:
  - **Speed slider** (above the bottom controls HUD): Click or drag to adjust auto-rotation speed between `1.0x` and `5.0x`
  - **Mouse drag**: Orbit horizontally (yaw) and tilt vertically (pitch)
  - **Mouse wheel** (or `+` / `-`): Zoom in and out
  - **Arrow keys**: Fine camera orbit and tilt
  - **`Space`**: Pause / resume auto-rotation
  - **`B`**: Replay the bud-to-bloom unfurling animation
  - **`R`**: Reset to the startup bloom and camera animation
  - **`F11`**: Toggle fullscreen mode
  - **`Esc`**: Exit fullscreen (or close the window when windowed)

## Running

Requires Python 3.10+ with standard-library `tkinter`/`turtle` support (no `pip install` needed):

```bash
python rose_3d.py
```

On Windows, `rose_3d.py` automatically relaunches detached via `pythonw.exe` so no console window stays open behind the main window (pass `--no-detach` to stay attached to the terminal for debugging).

## Credits

- **Antigravity**: This whole project was fully made with Antigravity.
- **Bundled Assets**:
  - `Google Sans` fonts (`assets/fonts/OFL.txt`, SIL Open Font License 1.1)
  - `Google Material Symbols` icons (`assets/icons/LICENSE`, Apache License 2.0)
