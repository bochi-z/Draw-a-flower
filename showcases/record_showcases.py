"""Script to record gameplay GIFs of 3D Flowers and save them to showcases/."""

from __future__ import annotations

import array
import ctypes
from ctypes import byref, create_string_buffer, wintypes
import math
import os
import struct
import sys
import time
from collections import Counter
from pathlib import Path

# Ensure parent directory is on sys.path when executed directly from inside showcases/
_PARENT_DIR = Path(__file__).resolve().parent.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

import flowers_3d


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def encode_lzw(pixels: bytes, min_code_size: int = 8) -> bytes:
    clear_code = 1 << min_code_size
    end_code = clear_code + 1
    code_size = min_code_size + 1
    max_code = 1 << code_size
    code_table = {bytes([i]): i for i in range(clear_code)}
    next_code = end_code + 1
    stream = bytearray()
    bit_buf = 0
    bit_count = 0

    def write_bits(code: int, length: int) -> None:
        nonlocal bit_buf, bit_count
        bit_buf |= code << bit_count
        bit_count += length
        while bit_count >= 8:
            stream.append(bit_buf & 0xFF)
            bit_buf >>= 8
            bit_count -= 8

    write_bits(clear_code, code_size)
    pattern = b""
    for p in pixels:
        c = bytes([p])
        pc = pattern + c
        if pc in code_table:
            pattern = pc
        else:
            write_bits(code_table[pattern], code_size)
            if next_code < 4096:
                code_table[pc] = next_code
                next_code += 1
                if next_code > max_code and code_size < 12:
                    code_size += 1
                    max_code = 1 << code_size
            else:
                write_bits(clear_code, code_size)
                code_table = {bytes([i]): i for i in range(clear_code)}
                next_code = end_code + 1
                code_size = min_code_size + 1
                max_code = 1 << code_size
            pattern = c
    if pattern:
        write_bits(code_table[pattern], code_size)
    write_bits(end_code, code_size)
    if bit_count > 0:
        stream.append(bit_buf & 0xFF)

    out = bytearray()
    i = 0
    slen = len(stream)
    while i < slen:
        chunk = stream[i : i + 254]
        out.append(len(chunk))
        out.extend(chunk)
        i += len(chunk)
    out.append(0)
    return bytes(out)


def quantize_median_cut(
    color_counts: dict[int, int], max_colors: int = 256
) -> tuple[list[tuple[int, int, int]], dict[int, int]]:
    if len(color_counts) <= max_colors:
        palette = []
        mapping = {}
        for idx, val in enumerate(color_counts.keys()):
            r = (val >> 16) & 0xFF
            g = (val >> 8) & 0xFF
            b = val & 0xFF
            palette.append((r, g, b))
            mapping[val] = idx
        while len(palette) < max_colors:
            palette.append((0, 0, 0))
        return palette, mapping

    items = []
    for val, count in color_counts.items():
        r = (val >> 16) & 0xFF
        g = (val >> 8) & 0xFF
        b = val & 0xFF
        items.append((val, count, r, g, b))

    boxes = [items]
    while len(boxes) < max_colors:
        best_box_idx = -1
        best_range = -1
        best_ch_idx = 2
        for idx, box in enumerate(boxes):
            if len(box) <= 1:
                continue
            r_vals = [it[2] for it in box]
            g_vals = [it[3] for it in box]
            b_vals = [it[4] for it in box]
            ranges = [
                max(r_vals) - min(r_vals),
                max(g_vals) - min(g_vals),
                max(b_vals) - min(b_vals),
            ]
            max_r = max(ranges)
            if max_r > best_range:
                best_range = max_r
                best_box_idx = idx
                best_ch_idx = 2 + ranges.index(max_r)
        if best_box_idx == -1 or best_range == 0:
            break
        box_to_split = boxes.pop(best_box_idx)
        box_to_split.sort(key=lambda it: it[best_ch_idx])
        total = sum(it[1] for it in box_to_split)
        running = 0
        split_idx = len(box_to_split) // 2
        for i, it in enumerate(box_to_split):
            running += it[1]
            if running >= total // 2:
                split_idx = max(1, min(i, len(box_to_split) - 1))
                break
        boxes.append(box_to_split[:split_idx])
        boxes.append(box_to_split[split_idx:])

    palette = []
    mapping = {}
    for palette_idx, box in enumerate(boxes):
        total_w = sum(it[1] for it in box) or 1
        avg_r = int(sum(it[2] * it[1] for it in box) / total_w)
        avg_g = int(sum(it[3] * it[1] for it in box) / total_w)
        avg_b = int(sum(it[4] * it[1] for it in box) / total_w)
        palette.append((avg_r, avg_g, avg_b))
        for it in box:
            mapping[it[0]] = palette_idx

    while len(palette) < max_colors:
        palette.append((0, 0, 0))

    return palette, mapping


class GifRecorder:
    def __init__(self, app: flowers_3d.FlowerViewerApp, delay_cs: int = 10) -> None:
        self.app = app
        self.delay_cs = delay_cs
        self.w = app._tk_canvas.winfo_width()
        self.h = app._tk_canvas.winfo_height()
        self.hwnd = app._tk_canvas.winfo_id()

        self.user32 = ctypes.windll.user32
        self.gdi32 = ctypes.windll.gdi32
        self.hdc_win = self.user32.GetDC(self.hwnd)
        self.hdc_mem = self.gdi32.CreateCompatibleDC(self.hdc_win)
        self.hbm = self.gdi32.CreateCompatibleBitmap(self.hdc_win, self.w, self.h)
        self.old_bmp = self.gdi32.SelectObject(self.hdc_mem, self.hbm)

        self.bmi = BITMAPINFO()
        self.bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        self.bmi.bmiHeader.biWidth = self.w
        self.bmi.bmiHeader.biHeight = -self.h
        self.bmi.bmiHeader.biPlanes = 1
        self.bmi.bmiHeader.biBitCount = 32
        self.bmi.bmiHeader.biCompression = 0
        self.buf = create_string_buffer(self.w * self.h * 4)

        self.gif_buf = bytearray()
        self.gif_buf.extend(b"GIF89a")
        self.gif_buf.extend(struct.pack("<HH", self.w, self.h))
        self.gif_buf.extend(b"\x00\x00\x00")
        self.gif_buf.extend(b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00")
        self.frame_count = 0

    def capture_frame(self) -> None:
        self.app._apply_fps_reading(60.0)
        self.app._render_frame()
        self.app._root.update()

        self.gdi32.BitBlt(
            self.hdc_mem, 0, 0, self.w, self.h, self.hdc_win, 0, 0, 0x00CC0020
        )
        self.gdi32.GetDIBits(
            self.hdc_mem, self.hbm, 0, self.h, self.buf, byref(self.bmi), 0
        )

        ints = array.array("I")
        ints.frombytes(self.buf)
        counts = Counter(ints)
        palette, mapping = quantize_median_cut(counts, 256)
        mapped_pixels = bytes(map(mapping.get, ints))

        # Graphic Control Extension
        self.gif_buf.extend(b"\x21\xf9\x04\x00")
        self.gif_buf.extend(struct.pack("<H", self.delay_cs))
        self.gif_buf.extend(b"\x00\x00\x2c")
        self.gif_buf.extend(struct.pack("<HHHH", 0, 0, self.w, self.h))
        self.gif_buf.append(0x87)  # local table 256 colors

        pal_bytes = bytearray()
        for r, g, b in palette:
            pal_bytes.extend((r, g, b))
        self.gif_buf.extend(pal_bytes)
        self.gif_buf.append(8)
        self.gif_buf.extend(encode_lzw(mapped_pixels, 8))
        self.frame_count += 1

    def save(self, filepath: Path) -> None:
        self.gif_buf.append(0x3B)
        filepath.write_bytes(bytes(self.gif_buf))
        self.cleanup()

    def cleanup(self) -> None:
        if self.hdc_mem:
            self.gdi32.SelectObject(self.hdc_mem, self.old_bmp)
            self.gdi32.DeleteObject(self.hbm)
            self.gdi32.DeleteDC(self.hdc_mem)
            self.user32.ReleaseDC(self.hwnd, self.hdc_win)
            self.hdc_mem = None


def record_full_gameplay_tour(output_dir: Path) -> Path:
    print("\n[1/5] Recording full_gameplay_tour_15s.gif (15 seconds, 150 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Daylight")
    app.set_species("Rose")
    app.set_cultivar("Scarlet")
    app.set_bloom(0.0)
    app.breeze_enabled = False
    app.breeze_time = 0.0
    app.yaw = app.species.default_yaw
    app.pitch = app.species.startup_pitch
    app.zoom = app.species.default_zoom
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(150):
        # 0.0s - 3.5s (frames 0..35): Rose bloom unfurling from bud
        if f <= 35:
            bloom_val = (f / 35.0) ** 1.8
            app.set_bloom(bloom_val)
            app.yaw += 0.03
            app.pitch = app.species.startup_pitch + (f / 35.0) * (app.species.default_pitch - app.species.startup_pitch)
        # 3.5s - 6.5s (frames 36..65): Orbit + Breeze + Cultivar change to Noir
        elif f <= 65:
            if f == 36:
                app.breeze_enabled = True
                app.set_cultivar("Noir")
            app.breeze_time += dt
            app.yaw += 0.05
            app.pitch += 0.005 * math.sin((f - 35) * 0.2)
        # 6.5s - 9.5s (frames 66..95): Lotus in Sage mood
        elif f <= 95:
            if f == 66:
                app.set_mood("Sage")
                app.set_species("Lotus")
                app.set_cultivar("Pink")
                app.set_bloom(1.0)
            app.breeze_time += dt
            app.yaw += 0.04
            app.zoom = app.species.default_zoom + 0.15 * math.sin((f - 65) * 0.1)
        # 9.5s - 12.5s (frames 96..125): Sunflower in Golden mood
        elif f <= 125:
            if f == 96:
                app.set_mood("Golden")
                app.set_species("Sunflower")
                app.set_cultivar("Classic")
                app.set_bloom(1.0)
            app.breeze_time += dt
            app.yaw += 0.045
        # 12.5s - 15.0s (frames 126..149): Sakura in Twilight dark mode
        else:
            if f == 126:
                app.set_mood("Twilight")
                app.set_species("Sakura")
                app.set_cultivar("Yoshino")
                app.set_bloom(1.0)
            app.breeze_time += dt
            app.yaw += 0.04

        rec.capture_frame()

    target_file = output_dir / "01_full_gameplay_tour_15s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_rose_bloom_and_orbit(output_dir: Path) -> Path:
    print("\n[2/5] Recording 02_rose_bloom_and_orbit_12s.gif (12 seconds, 120 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Daylight")
    app.set_species("Rose")
    app.set_cultivar("Scarlet")
    app.set_bloom(0.0)
    app.breeze_enabled = False
    app.breeze_time = 0.0
    app.yaw = app.species.default_yaw
    app.pitch = app.species.startup_pitch
    app.zoom = app.species.startup_zoom
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(120):
        # 0.0s - 4.5s (frames 0..45): Blooming from closed bud to full blossom
        if f <= 45:
            progress = f / 45.0
            bloom_val = progress ** 2.0
            app.set_bloom(bloom_val)
            app.yaw += 0.02
            app.pitch = app.species.startup_pitch + progress * (app.species.default_pitch - app.species.startup_pitch)
            app.zoom = app.species.startup_zoom + progress * (app.species.default_zoom - app.species.startup_zoom)
        # 4.5s - 8.5s (frames 46..85): 360-degree orbit inspect
        elif f <= 85:
            app.yaw += 0.06
            app.pitch = app.species.default_pitch + 0.1 * math.sin((f - 45) * 0.15)
        # 8.5s - 12.0s (frames 86..119): Wind breeze + zoom in
        else:
            if f == 86:
                app.breeze_enabled = True
            app.breeze_time += dt
            app.yaw += 0.04
            app.zoom = app.species.default_zoom + 0.25 * math.sin((f - 85) / 34.0 * math.pi)

        rec.capture_frame()

    target_file = output_dir / "02_rose_bloom_and_orbit_12s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_species_gallery(output_dir: Path) -> Path:
    print("\n[3/5] Recording 03_species_gallery_15s.gif (15 seconds, 150 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Daylight")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    species_list = [
        ("Rose", "Champagne"),
        ("Tulip", "Crimson"),
        ("Lotus", "Gold"),
        ("Sunflower", "Velvet"),
        ("Sakura", "Yaezakura"),
    ]

    for f in range(150):
        spec_idx = min(f // 30, 4)
        spec_name, cultivar_name = species_list[spec_idx]
        if f % 30 == 0:
            app.set_species(spec_name)
            app.set_cultivar(cultivar_name)
            app.set_bloom(1.0)

        app.breeze_time += dt
        app.yaw += 0.045
        rec.capture_frame()

    target_file = output_dir / "03_species_gallery_15s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_lighting_moods_and_wind(output_dir: Path) -> Path:
    print("\n[4/5] Recording 04_lighting_moods_and_wind_12s.gif (12 seconds, 120 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_species("Tulip")
    app.set_cultivar("Crimson")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    mood_list = ["Daylight", "Golden", "Sage", "Twilight"]

    for f in range(120):
        mood_idx = min(f // 30, 3)
        if f % 30 == 0:
            app.set_mood(mood_list[mood_idx])

        app.breeze_time += dt
        app.yaw += 0.04
        rec.capture_frame()

    target_file = output_dir / "04_lighting_moods_and_wind_12s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_lotus_twilight_unfurl(output_dir: Path) -> Path:
    print("\n[5/5] Recording 05_lotus_twilight_unfurl_10s.gif (10 seconds, 100 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Twilight")
    app.set_species("Lotus")
    app.set_cultivar("Pink")
    app.set_bloom(0.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app.yaw = app.species.default_yaw
    app.pitch = app.species.startup_pitch
    app.zoom = app.species.startup_zoom
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(100):
        progress = f / 100.0
        bloom_val = progress ** 1.6
        app.set_bloom(bloom_val)
        app.breeze_time += dt
        app.yaw += 0.035
        app.pitch = app.species.startup_pitch + progress * (app.species.default_pitch - app.species.startup_pitch)
        app.zoom = app.species.startup_zoom + progress * (app.species.default_zoom - app.species.startup_zoom)
        rec.capture_frame()

    target_file = output_dir / "05_lotus_twilight_unfurl_10s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file




def record_sunflower_golden_orbit(output_dir: Path) -> Path:
    print("\n[6/12] Recording 06_sunflower_golden_orbit_12s.gif (12s, 120 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Golden")
    app.set_species("Sunflower")
    app.set_cultivar("Classic")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(120):
        app.breeze_time += dt
        app.yaw += 0.05
        app.pitch = app.species.default_pitch + 0.18 * math.sin(f * 0.08)
        app.zoom = app.species.default_zoom + 0.12 * math.cos(f * 0.06)
        rec.capture_frame()

    target_file = output_dir / "06_sunflower_golden_orbit_12s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_tulip_cultivars_and_breeze(output_dir: Path) -> Path:
    print("\n[7/12] Recording 07_tulip_cultivars_and_breeze_12s.gif (12s, 120 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Daylight")
    app.set_species("Tulip")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    cultivars = ["Crimson", "Apricot", "Ivory", "Violet", "Golden"]
    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(120):
        c_idx = min(f // 24, len(cultivars) - 1)
        if f % 24 == 0:
            app.set_cultivar(cultivars[c_idx])
        app.breeze_time += dt
        app.yaw += 0.04
        rec.capture_frame()

    target_file = output_dir / "07_tulip_cultivars_and_breeze_12s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_sakura_twilight_breeze(output_dir: Path) -> Path:
    print("\n[8/12] Recording 08_sakura_twilight_breeze_10s.gif (10s, 100 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Twilight")
    app.set_species("Sakura")
    app.set_cultivar("Yoshino")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(100):
        app.breeze_time += dt
        app.yaw += 0.045
        app.pitch = app.species.default_pitch + 0.1 * math.sin(f * 0.1)
        rec.capture_frame()

    target_file = output_dir / "08_sakura_twilight_breeze_10s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_rose_cultivars_palette(output_dir: Path) -> Path:
    print("\n[9/12] Recording 09_rose_cultivars_palette_12s.gif (12s, 120 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Daylight")
    app.set_species("Rose")
    app.set_bloom(1.0)
    app.breeze_enabled = False
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    cultivars = ["Scarlet", "Champagne", "Blush", "Amber", "Noir", "Coral"]
    rec = GifRecorder(app, delay_cs=10)
    t0 = time.perf_counter()

    for f in range(120):
        c_idx = min(f // 20, len(cultivars) - 1)
        if f % 20 == 0:
            app.set_cultivar(cultivars[c_idx])
        app.yaw += 0.045
        rec.capture_frame()

    target_file = output_dir / "09_rose_cultivars_palette_12s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_interactive_zoom_and_tilt(output_dir: Path) -> Path:
    print("\n[10/12] Recording 10_interactive_zoom_and_tilt_10s.gif (10s, 100 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Sage")
    app.set_species("Lotus")
    app.set_cultivar("Pink")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(100):
        progress = f / 100.0
        app.breeze_time += dt
        app.yaw += 0.05
        # Deep zoom in then pull back
        zoom_curve = math.sin(progress * math.pi)
        app.zoom = app.species.default_zoom + 0.45 * zoom_curve
        app.pitch = app.species.default_pitch + 0.25 * math.sin(progress * 2.0 * math.pi)
        rec.capture_frame()

    target_file = output_dir / "10_interactive_zoom_and_tilt_10s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_speed_and_motion_controls(output_dir: Path) -> Path:
    print("\n[11/12] Recording 11_speed_and_motion_controls_10s.gif (10s, 100 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Golden")
    app.set_species("Sakura")
    app.set_cultivar("Yaezakura")
    app.set_bloom(1.0)
    app.breeze_enabled = False
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    t0 = time.perf_counter()

    for f in range(100):
        # 0..30: 1.0x spin
        if f < 30:
            speed = 1.0
        # 30..70: ramp up to 4.0x spin
        elif f < 70:
            speed = 1.0 + 3.0 * ((f - 30) / 40.0)
        # 70..100: gentle slowdown
        else:
            speed = 4.0 - 3.0 * ((f - 70) / 30.0)
        app.set_rotation_speed(speed)
        app.yaw += 0.03 * speed
        rec.capture_frame()

    target_file = output_dir / "11_speed_and_motion_controls_10s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def record_lush_detail_comparison(output_dir: Path) -> Path:
    print("\n[12/12] Recording 12_lush_detail_comparison_10s.gif (10s, 100 frames)...")
    flowers_3d.WINDOW_WIDTH = 480
    flowers_3d.WINDOW_HEIGHT = 480
    flowers_3d.WINDOW_SIZE = 480

    app = flowers_3d.FlowerViewerApp()
    app.set_mood("Daylight")
    app.set_species("Rose")
    app.set_cultivar("Scarlet")
    app.set_bloom(1.0)
    app.breeze_enabled = True
    app.breeze_time = 0.0
    app._sync_hud_to_viewport()
    app._render_frame()
    app._root.update()

    rec = GifRecorder(app, delay_cs=10)
    dt = 0.1
    t0 = time.perf_counter()

    for f in range(100):
        if f == 50:
            app.set_detail_tier(flowers_3d.LUSH_TIER)
        app.breeze_time += dt
        app.yaw += 0.045
        rec.capture_frame()

    target_file = output_dir / "12_lush_detail_comparison_10s.gif"
    rec.save(target_file)
    app.close()
    elapsed = time.perf_counter() - t0
    print(f"Saved: {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB in {elapsed:.1f}s)")
    return target_file


def main() -> None:
    showcases_dir = Path(__file__).resolve().parent

    print(f"Starting showcase recordings into '{showcases_dir.resolve()}'...")
    total_t0 = time.perf_counter()

    recorders = [
        ("01_full_gameplay_tour_15s.gif", record_full_gameplay_tour),
        ("02_rose_bloom_and_orbit_12s.gif", record_rose_bloom_and_orbit),
        ("03_species_gallery_15s.gif", record_species_gallery),
        ("04_lighting_moods_and_wind_12s.gif", record_lighting_moods_and_wind),
        ("05_lotus_twilight_unfurl_10s.gif", record_lotus_twilight_unfurl),
        ("06_sunflower_golden_orbit_12s.gif", record_sunflower_golden_orbit),
        ("07_tulip_cultivars_and_breeze_12s.gif", record_tulip_cultivars_and_breeze),
        ("08_sakura_twilight_breeze_10s.gif", record_sakura_twilight_breeze),
        ("09_rose_cultivars_palette_12s.gif", record_rose_cultivars_palette),
        ("10_interactive_zoom_and_tilt_10s.gif", record_interactive_zoom_and_tilt),
        ("11_speed_and_motion_controls_10s.gif", record_speed_and_motion_controls),
        ("12_lush_detail_comparison_10s.gif", record_lush_detail_comparison),
    ]

    files = []
    for filename, fn in recorders:
        dest = showcases_dir / filename
        if dest.exists() and dest.stat().st_size > 100000:
            print(f"Skipping existing: {filename} ({dest.stat().st_size / 1024 / 1024:.2f} MB)")
            files.append(dest)
        else:
            files.append(fn(showcases_dir))

    total_time = time.perf_counter() - total_t0
    print(f"\nAll {len(files)} showcase GIFs ready in {total_time:.1f}s!")
    for f in files:
        print(f"  - {f.name}: {f.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
