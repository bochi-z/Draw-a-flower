"""3D Interactive Botanical Showcase rendered with pure Python turtle.

Features:
- Multi-species 3D botanical geometry: Rose, Tulip, Lotus, Sunflower, and Sakura
  with authentic bud-to-bloom unfurling, stamens/pistils/seed pods, and stems/foliage.
- Selectable Standard (60 FPS) and Lush High-Detail mesh tessellation tiers
  backed by a growable reusable canvas polygon pool.
- Curated per-species cultivars and 4 adaptive light/dark lighting moods
  (Daylight, Golden, Sage, Twilight).
- Seam-safe organic wind sway, interactive Bloom scrubber, and smooth
  framerate-independent camera & zoom inertia.
- Translucent frosted HUD pills rendered with bundled Google Sans typography
  and Material Symbols icons using zero external runtime dependencies.
"""

from __future__ import annotations

import array
import atexit
from collections import deque
import math
import os
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import turtle
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

WINDOW_SIZE = 600
WINDOW_WIDTH = WINDOW_SIZE
WINDOW_HEIGHT = WINDOW_SIZE
BACKGROUND_COLOR = "#FAF5EC"  # Soft warm cream botanical canvas (Daylight default)
WINDOW_TITLE = "3D Flowers"

HUD_Y = -268.0
HUD_MARGIN_X = 14.0
HUD_MARGIN_Y = 14.0
HUD_INK_COLOR = "#4A4239"
HUD_TEXT_COLOR = HUD_INK_COLOR
HUD_DISABLED_INK_COLOR = "#64625F"
HUD_ENABLED_INK_RGB = (74, 66, 57)
HUD_DISABLED_INK_RGB = (100, 98, 95)
HUD_HEIGHT = 32
HUD_PILL_FILL_RGBA = (245, 238, 226, 194)
HUD_PILL_EDGE_RGBA = (190, 178, 160, 212)
HUD_DISABLED_FILL_RGBA = (196, 196, 198, 196)
HUD_DISABLED_EDGE_RGBA = (158, 158, 162, 212)
HUD_COLOR_TRANSITION_DURATION = 0.35
HUD_TRANSITION_STEPS = 10

SLIDER_HUD_HEIGHT = 28
SLIDER_ROW_GAP = 10.0
SLIDER_STACK_GAP = 8.0
SLIDER_TRACK_WIDTH = 112
SLIDER_TRACK_HEIGHT = 16
SLIDER_TRACK_PAD = 7.0
SPEED_HUD_HEIGHT = SLIDER_HUD_HEIGHT
SPEED_HUD_GAP = SLIDER_STACK_GAP
SPEED_TRACK_WIDTH = SLIDER_TRACK_WIDTH
SPEED_TRACK_HEIGHT = SLIDER_TRACK_HEIGHT
SPEED_TRACK_PAD = SLIDER_TRACK_PAD

ROTATION_SPEED_MIN = 1.0
ROTATION_SPEED_MAX = 5.0
DEFAULT_ROTATION_SPEED = 1.0

BLOOM_MIN = 0.0
BLOOM_MAX = 1.0
BLOOM_WHEEL_STEP = 0.05

SPEED_TRACK_GROOVE_ENABLED_RGBA = (184, 172, 156, 138)
SPEED_TRACK_GROOVE_DISABLED_RGBA = (158, 158, 162, 120)
SPEED_TRACK_ACTIVE_ENABLED_RGBA = (212, 34, 48, 255)
SPEED_TRACK_ACTIVE_DISABLED_RGBA = (132, 132, 136, 220)
SPEED_THUMB_CORE_ENABLED_RGBA = (250, 245, 236, 255)
SPEED_THUMB_CORE_DISABLED_RGBA = (230, 230, 232, 235)

TARGET_FPS = 60
TARGET_FRAME_INTERVAL = 1.0 / TARGET_FPS
FPS_BADGE_HEIGHT = 26
FPS_UPDATE_INTERVAL = 0.25  # seconds between FPS badge refreshes
FACES_BADGE_HEIGHT = FPS_BADGE_HEIGHT
FACES_BADGE_GAP = 8.0

SWITCHER_HUD_HEIGHT = 26
SWITCHER_MIN_GAP = 10.0
SPECIES_HUD_HEIGHT = 26
SPECIES_STACK_GAP = 8.0
BGM_HUD_HEIGHT = 26
BGM_STACK_GAP = 8.0
BGM_VIZ_BAR_COUNT = 4
BGM_VIZ_BAR_WIDTH = 2
BGM_VIZ_BAR_GAP = 2
BGM_VIZ_MAX_HALF_H = 5.0
BGM_VIZ_MIN_HALF_H = 1.2
BGM_SAMPLE_RATE = 44100
BGM_TOOLTIP_HEIGHT = 24
BGM_TOOLTIP_GAP = 6.0
BGM_RESIZE_DURATION = 0.18
BGM_RESIZE_STEPS = 8

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))

# Standard mesh resolution constants (~709 faces, ~667 drawn at default view)
NUM_PETALS = 26
PETAL_U_STEPS = 5
PETAL_V_STEPS = 4
RECEPTACLE_RADIAL_STEPS = 8
RECEPTACLE_HEIGHT_STEPS = 3
NUM_SEPALS = 5
SEPAL_U_STEPS = 2
SEPAL_V_STEPS = 4
STEM_RADIAL_STEPS = 6
STEM_HEIGHT_STEPS = 9
LEAF_U_STEPS = 4
LEAF_V_STEPS = 5

# Stem bottom y at s=1.0: -0.13 - 1.24 * 1.0 = -1.37
STEM_ANCHOR_Y = -1.37

# Default receptacle profile rings ordered top-to-bottom (y, radius)
_RECEPTACLE_PROFILE: tuple[tuple[float, float], ...] = (
    (0.11, 0.268),
    (0.05, 0.285),
    (-0.04, 0.215),
    (-0.14, 0.062),
)

_THORN_SPECS: tuple[tuple[float, float], ...] = (
    (0.28, 1.9),
    (0.54, 4.1),
    (0.76, 0.6),
)

_LEAF_SPECS: tuple[tuple[float, float, float, float, float, float], ...] = (
    (0.25, 0.45, 0.70, 0.24, 0.34, 0.16),
    (0.49, 2.60, 0.78, 0.27, 0.40, -0.18),
    (0.71, 4.70, 0.64, 0.22, 0.44, 0.12),
)

# Camera & Animation defaults
DEFAULT_YAW = 0.35
DEFAULT_PITCH = 0.50  # ~28.6 deg 3/4 view looking gently into the rose cup
DEFAULT_ZOOM = 1.0
STARTUP_PITCH = 1.42  # Overhead view looking down into the opening rosebud
STARTUP_ZOOM = 1.18
PITCH_MIN = -1.25
PITCH_MAX = 1.45
ZOOM_MIN = 0.55
ZOOM_MAX = 2.35
PIVOT_Y = -0.22
CAMERA_DISTANCE = 6.2
FOV_SCALE = 1100.0

AUTO_ROTATE_SPEED = 0.55        # radians per second
BLOOM_DURATION = 2.6            # seconds for bud-to-bloom intro
CAMERA_TWEEN_DURATION = 1.6     # seconds to glide from overhead to default angle
RESET_TRANSITION_DURATION = 0.8 # seconds to smoothly glide back to startup state
SPECIES_ENTRY_DURATION = 0.55   # seconds to smoothly frame overhead on species switch


# ---------------------------------------------------------------------------
# Math & Color Utilities
# ---------------------------------------------------------------------------

def _normalize(vx: float, vy: float, vz: float) -> tuple[float, float, float]:
    length = math.sqrt(vx * vx + vy * vy + vz * vz)
    if length < 1e-12:
        return (0.0, 0.0, 1.0)
    return (vx / length, vy / length, vz / length)


KEY_LIGHT = _normalize(0.55, 0.72, 0.58)
FILL_LIGHT = _normalize(-0.62, 0.20, 0.36)


def _clamp(value: float, low: float, high: float) -> float:
    if value < low:
        return low
    if value > high:
        return high
    return value


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = _clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _smootherstep(x: float) -> float:
    t = _clamp(x, 0.0, 1.0)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    ri = int(_clamp(r, 0.0, 255.0) + 0.5)
    gi = int(_clamp(g, 0.0, 255.0) + 0.5)
    bi = int(_clamp(b, 0.0, 255.0) + 0.5)
    return f"#{ri:02x}{gi:02x}{bi:02x}"


def _lerp_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    return (
        int(_lerp(float(start[0]), float(end[0]), t) + 0.5),
        int(_lerp(float(start[1]), float(end[1]), t) + 0.5),
        int(_lerp(float(start[2]), float(end[2]), t) + 0.5),
    )


def _lerp_rgba(
    start: tuple[int, int, int, int],
    end: tuple[int, int, int, int],
    t: float,
) -> tuple[int, int, int, int]:
    return (
        int(_lerp(float(start[0]), float(end[0]), t) + 0.5),
        int(_lerp(float(start[1]), float(end[1]), t) + 0.5),
        int(_lerp(float(start[2]), float(end[2]), t) + 0.5),
        int(_lerp(float(start[3]), float(end[3]), t) + 0.5),
    )


# ---------------------------------------------------------------------------
# Botanical Species, Cultivars, Adaptive Moods & Mesh Detail Tiers
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class CultivarSpec:
    """Botanical color palette, surface gradients, and HUD accent for one cultivar."""

    key: str
    name: str
    short_name: str
    petal_outer_rgb: tuple[float, float, float]
    petal_inner_rgb: tuple[float, float, float]
    petal_heart_rgb: tuple[float, float, float]
    petal_tip_rgb: tuple[float, float, float]
    petal_spec_rgb: tuple[float, float, float]
    foliage_rgb: tuple[float, float, float]
    foliage_spec_rgb: tuple[float, float, float]
    thorn_rgb: tuple[float, float, float]
    accent_rgba: tuple[int, int, int, int]
    accent_disabled_rgba: tuple[int, int, int, int]
    heart_blend: float = 0.55
    tip_blend: float = 0.45
    tip_lift_base: float = 0.86
    tip_lift_span: float = 0.20
    spec_strength: float = 0.14
    species: str = "rose"
    heart_uses_v: bool = False
    petal_ao_floor: float = 0.50
    stamen_rgb: tuple[float, float, float] = (232.0, 186.0, 68.0)
    anther_rgb: tuple[float, float, float] = (214.0, 152.0, 38.0)
    center_rgb: tuple[float, float, float] = (140.0, 156.0, 74.0)
    center_accent_rgb: tuple[float, float, float] = (196.0, 146.0, 48.0)
    bark_rgb: tuple[float, float, float] = (124.0, 88.0, 60.0)
    calyx_rgb: tuple[float, float, float] | None = None


CULTIVARS: tuple[CultivarSpec, ...] = (
    CultivarSpec(
        key="scarlet",
        name="Scarlet",
        short_name="Scarlet",
        petal_outer_rgb=(208.0, 34.0, 48.0),
        petal_inner_rgb=(222.0, 24.0, 36.0),
        petal_heart_rgb=(200.0, 18.0, 30.0),
        petal_tip_rgb=(228.0, 44.0, 56.0),
        petal_spec_rgb=(252.0, 128.0, 102.0),
        foliage_rgb=(76.0, 136.0, 56.0),
        foliage_spec_rgb=(168.0, 198.0, 96.0),
        thorn_rgb=(124.0, 88.0, 60.0),
        accent_rgba=SPEED_TRACK_ACTIVE_ENABLED_RGBA,
        accent_disabled_rgba=SPEED_TRACK_ACTIVE_DISABLED_RGBA,
        heart_blend=0.18,
        tip_blend=0.16,
        tip_lift_base=0.86,
        tip_lift_span=0.24,
        spec_strength=0.14,
    ),
    CultivarSpec(
        key="champagne",
        name="Champagne",
        short_name="Champ.",
        petal_outer_rgb=(222.0, 200.0, 172.0),
        petal_inner_rgb=(236.0, 218.0, 190.0),
        petal_heart_rgb=(224.0, 166.0, 144.0),
        petal_tip_rgb=(244.0, 234.0, 212.0),
        petal_spec_rgb=(255.0, 242.0, 196.0),
        foliage_rgb=(82.0, 132.0, 72.0),
        foliage_spec_rgb=(176.0, 202.0, 128.0),
        thorn_rgb=(136.0, 104.0, 74.0),
        accent_rgba=(196, 150, 96, 255),
        accent_disabled_rgba=(146, 140, 132, 220),
        heart_blend=0.62,
        tip_blend=0.55,
        tip_lift_base=0.88,
        tip_lift_span=0.14,
        spec_strength=0.15,
    ),
    CultivarSpec(
        key="blush",
        name="Blush",
        short_name="Blush",
        petal_outer_rgb=(222.0, 154.0, 168.0),
        petal_inner_rgb=(232.0, 134.0, 152.0),
        petal_heart_rgb=(206.0, 88.0, 114.0),
        petal_tip_rgb=(242.0, 188.0, 198.0),
        petal_spec_rgb=(255.0, 222.0, 224.0),
        foliage_rgb=(78.0, 128.0, 78.0),
        foliage_spec_rgb=(164.0, 194.0, 132.0),
        thorn_rgb=(128.0, 90.0, 78.0),
        accent_rgba=(212, 104, 126, 255),
        accent_disabled_rgba=(144, 132, 136, 220),
        heart_blend=0.70,
        tip_blend=0.45,
        tip_lift_base=0.87,
        tip_lift_span=0.16,
        spec_strength=0.14,
    ),
    CultivarSpec(
        key="amber",
        name="Amber",
        short_name="Amber",
        petal_outer_rgb=(232.0, 142.0, 46.0),
        petal_inner_rgb=(244.0, 164.0, 60.0),
        petal_heart_rgb=(214.0, 84.0, 24.0),
        petal_tip_rgb=(250.0, 202.0, 98.0),
        petal_spec_rgb=(255.0, 232.0, 152.0),
        foliage_rgb=(84.0, 134.0, 52.0),
        foliage_spec_rgb=(178.0, 204.0, 96.0),
        thorn_rgb=(132.0, 84.0, 48.0),
        accent_rgba=(224, 126, 36, 255),
        accent_disabled_rgba=(144, 136, 124, 220),
        heart_blend=0.68,
        tip_blend=0.48,
        tip_lift_base=0.86,
        tip_lift_span=0.18,
        spec_strength=0.15,
    ),
    CultivarSpec(
        key="noir",
        name="Noir",
        short_name="Noir",
        petal_outer_rgb=(98.0, 24.0, 52.0),
        petal_inner_rgb=(124.0, 20.0, 44.0),
        petal_heart_rgb=(146.0, 16.0, 38.0),
        petal_tip_rgb=(134.0, 38.0, 68.0),
        petal_spec_rgb=(218.0, 112.0, 142.0),
        foliage_rgb=(78.0, 116.0, 104.0),
        foliage_spec_rgb=(148.0, 184.0, 172.0),
        thorn_rgb=(98.0, 68.0, 74.0),
        accent_rgba=(156, 42, 76, 255),
        accent_disabled_rgba=(128, 122, 128, 220),
        heart_blend=0.65,
        tip_blend=0.38,
        tip_lift_base=0.84,
        tip_lift_span=0.24,
        spec_strength=0.16,
    ),
    CultivarSpec(
        key="coral",
        name="Coral",
        short_name="Coral",
        petal_outer_rgb=(232.0, 90.0, 74.0),
        petal_inner_rgb=(242.0, 108.0, 86.0),
        petal_heart_rgb=(214.0, 62.0, 56.0),
        petal_tip_rgb=(252.0, 176.0, 132.0),
        petal_spec_rgb=(255.0, 210.0, 180.0),
        foliage_rgb=(74.0, 134.0, 70.0),
        foliage_spec_rgb=(168.0, 202.0, 118.0),
        thorn_rgb=(126.0, 86.0, 64.0),
        accent_rgba=(236, 98, 78, 255),
        accent_disabled_rgba=(144, 132, 130, 220),
        heart_blend=0.58,
        tip_blend=0.65,
        tip_lift_base=0.87,
        tip_lift_span=0.18,
        spec_strength=0.14,
    ),
)

ROSE_CULTIVARS: tuple[CultivarSpec, ...] = CULTIVARS

TULIP_CULTIVARS: tuple[CultivarSpec, ...] = (
    CultivarSpec(
        key="crimson",
        name="Crimson",
        short_name="Crimson",
        species="tulip",
        heart_uses_v=True,
        petal_ao_floor=0.68,
        petal_outer_rgb=(208.0, 32.0, 50.0),
        petal_inner_rgb=(228.0, 38.0, 58.0),
        petal_heart_rgb=(54.0, 22.0, 40.0),
        petal_tip_rgb=(242.0, 76.0, 76.0),
        petal_spec_rgb=(255.0, 152.0, 132.0),
        foliage_rgb=(78.0, 132.0, 92.0),
        foliage_spec_rgb=(162.0, 204.0, 162.0),
        thorn_rgb=(78.0, 132.0, 92.0),
        stamen_rgb=(218.0, 186.0, 96.0),
        anther_rgb=(56.0, 36.0, 52.0),
        center_rgb=(172.0, 186.0, 94.0),
        accent_rgba=(208, 36, 54, 255),
        accent_disabled_rgba=(138, 130, 132, 220),
        heart_blend=0.78,
        tip_blend=0.45,
        tip_lift_base=0.92,
        tip_lift_span=0.14,
        spec_strength=0.16,
    ),
    CultivarSpec(
        key="apricot",
        name="Apricot",
        short_name="Apricot",
        species="tulip",
        heart_uses_v=True,
        petal_ao_floor=0.78,
        petal_outer_rgb=(242.0, 156.0, 114.0),
        petal_inner_rgb=(252.0, 180.0, 136.0),
        petal_heart_rgb=(224.0, 98.0, 66.0),
        petal_tip_rgb=(255.0, 228.0, 192.0),
        petal_spec_rgb=(255.0, 242.0, 218.0),
        foliage_rgb=(84.0, 134.0, 94.0),
        foliage_spec_rgb=(168.0, 206.0, 158.0),
        thorn_rgb=(84.0, 134.0, 94.0),
        stamen_rgb=(232.0, 198.0, 104.0),
        anther_rgb=(104.0, 66.0, 48.0),
        center_rgb=(188.0, 194.0, 104.0),
        accent_rgba=(226, 128, 86, 255),
        accent_disabled_rgba=(144, 136, 130, 220),
        heart_blend=0.66,
        tip_blend=0.58,
        tip_lift_base=0.96,
        tip_lift_span=0.10,
        spec_strength=0.15,
    ),
    CultivarSpec(
        key="ivory",
        name="Ivory",
        short_name="Ivory",
        species="tulip",
        heart_uses_v=True,
        petal_ao_floor=0.82,
        petal_outer_rgb=(240.0, 234.0, 218.0),
        petal_inner_rgb=(250.0, 246.0, 234.0),
        petal_heart_rgb=(230.0, 212.0, 142.0),
        petal_tip_rgb=(255.0, 253.0, 248.0),
        petal_spec_rgb=(255.0, 252.0, 236.0),
        foliage_rgb=(82.0, 130.0, 98.0),
        foliage_spec_rgb=(166.0, 202.0, 166.0),
        thorn_rgb=(82.0, 130.0, 98.0),
        stamen_rgb=(232.0, 202.0, 96.0),
        anther_rgb=(128.0, 92.0, 52.0),
        center_rgb=(184.0, 196.0, 114.0),
        accent_rgba=(190, 148, 82, 255),
        accent_disabled_rgba=(146, 142, 134, 220),
        heart_blend=0.55,
        tip_blend=0.50,
        tip_lift_base=0.98,
        tip_lift_span=0.08,
        spec_strength=0.14,
    ),
    CultivarSpec(
        key="violet",
        name="Violet",
        short_name="Violet",
        species="tulip",
        heart_uses_v=True,
        petal_ao_floor=0.72,
        petal_outer_rgb=(128.0, 68.0, 166.0),
        petal_inner_rgb=(152.0, 88.0, 194.0),
        petal_heart_rgb=(58.0, 28.0, 92.0),
        petal_tip_rgb=(204.0, 154.0, 236.0),
        petal_spec_rgb=(236.0, 202.0, 252.0),
        foliage_rgb=(76.0, 124.0, 102.0),
        foliage_spec_rgb=(156.0, 196.0, 174.0),
        thorn_rgb=(76.0, 124.0, 102.0),
        stamen_rgb=(218.0, 192.0, 102.0),
        anther_rgb=(52.0, 32.0, 68.0),
        center_rgb=(166.0, 182.0, 108.0),
        accent_rgba=(146, 82, 186, 255),
        accent_disabled_rgba=(134, 128, 140, 220),
        heart_blend=0.72,
        tip_blend=0.52,
        tip_lift_base=0.92,
        tip_lift_span=0.14,
        spec_strength=0.16,
    ),
    CultivarSpec(
        key="golden",
        name="Golden",
        short_name="Golden",
        species="tulip",
        heart_uses_v=True,
        petal_ao_floor=0.78,
        petal_outer_rgb=(240.0, 188.0, 32.0),
        petal_inner_rgb=(252.0, 208.0, 48.0),
        petal_heart_rgb=(204.0, 118.0, 20.0),
        petal_tip_rgb=(255.0, 236.0, 112.0),
        petal_spec_rgb=(255.0, 248.0, 180.0),
        foliage_rgb=(82.0, 134.0, 74.0),
        foliage_spec_rgb=(172.0, 206.0, 132.0),
        thorn_rgb=(82.0, 134.0, 74.0),
        stamen_rgb=(234.0, 192.0, 64.0),
        anther_rgb=(96.0, 64.0, 38.0),
        center_rgb=(180.0, 192.0, 88.0),
        accent_rgba=(226, 166, 24, 255),
        accent_disabled_rgba=(146, 140, 126, 220),
        heart_blend=0.62,
        tip_blend=0.52,
        tip_lift_base=0.96,
        tip_lift_span=0.10,
        spec_strength=0.16,
    ),
)

LOTUS_CULTIVARS: tuple[CultivarSpec, ...] = (
    CultivarSpec(
        key="pink",
        name="Pink",
        short_name="Pink",
        species="lotus",
        heart_uses_v=True,
        petal_ao_floor=0.82,
        petal_outer_rgb=(250.0, 188.0, 208.0),
        petal_inner_rgb=(255.0, 212.0, 226.0),
        petal_heart_rgb=(254.0, 240.0, 206.0),
        petal_tip_rgb=(236.0, 84.0, 138.0),
        petal_spec_rgb=(255.0, 236.0, 242.0),
        foliage_rgb=(74.0, 134.0, 90.0),
        foliage_spec_rgb=(156.0, 202.0, 152.0),
        thorn_rgb=(74.0, 134.0, 90.0),
        stamen_rgb=(244.0, 204.0, 86.0),
        anther_rgb=(228.0, 166.0, 42.0),
        center_rgb=(226.0, 198.0, 74.0),
        center_accent_rgb=(116.0, 96.0, 44.0),
        accent_rgba=(218, 92, 134, 255),
        accent_disabled_rgba=(144, 132, 136, 220),
        heart_blend=0.72,
        tip_blend=0.78,
        tip_lift_base=0.98,
        tip_lift_span=0.10,
        spec_strength=0.13,
    ),
    CultivarSpec(
        key="white",
        name="White",
        short_name="White",
        species="lotus",
        heart_uses_v=True,
        petal_ao_floor=0.84,
        petal_outer_rgb=(240.0, 244.0, 236.0),
        petal_inner_rgb=(250.0, 252.0, 248.0),
        petal_heart_rgb=(236.0, 242.0, 184.0),
        petal_tip_rgb=(255.0, 255.0, 253.0),
        petal_spec_rgb=(255.0, 255.0, 246.0),
        foliage_rgb=(72.0, 134.0, 96.0),
        foliage_spec_rgb=(154.0, 204.0, 162.0),
        thorn_rgb=(72.0, 134.0, 96.0),
        stamen_rgb=(242.0, 204.0, 82.0),
        anther_rgb=(224.0, 162.0, 38.0),
        center_rgb=(218.0, 198.0, 78.0),
        center_accent_rgb=(118.0, 102.0, 48.0),
        accent_rgba=(76, 152, 118, 255),
        accent_disabled_rgba=(134, 142, 138, 220),
        heart_blend=0.68,
        tip_blend=0.60,
        tip_lift_base=0.99,
        tip_lift_span=0.07,
        spec_strength=0.13,
    ),
    CultivarSpec(
        key="gold",
        name="Gold",
        short_name="Gold",
        species="lotus",
        heart_uses_v=True,
        petal_ao_floor=0.80,
        petal_outer_rgb=(242.0, 200.0, 88.0),
        petal_inner_rgb=(252.0, 220.0, 120.0),
        petal_heart_rgb=(222.0, 152.0, 46.0),
        petal_tip_rgb=(255.0, 244.0, 174.0),
        petal_spec_rgb=(255.0, 248.0, 210.0),
        foliage_rgb=(78.0, 134.0, 84.0),
        foliage_spec_rgb=(166.0, 204.0, 142.0),
        thorn_rgb=(78.0, 134.0, 84.0),
        stamen_rgb=(248.0, 212.0, 92.0),
        anther_rgb=(214.0, 146.0, 34.0),
        center_rgb=(214.0, 178.0, 56.0),
        center_accent_rgb=(112.0, 84.0, 36.0),
        accent_rgba=(214, 158, 44, 255),
        accent_disabled_rgba=(144, 138, 128, 220),
        heart_blend=0.64,
        tip_blend=0.58,
        tip_lift_base=0.97,
        tip_lift_span=0.09,
        spec_strength=0.14,
    ),
    CultivarSpec(
        key="plum",
        name="Plum",
        short_name="Plum",
        species="lotus",
        heart_uses_v=True,
        petal_ao_floor=0.76,
        petal_outer_rgb=(184.0, 92.0, 142.0),
        petal_inner_rgb=(206.0, 112.0, 162.0),
        petal_heart_rgb=(242.0, 206.0, 214.0),
        petal_tip_rgb=(126.0, 42.0, 92.0),
        petal_spec_rgb=(242.0, 190.0, 218.0),
        foliage_rgb=(74.0, 124.0, 96.0),
        foliage_spec_rgb=(152.0, 192.0, 164.0),
        thorn_rgb=(74.0, 124.0, 96.0),
        stamen_rgb=(240.0, 202.0, 98.0),
        anther_rgb=(216.0, 156.0, 48.0),
        center_rgb=(218.0, 188.0, 76.0),
        center_accent_rgb=(98.0, 68.0, 52.0),
        accent_rgba=(166, 68, 122, 255),
        accent_disabled_rgba=(138, 128, 134, 220),
        heart_blend=0.74,
        tip_blend=0.70,
        tip_lift_base=0.95,
        tip_lift_span=0.11,
        spec_strength=0.15,
    ),
)

SUNFLOWER_CULTIVARS: tuple[CultivarSpec, ...] = (
    CultivarSpec(
        key="classic",
        name="Classic",
        short_name="Classic",
        species="sunflower",
        heart_uses_v=True,
        petal_ao_floor=0.78,
        petal_outer_rgb=(244.0, 184.0, 24.0),
        petal_inner_rgb=(254.0, 206.0, 38.0),
        petal_heart_rgb=(234.0, 144.0, 16.0),
        petal_tip_rgb=(255.0, 232.0, 92.0),
        petal_spec_rgb=(255.0, 244.0, 162.0),
        foliage_rgb=(78.0, 134.0, 56.0),
        foliage_spec_rgb=(168.0, 202.0, 102.0),
        thorn_rgb=(78.0, 134.0, 56.0),
        stamen_rgb=(224.0, 164.0, 36.0),
        anther_rgb=(188.0, 118.0, 24.0),
        center_rgb=(62.0, 38.0, 24.0),
        center_accent_rgb=(214.0, 146.0, 30.0),
        accent_rgba=(228, 162, 18, 255),
        accent_disabled_rgba=(144, 138, 126, 220),
        heart_blend=0.58,
        tip_blend=0.45,
        tip_lift_base=0.96,
        tip_lift_span=0.10,
        spec_strength=0.13,
    ),
    CultivarSpec(
        key="velvet",
        name="Velvet",
        short_name="Velvet",
        species="sunflower",
        heart_uses_v=True,
        petal_ao_floor=0.72,
        petal_outer_rgb=(162.0, 40.0, 44.0),
        petal_inner_rgb=(192.0, 52.0, 52.0),
        petal_heart_rgb=(96.0, 22.0, 28.0),
        petal_tip_rgb=(232.0, 124.0, 58.0),
        petal_spec_rgb=(248.0, 168.0, 122.0),
        foliage_rgb=(76.0, 126.0, 58.0),
        foliage_spec_rgb=(162.0, 194.0, 104.0),
        thorn_rgb=(76.0, 126.0, 58.0),
        stamen_rgb=(204.0, 132.0, 46.0),
        anther_rgb=(142.0, 74.0, 30.0),
        center_rgb=(46.0, 26.0, 22.0),
        center_accent_rgb=(198.0, 118.0, 42.0),
        accent_rgba=(178, 48, 48, 255),
        accent_disabled_rgba=(138, 128, 128, 220),
        heart_blend=0.68,
        tip_blend=0.58,
        tip_lift_base=0.94,
        tip_lift_span=0.12,
        spec_strength=0.14,
    ),
    CultivarSpec(
        key="lemon",
        name="Lemon",
        short_name="Lemon",
        species="sunflower",
        heart_uses_v=True,
        petal_ao_floor=0.82,
        petal_outer_rgb=(240.0, 228.0, 122.0),
        petal_inner_rgb=(252.0, 242.0, 146.0),
        petal_heart_rgb=(220.0, 196.0, 74.0),
        petal_tip_rgb=(255.0, 252.0, 204.0),
        petal_spec_rgb=(255.0, 254.0, 228.0),
        foliage_rgb=(82.0, 136.0, 68.0),
        foliage_spec_rgb=(170.0, 204.0, 120.0),
        thorn_rgb=(82.0, 136.0, 68.0),
        stamen_rgb=(224.0, 188.0, 76.0),
        anther_rgb=(176.0, 132.0, 46.0),
        center_rgb=(82.0, 60.0, 40.0),
        center_accent_rgb=(218.0, 180.0, 68.0),
        accent_rgba=(204, 168, 42, 255),
        accent_disabled_rgba=(146, 142, 130, 220),
        heart_blend=0.54,
        tip_blend=0.52,
        tip_lift_base=0.98,
        tip_lift_span=0.08,
        spec_strength=0.13,
    ),
)

SAKURA_CULTIVARS: tuple[CultivarSpec, ...] = (
    CultivarSpec(
        key="yoshino",
        name="Yoshino",
        short_name="Yoshino",
        species="sakura",
        heart_uses_v=True,
        petal_ao_floor=0.84,
        petal_outer_rgb=(252.0, 212.0, 226.0),
        petal_inner_rgb=(255.0, 228.0, 238.0),
        petal_heart_rgb=(236.0, 102.0, 144.0),
        petal_tip_rgb=(255.0, 248.0, 251.0),
        petal_spec_rgb=(255.0, 246.0, 250.0),
        foliage_rgb=(94.0, 138.0, 72.0),
        foliage_spec_rgb=(178.0, 204.0, 118.0),
        thorn_rgb=(102.0, 70.0, 60.0),
        bark_rgb=(102.0, 70.0, 60.0),
        calyx_rgb=(142.0, 72.0, 82.0),
        stamen_rgb=(236.0, 162.0, 182.0),
        anther_rgb=(228.0, 174.0, 62.0),
        center_rgb=(194.0, 112.0, 124.0),
        accent_rgba=(224, 120, 150, 255),
        accent_disabled_rgba=(144, 134, 138, 220),
        heart_blend=0.72,
        tip_blend=0.55,
        tip_lift_base=0.99,
        tip_lift_span=0.07,
        spec_strength=0.12,
    ),
    CultivarSpec(
        key="yaezakura",
        name="Yaezakura",
        short_name="Yaezak.",
        species="sakura",
        heart_uses_v=True,
        petal_ao_floor=0.80,
        petal_outer_rgb=(242.0, 146.0, 178.0),
        petal_inner_rgb=(252.0, 178.0, 202.0),
        petal_heart_rgb=(206.0, 56.0, 104.0),
        petal_tip_rgb=(255.0, 220.0, 234.0),
        petal_spec_rgb=(255.0, 232.0, 240.0),
        foliage_rgb=(88.0, 132.0, 68.0),
        foliage_spec_rgb=(170.0, 198.0, 114.0),
        thorn_rgb=(96.0, 66.0, 58.0),
        bark_rgb=(96.0, 66.0, 58.0),
        calyx_rgb=(136.0, 60.0, 76.0),
        stamen_rgb=(238.0, 152.0, 178.0),
        anther_rgb=(234.0, 182.0, 66.0),
        center_rgb=(188.0, 86.0, 114.0),
        accent_rgba=(216, 88, 132, 255),
        accent_disabled_rgba=(142, 130, 136, 220),
        heart_blend=0.78,
        tip_blend=0.52,
        tip_lift_base=0.97,
        tip_lift_span=0.09,
        spec_strength=0.13,
    ),
    CultivarSpec(
        key="shirotae",
        name="Shirotae",
        short_name="Shiro.",
        species="sakura",
        heart_uses_v=True,
        petal_ao_floor=0.86,
        petal_outer_rgb=(242.0, 246.0, 240.0),
        petal_inner_rgb=(252.0, 254.0, 250.0),
        petal_heart_rgb=(218.0, 218.0, 140.0),
        petal_tip_rgb=(255.0, 255.0, 255.0),
        petal_spec_rgb=(255.0, 255.0, 248.0),
        foliage_rgb=(88.0, 140.0, 74.0),
        foliage_spec_rgb=(172.0, 206.0, 126.0),
        thorn_rgb=(104.0, 74.0, 62.0),
        bark_rgb=(104.0, 74.0, 62.0),
        calyx_rgb=(118.0, 124.0, 74.0),
        stamen_rgb=(228.0, 218.0, 164.0),
        anther_rgb=(222.0, 176.0, 62.0),
        center_rgb=(166.0, 184.0, 96.0),
        accent_rgba=(124, 158, 74, 255),
        accent_disabled_rgba=(138, 142, 134, 220),
        heart_blend=0.64,
        tip_blend=0.55,
        tip_lift_base=0.99,
        tip_lift_span=0.06,
        spec_strength=0.12,
    ),
)


@dataclass(frozen=True, slots=True)
class SpeciesSpec:
    """Botanical species specification, curated cultivars, and default camera framing."""

    key: str
    name: str
    short_name: str
    hotkey: str
    cultivars: tuple[CultivarSpec, ...]
    default_yaw: float = DEFAULT_YAW
    default_pitch: float = DEFAULT_PITCH
    default_zoom: float = DEFAULT_ZOOM
    startup_pitch: float = STARTUP_PITCH
    startup_zoom: float = STARTUP_ZOOM
    pivot_y: float = PIVOT_Y


SPECIES: tuple[SpeciesSpec, ...] = (
    SpeciesSpec(
        key="rose",
        name="Rose",
        short_name="Rose",
        hotkey="1",
        cultivars=ROSE_CULTIVARS,
        default_yaw=DEFAULT_YAW,
        default_pitch=DEFAULT_PITCH,
        default_zoom=DEFAULT_ZOOM,
        startup_pitch=STARTUP_PITCH,
        startup_zoom=STARTUP_ZOOM,
        pivot_y=PIVOT_Y,
    ),
    SpeciesSpec(
        key="tulip",
        name="Tulip",
        short_name="Tulip",
        hotkey="2",
        cultivars=TULIP_CULTIVARS,
        default_yaw=0.45,
        default_pitch=0.42,
        default_zoom=1.02,
        startup_pitch=1.38,
        startup_zoom=1.18,
        pivot_y=-0.20,
    ),
    SpeciesSpec(
        key="lotus",
        name="Lotus",
        short_name="Lotus",
        hotkey="3",
        cultivars=LOTUS_CULTIVARS,
        default_yaw=0.35,
        default_pitch=0.56,
        default_zoom=0.98,
        startup_pitch=1.42,
        startup_zoom=1.16,
        pivot_y=-0.18,
    ),
    SpeciesSpec(
        key="sunflower",
        name="Sunflower",
        short_name="Sunfl.",
        hotkey="4",
        cultivars=SUNFLOWER_CULTIVARS,
        default_yaw=0.30,
        default_pitch=0.60,
        default_zoom=0.98,
        startup_pitch=1.38,
        startup_zoom=1.14,
        pivot_y=-0.16,
    ),
    SpeciesSpec(
        key="sakura",
        name="Sakura",
        short_name="Sakura",
        hotkey="5",
        cultivars=SAKURA_CULTIVARS,
        default_yaw=0.40,
        default_pitch=0.54,
        default_zoom=1.02,
        startup_pitch=1.42,
        startup_zoom=1.20,
        pivot_y=-0.18,
    ),
)

SPECIES_BY_KEY: dict[str, SpeciesSpec] = {s.key: s for s in SPECIES}
DEFAULT_SPECIES: SpeciesSpec = SPECIES[0]

CULTIVAR_BY_KEY: dict[str, CultivarSpec] = {c.key: c for c in CULTIVARS}
ALL_CULTIVARS_BY_SPECIES: dict[str, dict[str, CultivarSpec]] = {
    s.key: {c.key: c for c in s.cultivars} for s in SPECIES
}
DEFAULT_CULTIVAR: CultivarSpec = CULTIVARS[0]


def get_species(species: SpeciesSpec | str | None) -> SpeciesSpec:
    """Resolve a ``SpeciesSpec`` from an instance, key/name string, or hotkey ('1'..'5')."""
    if species is None:
        return DEFAULT_SPECIES
    if isinstance(species, SpeciesSpec):
        return species
    norm = species.strip().lower()
    if norm in SPECIES_BY_KEY:
        return SPECIES_BY_KEY[norm]
    for candidate in SPECIES:
        if candidate.name.lower() == norm or candidate.hotkey == norm:
            return candidate
    raise ValueError(f"Unknown flower species: {species!r}")


def get_cultivar(
    cultivar: CultivarSpec | str | None,
    species: SpeciesSpec | str | None = None,
) -> CultivarSpec:
    """Resolve a cultivar spec, optionally scoped to a specific species."""
    species_spec = get_species(species) if species is not None else None
    if cultivar is None:
        return species_spec.cultivars[0] if species_spec is not None else DEFAULT_CULTIVAR
    if isinstance(cultivar, CultivarSpec):
        return cultivar
    norm = cultivar.strip().lower()
    if species_spec is not None:
        resolved = ALL_CULTIVARS_BY_SPECIES[species_spec.key].get(norm)
        if resolved is None:
            for cand in species_spec.cultivars:
                if cand.name.lower() == norm:
                    return cand
            raise ValueError(
                f"Unknown cultivar {cultivar!r} for species {species_spec.key!r}"
            )
        return resolved
    resolved = CULTIVAR_BY_KEY.get(norm)
    if resolved is not None:
        return resolved
    for spec in SPECIES:
        for cand in spec.cultivars:
            if cand.key == norm or cand.name.lower() == norm:
                return cand
    raise ValueError(f"Unknown flower cultivar: {cultivar!r}")


@dataclass(frozen=True, slots=True)
class MoodSpec:
    """Canvas, directional lighting, bounce, and adaptive HUD palette for one mood."""

    key: str
    name: str
    short_name: str
    is_dark: bool
    bg_hex: str
    key_light: tuple[float, float, float]
    fill_light: tuple[float, float, float]
    ambient_strength: float
    key_strength: float
    fill_strength: float
    bounce_strength: float
    ambient_tint: tuple[float, float, float]
    key_tint: tuple[float, float, float]
    fill_tint: tuple[float, float, float]
    bounce_tint: tuple[float, float, float]
    bounce_scatter_rgb: tuple[float, float, float]
    min_light: float
    max_light: float
    pill_fill_rgba: tuple[int, int, int, int]
    pill_edge_rgba: tuple[int, int, int, int]
    disabled_fill_rgba: tuple[int, int, int, int]
    disabled_edge_rgba: tuple[int, int, int, int]
    ink_enabled_rgb: tuple[int, int, int]
    ink_disabled_rgb: tuple[int, int, int]
    icon_enabled_rgb: tuple[int, int, int]
    icon_disabled_rgb: tuple[int, int, int]
    track_groove_enabled_rgba: tuple[int, int, int, int]
    track_groove_disabled_rgba: tuple[int, int, int, int]
    thumb_core_enabled_rgba: tuple[int, int, int, int]
    thumb_core_disabled_rgba: tuple[int, int, int, int]
    thumb_shadow_rgb: tuple[int, int, int]
    thumb_shadow_alphas: tuple[float, float]


MOODS: tuple[MoodSpec, ...] = (
    MoodSpec(
        key="daylight",
        name="Daylight",
        short_name="Day",
        is_dark=False,
        bg_hex="#FAF5EC",
        key_light=KEY_LIGHT,
        fill_light=FILL_LIGHT,
        ambient_strength=0.34,
        key_strength=0.56,
        fill_strength=0.16,
        bounce_strength=0.24,
        ambient_tint=(1.0, 1.0, 1.0),
        key_tint=(1.0, 1.0, 1.0),
        fill_tint=(1.0, 1.0, 1.0),
        bounce_tint=(1.0, 1.0, 1.0),
        bounce_scatter_rgb=(0.0, 0.0, 0.0),
        min_light=0.24,
        max_light=1.18,
        pill_fill_rgba=HUD_PILL_FILL_RGBA,
        pill_edge_rgba=HUD_PILL_EDGE_RGBA,
        disabled_fill_rgba=HUD_DISABLED_FILL_RGBA,
        disabled_edge_rgba=HUD_DISABLED_EDGE_RGBA,
        ink_enabled_rgb=HUD_ENABLED_INK_RGB,
        ink_disabled_rgb=HUD_DISABLED_INK_RGB,
        icon_enabled_rgb=HUD_ENABLED_INK_RGB,
        icon_disabled_rgb=HUD_DISABLED_INK_RGB,
        track_groove_enabled_rgba=SPEED_TRACK_GROOVE_ENABLED_RGBA,
        track_groove_disabled_rgba=SPEED_TRACK_GROOVE_DISABLED_RGBA,
        thumb_core_enabled_rgba=SPEED_THUMB_CORE_ENABLED_RGBA,
        thumb_core_disabled_rgba=SPEED_THUMB_CORE_DISABLED_RGBA,
        thumb_shadow_rgb=HUD_ENABLED_INK_RGB,
        thumb_shadow_alphas=(28.0, 52.0),
    ),
    MoodSpec(
        key="golden",
        name="Golden",
        short_name="Gold",
        is_dark=False,
        bg_hex="#F7EDE0",
        key_light=_normalize(0.78, 0.34, 0.52),
        fill_light=_normalize(-0.56, 0.32, 0.40),
        ambient_strength=0.32,
        key_strength=0.58,
        fill_strength=0.16,
        bounce_strength=0.24,
        ambient_tint=(1.02, 0.96, 0.90),
        key_tint=(1.06, 0.94, 0.76),
        fill_tint=(0.94, 0.88, 0.96),
        bounce_tint=(1.04, 0.96, 0.86),
        bounce_scatter_rgb=(10.0, 6.0, 1.0),
        min_light=0.24,
        max_light=1.18,
        pill_fill_rgba=(248, 236, 218, 198),
        pill_edge_rgba=(198, 176, 148, 214),
        disabled_fill_rgba=(202, 198, 194, 196),
        disabled_edge_rgba=(162, 158, 154, 212),
        ink_enabled_rgb=(76, 62, 48),
        ink_disabled_rgb=(104, 98, 92),
        icon_enabled_rgb=(76, 62, 48),
        icon_disabled_rgb=(104, 98, 92),
        track_groove_enabled_rgba=(194, 174, 148, 142),
        track_groove_disabled_rgba=(160, 156, 152, 120),
        thumb_core_enabled_rgba=(252, 244, 232, 255),
        thumb_core_disabled_rgba=(232, 230, 226, 235),
        thumb_shadow_rgb=(76, 62, 48),
        thumb_shadow_alphas=(28.0, 54.0),
    ),
    MoodSpec(
        key="sage",
        name="Sage",
        short_name="Sage",
        is_dark=False,
        bg_hex="#ECF1EB",
        key_light=_normalize(0.32, 0.84, 0.44),
        fill_light=_normalize(-0.58, 0.36, 0.52),
        ambient_strength=0.40,
        key_strength=0.44,
        fill_strength=0.24,
        bounce_strength=0.25,
        ambient_tint=(0.95, 1.00, 0.97),
        key_tint=(0.94, 1.00, 0.98),
        fill_tint=(0.92, 0.98, 0.95),
        bounce_tint=(0.92, 0.99, 0.95),
        bounce_scatter_rgb=(4.0, 10.0, 6.0),
        min_light=0.26,
        max_light=1.12,
        pill_fill_rgba=(228, 238, 228, 196),
        pill_edge_rgba=(164, 182, 166, 212),
        disabled_fill_rgba=(194, 200, 196, 196),
        disabled_edge_rgba=(154, 162, 156, 212),
        ink_enabled_rgb=(54, 68, 58),
        ink_disabled_rgb=(94, 104, 96),
        icon_enabled_rgb=(54, 68, 58),
        icon_disabled_rgb=(94, 104, 96),
        track_groove_enabled_rgba=(162, 178, 164, 142),
        track_groove_disabled_rgba=(154, 162, 156, 120),
        thumb_core_enabled_rgba=(240, 246, 240, 255),
        thumb_core_disabled_rgba=(226, 232, 228, 235),
        thumb_shadow_rgb=(54, 68, 58),
        thumb_shadow_alphas=(28.0, 50.0),
    ),
    MoodSpec(
        key="twilight",
        name="Twilight",
        short_name="Night",
        is_dark=True,
        bg_hex="#141822",
        key_light=_normalize(-0.46, 0.76, 0.45),
        fill_light=_normalize(0.74, 0.18, 0.10),
        ambient_strength=0.28,
        key_strength=0.56,
        fill_strength=0.24,
        bounce_strength=0.28,
        ambient_tint=(0.82, 0.88, 1.04),
        key_tint=(0.86, 0.92, 1.05),
        fill_tint=(1.14, 0.90, 0.72),
        bounce_tint=(0.64, 0.72, 1.10),
        bounce_scatter_rgb=(8.0, 12.0, 30.0),
        min_light=0.22,
        max_light=1.14,
        pill_fill_rgba=(34, 40, 54, 210),
        pill_edge_rgba=(82, 94, 118, 220),
        disabled_fill_rgba=(26, 30, 42, 192),
        disabled_edge_rgba=(62, 70, 88, 200),
        ink_enabled_rgb=(237, 234, 228),
        ink_disabled_rgb=(138, 144, 158),
        icon_enabled_rgb=(237, 234, 228),
        icon_disabled_rgb=(138, 144, 158),
        track_groove_enabled_rgba=(96, 108, 134, 150),
        track_groove_disabled_rgba=(72, 82, 102, 128),
        thumb_core_enabled_rgba=(237, 234, 228, 255),
        thumb_core_disabled_rgba=(176, 182, 196, 225),
        thumb_shadow_rgb=(10, 12, 18),
        thumb_shadow_alphas=(36.0, 74.0),
    ),
)

MOOD_BY_KEY: dict[str, MoodSpec] = {m.key: m for m in MOODS}
DEFAULT_MOOD: MoodSpec = MOODS[0]


def get_mood(mood: MoodSpec | str | None) -> MoodSpec:
    """Resolve a mood spec from a ``MoodSpec`` instance or key string."""
    if mood is None:
        return DEFAULT_MOOD
    if isinstance(mood, MoodSpec):
        return mood
    resolved = MOOD_BY_KEY.get(mood.strip().lower())
    if resolved is None:
        raise ValueError(f"Unknown mood: {mood!r}")
    return resolved


@dataclass(frozen=True, slots=True)
class DetailTierSpec:
    """Immutable tessellation and surface-detail specification for a mesh tier."""

    key: str
    label: str
    num_petals: int
    petal_u_steps: int
    petal_v_steps: int
    receptacle_radial_steps: int
    receptacle_height_steps: int
    num_sepals: int
    sepal_u_steps: int
    sepal_v_steps: int
    stem_radial_steps: int
    stem_height_steps: int
    leaf_u_steps: int
    leaf_v_steps: int
    petal_fullness: float = 0.0
    petal_ripple_amp: float = 0.0


STANDARD_TIER = DetailTierSpec(
    key="standard",
    label="Standard",
    num_petals=NUM_PETALS,
    petal_u_steps=PETAL_U_STEPS,
    petal_v_steps=PETAL_V_STEPS,
    receptacle_radial_steps=RECEPTACLE_RADIAL_STEPS,
    receptacle_height_steps=RECEPTACLE_HEIGHT_STEPS,
    num_sepals=NUM_SEPALS,
    sepal_u_steps=SEPAL_U_STEPS,
    sepal_v_steps=SEPAL_V_STEPS,
    stem_radial_steps=STEM_RADIAL_STEPS,
    stem_height_steps=STEM_HEIGHT_STEPS,
    leaf_u_steps=LEAF_U_STEPS,
    leaf_v_steps=LEAF_V_STEPS,
    petal_fullness=0.0,
    petal_ripple_amp=0.0,
)

LUSH_TIER = DetailTierSpec(
    key="lush",
    label="Lush",
    num_petals=32,
    petal_u_steps=7,
    petal_v_steps=6,
    receptacle_radial_steps=12,
    receptacle_height_steps=5,
    num_sepals=5,
    sepal_u_steps=4,
    sepal_v_steps=5,
    stem_radial_steps=8,
    stem_height_steps=12,
    leaf_u_steps=6,
    leaf_v_steps=7,
    petal_fullness=0.013,
    petal_ripple_amp=0.0085,
)

DETAIL_TIERS: tuple[DetailTierSpec, ...] = (STANDARD_TIER, LUSH_TIER)
_DETAIL_TIER_BY_KEY: dict[str, DetailTierSpec] = {tier.key: tier for tier in DETAIL_TIERS}


def resolve_detail_tier(tier: DetailTierSpec | str) -> DetailTierSpec:
    """Resolve a ``DetailTierSpec`` or tier key/label string into a ``DetailTierSpec``."""
    if isinstance(tier, DetailTierSpec):
        return tier
    normalized = tier.strip().lower()
    if normalized == "std":
        return STANDARD_TIER
    if normalized in _DETAIL_TIER_BY_KEY:
        return _DETAIL_TIER_BY_KEY[normalized]
    for candidate in DETAIL_TIERS:
        if candidate.label.lower() == normalized:
            return candidate
    raise ValueError(f"Unknown detail tier: {tier!r}")


# ---------------------------------------------------------------------------
# 3D Mesh Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FaceSpec:
    """Topology and botanical shading metadata for one mesh polygon."""

    indices: tuple[int, ...]
    # Material keys: "petal", "foliage", "thorn", "bark", "calyx",
    # "stamen", "anther", "center", "center_accent"
    material: str
    v_frac: float = 0.5
    layer_frac: float = 0.5
    double_sided: bool = True


def _catmull_rom_1d(p0: float, p1: float, p2: float, p3: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def _sample_receptacle_profile(height_steps: int) -> list[tuple[float, float]]:
    """Sample ``height_steps + 1`` rings smoothly through ``_RECEPTACLE_PROFILE``."""
    if height_steps == 3:
        return list(_RECEPTACLE_PROFILE)

    pts = _RECEPTACLE_PROFILE
    n_seg = len(pts) - 1
    p_start = (2.0 * pts[0][0] - pts[1][0], 2.0 * pts[0][1] - pts[1][1])
    p_end = (2.0 * pts[-1][0] - pts[-2][0], 2.0 * pts[-1][1] - pts[-2][1])
    ext = (p_start, *pts, p_end)

    sampled: list[tuple[float, float]] = []
    for iv in range(height_steps + 1):
        if iv == 0:
            sampled.append(pts[0])
            continue
        if iv == height_steps:
            sampled.append(pts[-1])
            continue
        u = (iv / height_steps) * n_seg
        seg = min(n_seg - 1, int(u))
        local_t = u - seg
        a0, a1, a2, a3 = ext[seg], ext[seg + 1], ext[seg + 2], ext[seg + 3]
        y = _catmull_rom_1d(a0[0], a1[0], a2[0], a3[0], local_t)
        r = max(0.02, _catmull_rom_1d(a0[1], a1[1], a2[1], a3[1], local_t))
        sampled.append((y, r))
    return sampled


class FlowerMesh:
    """Holds mutable 3D vertices, fixed polygon topology, and breeze sway metadata."""

    def __init__(
        self,
        bloom: float = 1.0,
        detail_tier: DetailTierSpec | str = STANDARD_TIER,
        species: SpeciesSpec | str = DEFAULT_SPECIES,
    ) -> None:
        self.species: SpeciesSpec = get_species(species)
        self.detail_tier: DetailTierSpec = resolve_detail_tier(detail_tier)
        self.bloom: float = _clamp(bloom, 0.0, 1.0)
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[FaceSpec] = []
        # Parallel to self.vertices: (stem_height_factor, local_flutter_amp, phase_offset)
        self.vertex_sway: list[tuple[float, float, float]] = []
        self._build_topology_and_vertices(self.bloom)

    def set_species(
        self,
        species: SpeciesSpec | str,
        detail_tier: DetailTierSpec | str | None = None,
        bloom: float | None = None,
    ) -> None:
        """Switch flower species (and optionally detail tier / bloom) and rebuild mesh."""
        self.species = get_species(species)
        if detail_tier is not None:
            self.detail_tier = resolve_detail_tier(detail_tier)
        if bloom is not None:
            self.bloom = _clamp(bloom, 0.0, 1.0)
        self._build_topology_and_vertices(self.bloom)

    def set_detail_tier(
        self,
        detail_tier: DetailTierSpec | str,
        bloom: float | None = None,
    ) -> None:
        """Switch detail tier and rebuild vertices, topology, and sway metadata."""
        self.detail_tier = resolve_detail_tier(detail_tier)
        if bloom is not None:
            self.bloom = _clamp(bloom, 0.0, 1.0)
        self._build_topology_and_vertices(self.bloom)

    def update_bloom(self, bloom: float) -> None:
        """Recompute vertex positions for a given bloom factor in [0, 1] without topology churn."""
        self.bloom = _clamp(bloom, 0.0, 1.0)
        self.vertices.clear()
        self._populate_vertices(self.bloom, build_topology=False)

    def _build_topology_and_vertices(self, bloom: float) -> None:
        self.vertices.clear()
        self.faces.clear()
        self.vertex_sway.clear()
        self._populate_vertices(bloom, build_topology=True)

    def _add_grid_surface(
        self,
        grid: list[list[int]],
        material: str,
        layer_frac: float,
        double_sided: bool,
        v_max: int,
        u_max: int,
        *,
        collapse_tip: bool = False,
        v_base: float = 0.0,
        v_span: float = 1.0,
    ) -> None:
        for iv in range(v_max):
            v_mid = v_base + v_span * ((iv + 0.5) / v_max)
            is_tip_row = collapse_tip and (iv == v_max - 1)
            for iu in range(u_max):
                i0 = grid[iv][iu]
                i1 = grid[iv][iu + 1]
                i2 = grid[iv + 1][iu + 1]
                i3 = grid[iv + 1][iu]
                verts = (i0, i1, i2) if is_tip_row else (i0, i1, i2, i3)
                self.faces.append(
                    FaceSpec(
                        indices=verts,
                        material=material,
                        v_frac=v_mid,
                        layer_frac=layer_frac,
                        double_sided=double_sided,
                    )
                )

    def _build_tube_from_rings(
        self,
        rings: Sequence[tuple[float, float, float, float, float]],
        radial_steps: int,
        material: str,
        layer_frac: float,
        build_topology: bool,
        *,
        double_sided_walls: bool = False,
        cap_bottom: bool = False,
        cap_top: bool = False,
    ) -> list[list[int]]:
        """Build a cylindrical/conical tube along ``(cx, cy, cz, radius, sway_h)`` rings."""
        grid: list[list[int]] = []
        for cx, cy, cz, r, sway_h in rings:
            row: list[int] = []
            for iu in range(radial_steps + 1):
                ang = 2.0 * math.pi * (iu % radial_steps) / radial_steps
                row.append(len(self.vertices))
                self.vertices.append((cx + r * math.cos(ang), cy, cz + r * math.sin(ang)))
                if build_topology:
                    self.vertex_sway.append((sway_h, 0.0, 0.0))
            grid.append(row)

        if build_topology:
            self._add_grid_surface(
                grid=grid,
                material=material,
                layer_frac=layer_frac,
                double_sided=double_sided_walls,
                v_max=len(rings) - 1,
                u_max=radial_steps,
            )
            if cap_bottom:
                self.faces.append(
                    FaceSpec(
                        indices=tuple(grid[-1][:-1][::-1]),
                        material=material,
                        v_frac=0.2,
                        layer_frac=layer_frac,
                        double_sided=True,
                    )
                )
            if cap_top:
                self.faces.append(
                    FaceSpec(
                        indices=tuple(grid[0][:-1]),
                        material=material,
                        v_frac=0.95,
                        layer_frac=layer_frac,
                        double_sided=True,
                    )
                )
        return grid

    def _build_stamen_filament(
        self,
        base_r: float,
        base_y: float,
        tip_r: float,
        tip_y: float,
        theta: float,
        filament_half_w: float,
        anther_len: float,
        anther_w: float,
        build_topology: bool,
        *,
        flutter_amp: float = 0.012,
    ) -> None:
        """Build a curved slender 2-segment stamen filament ribbon + 3D diamond anther tip."""
        cx = math.cos(theta)
        cz = math.sin(theta)
        tx = -cz
        tz = cx

        mid_r = _lerp(base_r, tip_r, 0.45) - 0.012
        mid_y = _lerp(base_y, tip_y, 0.54)

        pts_ring: list[tuple[float, float, float, float]] = [
            (base_r, base_y, filament_half_w, 0.0),
            (mid_r, mid_y, filament_half_w * 0.85, 0.45),
            (tip_r, tip_y, filament_half_w * 0.70, 0.90),
        ]
        grid: list[list[int]] = []
        for idx_r, (rr, yy, hw, frac) in enumerate(pts_ring):
            row: list[int] = []
            for side in (-1.0, 1.0):
                row.append(len(self.vertices))
                self.vertices.append((rr * cx + side * hw * tx, yy, rr * cz + side * hw * tz))
                if build_topology:
                    amp = 0.0 if idx_r == 0 else flutter_amp * frac
                    self.vertex_sway.append((1.0, amp, theta))
            grid.append(row)

        if build_topology:
            self._add_grid_surface(
                grid=grid,
                material="stamen",
                layer_frac=0.2,
                double_sided=True,
                v_max=2,
                u_max=1,
            )

        # 3D faceted diamond anther cap sitting cleanly at (tip_r, tip_y)
        a_base_y = tip_y - anther_len * 0.20
        a_mid_y = tip_y + anther_len * 0.35
        a_top_y = tip_y + anther_len * 0.85
        dr = (tip_r - mid_r)
        dy_d = (tip_y - mid_y)
        d_len = math.sqrt(dr * dr + dy_d * dy_d) or 1.0
        nr = dy_d / d_len
        ny_d = -dr / d_len

        i_bot = len(self.vertices)
        self.vertices.append((tip_r * cx, a_base_y, tip_r * cz))
        self.vertices.append((tip_r * cx + anther_w * tx, a_mid_y, tip_r * cz + anther_w * tz))
        self.vertices.append((tip_r * cx - anther_w * tx, a_mid_y, tip_r * cz - anther_w * tz))
        out_r = tip_r + anther_w * 0.85 * nr
        self.vertices.append((out_r * cx, a_mid_y + anther_w * 0.85 * ny_d, out_r * cz))
        self.vertices.append((tip_r * cx, a_top_y, tip_r * cz))
        if build_topology:
            for _ in range(5):
                self.vertex_sway.append((1.0, flutter_amp, theta))
            self.faces.extend(
                (
                    FaceSpec((i_bot, i_bot + 1, i_bot + 3), "anther", 0.7, 0.2, True),
                    FaceSpec((i_bot, i_bot + 3, i_bot + 2), "anther", 0.7, 0.2, True),
                    FaceSpec((i_bot + 1, i_bot + 4, i_bot + 3), "anther", 0.95, 0.2, True),
                    FaceSpec((i_bot + 3, i_bot + 4, i_bot + 2), "anther", 0.95, 0.2, True),
                )
            )

    def _populate_vertices(self, bloom: float, build_topology: bool) -> None:
        b = _clamp(bloom, 0.0, 1.0)
        key = self.species.key
        if key == "rose":
            self._populate_rose(b, build_topology)
        elif key == "tulip":
            self._populate_tulip(b, build_topology)
        elif key == "lotus":
            self._populate_lotus(b, build_topology)
        elif key == "sunflower":
            self._populate_sunflower(b, build_topology)
        elif key == "sakura":
            self._populate_sakura(b, build_topology)
        else:
            raise ValueError(f"Unsupported species: {key!r}")

    def _populate_rose(self, bloom: float, build_topology: bool) -> None:
        self._build_petals(bloom, build_topology)
        self._build_receptacle(build_topology)
        self._build_sepals(bloom, build_topology)
        self._build_stem_and_thorns(build_topology)
        self._build_leaves(build_topology)

    # -- Rose Petals ---------------------------------------------------------

    def _build_petals(self, bloom: float, build_topology: bool) -> None:
        tier = self.detail_tier
        num_petals = tier.num_petals
        u_steps = tier.petal_u_steps
        v_steps = tier.petal_v_steps
        fullness_amp = tier.petal_fullness
        ripple_amp = tier.petal_ripple_amp

        for idx in range(num_petals):
            t = idx / (num_petals - 1) if num_petals > 1 else 0.0

            # Outer petals peel open slightly earlier than the inner spiral core
            lag = 0.34 * (1.0 - t)
            local_b = _smoothstep(lag, 1.0, bloom)

            theta_center = idx * GOLDEN_ANGLE
            r_base = 0.036 + 0.195 * (t ** 1.10)
            y_base = 0.23 - 0.10 * (t ** 1.15)
            petal_len = 0.45 + 0.42 * (t ** 0.72)

            tilt_bud = -0.04 + 0.22 * t
            tilt_open = 0.16 + 0.70 * (t ** 1.05)
            tilt = _lerp(tilt_bud, tilt_open, local_b)

            sin_tilt = math.sin(tilt)
            cos_tilt = math.cos(tilt)

            twist_max = _lerp(0.58, 0.07, t) * (1.0 - 0.30 * local_b)
            half_wrap_base = _lerp(1.26, 0.68, t ** 0.72) * _lerp(1.08, 1.0, local_b)

            curl_out = local_b * (0.04 + 0.24 * (t ** 1.20))
            bud_inward = (1.0 - local_b) * (0.12 + 0.14 * t)
            belly_amp = 0.14 * (0.35 + 0.65 * t)
            edge_roll = local_b * (0.02 + 0.075 * t)

            grid: list[list[int]] = []
            for iv in range(v_steps + 1):
                v = iv / v_steps
                w_env = 0.26 + 0.74 * math.sin(math.pi * (0.08 + 0.79 * v))
                flutter_v = (v ** 1.8) * (0.30 + 0.70 * t)
                row: list[int] = []
                for iu in range(u_steps + 1):
                    u = -1.0 + 2.0 * (iu / u_steps)
                    u2 = u * u

                    s = v * (1.0 - 0.14 * u2 * v)
                    s -= 0.016 * t * math.exp(-12.0 * u2) * (v ** 2)

                    r = (
                        r_base
                        + petal_len
                        * (
                            sin_tilt * s
                            + belly_amp * math.sin(math.pi * s)
                            + curl_out * max(0.0, s - 0.52) ** 2
                            - bud_inward * (s ** 2.2)
                        )
                        + edge_roll * u2 * max(0.0, s - 0.38) ** 1.4
                        + 0.016 * t * math.sin(u * 2.4 + idx * 1.85) * (s ** 1.5)
                    )
                    y_extra = 0.0
                    if fullness_amp > 0.0:
                        r += (
                            fullness_amp
                            * (0.45 + 0.55 * t)
                            * math.sin(math.pi * s)
                            * (1.0 - 0.35 * u2)
                        )
                    if ripple_amp > 0.0:
                        ripple_s = max(0.0, s - 0.42)
                        if ripple_s > 0.0:
                            ripple_env = (
                                ripple_amp
                                * (0.25 + 0.75 * local_b)
                                * (0.20 + 0.80 * t)
                                * (ripple_s ** 1.5)
                            )
                            r += ripple_env * (
                                math.sin(u * 4.2 + idx * 2.17)
                                + 0.45 * math.cos(u * 6.5 - idx * 1.3)
                            )
                            y_extra = 0.45 * ripple_env * math.cos(u * 4.2 + idx * 2.17)

                    min_r = 0.020 + 0.028 * t + 0.012 * v
                    if r < min_r:
                        r = min_r

                    y = (
                        y_base
                        + petal_len
                        * (
                            cos_tilt * s
                            - 0.15 * curl_out * max(0.0, s - 0.58) ** 2
                        )
                        - 0.032 * edge_roll * u2 * max(0.0, s - 0.48) ** 1.5
                        + y_extra
                    )

                    theta = (
                        theta_center
                        + twist_max * (s - 0.12)
                        + u * half_wrap_base * w_env
                    )
                    x = r * math.cos(theta)
                    z = r * math.sin(theta)

                    row.append(len(self.vertices))
                    self.vertices.append((x, y, z))
                    if build_topology:
                        # Anchor petal base (iv == 0) to receptacle stem_height_factor=1.0
                        amp = 0.0 if iv == 0 else 0.022 * flutter_v
                        self.vertex_sway.append((1.0, amp, theta_center + 0.35 * u))
                grid.append(row)

            if build_topology:
                self._add_grid_surface(
                    grid=grid,
                    material="petal",
                    layer_frac=t,
                    double_sided=True,
                    v_max=v_steps,
                    u_max=u_steps,
                )

    # -- Receptacle (floral cup under petals) --------------------------------

    def _build_receptacle(self, build_topology: bool) -> None:
        tier = self.detail_tier
        radial_steps = tier.receptacle_radial_steps
        height_steps = tier.receptacle_height_steps
        profile = _sample_receptacle_profile(height_steps)

        grid: list[list[int]] = []
        for y, r in profile:
            row: list[int] = []
            for iu in range(radial_steps + 1):
                ang = 2.0 * math.pi * (iu % radial_steps) / radial_steps
                row.append(len(self.vertices))
                self.vertices.append((r * math.cos(ang), y, r * math.sin(ang)))
                if build_topology:
                    self.vertex_sway.append((1.0, 0.0, 0.0))
            grid.append(row)

        disc_start = len(self.vertices)
        for iu in range(radial_steps):
            ang = 2.0 * math.pi * iu / radial_steps
            self.vertices.append((0.268 * math.cos(ang), 0.108, 0.268 * math.sin(ang)))
            if build_topology:
                self.vertex_sway.append((1.0, 0.0, 0.0))

        if build_topology:
            self._add_grid_surface(
                grid=grid,
                material="foliage",
                layer_frac=0.35,
                double_sided=False,
                v_max=height_steps,
                u_max=radial_steps,
            )
            self.faces.append(
                FaceSpec(
                    indices=tuple(range(disc_start, disc_start + radial_steps)),
                    material="petal",
                    v_frac=0.02,
                    layer_frac=0.0,
                    double_sided=True,
                )
            )

    # -- Sepals (calyx leaves) -----------------------------------------------

    def _build_sepals(self, bloom: float, build_topology: bool) -> None:
        tier = self.detail_tier
        num_sepals = tier.num_sepals
        u_steps = tier.sepal_u_steps
        v_steps = tier.sepal_v_steps

        b = _smoothstep(0.0, 0.85, bloom)
        for idx in range(num_sepals):
            theta_center = idx * (2.0 * math.pi / num_sepals) + 0.35
            r_base = 0.272
            y_base = 0.095
            sepal_len = 0.48
            tilt = _lerp(0.36, 1.80, b)

            cx = math.cos(theta_center)
            cz = math.sin(theta_center)
            tx = -cz
            tz = cx

            grid: list[list[int]] = []
            for iv in range(v_steps + 1):
                v = iv / v_steps
                half_w = 0.105 * (1.0 - v ** 0.95) * (0.85 + 0.35 * math.sin(math.pi * v))
                if iv == v_steps:
                    half_w = 0.0

                row: list[int] = []
                for iu in range(u_steps + 1):
                    u = -1.0 + 2.0 * (iu / u_steps)
                    arch = _lerp(0.11, 0.14, b) * math.sin(math.pi * v)
                    tip_curl = b * 0.11 * max(0.0, v - 0.45) ** 2

                    r_mid = r_base + sepal_len * (
                        math.sin(tilt) * v + arch - tip_curl * 0.35
                    )
                    y_mid = y_base + sepal_len * (
                        math.cos(tilt) * v - tip_curl + 0.04 * (1.0 - abs(u)) * (1.0 - v)
                    )

                    x = r_mid * cx + u * half_w * tx
                    z = r_mid * cz + u * half_w * tz
                    row.append(len(self.vertices))
                    self.vertices.append((x, y_mid, z))
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.024 * (v ** 1.7)
                        # Collapse u-phase variation at v=1 so sepal tip vertices stay coincident
                        self.vertex_sway.append((1.0, amp, theta_center + 0.25 * u * (1.0 - v)))
                grid.append(row)

            if build_topology:
                for iv in range(v_steps):
                    v_mid = (iv + 0.5) / v_steps
                    for iu in range(u_steps):
                        i0 = grid[iv][iu]
                        i1 = grid[iv][iu + 1]
                        i2 = grid[iv + 1][iu + 1]
                        i3 = grid[iv + 1][iu]
                        verts = (i0, i1, i2) if iv == v_steps - 1 else (i0, i1, i2, i3)
                        self.faces.append(
                            FaceSpec(
                                indices=verts,
                                material="foliage",
                                v_frac=0.35 + 0.55 * v_mid,
                                layer_frac=0.6,
                                double_sided=True,
                            )
                        )

    # -- Curved Stem & Thorns ------------------------------------------------

    @staticmethod
    def _stem_center(s: float) -> tuple[float, float, float, float]:
        """Return ``(x, y, z, radius)`` along the stem for ``s`` in ``[0 (top), 1 (bottom)]``."""
        y = -0.13 - 1.24 * s
        x = 0.075 * math.sin(s * 2.8)
        z = 0.040 * (1.0 - math.cos(s * 2.3))
        radius = _lerp(0.062, 0.045, s)
        return (x, y, z, radius)

    def _build_stem_and_thorns(self, build_topology: bool) -> None:
        tier = self.detail_tier
        radial_steps = tier.stem_radial_steps
        height_steps = tier.stem_height_steps

        grid: list[list[int]] = []
        for iv in range(height_steps + 1):
            s = iv / height_steps
            height_factor = 1.0 - s
            cx, cy, cz, r = self._stem_center(s)
            row: list[int] = []
            for iu in range(radial_steps + 1):
                ang = 2.0 * math.pi * (iu % radial_steps) / radial_steps
                row.append(len(self.vertices))
                self.vertices.append((cx + r * math.cos(ang), cy, cz + r * math.sin(ang)))
                if build_topology:
                    self.vertex_sway.append((height_factor, 0.0, 0.0))
            grid.append(row)

        if build_topology:
            self._add_grid_surface(
                grid=grid,
                material="foliage",
                layer_frac=0.25,
                double_sided=False,
                v_max=height_steps,
                u_max=radial_steps,
            )
            bottom_ring = tuple(grid[-1][:-1][::-1])
            self.faces.append(
                FaceSpec(
                    indices=bottom_ring,
                    material="foliage",
                    v_frac=0.2,
                    layer_frac=0.2,
                    double_sided=True,
                )
            )

        for s_pos, ang in _THORN_SPECS:
            cx, cy, cz, r_stem = self._stem_center(s_pos)
            dx = math.cos(ang)
            dz = math.sin(ang)
            tx = -dz
            tz = dx

            base_r = r_stem * 0.90
            tip_x = cx + (r_stem + 0.115) * dx
            tip_y = cy - 0.045
            tip_z = cz + (r_stem + 0.115) * dz

            p_top = (cx + base_r * dx, cy + 0.042, cz + base_r * dz)
            p_left = (cx + base_r * dx + 0.022 * tx, cy - 0.025, cz + base_r * dz + 0.022 * tz)
            p_right = (cx + base_r * dx - 0.022 * tx, cy - 0.025, cz + base_r * dz - 0.022 * tz)
            p_tip = (tip_x, tip_y, tip_z)

            idx_base = len(self.vertices)
            self.vertices.extend((p_top, p_left, p_right, p_tip))
            if build_topology:
                thorn_sway = (1.0 - s_pos, 0.0, 0.0)
                self.vertex_sway.extend((thorn_sway, thorn_sway, thorn_sway, thorn_sway))
                self.faces.extend(
                    (
                        FaceSpec((idx_base, idx_base + 1, idx_base + 3), "thorn", 0.6, 0.5, True),
                        FaceSpec(
                            (idx_base + 1, idx_base + 2, idx_base + 3), "thorn", 0.5, 0.5, True
                        ),
                        FaceSpec((idx_base + 2, idx_base, idx_base + 3), "thorn", 0.6, 0.5, True),
                    )
                )

    # -- 3D Folded Rose Leaves -----------------------------------------------

    def _build_leaves(self, build_topology: bool) -> None:
        tier = self.detail_tier
        u_steps = tier.leaf_u_steps
        v_steps = tier.leaf_v_steps

        for s_pos, az, leaf_len, leaf_w, pitch_down, bank in _LEAF_SPECS:
            cx, cy, cz, r_stem = self._stem_center(s_pos)
            dx = math.cos(az)
            dz = math.sin(az)
            tx = -dz
            tz = dx

            r_anchor = r_stem * 0.65
            root_x = cx + r_anchor * dx
            root_y = cy
            root_z = cz + r_anchor * dz
            root_height_factor = 1.0 - s_pos

            grid: list[list[int]] = []
            for iv in range(v_steps + 1):
                v = iv / v_steps
                if iv == v_steps:
                    width_profile = 0.0
                else:
                    width_profile = 0.08 * (1.0 - v) + 0.96 * math.sin(math.pi * (v ** 0.72))

                row: list[int] = []
                for iu in range(u_steps + 1):
                    u = -1.0 + 2.0 * (iu / u_steps)
                    dist_along = v * leaf_len
                    arch_y = -pitch_down * dist_along - 0.12 * (v ** 2.1)
                    v_fold = 0.048 * abs(u) * math.sin(math.pi * v)
                    roll_y = bank * u * (width_profile - 0.08 * (1.0 - v)) * leaf_w

                    lateral = u * width_profile * leaf_w
                    vx = root_x + dist_along * dx + lateral * tx
                    vz = root_z + dist_along * dz + lateral * tz
                    vy = root_y + arch_y + v_fold + roll_y

                    row.append(len(self.vertices))
                    self.vertices.append((vx, vy, vz))
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.036 * (v ** 1.6)
                        self.vertex_sway.append(
                            (root_height_factor, amp, az + 1.2 * v + 0.4 * u * (1.0 - v))
                        )
                grid.append(row)

            if build_topology:
                for iv in range(v_steps):
                    v_mid = (iv + 0.5) / v_steps
                    for iu in range(u_steps):
                        i0 = grid[iv][iu]
                        i1 = grid[iv][iu + 1]
                        i2 = grid[iv + 1][iu + 1]
                        i3 = grid[iv + 1][iu]
                        verts = (i0, i1, i2) if iv == v_steps - 1 else (i0, i1, i2, i3)
                        self.faces.append(
                            FaceSpec(
                                indices=verts,
                                material="foliage",
                                v_frac=0.35 + 0.65 * v_mid,
                                layer_frac=0.75,
                                double_sided=True,
                            )
                        )

    # -- Species 2: Tulip ----------------------------------------------------

    @staticmethod
    def _tulip_stem_center(s: float) -> tuple[float, float, float, float]:
        y = -0.08 - 1.29 * s
        x = 0.038 * math.sin(s * 2.2)
        z = 0.022 * (1.0 - math.cos(s * 1.9))
        radius = _lerp(0.056, 0.064, s)
        return (x, y, z, radius)

    def _populate_tulip(self, bloom: float, build_topology: bool) -> None:
        is_lush = self.detail_tier.key == "lush"
        u_steps = 8 if is_lush else 6
        v_steps = 9 if is_lush else 7
        fullness = self.detail_tier.petal_fullness
        ripple = self.detail_tier.petal_ripple_amp

        # 6 Goblet tepals in 2 alternating whorls (3 outer, 3 inner)
        for idx in range(6):
            is_outer = (idx % 2 == 0)
            layer_frac = 0.85 if is_outer else 0.25
            lag = 0.05 if is_outer else 0.16
            local_b = _smoothstep(lag, 1.0, bloom)

            theta_center = idx * (math.pi / 3.0) + 0.15
            r_base = 0.066 if is_outer else 0.048
            y_base = -0.015 if is_outer else 0.005
            petal_len = 0.90 if is_outer else 0.86

            tilt_bud = 0.14 if is_outer else 0.09
            tilt_open = 0.50 if is_outer else 0.34
            tilt = _lerp(tilt_bud, tilt_open, local_b)
            sin_t = math.sin(tilt)
            cos_t = math.cos(tilt)

            half_wrap = (0.90 if is_outer else 0.84) * _lerp(0.92, 1.0, local_b)
            inward_rim = _lerp(0.28, 0.085 if is_outer else 0.125, local_b)
            belly_amp = _lerp(0.18, 0.24, local_b)

            grid: list[list[int]] = []
            for iv in range(v_steps + 1):
                v = iv / v_steps
                w_env = 0.40 + 0.60 * math.sin(math.pi * (0.08 + 0.84 * v))
                row: list[int] = []
                for iu in range(u_steps + 1):
                    u = -1.0 + 2.0 * (iu / u_steps)
                    u2 = u * u
                    s = v * (1.0 - 0.10 * u2 * v)

                    spoon_cup = 0.046 * (1.0 - u2) * math.sin(math.pi * s)
                    rim_in = inward_rim * (max(0.0, s - 0.34) ** 1.65)
                    r = (
                        r_base
                        + petal_len
                        * (sin_t * s + belly_amp * math.sin(math.pi * (s ** 0.82)) - rim_in)
                        + spoon_cup
                    )
                    y_extra = 0.0
                    if fullness > 0.0:
                        r += fullness * math.sin(math.pi * s) * (1.0 - 0.3 * u2)
                    if ripple > 0.0 and s > 0.5:
                        env = ripple * 0.75 * local_b * ((s - 0.5) ** 1.3)
                        r += env * math.sin(u * 3.6 + idx * 1.4)
                        y_extra = 0.35 * env * math.cos(u * 3.6 + idx * 1.4)

                    r = max(0.030 + 0.015 * v, r)
                    y = y_base + petal_len * (cos_t * s - 0.08 * rim_in) + y_extra
                    theta = theta_center + u * half_wrap * w_env

                    row.append(len(self.vertices))
                    self.vertices.append((r * math.cos(theta), y, r * math.sin(theta)))
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.018 * (v ** 1.7)
                        self.vertex_sway.append((1.0, amp, theta_center + 0.3 * u))
                grid.append(row)

            if build_topology:
                self._add_grid_surface(
                    grid=grid,
                    material="petal",
                    layer_frac=layer_frac,
                    double_sided=True,
                    v_max=v_steps,
                    u_max=u_steps,
                )

        # Central pistil ovary & 3-lobed stigma crown
        pistil_rad = 9 if is_lush else 6
        pistil_rings = (
            (0.0, 0.36, 0.0, 0.044, 1.0),
            (0.0, 0.25, 0.0, 0.028, 1.0),
            (0.0, 0.13, 0.0, 0.042, 1.0),
            (0.0, 0.01, 0.0, 0.034, 1.0),
        )
        self._build_tube_from_rings(
            pistil_rings, pistil_rad, "center", 0.5, build_topology, cap_top=True
        )
        for lobe_idx in range(3):
            th_l = lobe_idx * (2.0 * math.pi / 3.0) + 0.35
            lcx = math.cos(th_l)
            lcz = math.sin(th_l)
            ltx = -lcz
            ltz = lcx
            i_l = len(self.vertices)
            self.vertices.extend(
                (
                    (0.022 * lcx, 0.356, 0.022 * lcz),
                    (0.038 * lcx + 0.020 * ltx, 0.360, 0.038 * lcz + 0.020 * ltz),
                    (0.056 * lcx, 0.364, 0.056 * lcz),
                    (0.038 * lcx - 0.020 * ltx, 0.360, 0.038 * lcz - 0.020 * ltz),
                    (0.040 * lcx, 0.382, 0.040 * lcz),
                )
            )
            if build_topology:
                for _ in range(5):
                    self.vertex_sway.append((1.0, 0.0, 0.0))
                self.faces.extend(
                    (
                        FaceSpec((i_l, i_l + 1, i_l + 4), "center", 0.95, 0.5, True),
                        FaceSpec((i_l + 1, i_l + 2, i_l + 4), "center", 0.95, 0.5, True),
                        FaceSpec((i_l + 2, i_l + 3, i_l + 4), "center", 0.95, 0.5, True),
                        FaceSpec((i_l + 3, i_l, i_l + 4), "center", 0.95, 0.5, True),
                    )
                )

        # 6 Stamens encircling pistil inside cup
        stamen_b = _smoothstep(0.15, 0.95, bloom)
        for k in range(6):
            th = k * (math.pi / 3.0) + 0.48
            self._build_stamen_filament(
                base_r=0.040,
                base_y=0.01,
                tip_r=_lerp(0.056, 0.138, stamen_b),
                tip_y=_lerp(0.32, 0.34, stamen_b),
                theta=th,
                filament_half_w=0.010,
                anther_len=0.095,
                anther_w=0.016,
                build_topology=build_topology,
                flutter_amp=0.010,
            )

        # Small rounded green collar/base receptacle connecting stem to cup
        collar_rad = 8 if is_lush else 6
        collar_rings = (
            (0.0, 0.01, 0.0, 0.072, 1.0),
            (0.0, -0.04, 0.0, 0.084, 1.0),
            (0.0, -0.08, 0.0, 0.056, 1.0),
        )
        self._build_tube_from_rings(
            collar_rings, collar_rad, "foliage", 0.35, build_topology, cap_top=True
        )

        # Smooth succulent tulip stem
        stem_rad = 8 if is_lush else 6
        stem_h = 12 if is_lush else 9
        stem_rings: list[tuple[float, float, float, float, float]] = []
        for iv in range(stem_h + 1):
            s = iv / stem_h
            cx, cy, cz, r = self._tulip_stem_center(s)
            stem_rings.append((cx, cy, cz, r, 1.0 - s))
        self._build_tube_from_rings(
            stem_rings, stem_rad, "foliage", 0.25, build_topology, cap_bottom=True
        )

        # Broad upright-arching clasping tulip leaves
        leaf_specs: tuple[tuple[float, float, float, float], ...] = (
            (0.56, 0.65, 0.90, 0.21),
            (0.80, 3.70, 0.98, 0.24),
            (0.68, 2.15, 0.82, 0.19),
        ) if is_lush else (
            (0.58, 0.70, 0.90, 0.21),
            (0.80, 3.80, 0.96, 0.24),
        )
        lu = 6 if is_lush else 4
        lv = 9 if is_lush else 7
        for s_pos, az, leaf_len, leaf_w in leaf_specs:
            cx, cy, cz, r_stem = self._tulip_stem_center(s_pos)
            dx = math.cos(az)
            dz = math.sin(az)
            tx = -dz
            tz = dx
            root_h = 1.0 - s_pos
            root_x = cx + r_stem * 0.75 * dx
            root_y = cy
            root_z = cz + r_stem * 0.75 * dz

            grid_l: list[list[int]] = []
            for iv in range(lv + 1):
                v = iv / lv
                w_prof = (
                    0.0
                    if iv == lv
                    else (0.18 * (1.0 - v) + 0.94 * math.sin(math.pi * (v ** 0.76)))
                )
                row_l: list[int] = []
                for iu in range(lu + 1):
                    u = -1.0 + 2.0 * (iu / lu)
                    # Tulip leaves arch upward then drape gracefully outward
                    reach = 0.56 * leaf_len * (v ** 1.15)
                    rise = (
                        0.68 * leaf_len * math.sin(math.pi * 0.58 * v)
                        - 0.18 * leaf_len * (v ** 2.3)
                    )
                    u_trough = 0.048 * (u * u) * math.sin(math.pi * v)
                    lateral = u * w_prof * leaf_w
                    vx = root_x + reach * dx + lateral * tx
                    vz = root_z + reach * dz + lateral * tz
                    vy = root_y + rise + u_trough
                    row_l.append(len(self.vertices))
                    self.vertices.append((vx, vy, vz))
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.032 * (v ** 1.6)
                        self.vertex_sway.append((root_h, amp, az + 0.9 * v + 0.3 * u * (1.0 - v)))
                grid_l.append(row_l)

            if build_topology:
                self._add_grid_surface(
                    grid=grid_l,
                    material="foliage",
                    layer_frac=0.75,
                    double_sided=True,
                    v_max=lv,
                    u_max=lu,
                    collapse_tip=True,
                    v_base=0.35,
                    v_span=0.65,
                )

    # -- Species 3: Lotus ----------------------------------------------------

    @staticmethod
    def _lotus_stem_center(s: float) -> tuple[float, float, float, float]:
        y = -0.10 - 1.27 * s
        x = 0.046 * math.sin(s * 2.1)
        z = 0.025 * (1.0 - math.cos(s * 2.0))
        radius = _lerp(0.058, 0.046, s)
        return (x, y, z, radius)

    def _populate_lotus(self, bloom: float, build_topology: bool) -> None:
        is_lush = self.detail_tier.key == "lush"
        u_steps = 6 if is_lush else 4
        v_steps = 6 if is_lush else 5
        per_tier = 8 if is_lush else 6
        fullness = self.detail_tier.petal_fullness
        ripple = self.detail_tier.petal_ripple_amp

        # 3 concentric tiers of pointed boat-shaped lotus petals
        tier_configs = (
            # (layer_frac, r_base, y_base, len, lag, tilt_bud, tilt_open, phase_off)
            (0.48, 0.140, 0.05, 0.68, 0.24, 0.06, 0.54, 0.20),
            (0.72, 0.175, 0.02, 0.76, 0.14, 0.12, 0.90, 0.20 + math.pi / per_tier),
            (0.96, 0.200, -0.01, 0.82, 0.03, 0.18, 1.26, 0.20 + 0.35 / per_tier),
        )
        for layer_idx, cfg in enumerate(tier_configs):
            layer_frac, r_base, y_base, p_len, lag, t_bud, t_open, phase_off = cfg
            local_b = _smoothstep(lag, 1.0, bloom)
            tilt = _lerp(t_bud, t_open, local_b)
            sin_t = math.sin(tilt)
            cos_t = math.cos(tilt)
            bud_inward = (1.0 - local_b) * (0.34 + 0.04 * layer_idx)
            tip_lift = local_b * (0.09 + 0.06 * layer_idx)

            for idx in range(per_tier):
                theta_center = phase_off + idx * (2.0 * math.pi / per_tier)
                half_wrap = (0.60 if is_lush else 0.68) * _lerp(0.98, 1.0, local_b)

                grid: list[list[int]] = []
                for iv in range(v_steps + 1):
                    v = iv / v_steps
                    w_env = (
                        0.0
                        if iv == v_steps
                        else (0.36 * (1.0 - v) + 0.96 * math.sin(math.pi * (v ** 0.72)))
                    )
                    row: list[int] = []
                    for iu in range(u_steps + 1):
                        u = -1.0 + 2.0 * (iu / u_steps)
                        u2 = u * u
                        s = v * (1.0 - 0.07 * u2 * v)
                        boat_keel = 0.052 * (1.0 - u2) * math.sin(math.pi * s)

                        r = (
                            r_base
                            + p_len
                            * (
                                sin_t * s
                                + 0.10 * math.sin(math.pi * s)
                                - bud_inward * (s ** 2.1)
                            )
                            + boat_keel
                        )
                        y_extra = 0.0
                        if fullness > 0.0:
                            r += fullness * math.sin(math.pi * s) * (1.0 - 0.3 * u2)
                        if ripple > 0.0 and s > 0.45:
                            env = ripple * 0.6 * local_b * ((s - 0.45) ** 1.4)
                            y_extra = env * math.sin(u * 4.0 + idx * 1.7)

                        r = max(0.025 + 0.02 * (1.0 - v), r)
                        y = (
                            y_base
                            + p_len
                            * (
                                cos_t * s
                                + tip_lift * max(0.0, s - 0.48) ** 2
                                + 0.08 * bud_inward * math.sin(math.pi * s)
                            )
                            + 0.022 * u2 * math.sin(math.pi * s)
                            + y_extra
                        )
                        theta = theta_center + u * half_wrap * w_env

                        row.append(len(self.vertices))
                        self.vertices.append((r * math.cos(theta), y, r * math.sin(theta)))
                        if build_topology:
                            amp = 0.0 if iv == 0 else 0.020 * (v ** 1.7)
                            # Collapse u-phase at pointed tip v=1 so vertices stay sealed
                            self.vertex_sway.append((1.0, amp, theta_center + 0.3 * u * (1.0 - v)))
                    grid.append(row)

                if build_topology:
                    self._add_grid_surface(
                        grid=grid,
                        material="petal",
                        layer_frac=layer_frac,
                        double_sided=True,
                        v_max=v_steps,
                        u_max=u_steps,
                        collapse_tip=True,
                    )

        # Green floral receptacle base under petals connecting cleanly to stem
        rec_rad = 12 if is_lush else 9
        rec_rings = (
            (0.0, 0.02, 0.0, 0.210, 1.0),
            (0.0, -0.04, 0.0, 0.145, 1.0),
            (0.0, -0.10, 0.0, 0.058, 1.0),
        )
        self._build_tube_from_rings(
            rec_rings, rec_rad, "foliage", 0.35, build_topology, cap_top=True
        )

        # Iconic flat-topped golden lotus seed pod (torus) nestled inside the cup
        pod_rad = 14 if is_lush else 10
        pod_steps = 4 if is_lush else 3
        pod_rings: list[tuple[float, float, float, float, float]] = []
        for iv in range(pod_steps + 1):
            t_p = iv / pod_steps
            y_p = _lerp(0.20, 0.02, t_p)
            r_p = _lerp(0.170, 0.118, t_p ** 1.15) + 0.010 * math.sin(math.pi * t_p)
            pod_rings.append((0.0, y_p, 0.0, r_p, 1.0))
        self._build_tube_from_rings(
            pod_rings, pod_rad, "center", 0.5, build_topology, cap_top=True
        )

        # Raised seed dimples on top of the flat lotus seed pod
        seed_positions: list[tuple[float, float]] = [(0.0, 0.0)]
        for k in range(6):
            a = k * (math.pi / 3.0) + 0.25
            seed_positions.append((0.092 * math.cos(a), 0.092 * math.sin(a)))
        if is_lush:
            for k in range(6):
                a = k * (math.pi / 3.0) + 0.77
                seed_positions.append((0.132 * math.cos(a), 0.132 * math.sin(a)))
        for sx, sz in seed_positions:
            idx_s = len(self.vertices)
            r_sd = 0.020
            self.vertices.extend(
                (
                    (sx + r_sd, 0.202, sz),
                    (sx, 0.202, sz + r_sd),
                    (sx - r_sd, 0.202, sz),
                    (sx, 0.202, sz - r_sd),
                    (sx, 0.214, sz),
                )
            )
            if build_topology:
                for _ in range(5):
                    self.vertex_sway.append((1.0, 0.0, 0.0))
                self.faces.extend(
                    (
                        FaceSpec((idx_s, idx_s + 1, idx_s + 4), "center_accent", 0.9, 0.5, True),
                        FaceSpec(
                            (idx_s + 1, idx_s + 2, idx_s + 4), "center_accent", 0.9, 0.5, True
                        ),
                        FaceSpec(
                            (idx_s + 2, idx_s + 3, idx_s + 4), "center_accent", 0.9, 0.5, True
                        ),
                        FaceSpec((idx_s + 3, idx_s, idx_s + 4), "center_accent", 0.9, 0.5, True),
                    )
                )

        # Golden stamen halo hugging the seed pod
        n_stamens = 18 if is_lush else 12
        stamen_b = _smoothstep(0.18, 0.95, bloom)
        for k in range(n_stamens):
            th = k * (2.0 * math.pi / n_stamens) + 0.12
            self._build_stamen_filament(
                base_r=0.130,
                base_y=0.05,
                tip_r=_lerp(0.115, 0.235, stamen_b),
                tip_y=_lerp(0.23, 0.25, stamen_b),
                theta=th,
                filament_half_w=0.008,
                anther_len=0.058,
                anther_w=0.012,
                build_topology=build_topology,
                flutter_amp=0.010,
            )

        # Smooth lotus stem
        stem_rad = 8 if is_lush else 6
        stem_h = 12 if is_lush else 9
        stem_rings: list[tuple[float, float, float, float, float]] = []
        for iv in range(stem_h + 1):
            s = iv / stem_h
            cx, cy, cz, r = self._lotus_stem_center(s)
            stem_rings.append((cx, cy, cz, r, 1.0 - s))
        self._build_tube_from_rings(
            stem_rings, stem_rad, "foliage", 0.25, build_topology, cap_bottom=True
        )

        # Sculpted cupped lotus pad(s) on curved petioles
        pad_specs: tuple[tuple[float, float, float, float, float], ...] = (
            (0.74, 0.55, 0.48, 0.34, 0.22),
            (0.56, 3.65, 0.38, 0.24, 0.28),
        ) if is_lush else (
            (0.74, 0.55, 0.48, 0.34, 0.22),
        )
        for s_pos, az, reach_len, pad_r, rise_y in pad_specs:
            cx, cy, cz, r_stem = self._lotus_stem_center(s_pos)
            dx = math.cos(az)
            dz = math.sin(az)
            root_h = 1.0 - s_pos
            p0 = (cx + r_stem * 0.7 * dx, cy, cz + r_stem * 0.7 * dz)
            p1 = (p0[0] + reach_len * 0.55 * dx, cy + rise_y * 0.55, p0[2] + reach_len * 0.55 * dz)
            pad_cx = p0[0] + reach_len * dx
            pad_cy = cy + rise_y
            pad_cz = p0[2] + reach_len * dz

            # Petiole tube
            pet_rings = (
                (pad_cx, pad_cy - 0.01, pad_cz, 0.024, root_h),
                (p1[0], p1[1], p1[2], 0.026, root_h),
                (p0[0], p0[1], p0[2], 0.030, root_h),
            )
            self._build_tube_from_rings(pet_rings, 5, "foliage", 0.35, build_topology)

            # Peltate cupped circular lotus pad (pinhole-free center fan + concentric rings)
            rad_steps = 12 if is_lush else 9
            ring_steps = 4 if is_lush else 3
            center_idx = len(self.vertices)
            self.vertices.append((pad_cx, pad_cy + 0.002, pad_cz))
            if build_topology:
                self.vertex_sway.append((root_h, 0.0, az))

            pad_grid: list[list[int]] = []
            for ir in range(1, ring_steps + 1):
                rf = ir / ring_steps
                row_p: list[int] = []
                for iu in range(rad_steps + 1):
                    ang = az + math.pi + 2.0 * math.pi * (iu % rad_steps) / rad_steps
                    notch = 1.0 - 0.10 * math.exp(-12.0 * ((iu % rad_steps) / rad_steps - 0.5) ** 2)
                    rr = rf * pad_r * notch
                    wave = 0.016 * rf * math.sin(5.0 * ang)
                    cup = 0.055 * (rf ** 1.6)
                    px = pad_cx + rr * math.cos(ang)
                    pz = pad_cz + rr * math.sin(ang)
                    py = pad_cy + cup + wave
                    row_p.append(len(self.vertices))
                    self.vertices.append((px, py, pz))
                    if build_topology:
                        # Synced gentle bob so pad never separates from petiole tip
                        self.vertex_sway.append((root_h, 0.018 * rf, az))
                pad_grid.append(row_p)

            if build_topology:
                for iu in range(rad_steps):
                    self.faces.append(
                        FaceSpec(
                            indices=(center_idx, pad_grid[0][iu], pad_grid[0][iu + 1]),
                            material="foliage",
                            v_frac=0.45,
                            layer_frac=0.75,
                            double_sided=True,
                        )
                    )
                self._add_grid_surface(
                    grid=pad_grid,
                    material="foliage",
                    layer_frac=0.75,
                    double_sided=True,
                    v_max=ring_steps - 1,
                    u_max=rad_steps,
                    v_base=0.50,
                    v_span=0.50,
                )

    # -- Species 4: Sunflower ------------------------------------------------

    @staticmethod
    def _sunflower_stem_center(s: float) -> tuple[float, float, float, float]:
        y = -0.10 - 1.27 * s
        x = 0.055 * math.sin(s * 2.4)
        z = 0.030 * (1.0 - math.cos(s * 2.0))
        radius = _lerp(0.072, 0.062, s)
        return (x, y, z, radius)

    def _populate_sunflower(self, bloom: float, build_topology: bool) -> None:
        is_lush = self.detail_tier.key == "lush"
        fullness = self.detail_tier.petal_fullness
        ripple = self.detail_tier.petal_ripple_amp

        # Green involucre saucer receptacle under head
        rec_rad = 14 if is_lush else 10
        rec_rings = (
            (0.0, 0.076, 0.0, 0.335, 1.0),
            (0.0, 0.025, 0.0, 0.285, 1.0),
            (0.0, -0.045, 0.0, 0.165, 1.0),
            (0.0, -0.105, 0.0, 0.072, 1.0),
        )
        self._build_tube_from_rings(rec_rings, rec_rad, "foliage", 0.35, build_topology)

        # Ring of overlapping pointed green involucre calyx bracts
        n_bracts = 13 if is_lush else 10
        b_bract = _smoothstep(0.0, 0.85, bloom)
        for idx in range(n_bracts):
            th = idx * (2.0 * math.pi / n_bracts) + 0.18
            cx = math.cos(th)
            cz = math.sin(th)
            tx = -cz
            tz = cx
            tilt = _lerp(0.55, 1.72, b_bract)
            b_len = 0.26
            grid_b: list[list[int]] = []
            for iv in range(4):
                v = iv / 3.0
                hw = (
                    0.0
                    if iv == 3
                    else 0.088 * (1.0 - v ** 0.9) * (0.85 + 0.3 * math.sin(math.pi * v))
                )
                row_b: list[int] = []
                for iu in range(3):
                    u = -1.0 + iu
                    r_mid = 0.345 + b_len * (math.sin(tilt) * v + 0.08 * math.sin(math.pi * v))
                    y_mid = 0.072 + b_len * (math.cos(tilt) * v - 0.08 * max(0.0, v - 0.4) ** 2)
                    row_b.append(len(self.vertices))
                    self.vertices.append(
                        (r_mid * cx + u * hw * tx, y_mid, r_mid * cz + u * hw * tz)
                    )
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.018 * (v ** 1.6)
                        self.vertex_sway.append((1.0, amp, th + 0.2 * u * (1.0 - v)))
                grid_b.append(row_b)
            if build_topology:
                self._add_grid_surface(
                    grid=grid_b,
                    material="foliage",
                    layer_frac=0.6,
                    double_sided=True,
                    v_max=3,
                    u_max=2,
                    collapse_tip=True,
                    v_base=0.35,
                    v_span=0.55,
                )

        # Domed Fibonacci floret disc (espresso seed dome + outer golden pollen halo)
        disc_rad = 18 if is_lush else 14
        disc_ring_count = 6 if is_lush else 4
        disc_grid: list[list[int]] = []
        for ir in range(disc_ring_count):
            rf = 1.0 - ir / disc_ring_count  # 1.0 outer -> 1/N inner ring
            r_d = 0.365 * rf
            y_d = 0.085 + 0.130 * (1.0 - rf * rf)
            row_d: list[int] = []
            for iu in range(disc_rad + 1):
                ang = 2.0 * math.pi * (iu % disc_rad) / disc_rad
                row_d.append(len(self.vertices))
                self.vertices.append((r_d * math.cos(ang), y_d, r_d * math.sin(ang)))
                if build_topology:
                    self.vertex_sway.append((1.0, 0.0, 0.0))
            disc_grid.append(row_d)

        apex_idx = len(self.vertices)
        self.vertices.append((0.0, 0.215, 0.0))
        if build_topology:
            self.vertex_sway.append((1.0, 0.0, 0.0))

        if build_topology:
            for iv in range(disc_ring_count - 1):
                mat = "center_accent" if iv == 0 else "center"
                v_mid = 0.45 + 0.50 * ((iv + 0.5) / disc_ring_count)
                for iu in range(disc_rad):
                    i0 = disc_grid[iv][iu]
                    i1 = disc_grid[iv][iu + 1]
                    i2 = disc_grid[iv + 1][iu + 1]
                    i3 = disc_grid[iv + 1][iu]
                    self.faces.append(
                        FaceSpec((i0, i1, i2, i3), mat, v_mid, 0.5, True)
                    )
            inner_ring = disc_grid[-1]
            v_apex = 0.45 + 0.50 * ((disc_ring_count - 0.5) / disc_ring_count)
            for iu in range(disc_rad):
                self.faces.append(
                    FaceSpec(
                        (inner_ring[iu], inner_ring[iu + 1], apex_idx),
                        "center",
                        v_apex,
                        0.5,
                        True,
                    )
                )

        # Raised 3D Fibonacci phyllotaxis floret pyramids across the dome
        n_seeds = 34 if is_lush else 18
        for k in range(1, n_seeds + 1):
            frac_r = math.sqrt(k / (n_seeds + 0.5))
            r_c = 0.32 * frac_r
            ang = k * GOLDEN_ANGLE
            scx = r_c * math.cos(ang)
            scz = r_c * math.sin(ang)
            rf_n = r_c / 0.365
            base_y = 0.092 + 0.130 * (1.0 - rf_n * rf_n)
            mat_s = "center_accent" if frac_r > 0.74 else "center"
            sr_w = 0.026 if is_lush else 0.032
            sh = 0.022
            idx_p = len(self.vertices)
            self.vertices.extend(
                (
                    (scx + sr_w, base_y, scz),
                    (scx, base_y, scz + sr_w),
                    (scx - sr_w, base_y, scz),
                    (scx, base_y, scz - sr_w),
                    (scx, base_y + sh, scz),
                )
            )
            if build_topology:
                for _ in range(5):
                    self.vertex_sway.append((1.0, 0.0, 0.0))
                self.faces.extend(
                    (
                        FaceSpec((idx_p, idx_p + 1, idx_p + 4), mat_s, 0.85, 0.5, True),
                        FaceSpec((idx_p + 1, idx_p + 2, idx_p + 4), mat_s, 0.85, 0.5, True),
                        FaceSpec((idx_p + 2, idx_p + 3, idx_p + 4), mat_s, 0.85, 0.5, True),
                        FaceSpec((idx_p + 3, idx_p, idx_p + 4), mat_s, 0.85, 0.5, True),
                    )
                )

        # 2 staggered rows of pointed sunflower ray petals (21 outer + 13/21 inner)
        n_outer = 21
        n_inner = 21 if is_lush else 13
        u_steps = 4 if is_lush else 2
        v_steps = 5 if is_lush else 4
        ray_idx = 0
        for row_idx, count in ((0, n_inner), (1, n_outer)):
            is_outer_row = (row_idx == 1)
            layer_frac = 0.94 if is_outer_row else 0.64
            lag = 0.04 if is_outer_row else 0.16
            local_b = _smoothstep(lag, 1.0, bloom)
            r_base = 0.345 if is_outer_row else 0.330
            y_base = 0.082 if is_outer_row else 0.095
            p_len = 0.58 if is_outer_row else 0.51
            tilt_bud = 0.18 if is_outer_row else 0.10
            tilt_open = 1.46 if is_outer_row else 1.24
            tilt = _lerp(tilt_bud, tilt_open, local_b)
            sin_t = math.sin(tilt)
            cos_t = math.cos(tilt)
            bud_inward = (1.0 - local_b) * 0.20

            for k in range(count):
                th_off = 0.14 if is_outer_row else (0.14 + math.pi / count)
                theta_center = th_off + k * (2.0 * math.pi / count) + 0.03 * math.sin(ray_idx * 1.9)
                half_wrap = 0.20 if is_outer_row else 0.18
                droop_var = 0.035 * math.sin(ray_idx * 2.3)

                grid_r: list[list[int]] = []
                for iv in range(v_steps + 1):
                    v = iv / v_steps
                    w_env = (
                        0.0
                        if iv == v_steps
                        else (0.35 * (1.0 - v) + 0.90 * math.sin(math.pi * (0.12 + 0.78 * v)))
                    )
                    row_r: list[int] = []
                    for iu in range(u_steps + 1):
                        u = -1.0 + 2.0 * (iu / u_steps)
                        u2 = u * u
                        s = v * (1.0 - 0.05 * u2 * v)
                        r = r_base + p_len * (
                            sin_t * s
                            + 0.04 * math.sin(math.pi * s)
                            - bud_inward * (s ** 2.0)
                        )
                        if fullness > 0.0:
                            r += fullness * 0.6 * math.sin(math.pi * s) * (1.0 - 0.4 * u2)
                        arch_down = local_b * (0.14 + droop_var) * (max(0.0, s - 0.35) ** 1.8)
                        groove = 0.015 * (1.0 - u2) * math.sin(math.pi * s)
                        y_extra = 0.0
                        if ripple > 0.0 and s > 0.45:
                            y_extra = (
                                ripple
                                * 0.7
                                * local_b
                                * ((s - 0.45) ** 1.3)
                                * math.sin(u * 2.5 + ray_idx)
                            )
                        y = y_base + p_len * (cos_t * s - arch_down) - groove + y_extra
                        theta = theta_center + u * half_wrap * w_env

                        row_r.append(len(self.vertices))
                        self.vertices.append((r * math.cos(theta), y, r * math.sin(theta)))
                        if build_topology:
                            amp = 0.0 if iv == 0 else 0.022 * (v ** 1.7)
                            self.vertex_sway.append((1.0, amp, theta_center + 0.25 * u * (1.0 - v)))
                    grid_r.append(row_r)

                if build_topology:
                    self._add_grid_surface(
                        grid=grid_r,
                        material="petal",
                        layer_frac=layer_frac,
                        double_sided=True,
                        v_max=v_steps,
                        u_max=u_steps,
                        collapse_tip=True,
                    )
                ray_idx += 1

        # Sturdy stem
        stem_rad = 8 if is_lush else 6
        stem_h = 12 if is_lush else 10
        stem_rings: list[tuple[float, float, float, float, float]] = []
        for iv in range(stem_h + 1):
            s = iv / stem_h
            cx, cy, cz, r = self._sunflower_stem_center(s)
            stem_rings.append((cx, cy, cz, r, 1.0 - s))
        self._build_tube_from_rings(
            stem_rings, stem_rad, "foliage", 0.25, build_topology, cap_bottom=True
        )

        # Broad cordate sunflower leaves
        leaf_specs: tuple[tuple[float, float, float, float, float], ...] = (
            (0.46, 0.55, 0.76, 0.30, 0.32),
            (0.74, 3.45, 0.84, 0.33, 0.36),
            (0.60, 5.15, 0.70, 0.28, 0.34),
        ) if is_lush else (
            (0.48, 0.55, 0.76, 0.30, 0.32),
            (0.76, 3.45, 0.84, 0.33, 0.36),
        )
        lu = 6 if is_lush else 4
        lv = 7 if is_lush else 5
        for s_pos, az, leaf_len, leaf_w, pitch_down in leaf_specs:
            cx, cy, cz, r_stem = self._sunflower_stem_center(s_pos)
            dx = math.cos(az)
            dz = math.sin(az)
            tx = -dz
            tz = dx
            root_h = 1.0 - s_pos
            root_x = cx + r_stem * 0.70 * dx
            root_y = cy
            root_z = cz + r_stem * 0.70 * dz

            grid_l: list[list[int]] = []
            for iv in range(lv + 1):
                v = iv / lv
                # Heart/cordate silhouette: wide rapidly after short petiole base
                w_prof = (
                    0.0
                    if iv == lv
                    else (0.14 * (1.0 - v) + 1.05 * math.sin(math.pi * (v ** 0.56)))
                )
                row_l: list[int] = []
                for iu in range(lu + 1):
                    u = -1.0 + 2.0 * (iu / lu)
                    dist_along = v * leaf_len
                    arch_y = (
                        -pitch_down * dist_along
                        + 0.05 * math.sin(math.pi * v)
                        - 0.10 * (v ** 2.1)
                    )
                    v_fold = 0.042 * abs(u) * math.sin(math.pi * v)
                    lateral = u * w_prof * leaf_w
                    vx = root_x + dist_along * dx + lateral * tx
                    vz = root_z + dist_along * dz + lateral * tz
                    vy = root_y + arch_y + v_fold
                    row_l.append(len(self.vertices))
                    self.vertices.append((vx, vy, vz))
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.032 * (v ** 1.6)
                        self.vertex_sway.append((root_h, amp, az + 1.1 * v + 0.35 * u * (1.0 - v)))
                grid_l.append(row_l)

            if build_topology:
                self._add_grid_surface(
                    grid=grid_l,
                    material="foliage",
                    layer_frac=0.75,
                    double_sided=True,
                    v_max=lv,
                    u_max=lu,
                    collapse_tip=True,
                    v_base=0.35,
                    v_span=0.65,
                )

    # -- Species 5: Sakura ---------------------------------------------------

    @staticmethod
    def _sakura_twig_center(s: float) -> tuple[float, float, float, float]:
        # Woody cherry twig sweeps from blossom throat (0, -0.02, 0) down to (0, -1.37, 0)
        y = -0.02 - 1.35 * s
        x = 0.13 * math.sin(math.pi * s) - 0.045 * math.sin(2.0 * math.pi * s)
        z = 0.055 * math.sin(math.pi * s)
        radius = _lerp(0.036, 0.054, s)
        return (x, y, z, radius)

    def _populate_sakura(self, bloom: float, build_topology: bool) -> None:
        is_lush = self.detail_tier.key == "lush"
        # Even u_steps ensures u = 0 sits cleanly on a center column for crisp apical V-notch
        u_steps = 10 if is_lush else 6
        v_steps = 8 if is_lush else 6
        fullness = self.detail_tier.petal_fullness
        ripple = self.detail_tier.petal_ripple_amp

        # 5 Iconic Notched Sakura Petals
        for idx in range(5):
            local_b = _smoothstep(0.04 * (idx % 2), 1.0, bloom)
            theta_center = idx * (2.0 * math.pi / 5.0) + 0.18
            r_base = 0.026
            y_base = 0.036
            p_len = 0.78
            tilt = _lerp(0.16, 1.08, local_b)
            sin_t = math.sin(tilt)
            cos_t = math.cos(tilt)
            bud_inward = (1.0 - local_b) * 0.24
            half_wrap = 0.74 * _lerp(0.96, 1.0, local_b)

            grid: list[list[int]] = []
            for iv in range(v_steps + 1):
                v = iv / v_steps
                w_env = 0.44 + 0.56 * math.sin(math.pi * 0.76 * (v ** 0.58))
                row: list[int] = []
                for iu in range(u_steps + 1):
                    u = -1.0 + 2.0 * (iu / u_steps)
                    u2 = u * u
                    # Signature Sakura apical V-notch at (v=1, u=0) + rounded side lobes
                    notch = 0.18 * math.exp(-16.0 * u2) * (v ** 2.4)
                    shoulder = 0.13 * u2 * (v ** 1.8)
                    s = v * (1.0 - notch - shoulder)

                    cup = 0.075 * math.sin(math.pi * s) + 0.025 * (1.0 - u2) * math.sin(math.pi * v)
                    r = max(
                        0.022 + 0.015 * v,
                        r_base + p_len * (sin_t * s + cup - bud_inward * (s ** 2.0)),
                    )
                    y_extra = 0.0
                    if fullness > 0.0:
                        r += fullness * math.sin(math.pi * s) * (1.0 - 0.3 * u2)
                    if ripple > 0.0 and s > 0.45:
                        y_extra = (
                            ripple
                            * 0.55
                            * local_b
                            * ((s - 0.45) ** 1.3)
                            * math.cos(u * 4.5 + idx)
                        )

                    y = (
                        y_base
                        + p_len * (cos_t * s - 0.06 * local_b * max(0.0, s - 0.55) ** 2)
                        + 0.018 * u2 * math.sin(math.pi * v)
                        + y_extra
                    )
                    theta = theta_center + u * half_wrap * w_env

                    row.append(len(self.vertices))
                    self.vertices.append((r * math.cos(theta), y, r * math.sin(theta)))
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.024 * (v ** 1.7)
                        self.vertex_sway.append((1.0, amp, theta_center + 0.35 * u))
                grid.append(row)

            if build_topology:
                self._add_grid_surface(
                    grid=grid,
                    material="petal",
                    layer_frac=0.5,
                    double_sided=True,
                    v_max=v_steps,
                    u_max=u_steps,
                )

        # Central slender style (pistil) & radiating golden-tipped stamens
        style_rings = (
            (0.0, 0.28, 0.0, 0.014, 1.0),
            (0.0, 0.16, 0.0, 0.010, 1.0),
            (0.0, 0.03, 0.0, 0.018, 1.0),
        )
        self._build_tube_from_rings(style_rings, 5, "center", 0.5, build_topology, cap_top=True)

        n_stamens = 18 if is_lush else 12
        stamen_b = _smoothstep(0.15, 0.95, bloom)
        for k in range(n_stamens):
            th = k * (2.0 * math.pi / n_stamens) + 0.14
            ring_scale = 0.82 if (k % 2 == 0) else 1.08
            self._build_stamen_filament(
                base_r=0.038,
                base_y=0.04,
                tip_r=_lerp(0.055, 0.24 * ring_scale, stamen_b),
                tip_y=_lerp(0.26, 0.31 * (1.05 - 0.08 * ring_scale), stamen_b),
                theta=th,
                filament_half_w=0.0065,
                anther_len=0.045,
                anther_w=0.012,
                build_topology=build_topology,
                flutter_amp=0.015,
            )

        # Cherry calyx cup & 5 pointed calyx sepals underneath
        calyx_rad = 10 if is_lush else 7
        calyx_rings = (
            (0.0, 0.034, 0.0, 0.108, 1.0),
            (0.0, 0.005, 0.0, 0.078, 1.0),
            (0.0, -0.035, 0.0, 0.036, 1.0),
        )
        self._build_tube_from_rings(
            calyx_rings, calyx_rad, "calyx", 0.4, build_topology, cap_top=True
        )

        b_sep = _smoothstep(0.0, 0.85, bloom)
        for idx in range(5):
            th = idx * (2.0 * math.pi / 5.0) + 0.18 + math.pi / 5.0
            cx = math.cos(th)
            cz = math.sin(th)
            tx = -cz
            tz = cx
            tilt = _lerp(0.42, 1.65, b_sep)
            s_len = 0.20
            grid_s: list[list[int]] = []
            for iv in range(4):
                v = iv / 3.0
                hw = 0.0 if iv == 3 else 0.056 * (1.0 - v ** 0.9)
                row_s: list[int] = []
                for iu in range(3):
                    u = -1.0 + iu
                    r_mid = 0.082 + s_len * math.sin(tilt) * v
                    y_mid = 0.032 + s_len * (math.cos(tilt) * v - 0.08 * v * v)
                    row_s.append(len(self.vertices))
                    self.vertices.append(
                        (r_mid * cx + u * hw * tx, y_mid, r_mid * cz + u * hw * tz)
                    )
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.014 * (v ** 1.6)
                        self.vertex_sway.append((1.0, amp, th + 0.2 * u * (1.0 - v)))
                grid_s.append(row_s)
            if build_topology:
                self._add_grid_surface(
                    grid=grid_s,
                    material="calyx",
                    layer_frac=0.6,
                    double_sided=True,
                    v_max=3,
                    u_max=2,
                    collapse_tip=True,
                )

        # Woody cherry branch twig
        twig_rad = 8 if is_lush else 6
        twig_h = 12 if is_lush else 9
        twig_rings: list[tuple[float, float, float, float, float]] = []
        for iv in range(twig_h + 1):
            s = iv / twig_h
            cx, cy, cz, r = self._sakura_twig_center(s)
            twig_rings.append((cx, cy, cz, r, 1.0 - s))
        self._build_tube_from_rings(
            twig_rings, twig_rad, "bark", 0.25, build_topology, cap_bottom=True
        )

        # Side woody spur + companion closed cherry bud
        spur_s = 0.44
        scx, scy, scz, sr = self._sakura_twig_center(spur_s)
        spur_h = 1.0 - spur_s
        spur_az = 2.45
        sdx = math.cos(spur_az)
        sdz = math.sin(spur_az)
        bud_x = scx + 0.26 * sdx
        bud_y = scy + 0.26
        bud_z = scz + 0.26 * sdz
        spur_rings = (
            (bud_x, bud_y, bud_z, 0.022, spur_h),
            (scx + 0.13 * sdx, scy + 0.11, scz + 0.13 * sdz, 0.026, spur_h),
            (scx + sr * 0.5 * sdx, scy, scz + sr * 0.5 * sdz, 0.032, spur_h),
        )
        self._build_tube_from_rings(spur_rings, 5, "bark", 0.35, build_topology)

        # Companion cherry bud on spur tip (calyx + 5 closed miniature petals)
        bud_calyx_rings = (
            (bud_x, bud_y + 0.035, bud_z, 0.046, spur_h),
            (bud_x, bud_y, bud_z, 0.022, spur_h),
        )
        self._build_tube_from_rings(bud_calyx_rings, 6, "calyx", 0.45, build_topology, cap_top=True)
        bud_open = 0.12 + 0.18 * bloom
        for idx_b in range(5):
            th_b = idx_b * (2.0 * math.pi / 5.0) + 0.4
            grid_cb: list[list[int]] = []
            for iv in range(4):
                v = iv / 3.0
                w_cb = 0.60 + 0.40 * math.sin(math.pi * v * 0.80)
                row_cb: list[int] = []
                for iu in range(3):
                    u = -1.0 + iu
                    rr = 0.024 + 0.12 * (
                        math.sin(0.22 + 0.24 * bud_open) * v
                        + 0.34 * math.sin(math.pi * v)
                        - 0.26 * (v ** 1.8)
                    )
                    if iv == 3:
                        rr = 0.014
                    else:
                        rr = max(0.014, rr)
                    yy = bud_y + 0.032 + 0.16 * v
                    th_pt = th_b + u * 0.78 * w_cb
                    row_cb.append(len(self.vertices))
                    self.vertices.append(
                        (bud_x + rr * math.cos(th_pt), yy, bud_z + rr * math.sin(th_pt))
                    )
                    if build_topology:
                        self.vertex_sway.append((spur_h, 0.008 * v, th_b))
                grid_cb.append(row_cb)
            if build_topology:
                self._add_grid_surface(grid_cb, "petal", 0.4, True, 3, 2)

        # Fresh ovate cherry leaves along twig
        leaf_specs: tuple[tuple[float, float, float, float, float], ...] = (
            (0.32, 0.35, 0.44, 0.16, 0.14),
            (0.66, 4.30, 0.48, 0.18, 0.18),
            (0.52, 5.55, 0.40, 0.15, 0.16),
        ) if is_lush else (
            (0.32, 0.35, 0.44, 0.16, 0.14),
            (0.66, 4.30, 0.48, 0.18, 0.18),
        )
        lu = 6 if is_lush else 4
        lv = 7 if is_lush else 5
        for s_pos, az, leaf_len, leaf_w, pitch_down in leaf_specs:
            cx, cy, cz, r_stem = self._sakura_twig_center(s_pos)
            dx = math.cos(az)
            dz = math.sin(az)
            tx = -dz
            tz = dx
            root_h = 1.0 - s_pos
            root_x = cx + r_stem * 0.7 * dx
            root_y = cy
            root_z = cz + r_stem * 0.7 * dz

            grid_l: list[list[int]] = []
            for iv in range(lv + 1):
                v = iv / lv
                w_prof = (
                    0.0
                    if iv == lv
                    else (0.10 * (1.0 - v) + 0.96 * math.sin(math.pi * (v ** 0.70)))
                )
                row_l: list[int] = []
                for iu in range(lu + 1):
                    u = -1.0 + 2.0 * (iu / lu)
                    dist_along = v * leaf_len
                    arch_y = (
                        -pitch_down * dist_along
                        + 0.06 * math.sin(math.pi * v)
                        - 0.09 * (v ** 2.0)
                    )
                    v_fold = 0.036 * abs(u) * math.sin(math.pi * v)
                    lateral = u * w_prof * leaf_w
                    row_l.append(len(self.vertices))
                    self.vertices.append(
                        (
                            root_x + dist_along * dx + lateral * tx,
                            root_y + arch_y + v_fold,
                            root_z + dist_along * dz + lateral * tz,
                        )
                    )
                    if build_topology:
                        amp = 0.0 if iv == 0 else 0.030 * (v ** 1.6)
                        self.vertex_sway.append((root_h, amp, az + 1.0 * v + 0.3 * u * (1.0 - v)))
                grid_l.append(row_l)

            if build_topology:
                self._add_grid_surface(
                    grid=grid_l,
                    material="foliage",
                    layer_frac=0.75,
                    double_sided=True,
                    v_max=lv,
                    u_max=lu,
                    collapse_tip=True,
                    v_base=0.35,
                    v_span=0.65,
                )


RoseMesh = FlowerMesh


# ---------------------------------------------------------------------------
# Breeze Sway Kinematics, Shading, Transform Pipeline & Camera Inertia
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _BreezeFrameParams:
    tilt_z: float
    tilt_x: float
    wt_fast: float
    wt_gust: float
    strength: float
    cz1: float
    sz1: float
    cx1: float
    sx1: float


def _compute_breeze_frame_params(
    breeze_time: float,
    breeze_strength: float,
) -> _BreezeFrameParams:
    """Compute per-frame breeze sway parameters once before the vertex loop."""
    tilt_z = -breeze_strength * (
        0.052 * math.sin(breeze_time * 1.15)
        + 0.018 * math.sin(breeze_time * 2.53 + 0.8)
    )
    tilt_x = breeze_strength * (
        0.038 * math.cos(breeze_time * 0.92 + 0.4)
        + 0.014 * math.sin(breeze_time * 2.11 + 1.9)
    )
    return _BreezeFrameParams(
        tilt_z=tilt_z,
        tilt_x=tilt_x,
        wt_fast=breeze_time * 2.6,
        wt_gust=breeze_time * 4.1,
        strength=breeze_strength,
        cz1=math.cos(tilt_z),
        sz1=math.sin(tilt_z),
        cx1=math.cos(tilt_x),
        sx1=math.sin(tilt_x),
    )


def displace_vertex_breeze(
    x: float,
    y: float,
    z: float,
    stem_height_factor: float,
    local_flutter_amp: float,
    phase_offset: float,
    breeze_time: float,
    breeze_strength: float = 1.0,
) -> tuple[float, float, float]:
    """Return the breeze-displaced 3D coordinates for a single vertex."""
    if breeze_strength <= 0.0:
        return (x, y, z)
    bp = _compute_breeze_frame_params(breeze_time, breeze_strength)
    if local_flutter_amp > 0.0:
        fw = local_flutter_amp * bp.strength * math.sin(bp.wt_fast + phase_offset)
        fw2 = local_flutter_amp * bp.strength * 0.45 * math.cos(bp.wt_gust + phase_offset * 1.37)
        y += fw
        x += fw2 * math.cos(phase_offset)
        z += fw2 * math.sin(phase_offset)

    if stem_height_factor > 0.0:
        by = y - STEM_ANCHOR_Y
        if stem_height_factor == 1.0:
            cz_b, sz_b, cx_b, sx_b = bp.cz1, bp.sz1, bp.cx1, bp.sx1
        else:
            h = stem_height_factor
            bend = h * h * (1.35 - 0.35 * h)
            rz = bp.tilt_z * bend
            rx = bp.tilt_x * bend
            cz_b = math.cos(rz)
            sz_b = math.sin(rz)
            cx_b = math.cos(rx)
            sx_b = math.sin(rx)
        bx = x * cz_b - by * sz_b
        by1 = x * sz_b + by * cz_b
        by2 = by1 * cx_b - z * sx_b
        bz = by1 * sx_b + z * cx_b
        x = bx
        y = STEM_ANCHOR_Y + by2
        z = bz
    return (x, y, z)


def _compute_channel_lights(
    mood_spec: MoodSpec,
    key_wrap: float,
    fill_wrap: float,
    down_bounce: float,
    amb_weight: float,
    key_weight: float,
    fill_weight: float,
    bnc_weight: float,
) -> tuple[float, float, float]:
    """Combine mood-tinted ambient, wrapped key/fill, and bounce light per channel."""
    amb_r, amb_g, amb_b = mood_spec.ambient_tint
    key_r, key_g, key_b = mood_spec.key_tint
    fill_r, fill_g, fill_b = mood_spec.fill_tint
    bnc_r, bnc_g, bnc_b = mood_spec.bounce_tint

    return (
        amb_weight * amb_r
        + key_weight * key_wrap * key_r
        + fill_weight * fill_wrap * fill_r
        + bnc_weight * down_bounce * bnc_r,
        amb_weight * amb_g
        + key_weight * key_wrap * key_g
        + fill_weight * fill_wrap * fill_g
        + bnc_weight * down_bounce * bnc_g,
        amb_weight * amb_b
        + key_weight * key_wrap * key_b
        + fill_weight * fill_wrap * fill_b
        + bnc_weight * down_bounce * bnc_b,
    )


def shade_polygon(
    face: FaceSpec,
    nx: float,
    ny: float,
    nz: float,
    vx: float,
    vy: float,
    vz: float,
    cultivar: CultivarSpec | str = DEFAULT_CULTIVAR,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> str:
    """Compute cultivar- and mood-aware wrap-diffuse + bounce + AO hex color."""
    cultivar_spec = cultivar if isinstance(cultivar, CultivarSpec) else get_cultivar(cultivar)
    mood_spec = mood if isinstance(mood, MoodSpec) else get_mood(mood)

    view_dot = nx * vx + ny * vy + nz * vz
    is_outer_side = view_dot < 0.0
    if face.double_sided and is_outer_side:
        nx, ny, nz = -nx, -ny, -nz

    kx, ky, kz = mood_spec.key_light
    fx, fy, fz = mood_spec.fill_light
    raw_key = nx * kx + ny * ky + nz * kz
    raw_fill = nx * fx + ny * fy + nz * fz

    key_wrap = max(0.0, (raw_key + 0.45) / 1.45)
    fill_wrap = max(0.0, (raw_fill + 0.35) / 1.35)
    down_bounce = max(0.0, -ny)

    hx, hy, hz = _normalize(kx + vx, ky + vy, kz + vz)
    half_dot = max(0.0, nx * hx + ny * hy + nz * hz)

    key_r, key_g, key_b = mood_spec.key_tint
    scat_r, scat_g, scat_b = mood_spec.bounce_scatter_rgb
    v_frac = _clamp(face.v_frac, 0.0, 1.0)
    layer_frac = _clamp(face.layer_frac, 0.0, 1.0)

    if face.material == "petal":
        ao_floor = cultivar_spec.petal_ao_floor
        ao = ao_floor + (1.0 - ao_floor) * _smoothstep(
            0.0, 0.90, 0.42 * layer_frac + 0.58 * v_frac
        )
        diff_r, diff_g, diff_b = _compute_channel_lights(
            mood_spec,
            key_wrap,
            fill_wrap,
            down_bounce,
            mood_spec.ambient_strength,
            mood_spec.key_strength,
            mood_spec.fill_strength,
            mood_spec.bounce_strength,
        )
        min_l = mood_spec.min_light
        max_l = mood_spec.max_light
        light_r = _clamp(ao * diff_r, min_l, max_l)
        light_g = _clamp(ao * diff_g, min_l, max_l)
        light_b = _clamp(ao * diff_b, min_l, max_l)
        spec = (half_dot ** 10) * (cultivar_spec.spec_strength * ao)

        side_r, side_g, side_b = (
            cultivar_spec.petal_outer_rgb
            if is_outer_side
            else cultivar_spec.petal_inner_rgb
        )
        if cultivar_spec.heart_uses_v:
            base_curve = (1.0 - v_frac) ** 1.65
            layer_curve = 0.45 + 0.55 * (1.0 - layer_frac)
            heart_w = base_curve * layer_curve * cultivar_spec.heart_blend
        else:
            heart_w = ((1.0 - layer_frac) ** 1.35) * cultivar_spec.heart_blend
        base_r = _lerp(side_r, cultivar_spec.petal_heart_rgb[0], heart_w)
        base_g = _lerp(side_g, cultivar_spec.petal_heart_rgb[1], heart_w)
        base_b = _lerp(side_b, cultivar_spec.petal_heart_rgb[2], heart_w)

        tip_w = _smoothstep(0.15, 0.95, v_frac) * cultivar_spec.tip_blend
        base_r = _lerp(base_r, cultivar_spec.petal_tip_rgb[0], tip_w)
        base_g = _lerp(base_g, cultivar_spec.petal_tip_rgb[1], tip_w)
        base_b = _lerp(base_b, cultivar_spec.petal_tip_rgb[2], tip_w)

        tip_lift = cultivar_spec.tip_lift_base + cultivar_spec.tip_lift_span * v_frac
        sr, sg, sb = cultivar_spec.petal_spec_rgb
        r = base_r * light_r * tip_lift + sr * key_r * spec + scat_r * down_bounce
        g = base_g * (light_g ** 1.08) * tip_lift + sg * key_g * spec + scat_g * down_bounce
        b = base_b * (light_b ** 1.10) * tip_lift + sb * key_b * spec + scat_b * down_bounce
        return _rgb_to_hex(r, g, b)

    amb_scale = mood_spec.ambient_strength / 0.34
    key_scale = mood_spec.key_strength / 0.56
    fill_scale = mood_spec.fill_strength / 0.16
    bnc_scale = mood_spec.bounce_strength / 0.24

    if face.material in ("thorn", "bark"):
        diff_r, diff_g, diff_b = _compute_channel_lights(
            mood_spec,
            key_wrap,
            fill_wrap,
            down_bounce,
            0.42 * amb_scale,
            0.52 * key_scale,
            0.16 * fill_scale,
            0.12 * bnc_scale,
        )
        ao_b = 0.80 + 0.20 * v_frac if face.material == "bark" else 1.0
        tr, tg, tb = cultivar_spec.bark_rgb if face.material == "bark" else cultivar_spec.thorn_rgb
        return _rgb_to_hex(
            tr * diff_r * ao_b + scat_r * down_bounce * 0.45,
            tg * diff_g * ao_b + scat_g * down_bounce * 0.45,
            tb * diff_b * ao_b + scat_b * down_bounce * 0.45,
        )

    if face.material in ("stamen", "anther", "center", "center_accent"):
        ao_c = 0.68 + 0.32 * v_frac
        diff_r, diff_g, diff_b = _compute_channel_lights(
            mood_spec,
            key_wrap,
            fill_wrap,
            down_bounce,
            0.42 * amb_scale,
            0.56 * key_scale,
            0.18 * fill_scale,
            0.18 * bnc_scale,
        )
        if face.material == "stamen":
            cr, cg, cb = cultivar_spec.stamen_rgb
        elif face.material == "anther":
            cr, cg, cb = cultivar_spec.anther_rgb
        elif face.material == "center":
            cr, cg, cb = cultivar_spec.center_rgb
        else:
            cr, cg, cb = cultivar_spec.center_accent_rgb
        spec_c = (half_dot ** 12) * 0.08
        return _rgb_to_hex(
            cr * (diff_r * ao_c) + 255.0 * key_r * spec_c + scat_r * down_bounce * 0.45,
            cg * (diff_g * ao_c) + 245.0 * key_g * spec_c + scat_g * down_bounce * 0.45,
            cb * (diff_b * ao_c) + 220.0 * key_b * spec_c + scat_b * down_bounce * 0.45,
        )

    # Botanical foliage (receptacle, sepals, calyx, stem, leaves)
    ao = 0.62 + 0.38 * v_frac
    diff_r, diff_g, diff_b = _compute_channel_lights(
        mood_spec,
        key_wrap,
        fill_wrap,
        down_bounce,
        0.38 * amb_scale,
        0.56 * key_scale,
        0.16 * fill_scale,
        0.16 * bnc_scale,
    )
    spec = (half_dot ** 14) * 0.11
    if face.material == "calyx" and cultivar_spec.calyx_rgb is not None:
        fr, fg, fb = cultivar_spec.calyx_rgb
    else:
        fr, fg, fb = cultivar_spec.foliage_rgb
    fsr, fsg, fsb = cultivar_spec.foliage_spec_rgb
    r = fr * (diff_r * ao) + fsr * key_r * spec + scat_r * down_bounce * 0.65
    g = fg * (diff_g * ao) + fsg * key_g * spec + scat_g * down_bounce * 0.65
    b = fb * (diff_b * ao) + fsb * key_b * spec + scat_b * down_bounce * 0.65
    return _rgb_to_hex(r, g, b)


ShadeFn = Callable[[FaceSpec, float, float, float, float, float, float], str]


def build_draw_list(
    mesh: FlowerMesh,
    yaw: float,
    pitch: float,
    zoom: float,
    fov_scale: float = FOV_SCALE,
    *,
    cultivar: CultivarSpec | str | None = None,
    mood: MoodSpec | str = DEFAULT_MOOD,
    breeze_enabled: bool = False,
    breeze_time: float = 0.0,
    breeze_strength: float = 1.0,
    shade_fn: ShadeFn | None = None,
    pivot_y: float | None = None,
) -> list[tuple[float, str, tuple[tuple[float, float], ...]]]:
    """Transform vertices (with optional breeze sway), shade faces, and sort back-to-front."""
    mesh_species = getattr(mesh, "species", None)
    cultivar_spec = get_cultivar(cultivar, species=mesh_species)
    mood_spec = get_mood(mood)

    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    cos_p = math.cos(pitch)
    sin_p = math.sin(pitch)
    fov = fov_scale * zoom
    if pivot_y is None:
        pivot_y = mesh_species.pivot_y if isinstance(mesh_species, SpeciesSpec) else PIVOT_Y
    cam_dist = CAMERA_DISTANCE
    sqrt = math.sqrt
    cos = math.cos
    sin = math.sin

    verts = mesh.vertices
    n_verts = len(verts)
    tx = [0.0] * n_verts
    ty = [0.0] * n_verts
    tz = [0.0] * n_verts
    spx = [0.0] * n_verts
    spy = [0.0] * n_verts

    do_breeze = breeze_enabled and breeze_strength > 0.0
    if do_breeze:
        sway_data = mesh.vertex_sway
        bp = _compute_breeze_frame_params(breeze_time, breeze_strength)
        b_tilt_z = bp.tilt_z
        b_tilt_x = bp.tilt_x
        b_wt_fast = bp.wt_fast
        b_wt_gust = bp.wt_gust
        b_strength = bp.strength
        b_cz1 = bp.cz1
        b_sz1 = bp.sz1
        b_cx1 = bp.cx1
        b_sx1 = bp.sx1
        y_anchor = STEM_ANCHOR_Y

        for i in range(n_verts):
            x, y, z = verts[i]
            h, amp, phase = sway_data[i]
            if amp > 0.0:
                fw = amp * b_strength * sin(b_wt_fast + phase)
                fw2 = amp * b_strength * 0.45 * cos(b_wt_gust + phase * 1.37)
                y += fw
                x += fw2 * cos(phase)
                z += fw2 * sin(phase)
            if h > 0.0:
                by = y - y_anchor
                if h == 1.0:
                    cz_b, sz_b, cx_b, sx_b = b_cz1, b_sz1, b_cx1, b_sx1
                else:
                    bend = h * h * (1.35 - 0.35 * h)
                    rz = b_tilt_z * bend
                    rx = b_tilt_x * bend
                    cz_b = cos(rz)
                    sz_b = sin(rz)
                    cx_b = cos(rx)
                    sx_b = sin(rx)
                bx = x * cz_b - by * sz_b
                by1 = x * sz_b + by * cz_b
                by2 = by1 * cx_b - z * sx_b
                bz = by1 * sx_b + z * cx_b
                x = bx
                y = y_anchor + by2
                z = bz

            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            dy = y - pivot_y
            y2 = dy * cos_p - z1 * sin_p
            z2 = dy * sin_p + z1 * cos_p

            depth = cam_dist - z2
            if depth < 0.5:
                depth = 0.5
            inv_depth = fov / depth

            tx[i] = x1
            ty[i] = y2
            tz[i] = z2
            spx[i] = x1 * inv_depth
            spy[i] = y2 * inv_depth
    else:
        for i in range(n_verts):
            x, y, z = verts[i]
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            dy = y - pivot_y
            y2 = dy * cos_p - z1 * sin_p
            z2 = dy * sin_p + z1 * cos_p

            depth = cam_dist - z2
            if depth < 0.5:
                depth = 0.5
            inv_depth = fov / depth

            tx[i] = x1
            ty[i] = y2
            tz[i] = z2
            spx[i] = x1 * inv_depth
            spy[i] = y2 * inv_depth

    draw_items: list[tuple[float, str, tuple[tuple[float, float], ...]]] = []
    append_item = draw_items.append

    for face in mesh.faces:
        idxs = face.indices
        n_idx = len(idxs)
        if n_idx == 4:
            i0, i1, i2, i3 = idxs
            ax = tx[i2] - tx[i0]
            ay = ty[i2] - ty[i0]
            az = tz[i2] - tz[i0]
            bx = tx[i3] - tx[i1]
            by = ty[i3] - ty[i1]
            bz = tz[i3] - tz[i1]

            nx = ay * bz - az * by
            ny = az * bx - ax * bz
            nz = ax * by - ay * bx
            n_len = sqrt(nx * nx + ny * ny + nz * nz)
            if n_len < 1e-9:
                continue
            inv_n = 1.0 / n_len
            nx *= inv_n
            ny *= inv_n
            nz *= inv_n

            cx = (tx[i0] + tx[i1] + tx[i2] + tx[i3]) * 0.25
            cy = (ty[i0] + ty[i1] + ty[i2] + ty[i3]) * 0.25
            cz = (tz[i0] + tz[i1] + tz[i2] + tz[i3]) * 0.25
            pts: tuple[tuple[float, float], ...] = (
                (spx[i0], spy[i0]),
                (spx[i1], spy[i1]),
                (spx[i2], spy[i2]),
                (spx[i3], spy[i3]),
            )
        elif n_idx == 3:
            i0, i1, i2 = idxs
            ax = tx[i1] - tx[i0]
            ay = ty[i1] - ty[i0]
            az = tz[i1] - tz[i0]
            bx = tx[i2] - tx[i0]
            by = ty[i2] - ty[i0]
            bz = tz[i2] - tz[i0]

            nx = ay * bz - az * by
            ny = az * bx - ax * bz
            nz = ax * by - ay * bx
            n_len = sqrt(nx * nx + ny * ny + nz * nz)
            if n_len < 1e-9:
                continue
            inv_n = 1.0 / n_len
            nx *= inv_n
            ny *= inv_n
            nz *= inv_n

            cx = (tx[i0] + tx[i1] + tx[i2]) / 3.0
            cy = (ty[i0] + ty[i1] + ty[i2]) / 3.0
            cz = (tz[i0] + tz[i1] + tz[i2]) / 3.0
            pts = (
                (spx[i0], spy[i0]),
                (spx[i1], spy[i1]),
                (spx[i2], spy[i2]),
            )
        else:
            i0, i1, i2, i3 = idxs[0], idxs[1], idxs[2], idxs[3]
            ax = tx[i2] - tx[i0]
            ay = ty[i2] - ty[i0]
            az = tz[i2] - tz[i0]
            bx = tx[i3] - tx[i1]
            by = ty[i3] - ty[i1]
            bz = tz[i3] - tz[i1]

            nx = ay * bz - az * by
            ny = az * bx - ax * bz
            nz = ax * by - ay * bx
            n_len = sqrt(nx * nx + ny * ny + nz * nz)
            if n_len < 1e-9:
                continue
            inv_n = 1.0 / n_len
            nx *= inv_n
            ny *= inv_n
            nz *= inv_n

            cx = cy = cz = 0.0
            pts_list: list[tuple[float, float]] = []
            for idx in idxs:
                cx += tx[idx]
                cy += ty[idx]
                cz += tz[idx]
                pts_list.append((spx[idx], spy[idx]))
            inv_cnt = 1.0 / n_idx
            cx *= inv_cnt
            cy *= inv_cnt
            cz *= inv_cnt
            pts = tuple(pts_list)

        # View vector from centroid to camera at (0, 0, CAMERA_DISTANCE)
        vx = -cx
        vy = -cy
        vz = cam_dist - cz
        v_len = sqrt(vx * vx + vy * vy + vz * vz)
        if v_len < 1e-12:
            vx, vy, vz = 0.0, 0.0, 1.0
        else:
            inv_v = 1.0 / v_len
            vx *= inv_v
            vy *= inv_v
            vz *= inv_v

        if not face.double_sided and (nx * vx + ny * vy + nz * vz) <= 0.0:
            continue

        if shade_fn is not None:
            fill_hex = shade_fn(face, nx, ny, nz, vx, vy, vz)
        else:
            fill_hex = shade_polygon(
                face, nx, ny, nz, vx, vy, vz, cultivar=cultivar_spec, mood=mood_spec
            )
        append_item((cz, fill_hex, pts))

    draw_items.sort(key=lambda item: item[0])
    return draw_items


@dataclass(slots=True)
class CameraInertia:
    """Framerate-independent exponential inertia for orbit drag, nudges, and zoom."""

    yaw_vel: float = 0.0
    pitch_vel: float = 0.0
    zoom_vel: float = 0.0
    angular_damping: float = 10.5
    zoom_damping: float = 12.0
    pitch_min: float = PITCH_MIN
    pitch_max: float = PITCH_MAX
    zoom_min: float = ZOOM_MIN
    zoom_max: float = ZOOM_MAX
    max_angular_vel: float = 36.0
    max_drag_vel: float = 8.0
    max_zoom_vel: float = 24.0
    stop_epsilon: float = 1e-4
    _last_drag_time: float | None = None

    @property
    def is_active(self) -> bool:
        eps = self.stop_epsilon
        return (
            abs(self.yaw_vel) > eps
            or abs(self.pitch_vel) > eps
            or abs(self.zoom_vel) > eps
        )

    def reset(self) -> None:
        """Clear all residual angular and zoom velocities and drag tracking."""
        self.yaw_vel = 0.0
        self.pitch_vel = 0.0
        self.zoom_vel = 0.0
        self._last_drag_time = None

    def cancel(self) -> None:
        """Alias for ``reset()`` when cancelling camera transitions or resetting view."""
        self.reset()

    def begin_drag(self, now: float | None = None) -> None:
        """Stop residual orbit glide when the user grabs the scene."""
        self.yaw_vel = 0.0
        self.pitch_vel = 0.0
        self._last_drag_time = time.perf_counter() if now is None else now

    def record_drag(
        self,
        dyaw: float,
        dpitch: float,
        now: float | None = None,
    ) -> None:
        """Update smoothed drag velocity from an incremental pointer drag delta."""
        t_now = time.perf_counter() if now is None else now
        if self._last_drag_time is None:
            self._last_drag_time = t_now
            return

        dt_raw = max(0.0, t_now - self._last_drag_time)
        self._last_drag_time = t_now
        dt_eff = max(dt_raw, 1.0 / 120.0)
        inst_yaw = dyaw / dt_eff
        inst_pitch = dpitch / dt_eff
        alpha = max(0.25, 1.0 - math.exp(-min(dt_raw, 0.12) / 0.032))

        self.yaw_vel = _clamp(
            _lerp(self.yaw_vel, inst_yaw, alpha),
            -self.max_drag_vel,
            self.max_drag_vel,
        )
        self.pitch_vel = _clamp(
            _lerp(self.pitch_vel, inst_pitch, alpha),
            -self.max_drag_vel,
            self.max_drag_vel,
        )

    def end_drag(self, now: float | None = None) -> None:
        """Finalize drag release, damping stale velocity if pointer paused before release."""
        if self._last_drag_time is None:
            return
        t_now = time.perf_counter() if now is None else now
        idle = max(0.0, t_now - self._last_drag_time)
        self._last_drag_time = None
        if idle > 0.12:
            self.yaw_vel = 0.0
            self.pitch_vel = 0.0
        elif idle > 0.04:
            decay = math.exp(-self.angular_damping * 2.5 * idle)
            self.yaw_vel *= decay
            self.pitch_vel *= decay

    def impulse_angles(self, dyaw: float = 0.0, dpitch: float = 0.0) -> None:
        """Queue a smooth angular glide whose time-integral equals ``(dyaw, dpitch)``."""
        self.yaw_vel = _clamp(
            self.yaw_vel + dyaw * self.angular_damping,
            -self.max_angular_vel,
            self.max_angular_vel,
        )
        self.pitch_vel = _clamp(
            self.pitch_vel + dpitch * self.angular_damping,
            -self.max_angular_vel,
            self.max_angular_vel,
        )

    def impulse_zoom(self, factor: float) -> None:
        """Queue a smooth multiplicative zoom glide whose time-integral equals ``factor``."""
        if factor <= 0.0:
            return
        self.zoom_vel = _clamp(
            self.zoom_vel + math.log(factor) * self.zoom_damping,
            -self.max_zoom_vel,
            self.max_zoom_vel,
        )

    def step(
        self,
        yaw: float,
        pitch: float,
        zoom: float,
        dt: float,
    ) -> tuple[float, float, float]:
        """Advance camera pose by ``dt`` seconds with exponential damping and clamps."""
        if dt <= 0.0:
            return (
                yaw,
                _clamp(pitch, self.pitch_min, self.pitch_max),
                _clamp(zoom, self.zoom_min, self.zoom_max),
            )

        k_a = self.angular_damping
        if k_a > 1e-9:
            decay_a = math.exp(-k_a * dt)
            step_a = (1.0 - decay_a) / k_a
        else:
            decay_a = 1.0
            step_a = dt

        if abs(self.yaw_vel) > self.stop_epsilon:
            yaw += self.yaw_vel * step_a
            self.yaw_vel *= decay_a
        if abs(self.yaw_vel) <= self.stop_epsilon:
            self.yaw_vel = 0.0

        if abs(self.pitch_vel) > self.stop_epsilon:
            pitch += self.pitch_vel * step_a
            self.pitch_vel *= decay_a
        if pitch <= self.pitch_min:
            pitch = self.pitch_min
            if self.pitch_vel < 0.0:
                self.pitch_vel = 0.0
        elif pitch >= self.pitch_max:
            pitch = self.pitch_max
            if self.pitch_vel > 0.0:
                self.pitch_vel = 0.0
        if abs(self.pitch_vel) <= self.stop_epsilon:
            self.pitch_vel = 0.0

        k_z = self.zoom_damping
        if k_z > 1e-9:
            decay_z = math.exp(-k_z * dt)
            step_z = (1.0 - decay_z) / k_z
        else:
            decay_z = 1.0
            step_z = dt

        if abs(self.zoom_vel) > self.stop_epsilon:
            zoom *= math.exp(self.zoom_vel * step_z)
            self.zoom_vel *= decay_z
        if zoom <= self.zoom_min:
            zoom = self.zoom_min
            if self.zoom_vel < 0.0:
                self.zoom_vel = 0.0
        elif zoom >= self.zoom_max:
            zoom = self.zoom_max
            if self.zoom_vel > 0.0:
                self.zoom_vel = 0.0
        if abs(self.zoom_vel) <= self.stop_epsilon:
            self.zoom_vel = 0.0

        return (yaw, pitch, zoom)


# ---------------------------------------------------------------------------
# HUD Typography, Material Symbols Icons & Frosted Pill Helpers
# ---------------------------------------------------------------------------

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_ICONS_DIR = _ASSETS_DIR / "icons"
_AUDIOS_DIR = _ASSETS_DIR / "audios"
_APP_ICON_PNG = _ASSETS_DIR / "rose_icon.png"
_APP_ICON_ICO = _ASSETS_DIR / "rose_icon.ico"
_AUDIO_EXTENSIONS: tuple[str, ...] = (".m4a",)
_MAX_AUDIO_BYTES = 128 * 1024 * 1024

_FONT_FILENAMES = (
    "GoogleSans-Regular.ttf",
    "GoogleSans-Medium.ttf",
    "GoogleSans-Bold.ttf",
)

_ICON_ALIASES = {
    "orbit": "orbit",
    "360": "orbit",
    "zoom": "zoom",
    "zoom_in": "zoom",
    "pause": "pause",
    "play": "play",
    "play_arrow": "play",
    "bloom": "bloom",
    "spa": "bloom",
    "reset": "reset",
    "refresh": "reset",
    "speed": "speed",
    "fps": "speed",
    "palette": "palette",
    "cultivar": "palette",
    "light_mode": "light_mode",
    "dark_mode": "dark_mode",
    "air": "air",
    "breeze": "air",
    "wind": "air",
    "auto_awesome": "auto_awesome",
    "detail": "auto_awesome",
    "local_florist": "local_florist",
    "species": "local_florist",
    "flower": "local_florist",
    "skip_previous": "skip_previous",
    "previous": "skip_previous",
    "prev": "skip_previous",
    "skip_next": "skip_next",
    "next": "skip_next",
    "music_note": "music_note",
    "bgm": "music_note",
}

_FR_PRIVATE = 0x10
_MAX_FONT_BYTES = 4 * 1024 * 1024  # Bundled GoogleSans-*.ttf files are ~2.2 MiB each
_MAX_ICON_BYTES = 64 * 1024
_MAX_ICON_DIM = 128
_MAX_APP_ICON_BYTES = 2 * 1024 * 1024
_WINDOWS_APP_ID = "DrawAFlower.Flowers3D"

_LOADED_FONT_PATHS: list[str] = []
_LOADED_MEM_HANDLES: list[int] = []
_REGISTERED_FONT_PATHS: set[str] = set()
_FONT_CLEANUP_REGISTERED = False
_VERIFIED_FAMILY: str | None = None
_RAW_ICON_CACHE: dict[str, tuple[int, int, list[bytearray]]] = {}
_PILL_GEOMETRY_CACHE: dict[tuple[int, int], list[list[tuple[int, float, float]]]] = {}


def _validate_asset_path(path: Path, max_bytes: int) -> Path | None:
    """Ensure an asset file exists, is not a symlink, stays inside assets/, and is bounded."""
    try:
        if path.is_symlink():
            return None
        resolved_root = _ASSETS_DIR.resolve(strict=True)
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
            return None
        if resolved.stat().st_size > max_bytes:
            return None
        return resolved
    except OSError:
        return None


def _cleanup_windows_fonts() -> None:
    """Release privately registered Windows GDI fonts at interpreter shutdown."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        gdi32 = ctypes.WinDLL("gdi32")
        gdi32.RemoveFontMemResourceEx.argtypes = [wintypes.HANDLE]
        gdi32.RemoveFontMemResourceEx.restype = wintypes.BOOL
        gdi32.RemoveFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        gdi32.RemoveFontResourceExW.restype = wintypes.BOOL

        for handle in _LOADED_MEM_HANDLES:
            gdi32.RemoveFontMemResourceEx(wintypes.HANDLE(handle))
        _LOADED_MEM_HANDLES.clear()

        for path_str in _LOADED_FONT_PATHS:
            gdi32.RemoveFontResourceExW(path_str, _FR_PRIVATE, None)
        _LOADED_FONT_PATHS.clear()
    except Exception:
        pass


def _register_windows_fonts(font_paths: Sequence[Path]) -> None:
    """Register TTF files privately for the current Windows process."""
    global _FONT_CLEANUP_REGISTERED
    import ctypes
    from ctypes import wintypes

    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
    gdi32.AddFontResourceExW.restype = ctypes.c_int
    gdi32.AddFontMemResourceEx.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.DWORD),
    ]
    gdi32.AddFontMemResourceEx.restype = wintypes.HANDLE

    if not _FONT_CLEANUP_REGISTERED:
        atexit.register(_cleanup_windows_fonts)
        _FONT_CLEANUP_REGISTERED = True

    for raw_path in font_paths:
        path = _validate_asset_path(raw_path, _MAX_FONT_BYTES)
        if path is None:
            continue
        path_str = str(path)
        if path_str in _REGISTERED_FONT_PATHS:
            continue

        added = gdi32.AddFontResourceExW(path_str, _FR_PRIVATE, None)
        if added > 0:
            _REGISTERED_FONT_PATHS.add(path_str)
            _LOADED_FONT_PATHS.append(path_str)
            continue

        font_bytes = path.read_bytes()
        num_fonts = wintypes.DWORD(0)
        handle = gdi32.AddFontMemResourceEx(
            font_bytes,
            len(font_bytes),
            None,
            ctypes.byref(num_fonts),
        )
        if handle:
            _REGISTERED_FONT_PATHS.add(path_str)
            _LOADED_MEM_HANDLES.append(int(handle))


def _register_macos_fonts(font_paths: Sequence[Path]) -> None:
    """Register TTF files for the current macOS process via CoreText."""
    import ctypes
    from ctypes import util

    ct_path = util.find_library("CoreText")
    cf_path = util.find_library("CoreFoundation")
    if not ct_path or not cf_path:
        return
    try:
        ct = ctypes.cdll.LoadLibrary(ct_path)
        cf = ctypes.cdll.LoadLibrary(cf_path)
        cf.CFURLCreateFromFileSystemRepresentation.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_long,
            ctypes.c_bool,
        ]
        cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
        cf.CFRelease.argtypes = [ctypes.c_void_p]
        ct.CTFontManagerRegisterFontsForURL.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
        ]
        ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
        for raw_path in font_paths:
            path = _validate_asset_path(raw_path, _MAX_FONT_BYTES)
            if path is None:
                continue
            path_str = str(path)
            if path_str in _LOADED_FONT_PATHS:
                continue
            raw = path_str.encode("utf-8")
            url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
            if url:
                try:
                    if ct.CTFontManagerRegisterFontsForURL(url, 1, None):
                        _LOADED_FONT_PATHS.append(path_str)
                finally:
                    cf.CFRelease(url)
    except Exception:
        pass


def _resolve_tk_family(candidates: Sequence[str]) -> str:
    """Return the first candidate family that Tkinter resolves without fallback."""
    existing_root = tk._default_root
    temp_root: tk.Tk | None = None
    root = existing_root
    if root is None:
        temp_root = tk.Tk()
        temp_root.withdraw()
        root = temp_root

    try:
        for candidate in candidates:
            actual = tkfont.Font(root=root, family=candidate, size=9).actual()
            if str(actual.get("family", "")).casefold() == candidate.casefold():
                return str(actual["family"])
        return str(
            tkfont.Font(root=root, family=candidates[-1], size=9)
            .actual()
            .get("family", candidates[-1])
        )
    finally:
        if temp_root is not None:
            temp_root.destroy()


def load_google_sans() -> str:
    """Register bundled Google Sans TTFs privately and return the verified family name."""
    global _VERIFIED_FAMILY
    if _VERIFIED_FAMILY is not None:
        return _VERIFIED_FAMILY

    font_paths = [_FONTS_DIR / name for name in _FONT_FILENAMES]
    if sys.platform == "win32":
        _register_windows_fonts(font_paths)
    elif sys.platform == "darwin":
        _register_macos_fonts(font_paths)

    fallback = "Segoe UI" if sys.platform == "win32" else "Helvetica"
    _VERIFIED_FAMILY = _resolve_tk_family(("Google Sans", fallback, "Arial"))
    return _VERIFIED_FAMILY


def get_hud_font(size: int = 9, weight: str = "normal") -> tuple[str, int, str]:
    """Return a Tkinter/Turtle font tuple using Google Sans when available."""
    family = load_google_sans()
    normalized_weight = weight.strip().lower()
    if normalized_weight == "medium" and family == "Google Sans":
        resolved = _resolve_tk_family(("Google Sans Medium", "Google Sans"))
        if resolved == "Google Sans Medium":
            return (resolved, size, "normal")
        return (family, size, "bold")
    tk_weight = "bold" if normalized_weight in ("bold", "semibold", "medium") else "normal"
    return (family, size, tk_weight)


def _resolve_icon_path(name: str) -> Path:
    key = _ICON_ALIASES.get(name.strip().lower())
    if key is None:
        raise ValueError(f"Unknown HUD icon name: {name!r}")
    candidate = _ICONS_DIR / f"{key}.png"
    validated = _validate_asset_path(candidate, _MAX_ICON_BYTES)
    if validated is None:
        raise FileNotFoundError(f"HUD icon asset invalid or not found: {candidate}")
    return validated


def _set_windows_app_id() -> None:
    """Assign an explicit Windows AppUserModelID so the taskbar uses our app icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_WINDOWS_APP_ID)
    except Exception:
        pass


def apply_window_icon(root: tk.Misc) -> tk.PhotoImage | None:
    """Set the 1:1 window and taskbar icon from ``assets/`` with graceful fallback."""
    if sys.platform == "win32":
        ico_path = _validate_asset_path(_APP_ICON_ICO, _MAX_APP_ICON_BYTES)
        if ico_path is not None:
            try:
                ico_str = str(ico_path)
                root.wm_iconbitmap(ico_str)  # type: ignore[attr-defined]
                root.wm_iconbitmap(default=ico_str)  # type: ignore[attr-defined]
                return None
            except tk.TclError:
                pass

    png_path = _validate_asset_path(_APP_ICON_PNG, _MAX_APP_ICON_BYTES)
    if png_path is not None:
        try:
            photo = tk.PhotoImage(master=root, file=str(png_path), format="png")
            root.wm_iconphoto(True, photo)  # type: ignore[attr-defined]
            return photo
        except tk.TclError:
            return None
    return None


def _paeth_predictor(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _decode_rgba_png_bytes(data: bytes, key: str) -> tuple[int, int, list[bytearray]]:
    """Parse and decode validated 8-bit RGBA PNG bytes into scanline rows."""
    if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid PNG signature in icon {key!r}")

    pos = 8
    width = height = 0
    idat_parts: list[bytes] = []
    seen_ihdr = False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        if length > _MAX_ICON_BYTES or pos + 12 + length > len(data):
            raise ValueError(f"Corrupt PNG chunk bounds in icon {key!r}")
        tag = data[pos + 4 : pos + 8]
        payload = data[pos + 8 : pos + 8 + length]
        expected_crc = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])[0]
        if (zlib.crc32(tag + payload) & 0xFFFFFFFF) != expected_crc:
            raise ValueError(f"PNG chunk CRC mismatch in icon {key!r}")
        pos += 12 + length

        if tag == b"IHDR":
            if length != 13:
                raise ValueError(f"Invalid PNG IHDR length in icon {key!r}")
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if not (0 < width <= _MAX_ICON_DIM and 0 < height <= _MAX_ICON_DIM):
                raise ValueError(f"Unsupported PNG dimensions in icon {key!r}")
            if (bit_depth, color_type, comp, filt, interlace) != (8, 6, 0, 0, 0):
                raise ValueError(f"Unsupported PNG format in icon {key!r}")
            seen_ihdr = True
        elif tag == b"IDAT":
            idat_parts.append(payload)
        elif tag == b"IEND":
            break

    if not seen_ihdr or not idat_parts:
        raise ValueError(f"Missing PNG IHDR/IDAT in icon {key!r}")

    stride = width * 4
    expected_raw = height * (1 + stride)
    decomp = zlib.decompressobj()
    decompressed = decomp.decompress(b"".join(idat_parts), expected_raw + 1)
    if not decomp.eof or decomp.unconsumed_tail or len(decompressed) != expected_raw:
        raise ValueError(f"Unexpected decompressed PNG size in icon {key!r}")

    rows: list[bytearray] = []
    prev_row = bytearray(stride)
    offset = 0
    for _ in range(height):
        filt_type = decompressed[offset]
        offset += 1
        row = bytearray(decompressed[offset : offset + stride])
        offset += stride
        if filt_type == 1:
            for i in range(4, stride):
                row[i] = (row[i] + row[i - 4]) & 0xFF
        elif filt_type == 2:
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filt_type == 3:
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                row[i] = (row[i] + ((left + prev_row[i]) >> 1)) & 0xFF
        elif filt_type == 4:
            for i in range(stride):
                left = row[i - 4] if i >= 4 else 0
                up = prev_row[i]
                up_left = prev_row[i - 4] if i >= 4 else 0
                row[i] = (row[i] + _paeth_predictor(left, up, up_left)) & 0xFF
        elif filt_type != 0:
            raise ValueError(f"Unsupported PNG filter {filt_type} in icon {key!r}")
        rows.append(row)
        prev_row = row

    return (width, height, rows)


def _load_rgba_icon(name: str) -> tuple[int, int, list[bytearray]]:
    """Decode an 8-bit RGBA icon PNG into (width, height, scanline rows)."""
    key = _ICON_ALIASES.get(name.strip().lower(), name.strip().lower())
    cached = _RAW_ICON_CACHE.get(key)
    if cached is not None:
        return cached

    data = _resolve_icon_path(key).read_bytes()
    result = _decode_rgba_png_bytes(data, key)
    _RAW_ICON_CACHE[key] = result
    return result


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _encode_rgba_rows_png(width: int, height: int, rows: Sequence[bytearray | bytes]) -> bytes:
    raw = bytearray()
    for row in rows:
        raw.append(0)
        raw.extend(row)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def _compute_pill_geometry(
    width: int,
    height: int,
) -> list[list[tuple[int, float, float]]]:
    """Precompute per-row ``(byte_offset, coverage, border_t)`` for a rounded pill."""
    cache_key = (width, height)
    cached = _PILL_GEOMETRY_CACHE.get(cache_key)
    if cached is not None:
        return cached

    hw = width * 0.5
    hh = height * 0.5
    radius = hh - 1.5
    inner_half_w = max(0.0, hw - radius - 1.0)
    inner_half_h = max(0.0, hh - radius - 1.0)

    rows_geom: list[list[tuple[int, float, float]]] = []
    for iy in range(height):
        row_pixels: list[tuple[int, float, float]] = []
        dy = abs((iy + 0.5) - hh) - inner_half_h
        dy_pos = dy if dy > 0.0 else 0.0
        for ix in range(width):
            dx = abs((ix + 0.5) - hw) - inner_half_w
            dx_pos = dx if dx > 0.0 else 0.0
            inside_max = dx if dx > dy else dy
            dist = (
                math.sqrt(dx_pos * dx_pos + dy_pos * dy_pos)
                + (inside_max if inside_max < 0.0 else 0.0)
                - radius
            )
            if dist >= 0.75:
                continue

            cov = _clamp(0.75 - dist, 0.0, 1.0)
            border_t = _clamp((dist + 1.3) / 1.3, 0.0, 1.0)
            row_pixels.append((ix * 4, cov, border_t))
        rows_geom.append(row_pixels)

    if len(_PILL_GEOMETRY_CACHE) >= 64:
        _PILL_GEOMETRY_CACHE.clear()
    _PILL_GEOMETRY_CACHE[cache_key] = rows_geom
    return rows_geom


def _fill_pill_rows_from_geometry(
    width: int,
    rows_geom: Sequence[Sequence[tuple[int, float, float]]],
    fill_rgba: tuple[int, int, int, int],
    edge_rgba: tuple[int, int, int, int],
) -> list[bytearray]:
    """Shade precomputed rounded-pill SDF pixels into RGBA row buffers."""
    fill_r, fill_g, fill_b, fill_a = (float(c) for c in fill_rgba)
    edge_r, edge_g, edge_b, edge_a = (float(c) for c in edge_rgba)

    row_stride = width * 4
    rows: list[bytearray] = []
    for row_pixels in rows_geom:
        row = bytearray(row_stride)
        for base, cov, border_t in row_pixels:
            row[base] = int(_lerp(fill_r, edge_r, border_t) + 0.5)
            row[base + 1] = int(_lerp(fill_g, edge_g, border_t) + 0.5)
            row[base + 2] = int(_lerp(fill_b, edge_b, border_t) + 0.5)
            row[base + 3] = int(_lerp(fill_a, edge_a, border_t) * cov + 0.5)
        rows.append(row)
    return rows


def build_pill_rows(
    width: int,
    height: int,
    *,
    mood: MoodSpec | str = DEFAULT_MOOD,
    enabled: bool = True,
    fill_rgba: tuple[int, int, int, int] | None = None,
    edge_rgba: tuple[int, int, int, int] | None = None,
) -> list[bytearray]:
    """Render an anti-aliased frosted rounded-pill RGBA buffer for a given mood."""
    mood_spec = get_mood(mood)
    resolved_fill = (
        fill_rgba
        if fill_rgba is not None
        else (mood_spec.pill_fill_rgba if enabled else mood_spec.disabled_fill_rgba)
    )
    resolved_edge = (
        edge_rgba
        if edge_rgba is not None
        else (mood_spec.pill_edge_rgba if enabled else mood_spec.disabled_edge_rgba)
    )
    rows_geom = _compute_pill_geometry(width, height)
    return _fill_pill_rows_from_geometry(width, rows_geom, resolved_fill, resolved_edge)


def _composite_icon_over_rows(
    dst_rows: list[bytearray],
    dst_width: int,
    dst_height: int,
    icon_name: str,
    dest_x: int,
    dest_y: int,
    alpha_scale: float = 1.0,
    tint_rgb: tuple[int, int, int] | None = None,
) -> None:
    """Alpha-composite a straight-RGBA icon (with optional monochrome tint) onto RGBA rows."""
    icon_w, icon_h, icon_rows = _load_rgba_icon(icon_name)
    tint_r = tint_g = tint_b = 0
    if tint_rgb is not None:
        tint_r = int(_clamp(tint_rgb[0], 0.0, 255.0) + 0.5)
        tint_g = int(_clamp(tint_rgb[1], 0.0, 255.0) + 0.5)
        tint_b = int(_clamp(tint_rgb[2], 0.0, 255.0) + 0.5)

    for iy in range(icon_h):
        py = dest_y + iy
        if py < 0 or py >= dst_height:
            continue
        src_row = icon_rows[iy]
        dst_row = dst_rows[py]
        for ix in range(icon_w):
            px = dest_x + ix
            if px < 0 or px >= dst_width:
                continue
            s_off = ix * 4
            sa = src_row[s_off + 3]
            if sa == 0:
                continue
            d_off = px * 4
            da = dst_row[d_off + 3]
            sa_f = (sa / 255.0) * alpha_scale
            da_f = da / 255.0
            inv_sa = 1.0 - sa_f
            out_a = sa_f + da_f * inv_sa
            if out_a <= 1e-6:
                continue

            if tint_rgb is not None:
                sr, sg, sb = tint_r, tint_g, tint_b
            else:
                sr, sg, sb = src_row[s_off], src_row[s_off + 1], src_row[s_off + 2]

            dst_row[d_off] = int((sr * sa_f + dst_row[d_off] * da_f * inv_sa) / out_a + 0.5)
            dst_row[d_off + 1] = int(
                (sg * sa_f + dst_row[d_off + 1] * da_f * inv_sa) / out_a + 0.5
            )
            dst_row[d_off + 2] = int(
                (sb * sa_f + dst_row[d_off + 2] * da_f * inv_sa) / out_a + 0.5
            )
            dst_row[d_off + 3] = int(_clamp(out_a * 255.0, 0.0, 255.0) + 0.5)


def compute_hud_text_y(pill_y: float, font: tkfont.Font) -> float:
    """Return the turtle Y coordinate that optically centers text at ``pill_y``."""
    descent = int(font.metrics("descent"))
    try:
        raw_size = int(font.cget("size"))
    except (TypeError, ValueError, tk.TclError):
        raw_size = 9

    if raw_size < 0:
        em_px = float(-raw_size)
    else:
        root = getattr(font, "_root", None) or tk._default_root
        pt_to_px = 96.0 / 72.0
        if root is not None:
            try:
                pt_to_px = float(root.winfo_fpixels("1p"))
            except tk.TclError:
                pass
        em_px = float(raw_size) * pt_to_px

    cap_height_px = em_px * 0.72
    return pill_y - (descent + cap_height_px * 0.46)


def _hud_control_items(paused: bool, *, compact: bool = False) -> tuple[tuple[str, str], ...]:
    if compact:
        return (
            ("orbit", "Orbit"),
            ("zoom", "Zoom"),
            ("play" if paused else "pause", "Play" if paused else "Pause"),
            ("bloom", "Bloom"),
            ("reset", "Reset"),
        )
    return (
        ("orbit", "Drag: Orbit"),
        ("zoom", "Scroll: Zoom"),
        ("play" if paused else "pause", "Space: Resume" if paused else "Space: Pause"),
        ("bloom", "B: Bloom"),
        ("reset", "R: Reset"),
    )


def _measure_hud_layout(
    items: Sequence[tuple[str, str]],
    font: tkfont.Font,
    icon_gap: int,
    sep_gap: int,
) -> tuple[int, int, list[tuple[str, int, int, str]], list[tuple[int, str]]]:
    sep_text = "·"
    sep_w = int(font.measure(sep_text))
    cursor = 0
    item_positions: list[tuple[str, int, int, str]] = []
    sep_positions: list[tuple[int, str]] = []

    for idx, (icon_name, label) in enumerate(items):
        if idx > 0:
            cursor += sep_gap
            sep_positions.append((cursor, sep_text))
            cursor += sep_w + sep_gap
        icon_w, _icon_h, _ = _load_rgba_icon(icon_name)
        item_positions.append((icon_name, cursor, cursor + icon_w + icon_gap, label))
        cursor += icon_w + icon_gap + int(font.measure(label))

    max_icon_h = max(_load_rgba_icon(icon_name)[1] for icon_name, _ in items)
    return (cursor, max_icon_h, item_positions, sep_positions)


BOTTOM_HUD_ACTION_KEYS: tuple[str, ...] = ("pause", "bloom", "reset")
_BOTTOM_HUD_CONFIGS: tuple[tuple[bool, int, int, int], ...] = (
    (False, 4, 7, 18),
    (False, 4, 5, 12),
    (True, 3, 4, 10),
)


@dataclass(frozen=True, slots=True)
class SegmentHitRect:
    """Clickable segment bounding box in Turtle canvas coordinates."""

    key: str
    label: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    text_x: float
    icon_name: str = ""
    icon_x: float = 0.0


@dataclass(frozen=True, slots=True)
class BottomHudLayout:
    """Measured layout and clickable segment spans for the bottom control HUD pill."""

    pill_width: int
    pill_height: int
    compact: bool
    paused: bool
    content_left_px: int
    item_positions: tuple[tuple[str, int, int, str], ...]
    segments: tuple[tuple[float, str], ...]
    local_hit_spans: tuple[tuple[str, str, float, float, float, str, float], ...]


def _hit_test_rects(
    cx: float, cy: float, hit_rects: Sequence[SegmentHitRect]
) -> str | None:
    """Return segment key at canvas ``(cx, cy)``, or ``None`` if outside."""
    last_idx = len(hit_rects) - 1
    for idx, rect in enumerate(hit_rects):
        if cy < rect.y_min or cy > rect.y_max:
            continue
        in_x = (
            (rect.x_min <= cx <= rect.x_max)
            if idx == last_idx
            else (rect.x_min <= cx < rect.x_max)
        )
        if in_x:
            return rect.key
    return None


def _logical_bottom_hud_key(icon_name: str) -> str:
    return "pause" if icon_name in ("pause", "play") else icon_name


def resolve_bottom_hud_layout(
    paused: bool,
    font: tkfont.Font,
    *,
    max_width: int | None = None,
    height: int = HUD_HEIGHT,
) -> BottomHudLayout:
    """Measure bottom HUD pill with adaptive compact labels and clickable action spans."""
    chosen = _BOTTOM_HUD_CONFIGS[0]
    max_content_w = 0
    for compact, icon_gap, sep_gap, pad_x in _BOTTOM_HUD_CONFIGS:
        w_play, _, _, _ = _measure_hud_layout(
            _hud_control_items(False, compact=compact), font, icon_gap=icon_gap, sep_gap=sep_gap
        )
        w_pause, _, _, _ = _measure_hud_layout(
            _hud_control_items(True, compact=compact), font, icon_gap=icon_gap, sep_gap=sep_gap
        )
        max_content_w = max(w_play, w_pause)
        chosen = (compact, icon_gap, sep_gap, pad_x)
        if max_width is None or max_content_w + pad_x * 2 <= max_width:
            break

    compact, icon_gap, sep_gap, pad_x = chosen
    pill_w = max_content_w + pad_x * 2
    if max_width is not None:
        pill_w = min(max_width, pill_w)

    content_w, _, item_positions, sep_positions = _measure_hud_layout(
        _hud_control_items(paused, compact=compact), font, icon_gap=icon_gap, sep_gap=sep_gap
    )
    content_left_px = round((pill_w - content_w) * 0.5)

    # TurtleScreen._write places canvas text at (x - 1, -y); add +1.0 to align cleanly
    half_pill = pill_w * 0.5
    sep_w = int(font.measure("·"))
    raw_segments: list[tuple[float, str]] = []
    item_metrics: list[tuple[str, str, str, bool, float, float, float]] = []
    for icon_name, rel_icon_x, rel_text_x, label in item_positions:
        text_w = int(font.measure(label))
        rel_left = (content_left_px + rel_icon_x) - half_pill
        rel_right = (content_left_px + rel_text_x + text_w) - half_pill
        rel_text = ((content_left_px + rel_text_x) - half_pill) + 1.0
        raw_segments.append((rel_text, label))
        key = _logical_bottom_hud_key(icon_name)
        item_metrics.append(
            (key, icon_name, label, key in BOTTOM_HUD_ACTION_KEYS, rel_left, rel_right, rel_text)
        )

    for rel_sep_x, sep_text in sep_positions:
        raw_segments.append((((content_left_px + rel_sep_x) - half_pill) + 1.0, sep_text))
    raw_segments.sort(key=lambda item: item[0])

    # Keep the separator dot before 'pause' on the non-clickable hint side
    boundaries: list[float] = [-half_pill]
    for idx in range(len(item_metrics) - 1):
        curr = item_metrics[idx]
        nxt = item_metrics[idx + 1]
        if not curr[3] and nxt[3]:
            sep_right = (content_left_px + sep_positions[idx][0] + sep_w) - half_pill
            boundaries.append((sep_right + nxt[4]) * 0.5)
        else:
            boundaries.append((curr[5] + nxt[4]) * 0.5)
    boundaries.append(half_pill)

    local_hit_spans = tuple(
        (key, label, boundaries[idx], boundaries[idx + 1], rel_text, icon_name, rel_left)
        for idx, (key, icon_name, label, clickable, rel_left, _r, rel_text) in enumerate(
            item_metrics
        )
        if clickable
    )
    return BottomHudLayout(
        pill_width=pill_w,
        pill_height=height,
        compact=compact,
        paused=paused,
        content_left_px=content_left_px,
        item_positions=tuple(item_positions),
        segments=tuple(raw_segments),
        local_hit_spans=local_hit_spans,
    )


def place_bottom_hud_hit_rects(
    hud_x: float,
    hud_y: float,
    layout: BottomHudLayout,
) -> tuple[SegmentHitRect, ...]:
    """Compute clickable bottom HUD action hit rectangles ('pause', 'bloom', 'reset')."""
    y_min = hud_y - layout.pill_height * 0.5
    y_max = hud_y + layout.pill_height * 0.5
    return tuple(
        SegmentHitRect(
            key=key,
            label=label,
            x_min=hud_x + rel_xmin,
            x_max=hud_x + rel_xmax,
            y_min=y_min,
            y_max=y_max,
            text_x=hud_x + rel_text_x,
            icon_name=icon_name,
            icon_x=hud_x + rel_icon_x,
        )
        for (
            key,
            label,
            rel_xmin,
            rel_xmax,
            rel_text_x,
            icon_name,
            rel_icon_x,
        ) in layout.local_hit_spans
    )


def hit_test_bottom_hud(
    cx: float, cy: float, hit_rects: Sequence[SegmentHitRect]
) -> str | None:
    """Return bottom HUD action key ('pause'|'bloom'|'reset') at canvas (cx, cy), or None."""
    return _hit_test_rects(cx, cy, hit_rects)


def _bake_pill_photo_from_geometry(
    pill_w: int,
    height: int,
    rows_geom: Sequence[Sequence[tuple[int, float, float]]],
    content_left_px: int,
    item_positions: Sequence[tuple[str, int, int, str]],
    fill_rgba: tuple[int, int, int, int],
    edge_rgba: tuple[int, int, int, int],
    icon_alpha_scale: float,
    master: tk.Misc | None,
    *,
    icon_tint_rgb: tuple[int, int, int] | None = None,
) -> tk.PhotoImage:
    """Render one HUD pill ``PhotoImage`` from cached pill SDF geometry."""
    rows = _fill_pill_rows_from_geometry(pill_w, rows_geom, fill_rgba, edge_rgba)
    for icon_name, rel_icon_x, _rel_text_x, _label in item_positions:
        _, icon_h, _ = _load_rgba_icon(icon_name)
        icon_y = (height - icon_h) // 2
        _composite_icon_over_rows(
            rows,
            pill_w,
            height,
            icon_name,
            dest_x=content_left_px + rel_icon_x,
            dest_y=icon_y,
            alpha_scale=icon_alpha_scale,
            tint_rgb=icon_tint_rgb,
        )

    png_bytes = _encode_rgba_rows_png(pill_w, height, rows)
    photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
    if master is not None:
        photo_kwargs["master"] = master
    return tk.PhotoImage(**photo_kwargs)


def build_hud_pill_with_icons(
    paused: bool,
    font: tkfont.Font,
    *,
    height: int = HUD_HEIGHT,
    max_width: int | None = None,
    master: tk.Misc | None = None,
    mood: MoodSpec | str = DEFAULT_MOOD,
    fill_rgba: tuple[int, int, int, int] | None = None,
    edge_rgba: tuple[int, int, int, int] | None = None,
    icon_alpha_scale: float = 1.0,
    icon_tint_rgb: tuple[int, int, int] | None = None,
) -> tuple[tk.PhotoImage, list[tuple[float, str]]]:
    """Build the mood-aware frosted HUD pill ``PhotoImage`` with icons and text positions."""
    mood_spec = get_mood(mood)
    resolved_fill = fill_rgba if fill_rgba is not None else mood_spec.pill_fill_rgba
    resolved_edge = edge_rgba if edge_rgba is not None else mood_spec.pill_edge_rgba
    resolved_tint = icon_tint_rgb if icon_tint_rgb is not None else mood_spec.icon_enabled_rgb

    layout = resolve_bottom_hud_layout(paused, font, max_width=max_width, height=height)
    rows_geom = _compute_pill_geometry(layout.pill_width, height)
    pill_photo = _bake_pill_photo_from_geometry(
        layout.pill_width,
        height,
        rows_geom,
        layout.content_left_px,
        layout.item_positions,
        resolved_fill,
        resolved_edge,
        icon_alpha_scale,
        master,
        icon_tint_rgb=resolved_tint,
    )
    return (pill_photo, list(layout.segments))


def _bake_transition_pill_step(
    pill_w: int,
    height: int,
    rows_geom: Sequence[Sequence[tuple[int, float, float]]],
    content_left_px: int,
    item_positions: Sequence[tuple[str, int, int, str]],
    master: tk.Misc | None,
    step_idx: int,
    steps: int,
    mood_spec: MoodSpec,
) -> tk.PhotoImage:
    """Bake one frosted pill image at fractional enable step ``step_idx / steps``."""
    step_count = max(1, int(steps))
    t = _clamp(step_idx / float(step_count), 0.0, 1.0)
    fill_rgba = _lerp_rgba(mood_spec.disabled_fill_rgba, mood_spec.pill_fill_rgba, t)
    edge_rgba = _lerp_rgba(mood_spec.disabled_edge_rgba, mood_spec.pill_edge_rgba, t)
    icon_tint = _lerp_rgb(mood_spec.icon_disabled_rgb, mood_spec.icon_enabled_rgb, t)
    icon_alpha = _lerp(0.65, 1.0, t)
    return _bake_pill_photo_from_geometry(
        pill_w,
        height,
        rows_geom,
        content_left_px,
        item_positions,
        fill_rgba,
        edge_rgba,
        icon_alpha,
        master,
        icon_tint_rgb=icon_tint,
    )


def _bake_transition_pills(
    pill_w: int,
    height: int,
    content_left_px: int,
    item_positions: Sequence[tuple[str, int, int, str]],
    master: tk.Misc | None,
    steps: int,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> list[tk.PhotoImage]:
    """Pre-bake ``steps + 1`` frosted pill images from disabled (0) to enabled (1)."""
    mood_spec = get_mood(mood)
    step_count = max(1, int(steps))
    rows_geom = _compute_pill_geometry(pill_w, height)
    return [
        _bake_transition_pill_step(
            pill_w,
            height,
            rows_geom,
            content_left_px,
            item_positions,
            master,
            idx,
            step_count,
            mood_spec,
        )
        for idx in range(step_count + 1)
    ]


def build_hud_transition_pills(
    font: tkfont.Font,
    *,
    height: int = HUD_HEIGHT,
    max_width: int | None = None,
    master: tk.Misc | None = None,
    steps: int = HUD_TRANSITION_STEPS,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> tuple[list[tk.PhotoImage], list[tuple[float, str]], bool]:
    """Pre-bake ``steps + 1`` mood-aware bottom HUD pills and return (pills, segments, compact)."""
    layout = resolve_bottom_hud_layout(False, font, max_width=max_width, height=height)
    pills = _bake_transition_pills(
        layout.pill_width,
        height,
        layout.content_left_px,
        layout.item_positions,
        master,
        steps,
        mood=mood,
    )
    return (pills, list(layout.segments), layout.compact)


# -- Top-Right Compact Switcher Pill -----------------------------------------

SWITCHER_SEGMENT_KEYS = ("cultivar", "mood", "breeze", "detail")


@dataclass(frozen=True, slots=True)
class SwitcherState:
    """Display state for the 4-segment top-right compact switcher pill."""

    cultivar_label: str = "Scarlet"
    cultivar_short: str = "Scarlet"
    mood_label: str = "Daylight"
    mood_short: str = "Day"
    breeze_enabled: bool = False
    detail_lush: bool = False
    mood_is_dark: bool | None = None


@dataclass(frozen=True, slots=True)
class SwitcherLayout:
    """Measured layout and relative icon/text/hit geometry for the switcher pill."""

    pill_width: int
    pill_height: int
    compact_tier: int
    segments: tuple[tuple[str, float, str], ...]
    separators: tuple[tuple[float, str], ...]
    local_hit_spans: tuple[tuple[str, str, float, float], ...]
    item_positions: tuple[tuple[str, int, int, str], ...] = ()
    icon_spans: tuple[tuple[str, str, float, float], ...] = ()
    content_left_px: int = 0

    @property
    def icon_signature(self) -> tuple[tuple[str, int], ...]:
        """Hashable signature of icon names and pill-relative x coordinates."""
        return tuple(
            (icon_name, rel_icon_x)
            for icon_name, rel_icon_x, _rt, _lbl in self.item_positions
        )


def _is_dark_mood_state(state: SwitcherState) -> bool:
    if state.mood_is_dark is not None:
        return bool(state.mood_is_dark)
    return (
        state.mood_label.strip().lower() in ("twilight", "night")
        or state.mood_short.strip().lower() in ("night", "twilight")
    )


def _switcher_icon_names(state: SwitcherState) -> tuple[str, str, str, str]:
    mood_icon = "dark_mode" if _is_dark_mood_state(state) else "light_mode"
    return ("palette", mood_icon, "air", "auto_awesome")


def _truncate_label_to_px(label: str, font: tkfont.Font, max_px: int) -> str:
    if int(font.measure(label)) <= max_px:
        return label
    ellipsis = "…"
    for cut in range(len(label) - 1, 0, -1):
        candidate = label[:cut] + ellipsis
        if int(font.measure(candidate)) <= max_px:
            return candidate
    return label[:1]


def _measure_switcher_tier(
    items: Sequence[tuple[str, str]],
    font: tkfont.Font,
    pad_x: int,
    icon_gap: int,
    sep_gap: int,
    height: int,
    compact_tier: int,
) -> SwitcherLayout:
    sep_text = "·"
    sep_w = int(font.measure(sep_text))
    cursor = pad_x
    seg_records: list[tuple[str, str, int, int, str, int]] = []
    sep_records: list[tuple[int, str]] = []
    item_positions: list[tuple[str, int, int, str]] = []

    for idx, (key, (icon_name, label)) in enumerate(zip(SWITCHER_SEGMENT_KEYS, items)):
        if idx > 0:
            cursor += sep_gap
            sep_records.append((cursor, sep_text))
            cursor += sep_w + sep_gap
        icon_w, _icon_h, _ = _load_rgba_icon(icon_name)
        rel_icon_x = cursor
        rel_text_x = cursor + icon_w + icon_gap
        text_w = int(font.measure(label))
        seg_right_px = rel_text_x + text_w

        item_positions.append((icon_name, rel_icon_x, rel_text_x, label))
        seg_records.append((key, icon_name, rel_icon_x, rel_text_x, label, seg_right_px))
        cursor = seg_right_px

    pill_w = cursor + pad_x
    half_pill = pill_w * 0.5
    segments_rel: list[tuple[str, float, str]] = []
    icon_spans_rel: list[tuple[str, str, float, float]] = []
    seg_bounds: list[tuple[str, str, float, float]] = []
    for key, icon_name, icon_px, text_px, label, seg_right_px in seg_records:
        icon_w, _icon_h, _ = _load_rgba_icon(icon_name)
        rel_left = icon_px - half_pill
        rel_text_left = text_px - half_pill
        rel_right = seg_right_px - half_pill
        segments_rel.append((key, rel_text_left + 1.0, label))
        icon_spans_rel.append((key, icon_name, rel_left, rel_left + icon_w))
        seg_bounds.append((key, label, rel_left, rel_right))

    separators_rel = tuple(
        ((sep_px - half_pill) + 1.0, text) for sep_px, text in sep_records
    )

    boundaries: list[float] = [-half_pill]
    for i in range(len(seg_bounds) - 1):
        boundaries.append((seg_bounds[i][3] + seg_bounds[i + 1][2]) * 0.5)
    boundaries.append(half_pill)

    local_hit_spans = tuple(
        (key, label, boundaries[i], boundaries[i + 1])
        for i, (key, label, _l, _r) in enumerate(seg_bounds)
    )
    return SwitcherLayout(
        pill_width=pill_w,
        pill_height=height,
        compact_tier=compact_tier,
        segments=tuple(segments_rel),
        separators=separators_rel,
        local_hit_spans=local_hit_spans,
        item_positions=tuple(item_positions),
        icon_spans=tuple(icon_spans_rel),
        content_left_px=0,
    )


def resolve_switcher_layout(
    state: SwitcherState,
    font: tkfont.Font,
    *,
    max_width: int | None = None,
    height: int = SWITCHER_HUD_HEIGHT,
) -> SwitcherLayout:
    """Measure top-right switcher pill with icons + hotkeys and adaptive compact tiers."""
    icons = _switcher_icon_names(state)
    detail_word = "Lush" if state.detail_lush else "Standard"

    full_labels = (
        f"C: {state.cultivar_label}",
        f"M: {state.mood_label}",
        "W: Wind On" if state.breeze_enabled else "W: Wind",
        f"T: {detail_word}",
    )
    short_labels = (
        f"C: {state.cultivar_short}",
        f"M: {state.mood_short}",
        "W: On" if state.breeze_enabled else "W: Off",
        f"T: {detail_word}",
    )
    compact_hotkey_labels = (
        "C",
        "M",
        "W:On" if state.breeze_enabled else "W:Off",
        "T:Lush" if state.detail_lush else "T:Standard",
    )
    tiny_hotkey_labels = ("C", "M", "W", "T")

    tier_specs: tuple[tuple[int, Sequence[str], int, int, int], ...] = (
        (0, full_labels, 12, 4, 7),
        (1, full_labels, 10, 3, 5),
        (2, short_labels, 9, 3, 4),
        (3, compact_hotkey_labels, 8, 3, 3),
        (4, tiny_hotkey_labels, 7, 3, 3),
    )

    chosen_layout: SwitcherLayout | None = None
    for tier_idx, labels, pad_x, icon_gap, sep_gap in tier_specs:
        layout = _measure_switcher_tier(
            list(zip(icons, labels)),
            font,
            pad_x=pad_x,
            icon_gap=icon_gap,
            sep_gap=sep_gap,
            height=height,
            compact_tier=tier_idx,
        )
        chosen_layout = layout
        if max_width is None or layout.pill_width <= max_width:
            return layout

    assert chosen_layout is not None
    if max_width is not None and chosen_layout.pill_width > max_width:
        tight_layout = _measure_switcher_tier(
            list(zip(icons, tiny_hotkey_labels)),
            font,
            pad_x=5,
            icon_gap=2,
            sep_gap=2,
            height=height,
            compact_tier=4,
        )
        if tight_layout.pill_width <= max_width:
            return tight_layout

        labels_mut = list(tiny_hotkey_labels)
        excess = tight_layout.pill_width - max_width
        per_seg_cut = max(1, (excess + 3) // 4)
        for idx in range(len(labels_mut)):
            w_cur = int(font.measure(labels_mut[idx]))
            labels_mut[idx] = _truncate_label_to_px(
                labels_mut[idx], font, max(4, w_cur - per_seg_cut)
            )
        return _measure_switcher_tier(
            list(zip(icons, labels_mut)),
            font,
            pad_x=5,
            icon_gap=2,
            sep_gap=2,
            height=height,
            compact_tier=4,
        )
    return chosen_layout


def place_switcher_hit_rects(
    switcher_x: float,
    switcher_y: float,
    layout: SwitcherLayout,
) -> tuple[SegmentHitRect, ...]:
    """Compute exact per-segment click hit rectangles in Turtle canvas coordinates."""
    y_min = switcher_y - layout.pill_height * 0.5
    y_max = switcher_y + layout.pill_height * 0.5
    rects: list[SegmentHitRect] = []
    icon_spans = layout.icon_spans or tuple(("", "", 0.0, 0.0) for _ in layout.segments)
    for (key, label, rel_xmin, rel_xmax), (_k, rel_text_x, _lbl), (
        _ik,
        icon_name,
        rel_ix,
        _ix_end,
    ) in zip(layout.local_hit_spans, layout.segments, icon_spans):
        rects.append(
            SegmentHitRect(
                key=key,
                label=label,
                x_min=switcher_x + rel_xmin,
                x_max=switcher_x + rel_xmax,
                y_min=y_min,
                y_max=y_max,
                text_x=switcher_x + rel_text_x,
                icon_name=icon_name,
                icon_x=switcher_x + rel_ix,
            )
        )
    return tuple(rects)


def hit_test_switcher(
    cx: float, cy: float, hit_rects: Sequence[SegmentHitRect]
) -> str | None:
    """Return segment key ('cultivar'|'mood'|'breeze'|'detail') at canvas (cx, cy), or None."""
    return _hit_test_rects(cx, cy, hit_rects)


# -- Top-Right Species Switcher Pill (directly below Switcher Pill) ----------

SPECIES_SEGMENT_KEYS: tuple[str, ...] = tuple(spec.key for spec in SPECIES)


@dataclass(frozen=True, slots=True)
class SpeciesPillLayout:
    """Measured layout and click/highlight geometry for the Species switcher pill."""

    pill_width: int
    pill_height: int
    compact_tier: int
    active_key: str
    segments: tuple[tuple[str, float, str, bool], ...]  # (species_key, rel_x, label, is_active)
    separators: tuple[tuple[float, str], ...]
    local_hit_spans: tuple[tuple[str, str, float, float], ...]
    icon_pos: tuple[str, int, int]  # (icon_name, rel_icon_x, rel_icon_y)
    highlight_box: tuple[int, int, int, int] | None  # (x0, y0, x1, y1) in pill px


def _measure_species_tier(
    active_key: str,
    entries: Sequence[tuple[str, str]],
    font: tkfont.Font,
    active_font: tkfont.Font,
    pad_x: int,
    icon_gap: int,
    sep_gap: int,
    height: int,
    compact_tier: int,
) -> SpeciesPillLayout:
    sep_text = "·"
    sep_w = int(font.measure(sep_text))
    icon_name = "local_florist"
    icon_w, icon_h, _ = _load_rgba_icon(icon_name)
    rel_icon_x = pad_x
    rel_icon_y = (height - icon_h) // 2

    cursor = pad_x + icon_w + icon_gap
    seg_records: list[tuple[str, int, int, str, bool]] = []
    sep_records: list[tuple[int, str]] = []

    for idx, (s_key, label) in enumerate(entries):
        if idx > 0:
            cursor += sep_gap
            sep_records.append((cursor, sep_text))
            cursor += sep_w + sep_gap
        is_active = s_key == active_key
        meas_font = active_font if is_active else font
        text_w = int(meas_font.measure(label))
        seg_records.append((s_key, cursor, cursor + text_w, label, is_active))
        cursor += text_w

    pill_w = cursor + pad_x
    half_pill = pill_w * 0.5
    segments_rel = tuple(
        (s_key, (left_px - half_pill) + 1.0, label, is_active)
        for s_key, left_px, _right_px, label, is_active in seg_records
    )
    separators_rel = tuple(
        ((sep_px - half_pill) + 1.0, text) for sep_px, text in sep_records
    )

    boundaries: list[float] = [-half_pill]
    for i in range(len(seg_records) - 1):
        boundaries.append((seg_records[i][2] + seg_records[i + 1][1]) * 0.5 - half_pill)
    boundaries.append(half_pill)

    local_hit_spans = tuple(
        (s_key, label, boundaries[i], boundaries[i + 1])
        for i, (s_key, _l, _r, label, _act) in enumerate(seg_records)
    )

    highlight_box: tuple[int, int, int, int] | None = None
    hl_pad_x = min(4, max(2, sep_gap - 2)) if len(seg_records) > 1 else 5
    for idx, (_s_key, left_px, right_px, _label, is_active) in enumerate(seg_records):
        if is_active:
            min_left = (rel_icon_x + icon_w + 1) if idx == 0 else 4
            hl_x0 = max(min_left, left_px - hl_pad_x)
            hl_x1 = min(pill_w - 4, right_px + hl_pad_x)
            highlight_box = (hl_x0, 3, hl_x1, height - 3)
            break

    return SpeciesPillLayout(
        pill_width=pill_w,
        pill_height=height,
        compact_tier=compact_tier,
        active_key=active_key,
        segments=segments_rel,
        separators=separators_rel,
        local_hit_spans=local_hit_spans,
        icon_pos=(icon_name, rel_icon_x, rel_icon_y),
        highlight_box=highlight_box,
    )


def resolve_species_pill_layout(
    active_species: SpeciesSpec | str,
    font: tkfont.Font,
    active_font: tkfont.Font | None = None,
    *,
    max_width: int | None = None,
    height: int = SPECIES_HUD_HEIGHT,
) -> SpeciesPillLayout:
    """Measure the Species switcher pill with adaptive compact tiers."""
    active_spec = get_species(active_species)
    act_font = active_font if active_font is not None else font

    full_entries = tuple((s.key, f"{s.hotkey}: {s.name}") for s in SPECIES)
    short_entries = tuple((s.key, f"{s.hotkey}: {s.short_name}") for s in SPECIES)
    single_entry = ((active_spec.key, f"F: {active_spec.name}"),)

    tier_specs: tuple[tuple[int, Sequence[tuple[str, str]], int, int, int], ...] = (
        (0, full_entries, 12, 4, 7),
        (1, full_entries, 9, 3, 5),
        (2, short_entries, 8, 3, 4),
        (3, single_entry, 10, 4, 0),
    )
    chosen: SpeciesPillLayout | None = None
    for tier_idx, entries, pad_x, icon_gap, sep_gap in tier_specs:
        layout = _measure_species_tier(
            active_spec.key,
            entries,
            font,
            act_font,
            pad_x=pad_x,
            icon_gap=icon_gap,
            sep_gap=sep_gap,
            height=height,
            compact_tier=tier_idx,
        )
        chosen = layout
        if max_width is None or layout.pill_width <= max_width:
            return layout

    assert chosen is not None
    return chosen


def _composite_highlight_capsule(
    rows: list[bytearray],
    width: int,
    height: int,
    box: tuple[int, int, int, int],
    fill_rgba: tuple[int, int, int, int],
    edge_rgba: tuple[int, int, int, int],
) -> None:
    """Blend a soft anti-aliased inner highlight capsule onto pill RGBA rows."""
    x0, y0, x1, y1 = box
    box_h = y1 - y0
    if box_h <= 2 or x1 - x0 <= 2:
        return
    cy = (y0 + y1) * 0.5
    radius = max(2.0, box_h * 0.5 - 0.5)
    cap_x0 = float(x0) + radius
    cap_x1 = float(x1) - radius
    if cap_x1 < cap_x0:
        cap_x0 = cap_x1 = (x0 + x1) * 0.5

    for iy in range(max(0, y0 - 1), min(height, y1 + 1)):
        row = rows[iy]
        py = iy + 0.5
        for ix in range(max(0, x0 - 1), min(width, x1 + 1)):
            px = ix + 0.5
            dist = _horizontal_capsule_sdf(px, py, cap_x0, cap_x1, cy, radius)
            if dist >= 0.75:
                continue
            cov = _clamp(0.75 - dist, 0.0, 1.0)
            border_t = _clamp((dist + 1.1) / 1.1, 0.0, 1.0)
            src_rgba = _lerp_rgba(fill_rgba, edge_rgba, border_t)
            off = ix * 4
            da = row[off + 3] / 255.0
            nr, ng, nb, na = _blend_rgba_over(
                float(row[off]),
                float(row[off + 1]),
                float(row[off + 2]),
                da,
                src_rgba,
                cov,
            )
            row[off] = int(_clamp(nr, 0.0, 255.0) + 0.5)
            row[off + 1] = int(_clamp(ng, 0.0, 255.0) + 0.5)
            row[off + 2] = int(_clamp(nb, 0.0, 255.0) + 0.5)
            row[off + 3] = int(_clamp(na * 255.0, 0.0, 255.0) + 0.5)


def _bake_species_transition_pills(
    layout: SpeciesPillLayout,
    accent_rgba: tuple[int, int, int, int],
    accent_disabled_rgba: tuple[int, int, int, int],
    master: tk.Misc | None,
    steps: int,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> list[tk.PhotoImage]:
    """Pre-bake ``steps + 1`` Species pill frames with active segment highlight."""
    mood_spec = get_mood(mood)
    step_count = max(1, int(steps))
    rows_geom = _compute_pill_geometry(layout.pill_width, layout.pill_height)
    icon_name, rel_icon_x, rel_icon_y = layout.icon_pos

    # Gently lift dark accent colors when rendering over dark Twilight capsule
    if mood_spec.is_dark:
        hl_rgb = _lerp_rgb(accent_rgba[:3], (242, 238, 232), 0.28)
        hl_dis_rgb = _lerp_rgb(accent_disabled_rgba[:3], (200, 206, 220), 0.20)
    else:
        hl_rgb = accent_rgba[:3]
        hl_dis_rgb = accent_disabled_rgba[:3]

    hl_fill_en = (hl_rgb[0], hl_rgb[1], hl_rgb[2], 42)
    hl_edge_en = (hl_rgb[0], hl_rgb[1], hl_rgb[2], 102)
    hl_fill_dis = (hl_dis_rgb[0], hl_dis_rgb[1], hl_dis_rgb[2], 18)
    hl_edge_dis = (hl_dis_rgb[0], hl_dis_rgb[1], hl_dis_rgb[2], 46)

    pills: list[tk.PhotoImage] = []
    for idx in range(step_count + 1):
        t = idx / float(step_count)
        fill_rgba = _lerp_rgba(mood_spec.disabled_fill_rgba, mood_spec.pill_fill_rgba, t)
        edge_rgba = _lerp_rgba(mood_spec.disabled_edge_rgba, mood_spec.pill_edge_rgba, t)
        icon_tint = _lerp_rgb(mood_spec.icon_disabled_rgb, mood_spec.icon_enabled_rgb, t)
        icon_alpha = _lerp(0.65, 1.0, t)

        rows = _fill_pill_rows_from_geometry(
            layout.pill_width, rows_geom, fill_rgba, edge_rgba
        )
        if layout.highlight_box is not None:
            _composite_highlight_capsule(
                rows,
                layout.pill_width,
                layout.pill_height,
                layout.highlight_box,
                _lerp_rgba(hl_fill_dis, hl_fill_en, t),
                _lerp_rgba(hl_edge_dis, hl_edge_en, t),
            )
        _composite_icon_over_rows(
            rows,
            layout.pill_width,
            layout.pill_height,
            icon_name,
            dest_x=rel_icon_x,
            dest_y=rel_icon_y,
            alpha_scale=icon_alpha,
            tint_rgb=icon_tint,
        )
        png_bytes = _encode_rgba_rows_png(layout.pill_width, layout.pill_height, rows)
        photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
        if master is not None:
            photo_kwargs["master"] = master
        pills.append(tk.PhotoImage(**photo_kwargs))
    return pills


def place_species_hit_rects(
    species_x: float,
    species_y: float,
    layout: SpeciesPillLayout,
) -> tuple[SegmentHitRect, ...]:
    """Compute clickable species segment hit rectangles in Turtle canvas coordinates."""
    y_min = species_y - layout.pill_height * 0.5
    y_max = species_y + layout.pill_height * 0.5
    rects: list[SegmentHitRect] = []
    for (s_key, label, rel_xmin, rel_xmax), (_sk, rel_text_x, _lbl, _act) in zip(
        layout.local_hit_spans, layout.segments
    ):
        rects.append(
            SegmentHitRect(
                key=s_key,
                label=label,
                x_min=species_x + rel_xmin,
                x_max=species_x + rel_xmax,
                y_min=y_min,
                y_max=y_max,
                text_x=species_x + rel_text_x,
            )
        )
    return tuple(rects)


def hit_test_species_pill(
    cx: float, cy: float, hit_rects: Sequence[SegmentHitRect]
) -> str | None:
    """Return species key ('rose'|'tulip'|'lotus'|'sunflower'|'sakura') at (cx, cy), or None."""
    return _hit_test_rects(cx, cy, hit_rects)


# -- Dual Slider Pills (Speed + Bloom Scrubber) ------------------------------

@dataclass(frozen=True, slots=True)
class SliderPillLayout:
    """Pixel geometry and relative offsets for a slider HUD pill."""

    pill_width: int
    pill_height: int
    label_x_offset: float
    track_x_offset: float
    track_width: int
    track_height: int
    track_pad: float
    value_x_offset: float
    value_align: str


SpeedSliderLayout = SliderPillLayout


def build_slider_transition_pills(
    icon_name: str,
    label_text: str,
    sample_values: Sequence[str],
    label_font: tkfont.Font,
    value_font: tkfont.Font,
    *,
    value_align: str = "left",
    height: int = SLIDER_HUD_HEIGHT,
    track_width: int = SLIDER_TRACK_WIDTH,
    track_height: int = SLIDER_TRACK_HEIGHT,
    track_pad: float = SLIDER_TRACK_PAD,
    master: tk.Misc | None = None,
    steps: int = HUD_TRANSITION_STEPS,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> tuple[list[tk.PhotoImage], SliderPillLayout]:
    """Pre-bake mood-aware frosted slider pill frames for Speed or Bloom sliders."""
    icon_w, _icon_h, _ = _load_rgba_icon(icon_name)
    pad_x = 12
    icon_gap = 5
    track_gap = 9
    value_gap = 8
    label_w = int(label_font.measure(label_text))
    value_w = max(int(value_font.measure(sample)) for sample in sample_values)

    label_rel_x = pad_x + icon_w + icon_gap
    track_rel_x = label_rel_x + label_w + track_gap
    value_rel_x = track_rel_x + track_width + value_gap
    pill_w = value_rel_x + value_w + pad_x
    half_pill = pill_w * 0.5
    value_anchor_rel = (value_rel_x + value_w) if value_align == "right" else value_rel_x

    layout = SliderPillLayout(
        pill_width=pill_w,
        pill_height=height,
        label_x_offset=(label_rel_x - half_pill) + 1.0,
        track_x_offset=(track_rel_x + track_width * 0.5) - half_pill,
        track_width=track_width,
        track_height=track_height,
        track_pad=track_pad,
        value_x_offset=(value_anchor_rel - half_pill) + 1.0,
        value_align=value_align,
    )
    item_positions = ((icon_name, pad_x, label_rel_x, label_text),)
    pills = _bake_transition_pills(
        pill_w, height, 0, item_positions, master, steps, mood=mood
    )
    return (pills, layout)


def _blend_rgba_over(
    dst_r: float,
    dst_g: float,
    dst_b: float,
    dst_a: float,
    src_rgba: tuple[int, int, int, int],
    coverage: float,
) -> tuple[float, float, float, float]:
    sa = (src_rgba[3] / 255.0) * coverage
    if sa <= 1e-6:
        return (dst_r, dst_g, dst_b, dst_a)
    inv_sa = 1.0 - sa
    out_a = sa + dst_a * inv_sa
    if out_a <= 1e-6:
        return (0.0, 0.0, 0.0, 0.0)
    return (
        (src_rgba[0] * sa + dst_r * dst_a * inv_sa) / out_a,
        (src_rgba[1] * sa + dst_g * dst_a * inv_sa) / out_a,
        (src_rgba[2] * sa + dst_b * dst_a * inv_sa) / out_a,
        out_a,
    )


def _horizontal_capsule_sdf(
    px: float, py: float, x0: float, x1: float, cy: float, radius: float
) -> float:
    clamped_x = x0 if px < x0 else (x1 if px > x1 else px)
    dx = px - clamped_x
    dy = py - cy
    return math.sqrt(dx * dx + dy * dy) - radius


def build_slider_track_photo(
    fraction: float,
    blend: float,
    accent_rgba: tuple[int, int, int, int] = SPEED_TRACK_ACTIVE_ENABLED_RGBA,
    accent_disabled_rgba: tuple[int, int, int, int] = SPEED_TRACK_ACTIVE_DISABLED_RGBA,
    mood: MoodSpec | str = DEFAULT_MOOD,
    *,
    width: int = SLIDER_TRACK_WIDTH,
    height: int = SLIDER_TRACK_HEIGHT,
    pad: float = SLIDER_TRACK_PAD,
    master: tk.Misc | None = None,
) -> tk.PhotoImage:
    """Render an anti-aliased RGBA slider track + circular thumb for Speed/Bloom sliders."""
    mood_spec = get_mood(mood)
    t = _smootherstep(_clamp(blend, 0.0, 1.0))
    frac = _clamp(fraction, 0.0, 1.0)
    track_x0 = pad
    track_x1 = float(width) - pad
    thumb_x = _lerp(track_x0, track_x1, frac)
    cy = height * 0.5
    track_r = 2.0
    thumb_r = 5.5
    core_r = 2.3

    groove_rgba = _lerp_rgba(
        mood_spec.track_groove_disabled_rgba, mood_spec.track_groove_enabled_rgba, t
    )
    active_rgba = _lerp_rgba(accent_disabled_rgba, accent_rgba, t)
    core_rgba = _lerp_rgba(
        mood_spec.thumb_core_disabled_rgba, mood_spec.thumb_core_enabled_rgba, t
    )
    sr, sg, sb = mood_spec.thumb_shadow_rgb
    sa_min, sa_max = mood_spec.thumb_shadow_alphas
    shadow_rgba = (sr, sg, sb, int(_lerp(sa_min, sa_max, t) + 0.5))

    rows: list[bytearray] = []
    row_stride = width * 4
    for iy in range(height):
        row = bytearray(row_stride)
        py = iy + 0.5
        for ix in range(width):
            px = ix + 0.5
            r = g = b = a = 0.0

            groove_dist = _horizontal_capsule_sdf(px, py, track_x0, track_x1, cy, track_r)
            if groove_dist < 0.75:
                cov = _clamp(0.75 - groove_dist, 0.0, 1.0)
                r, g, b, a = _blend_rgba_over(r, g, b, a, groove_rgba, cov)

            if thumb_x > track_x0 + 0.25:
                active_dist = _horizontal_capsule_sdf(px, py, track_x0, thumb_x, cy, track_r)
                if active_dist < 0.75:
                    cov = _clamp(0.75 - active_dist, 0.0, 1.0)
                    r, g, b, a = _blend_rgba_over(r, g, b, a, active_rgba, cov)

            sdx = px - thumb_x
            sdy = py - (cy + 0.85)
            s_dist = math.sqrt(sdx * sdx + sdy * sdy)
            if s_dist < 6.8:
                shadow_cov = _smoothstep(6.8, 4.0, s_dist)
                r, g, b, a = _blend_rgba_over(r, g, b, a, shadow_rgba, shadow_cov)

            tdx = px - thumb_x
            tdy = py - cy
            t_dist = math.sqrt(tdx * tdx + tdy * tdy)
            if t_dist < thumb_r + 0.75:
                thumb_cov = _clamp(0.75 - (t_dist - thumb_r), 0.0, 1.0)
                core_t = _clamp(0.75 - (t_dist - core_r), 0.0, 1.0)
                thumb_rgba = _lerp_rgba(active_rgba, core_rgba, core_t)
                r, g, b, a = _blend_rgba_over(r, g, b, a, thumb_rgba, thumb_cov)

            if a > 1e-4:
                off = ix * 4
                row[off] = int(_clamp(r, 0.0, 255.0) + 0.5)
                row[off + 1] = int(_clamp(g, 0.0, 255.0) + 0.5)
                row[off + 2] = int(_clamp(b, 0.0, 255.0) + 0.5)
                row[off + 3] = int(_clamp(a * 255.0, 0.0, 255.0) + 0.5)
        rows.append(row)

    png_bytes = _encode_rgba_rows_png(width, height, rows)
    photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
    if master is not None:
        photo_kwargs["master"] = master
    return tk.PhotoImage(**photo_kwargs)


FPS_TIERS: tuple[str, ...] = ("init", "low", "mid", "good")
FPS_LOW_THRESHOLD = 30.0
FPS_GOOD_THRESHOLD = 56.0


@dataclass(frozen=True, slots=True)
class FpsBadgeStyle:
    """Mood-tuned color palette for one FPS badge performance tier."""

    tier: str
    ink_rgb: tuple[int, int, int]
    icon_tint_rgb: tuple[int, int, int]
    pill_fill_rgba: tuple[int, int, int, int]
    pill_edge_rgba: tuple[int, int, int, int]

    @property
    def ink_hex(self) -> str:
        r, g, b = self.ink_rgb
        return f"#{r:02x}{g:02x}{b:02x}"


_FPS_LIGHT_PALETTE: dict[
    str,
    tuple[
        tuple[int, int, int],
        tuple[int, int, int],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
    ],
] = {
    "low": (
        (192, 26, 40),
        (202, 32, 46),
        (254, 230, 232, 208),
        (224, 126, 134, 228),
    ),
    "mid": (
        (152, 82, 4),
        (164, 90, 6),
        (254, 237, 206, 208),
        (216, 162, 86, 228),
    ),
    "good": (
        (16, 118, 54),
        (18, 124, 58),
        (224, 246, 231, 208),
        (114, 188, 140, 228),
    ),
}

_FPS_DARK_PALETTE: dict[
    str,
    tuple[
        tuple[int, int, int],
        tuple[int, int, int],
        tuple[int, int, int, int],
        tuple[int, int, int, int],
    ],
] = {
    "low": (
        (255, 112, 120),
        (255, 102, 112),
        (58, 30, 40, 216),
        (182, 86, 98, 228),
    ),
    "mid": (
        (250, 186, 70),
        (248, 178, 58),
        (54, 44, 30, 216),
        (174, 136, 68, 228),
    ),
    "good": (
        (96, 224, 144),
        (86, 216, 136),
        (26, 52, 44, 216),
        (76, 158, 114, 228),
    ),
}


def fps_tier_for_value(fps: float | None) -> str:
    """Classify an FPS reading into 'init', 'low' (<30), 'mid' (30..55.9), or 'good' (>=56)."""
    if fps is None or not math.isfinite(fps):
        return "init"
    if fps < FPS_LOW_THRESHOLD:
        return "low"
    if fps < FPS_GOOD_THRESHOLD:
        return "mid"
    return "good"


def get_fps_badge_style(mood: MoodSpec | str, fps_tier: str) -> FpsBadgeStyle:
    """Return mood-adapted FPS badge colors for ``fps_tier``."""
    mood_spec = get_mood(mood)
    tier = fps_tier.strip().lower()
    if tier not in FPS_TIERS:
        raise ValueError(f"Unknown FPS tier: {fps_tier!r}")
    if tier == "init":
        return FpsBadgeStyle(
            tier="init",
            ink_rgb=mood_spec.ink_enabled_rgb,
            icon_tint_rgb=mood_spec.icon_enabled_rgb,
            pill_fill_rgba=mood_spec.pill_fill_rgba,
            pill_edge_rgba=mood_spec.pill_edge_rgba,
        )
    palette = _FPS_DARK_PALETTE if mood_spec.is_dark else _FPS_LIGHT_PALETTE
    ink_rgb, icon_tint_rgb, fill_rgba, edge_rgba = palette[tier]
    return FpsBadgeStyle(
        tier=tier,
        ink_rgb=ink_rgb,
        icon_tint_rgb=icon_tint_rgb,
        pill_fill_rgba=fill_rgba,
        pill_edge_rgba=edge_rgba,
    )


def fps_badge_ink_hex(mood: MoodSpec | str, fps_tier: str) -> str:
    """Return hex ink color for FPS badge text in the given mood and tier."""
    return get_fps_badge_style(mood, fps_tier).ink_hex


def build_fps_badge_photo(
    sample_text: str = "99 FPS",
    font: tkfont.Font | None = None,
    *,
    height: int = FPS_BADGE_HEIGHT,
    master: tk.Misc | None = None,
    mood: MoodSpec | str = DEFAULT_MOOD,
    fps_tier: str = "init",
) -> tuple[tk.PhotoImage, float]:
    """Build a mood- and FPS-tier-aware frosted FPS badge ``PhotoImage``."""
    mood_spec = get_mood(mood)
    style = get_fps_badge_style(mood_spec, fps_tier)
    if font is None:
        family, size, weight = get_hud_font(size=9, weight="medium")
        font = tkfont.Font(root=master or tk._default_root, family=family, size=size, weight=weight)

    icon_w, icon_h, _ = _load_rgba_icon("speed")
    pad_x = 11
    icon_gap = 5
    text_w = int(font.measure(sample_text))
    badge_w = pad_x + icon_w + icon_gap + text_w + pad_x

    rows = build_pill_rows(
        badge_w,
        height,
        mood=mood_spec,
        enabled=True,
        fill_rgba=style.pill_fill_rgba,
        edge_rgba=style.pill_edge_rgba,
    )
    _composite_icon_over_rows(
        rows,
        badge_w,
        height,
        "speed",
        dest_x=pad_x,
        dest_y=(height - icon_h) // 2,
        tint_rgb=style.icon_tint_rgb,
    )
    png_bytes = _encode_rgba_rows_png(badge_w, height, rows)
    photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
    if master is not None:
        photo_kwargs["master"] = master
    badge_photo = tk.PhotoImage(**photo_kwargs)

    canvas_text_x = (pad_x + icon_w + icon_gap) - badge_w * 0.5
    return (badge_photo, canvas_text_x + 1.0)


def format_faces_text(face_count: int) -> str:
    """Format polygon face count for the top-left mesh Faces badge."""
    count = max(0, int(face_count))
    noun = "Face" if count == 1 else "Faces"
    return f"{count:,} {noun}"


def build_faces_badge_photo(
    face_count: int,
    font: tkfont.Font | None = None,
    *,
    height: int = FACES_BADGE_HEIGHT,
    master: tk.Misc | None = None,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> tuple[tk.PhotoImage, float, int]:
    """Build a mood-aware frosted mesh face-count badge ``PhotoImage``."""
    mood_spec = get_mood(mood)
    if font is None:
        family, size, weight = get_hud_font(size=9, weight="medium")
        font = tkfont.Font(root=master or tk._default_root, family=family, size=size, weight=weight)

    text = format_faces_text(face_count)
    icon_w, icon_h, _ = _load_rgba_icon("auto_awesome")
    pad_x = 11
    icon_gap = 5
    text_w = int(font.measure(text))
    badge_w = pad_x + icon_w + icon_gap + text_w + pad_x

    rows = build_pill_rows(
        badge_w,
        height,
        mood=mood_spec,
        enabled=True,
        fill_rgba=mood_spec.pill_fill_rgba,
        edge_rgba=mood_spec.pill_edge_rgba,
    )
    _composite_icon_over_rows(
        rows,
        badge_w,
        height,
        "auto_awesome",
        dest_x=pad_x,
        dest_y=(height - icon_h) // 2,
        tint_rgb=mood_spec.icon_enabled_rgb,
    )
    png_bytes = _encode_rgba_rows_png(badge_w, height, rows)
    photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
    if master is not None:
        photo_kwargs["master"] = master
    badge_photo = tk.PhotoImage(**photo_kwargs)

    canvas_text_x = (pad_x + icon_w + icon_gap) - badge_w * 0.5
    return (badge_photo, canvas_text_x + 1.0, badge_w)


def hud_ink_hex(blend: float, mood: MoodSpec | str = DEFAULT_MOOD) -> str:
    """Return the interpolated HUD ink hex color between disabled (0) and enabled (1)."""
    mood_spec = get_mood(mood)
    t = _clamp(blend, 0.0, 1.0)
    r, g, b = _lerp_rgb(mood_spec.ink_disabled_rgb, mood_spec.ink_enabled_rgb, t)
    return f"#{r:02x}{g:02x}{b:02x}"


# -- Top-Left BGM Audio Engine & Pill Layout ---------------------------------

@dataclass(frozen=True, slots=True)
class BgmTrack:
    """Validated local background audio asset metadata."""

    path: Path
    title: str
    duration_sec: float = 0.0


def _probe_m4a_duration(path: Path) -> float:
    """Read track duration in seconds from an MP4/M4A ``mvhd`` atom."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            head = fh.read(min(size, 131072))
            chunks = [head]
            if size > 131072:
                fh.seek(max(0, size - 131072))
                chunks.append(fh.read(131072))
        for buf in chunks:
            idx = buf.find(b"mvhd")
            if idx >= 4 and idx + 28 <= len(buf):
                version = buf[idx + 4]
                if version == 0:
                    timescale, duration = struct.unpack(">II", buf[idx + 16 : idx + 24])
                    if timescale > 0:
                        return float(duration) / float(timescale)
                elif version == 1 and idx + 36 <= len(buf):
                    timescale, duration = struct.unpack(">IQ", buf[idx + 24 : idx + 36])
                    if timescale > 0:
                        return float(duration) / float(timescale)
    except OSError:
        pass
    return 0.0


def _find_mp4_edts_tag_offsets(path: Path) -> list[int]:
    """Locate ``edts`` FourCC offsets inside ``moov/trak`` boxes of an MP4/M4A file."""
    offsets: list[int] = []
    try:
        file_size = path.stat().st_size
        with path.open("rb") as fh:
            pos = 0
            while pos + 8 <= file_size:
                fh.seek(pos)
                hdr = fh.read(8)
                if len(hdr) < 8:
                    break
                sz, tag = struct.unpack(">I4s", hdr)
                hdr_len = 8
                if sz == 1:
                    ext = fh.read(8)
                    if len(ext) < 8:
                        break
                    sz = struct.unpack(">Q", ext)[0]
                    hdr_len = 16
                elif sz == 0:
                    sz = file_size - pos
                if sz < hdr_len or pos + sz > file_size:
                    break
                if tag == b"moov":
                    moov_data = fh.read(sz - hdr_len)
                    moov_base = pos + hdr_len
                    m_pos = 0
                    while m_pos + 8 <= len(moov_data):
                        t_sz, t_tag = struct.unpack(">I4s", moov_data[m_pos : m_pos + 8])
                        if t_sz < 8 or m_pos + t_sz > len(moov_data):
                            break
                        if t_tag == b"trak":
                            c_pos = m_pos + 8
                            c_end = m_pos + t_sz
                            while c_pos + 8 <= c_end:
                                c_sz, c_tag = struct.unpack(">I4s", moov_data[c_pos : c_pos + 8])
                                if c_sz < 8 or c_pos + c_sz > c_end:
                                    break
                                if c_tag == b"edts":
                                    offsets.append(moov_base + c_pos + 4)
                                c_pos += c_sz
                        m_pos += t_sz
                    break
                pos += sz
    except OSError:
        return []
    return offsets


def _probe_wav_duration(path: Path) -> float:
    """Read track duration in seconds from a RIFF/WAVE header."""
    try:
        with path.open("rb") as fh:
            hdr = fh.read(65536)
        if len(hdr) < 44 or hdr[:4] != b"RIFF" or hdr[8:12] != b"WAVE":
            return 0.0
        pos = 12
        byte_rate = 0
        data_bytes = 0
        while pos + 8 <= len(hdr):
            chunk_id = hdr[pos : pos + 4]
            chunk_size = struct.unpack("<I", hdr[pos + 4 : pos + 8])[0]
            pos += 8
            if chunk_id == b"fmt " and pos + 16 <= len(hdr):
                byte_rate = struct.unpack("<I", hdr[pos + 8 : pos + 12])[0]
            elif chunk_id == b"data":
                data_bytes = chunk_size
                break
            pos += chunk_size + (chunk_size & 1)
        if byte_rate > 0 and data_bytes > 0:
            return float(data_bytes) / float(byte_rate)
    except OSError:
        pass
    return 0.0


def _probe_audio_duration(path: Path) -> float:
    """Return best-effort duration in seconds for a local audio track."""
    suffix = path.suffix.lower()
    if suffix in (".m4a", ".mp4", ".aac"):
        return _probe_m4a_duration(path)
    if suffix == ".wav":
        return _probe_wav_duration(path)
    return 0.0


def discover_bgm_tracks() -> tuple[BgmTrack, ...]:
    """Scan ``assets/audios`` for validated ``.m4a`` tracks sorted by filename."""
    try:
        if not _AUDIOS_DIR.exists() or _AUDIOS_DIR.is_symlink() or not _AUDIOS_DIR.is_dir():
            return ()
        entries = sorted(_AUDIOS_DIR.iterdir(), key=lambda p: p.name.casefold())
    except OSError:
        return ()

    tracks: list[BgmTrack] = []
    for entry in entries:
        if entry.name.startswith(".") or entry.suffix.lower() not in _AUDIO_EXTENSIONS:
            continue
        validated = _validate_asset_path(entry, _MAX_AUDIO_BYTES)
        if validated is None or validated.stat().st_size <= 0:
            continue
        tracks.append(
            BgmTrack(
                path=validated,
                title=entry.stem,
                duration_sec=_probe_audio_duration(validated),
            )
        )
    return tuple(tracks)


def _format_mmss(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins}:{secs:02d}"


def format_bgm_time(
    elapsed_sec: float, duration_sec: float, *, compact: bool = False
) -> str:
    """Format playback elapsed time and total track length (``m:ss / m:ss``)."""
    cur = _format_mmss(elapsed_sec)
    if compact or duration_sec <= 0.5:
        return cur
    return f"{cur} / {_format_mmss(duration_sec)}"


def _bgm_time_template(duration_sec: float, *, compact: bool = False) -> str:
    """Return wide-digit placeholder string for non-jittering time box sizing."""
    total_str = _format_mmss(max(0.0, duration_sec))
    wide_digits = "".join("8" if ch.isdigit() else ch for ch in total_str)
    if compact or duration_sec <= 0.5:
        return wide_digits
    return f"{wide_digits} / {wide_digits}"


_BGM_EFF_SR = BGM_SAMPLE_RATE / 4.0
_BGM_BAND_TAPS: tuple[tuple[float, ...], ...] = (
    tuple(2.0 * math.cos(2.0 * math.pi * f / _BGM_EFF_SR) for f in (98.0, 146.8)),
    tuple(2.0 * math.cos(2.0 * math.pi * f / _BGM_EFF_SR) for f in (220.0, 329.6)),
    tuple(2.0 * math.cos(2.0 * math.pi * f / _BGM_EFF_SR) for f in (523.3, 784.0)),
    tuple(2.0 * math.cos(2.0 * math.pi * f / _BGM_EFF_SR) for f in (1174.7, 1760.0)),
)
_BGM_BAND_GAINS: tuple[float, float, float, float] = (14.0, 12.0, 20.0, 28.0)


def _compute_pcm_4bands(pcm_bytes: bytes) -> tuple[float, float, float, float]:
    """Compute 4 normalized musical frequency-band levels from 44.1 kHz stereo PCM."""
    if len(pcm_bytes) < 128:
        return (0.0, 0.0, 0.0, 0.0)

    samples_arr = array.array("h")
    usable = len(pcm_bytes) - (len(pcm_bytes) & 3)
    samples_arr.frombytes(pcm_bytes[:usable])
    if sys.byteorder != "little":
        samples_arr.byteswap()

    limit = min(len(samples_arr), 2048)
    mono = [
        (samples_arr[i] + samples_arr[i + 1]) * (1.0 / 65536.0)
        for i in range(0, limit - 1, 8)
    ]
    n = len(mono)
    if n < 16:
        return (0.0, 0.0, 0.0, 0.0)

    rms = math.sqrt(sum(s * s for s in mono) / float(n))
    if rms < 1e-4:
        return (0.0, 0.0, 0.0, 0.0)

    levels: list[float] = []
    inv_n = 1.0 / float(n)
    denom = math.log1p(12.0)
    for coeffs, gain in zip(_BGM_BAND_TAPS, _BGM_BAND_GAINS):
        band_peak = 0.0
        for c in coeffs:
            q1 = 0.0
            q2 = 0.0
            for s in mono:
                q0 = c * q1 - q2 + s
                q2 = q1
                q1 = q0
            power = q1 * q1 + q2 * q2 - c * q1 * q2
            mag = math.sqrt(max(0.0, power)) * inv_n
            if mag > band_peak:
                band_peak = mag
        blended = band_peak * gain + rms * 1.4
        levels.append(_clamp(math.log1p(blended * 24.0) / denom, 0.0, 1.0))
    return (levels[0], levels[1], levels[2], levels[3])


class BgmPlayer:
    """Zero-dependency streaming background audio player (Windows MF + waveOut)."""

    def __init__(self, *, auto_play: bool = True) -> None:
        self._tracks: tuple[BgmTrack, ...] = discover_bgm_tracks()
        self._track_idx: int = 0
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._wave_event_handle: int = 0

        has_tracks = len(self._tracks) > 0
        self._want_playing: bool = bool(auto_play and has_tracks and sys.platform == "win32")
        self._is_playing: bool = self._want_playing
        self._elapsed_sec: float = 0.0
        self._duration_sec: float = self._tracks[0].duration_sec if has_tracks else 0.0
        self._spectrum: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
        self._pending_delta: int = 0
        self._worker: threading.Thread | None = None

        if has_tracks and sys.platform == "win32":
            self._worker = threading.Thread(
                target=self._run_windows_audio_loop,
                name="FlowerBgmAudio",
                daemon=True,
            )
            self._worker.start()

    @property
    def current_track(self) -> BgmTrack | None:
        if not self._tracks:
            return None
        with self._lock:
            idx = self._track_idx
        return self._tracks[idx]

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._is_playing

    def snapshot(self) -> tuple[bool, float, float, tuple[float, float, float, float]]:
        """Return ``(is_playing, elapsed_sec, duration_sec, 4_band_levels)``."""
        with self._lock:
            return (
                self._is_playing,
                self._elapsed_sec,
                self._duration_sec,
                self._spectrum,
            )

    def _signal_worker(self) -> None:
        self._wake_event.set()
        ev_handle = self._wave_event_handle
        if ev_handle and sys.platform == "win32":
            try:
                import ctypes

                ctypes.windll.kernel32.SetEvent(ctypes.c_void_p(ev_handle))
            except Exception:
                pass

    def toggle(self) -> bool:
        """Toggle playback between playing and paused; return new playing state."""
        if not self._tracks or sys.platform != "win32":
            return False
        with self._lock:
            self._want_playing = not self._want_playing
            self._is_playing = self._want_playing
            if not self._want_playing:
                self._spectrum = (0.0, 0.0, 0.0, 0.0)
            playing_now = self._want_playing
        self._signal_worker()
        return playing_now

    def previous(self) -> None:
        """Skip to the previous track in the playlist (wraps around)."""
        if not self._tracks or sys.platform != "win32":
            return
        with self._lock:
            self._pending_delta -= 1
        self._signal_worker()

    def next(self) -> None:
        """Skip to the next track in the playlist (wraps around)."""
        if not self._tracks or sys.platform != "win32":
            return
        with self._lock:
            self._pending_delta += 1
        self._signal_worker()

    def close(self) -> None:
        """Stop playback and release audio device and Media Foundation handles."""
        self._stop_event.set()
        with self._lock:
            self._want_playing = False
            self._is_playing = False
            self._spectrum = (0.0, 0.0, 0.0, 0.0)
        self._signal_worker()
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=0.75)
        self._worker = None

    def _run_windows_audio_loop(self) -> None:
        track = self.current_track
        if track is None:
            return

        import ctypes
        import ctypes.wintypes as wt

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_uint32),
                ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_uint8 * 8),
            ]

        def make_guid(d1: int, d2: int, d3: int, *b: int) -> GUID:
            return GUID(d1, d2, d3, (ctypes.c_uint8 * 8)(*b))

        is_64 = ctypes.sizeof(ctypes.c_void_p) == 8

        class PROPVARIANT(ctypes.Structure):
            _fields_ = (
                [
                    ("vt", ctypes.c_uint16),
                    ("wReserved1", ctypes.c_uint16),
                    ("wReserved2", ctypes.c_uint16),
                    ("wReserved3", ctypes.c_uint16),
                    ("val", ctypes.c_int64),
                    ("pad", ctypes.c_uint64),
                ]
                if is_64
                else [
                    ("vt", ctypes.c_uint16),
                    ("wReserved1", ctypes.c_uint16),
                    ("wReserved2", ctypes.c_uint16),
                    ("wReserved3", ctypes.c_uint16),
                    ("val", ctypes.c_int64),
                ]
            )

        class WAVEFORMATEX(ctypes.Structure):
            _pack_ = 1
            _fields_ = [
                ("wFormatTag", ctypes.c_uint16),
                ("nChannels", ctypes.c_uint16),
                ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32),
                ("nBlockAlign", ctypes.c_uint16),
                ("wBitsPerSample", ctypes.c_uint16),
                ("cbSize", ctypes.c_uint16),
            ]

        class WAVEHDR(ctypes.Structure):
            _fields_ = [
                ("lpData", ctypes.c_void_p),
                ("dwBufferLength", ctypes.c_uint32),
                ("dwBytesRecorded", ctypes.c_uint32),
                ("dwUser", ctypes.c_size_t),
                ("dwFlags", ctypes.c_uint32),
                ("dwLoops", ctypes.c_uint32),
                ("lpNext", ctypes.c_void_p),
                ("reserved", ctypes.c_size_t),
            ]

        class MMTIME(ctypes.Structure):
            _pack_ = 1

            class _U(ctypes.Union):
                _pack_ = 1
                _fields_ = [
                    ("ms", ctypes.c_uint32),
                    ("sample", ctypes.c_uint32),
                    ("cb", ctypes.c_uint32),
                    ("ticks", ctypes.c_uint32),
                    ("smpte_raw", ctypes.c_uint8 * 8),
                ]

            _fields_ = [("wType", ctypes.c_uint32), ("u", _U)]

        def vcall(ptr: ctypes.c_void_p, index: int, restype: object, *args_spec: tuple[object, object]) -> object:
            vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            argtypes = [ctypes.c_void_p] + [a[0] for a in args_spec]
            args = [ptr] + [a[1] for a in args_spec]
            fn = ctypes.WINFUNCTYPE(restype, *argtypes)(vtbl[index])  # type: ignore[arg-type]
            return fn(*args)

        def com_release(ptr: ctypes.c_void_p | None) -> None:
            if ptr and ptr.value:
                vcall(ptr, 2, ctypes.c_ulong)

        mf_version = 0x00020070
        first_audio_stream = 0xFFFFFFFD
        mf_eof_flag = 2
        vt_i8 = 20
        whdr_inqueue = 0x00000010
        whdr_prepared = 0x00000002
        time_bytes = 0x0004
        callback_event = 0x00050000
        wave_mapper = 0xFFFFFFFF
        chunk_target_bytes = 8192
        num_slots = 4
        bytes_per_sec = float(BGM_SAMPLE_RATE * 4)

        guid_null = make_guid(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        mf_mt_major = make_guid(0x48EBA18E, 0xF8C9, 0x4687, 0xBF, 0x11, 0x0A, 0x74, 0xC9, 0xF9, 0x6A, 0x8F)
        mf_mt_sub = make_guid(0xF7E34C9A, 0x42E8, 0x4714, 0xB7, 0x4B, 0xCB, 0x29, 0xD7, 0x2C, 0x35, 0xE5)
        mf_mt_ch = make_guid(0x37E48BF5, 0x645E, 0x4C5B, 0x89, 0xDE, 0xAD, 0xA9, 0xE2, 0x9B, 0x69, 0x6A)
        mf_mt_sr = make_guid(0x5FAEEAE7, 0x0290, 0x4C31, 0x9E, 0x8A, 0xC5, 0x34, 0xF6, 0x8D, 0x9D, 0xBA)
        mf_mt_bits = make_guid(0xF2DEB57F, 0x40FA, 0x4764, 0xAA, 0x33, 0xED, 0x4F, 0x2D, 0x1F, 0xF6, 0x69)
        mf_audio = make_guid(0x73647561, 0x0000, 0x0010, 0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71)
        mf_pcm = make_guid(0x00000001, 0x0000, 0x0010, 0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71)

        ole32 = mfplat = mfreadwrite = winmm = kernel32 = None
        com_ok = False
        mf_ok = False
        reader: ctypes.c_void_p | None = None
        hwo: wt.HANDLE | None = None
        h_event: wt.HANDLE | None = None
        slots: list[tuple[WAVEHDR, object] | None] = [None] * num_slots

        try:
            ole32 = ctypes.WinDLL("ole32")
            mfplat = ctypes.WinDLL("mfplat")
            mfreadwrite = ctypes.WinDLL("mfreadwrite")
            winmm = ctypes.WinDLL("winmm")
            kernel32 = ctypes.WinDLL("kernel32")
            shlwapi = ctypes.WinDLL("shlwapi")

            shlwapi.SHCreateMemStream.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            shlwapi.SHCreateMemStream.restype = ctypes.c_void_p
            mfplat.MFCreateMFByteStreamOnStream.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            mfplat.MFCreateMFByteStreamOnStream.restype = ctypes.c_long
            mfreadwrite.MFCreateSourceReaderFromURL.argtypes = [
                wt.LPCWSTR,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            mfreadwrite.MFCreateSourceReaderFromURL.restype = ctypes.c_long
            mfreadwrite.MFCreateSourceReaderFromByteStream.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            ]
            mfreadwrite.MFCreateSourceReaderFromByteStream.restype = ctypes.c_long
            mfplat.MFCreateMediaType.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
            mfplat.MFCreateMediaType.restype = ctypes.c_long

            kernel32.CreateEventW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.BOOL, wt.LPCWSTR]
            kernel32.CreateEventW.restype = wt.HANDLE
            kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
            kernel32.WaitForSingleObject.restype = wt.DWORD
            kernel32.CloseHandle.argtypes = [wt.HANDLE]
            kernel32.CloseHandle.restype = wt.BOOL

            winmm.waveOutOpen.argtypes = [
                ctypes.POINTER(wt.HANDLE),
                wt.UINT,
                ctypes.POINTER(WAVEFORMATEX),
                ctypes.c_size_t,
                ctypes.c_size_t,
                wt.DWORD,
            ]
            winmm.waveOutOpen.restype = wt.UINT
            winmm.waveOutPrepareHeader.argtypes = [wt.HANDLE, ctypes.POINTER(WAVEHDR), wt.UINT]
            winmm.waveOutUnprepareHeader.argtypes = [wt.HANDLE, ctypes.POINTER(WAVEHDR), wt.UINT]
            winmm.waveOutWrite.argtypes = [wt.HANDLE, ctypes.POINTER(WAVEHDR), wt.UINT]
            winmm.waveOutPause.argtypes = [wt.HANDLE]
            winmm.waveOutRestart.argtypes = [wt.HANDLE]
            winmm.waveOutReset.argtypes = [wt.HANDLE]
            winmm.waveOutClose.argtypes = [wt.HANDLE]
            winmm.waveOutGetPosition.argtypes = [wt.HANDLE, ctypes.POINTER(MMTIME), wt.UINT]

            hr_co = int(ole32.CoInitializeEx(None, 0))
            com_ok = hr_co in (0, 1)
            if int(mfplat.MFStartup(mf_version, 0)) != 0:
                raise RuntimeError("MFStartup failed")
            mf_ok = True

            def open_track_reader(track_path: Path) -> ctypes.c_void_p:
                new_reader = ctypes.c_void_p()
                edts_offsets = _find_mp4_edts_tag_offsets(track_path)
                if edts_offsets:
                    # Windows MF's DASH MP4 source can emit instant EOF when an edts box is present.
                    patched = bytearray(track_path.read_bytes())
                    for tag_off in edts_offsets:
                        patched[tag_off : tag_off + 4] = b"free"
                    raw_arr = (ctypes.c_uint8 * len(patched)).from_buffer(patched)
                    istream = ctypes.c_void_p(shlwapi.SHCreateMemStream(raw_arr, len(patched)))
                    if not istream.value:
                        raise RuntimeError(f"SHCreateMemStream failed: {track_path}")
                    bytestream = ctypes.c_void_p()
                    try:
                        if mfplat.MFCreateMFByteStreamOnStream(istream, ctypes.byref(bytestream)) != 0:
                            raise RuntimeError(f"MFCreateMFByteStreamOnStream failed: {track_path}")
                        if mfreadwrite.MFCreateSourceReaderFromByteStream(bytestream, None, ctypes.byref(new_reader)) != 0:
                            raise RuntimeError(f"MFCreateSourceReaderFromByteStream failed: {track_path}")
                    finally:
                        com_release(bytestream)
                        com_release(istream)
                elif mfreadwrite.MFCreateSourceReaderFromURL(str(track_path), None, ctypes.byref(new_reader)) != 0:
                    raise RuntimeError(f"MFCreateSourceReaderFromURL failed: {track_path}")

                mtype = ctypes.c_void_p()
                if mfplat.MFCreateMediaType(ctypes.byref(mtype)) != 0:
                    com_release(new_reader)
                    raise RuntimeError("MFCreateMediaType failed")
                try:
                    vcall(mtype, 24, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(mf_mt_major)), (ctypes.POINTER(GUID), ctypes.byref(mf_audio)))
                    vcall(mtype, 24, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(mf_mt_sub)), (ctypes.POINTER(GUID), ctypes.byref(mf_pcm)))
                    vcall(mtype, 21, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(mf_mt_bits)), (ctypes.c_uint32, 16))
                    vcall(mtype, 21, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(mf_mt_ch)), (ctypes.c_uint32, 2))
                    vcall(mtype, 21, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(mf_mt_sr)), (ctypes.c_uint32, BGM_SAMPLE_RATE))
                    if int(vcall(new_reader, 7, ctypes.c_long, (ctypes.c_uint32, first_audio_stream), (ctypes.c_void_p, None), (ctypes.c_void_p, mtype))) != 0:  # type: ignore[arg-type]
                        raise RuntimeError("SetCurrentMediaType failed")
                except Exception:
                    com_release(new_reader)
                    raise
                finally:
                    com_release(mtype)
                return new_reader

            reader = open_track_reader(track.path)

            ev_handle = kernel32.CreateEventW(None, False, False, None)
            if not ev_handle:
                raise RuntimeError("CreateEventW failed")
            h_event = ev_handle
            self._wave_event_handle = int(ev_handle)

            wfx = WAVEFORMATEX(1, 2, BGM_SAMPLE_RATE, BGM_SAMPLE_RATE * 4, 4, 16, 0)
            wave_handle = wt.HANDLE()
            if winmm.waveOutOpen(ctypes.byref(wave_handle), wave_mapper, ctypes.byref(wfx), int(ev_handle), 0, callback_event) != 0:
                raise RuntimeError("waveOutOpen failed")
            hwo = wave_handle

            def read_next_pcm_chunk() -> tuple[bytes, bool]:
                buf_parts: list[bytes] = []
                acc_len = 0
                ended = False
                while acc_len < chunk_target_bytes and not self._stop_event.is_set():
                    a_idx = ctypes.c_uint32()
                    flags = ctypes.c_uint32()
                    ts = ctypes.c_int64()
                    sample = ctypes.c_void_p()
                    hr_read = int(
                        vcall(  # type: ignore[arg-type]
                            reader,
                            9,
                            ctypes.c_long,
                            (ctypes.c_uint32, first_audio_stream),
                            (ctypes.c_uint32, 0),
                            (ctypes.POINTER(ctypes.c_uint32), ctypes.byref(a_idx)),
                            (ctypes.POINTER(ctypes.c_uint32), ctypes.byref(flags)),
                            (ctypes.POINTER(ctypes.c_int64), ctypes.byref(ts)),
                            (ctypes.POINTER(ctypes.c_void_p), ctypes.byref(sample)),
                        )
                    )
                    if sample and sample.value:
                        try:
                            mbuf = ctypes.c_void_p()
                            if int(vcall(sample, 41, ctypes.c_long, (ctypes.POINTER(ctypes.c_void_p), ctypes.byref(mbuf)))) == 0 and mbuf.value:  # type: ignore[arg-type]
                                try:
                                    pdata = ctypes.POINTER(ctypes.c_uint8)()
                                    max_l = ctypes.c_uint32()
                                    cur_l = ctypes.c_uint32()
                                    if int(vcall(mbuf, 3, ctypes.c_long, (ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)), ctypes.byref(pdata)), (ctypes.POINTER(ctypes.c_uint32), ctypes.byref(max_l)), (ctypes.POINTER(ctypes.c_uint32), ctypes.byref(cur_l)))) == 0:  # type: ignore[arg-type]
                                        if cur_l.value > 0:
                                            raw = ctypes.string_at(pdata, cur_l.value)
                                            buf_parts.append(raw)
                                            acc_len += len(raw)
                                        vcall(mbuf, 4, ctypes.c_long)
                                finally:
                                    com_release(mbuf)
                        finally:
                            com_release(sample)

                    if hr_read != 0 or (flags.value & mf_eof_flag):
                        ended = True
                        break
                return (b"".join(buf_parts), ended)

            hw_paused = False
            total_written = 0
            last_cb = 0
            cb_wrap_offset = 0
            decode_idx = 0
            decode_durations = [t.duration_sec for t in self._tracks]
            seg_start_bytes = 0
            track_segments: deque[tuple[int, int, float]] = deque(
                [(0, 0, decode_durations[0])]
            )
            inflight: deque[tuple[int, int, tuple[float, float, float, float]]] = deque()
            mm = MMTIME()

            while not self._stop_event.is_set():
                with self._lock:
                    want_play = self._want_playing
                    skip_delta = self._pending_delta
                    self._pending_delta = 0
                    cur_active_idx = self._track_idx

                if skip_delta != 0:
                    num_tracks = len(self._tracks)
                    target_idx = (cur_active_idx + skip_delta) % num_tracks
                    winmm.waveOutReset(hwo)
                    for slot_idx in range(num_slots):
                        slot = slots[slot_idx]
                        if slot is not None:
                            hdr, _cb_ref = slot
                            if hdr.dwFlags & whdr_prepared:
                                winmm.waveOutUnprepareHeader(
                                    hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)
                                )
                            slots[slot_idx] = None
                    hw_paused = False
                    if target_idx == decode_idx:
                        pv_zero = PROPVARIANT(vt=vt_i8, val=0)
                        vcall(
                            reader,
                            8,
                            ctypes.c_long,
                            (ctypes.POINTER(GUID), ctypes.byref(guid_null)),
                            (ctypes.POINTER(PROPVARIANT), ctypes.byref(pv_zero)),
                        )
                    else:
                        try:
                            next_reader = open_track_reader(self._tracks[target_idx].path)
                            com_release(reader)
                            reader = next_reader
                            decode_idx = target_idx
                        except Exception:
                            pv_zero = PROPVARIANT(vt=vt_i8, val=0)
                            vcall(
                                reader,
                                8,
                                ctypes.c_long,
                                (ctypes.POINTER(GUID), ctypes.byref(guid_null)),
                                (ctypes.POINTER(PROPVARIANT), ctypes.byref(pv_zero)),
                            )
                            target_idx = decode_idx
                    total_written = 0
                    last_cb = 0
                    cb_wrap_offset = 0
                    seg_start_bytes = 0
                    inflight.clear()
                    track_segments.clear()
                    track_segments.append((0, target_idx, decode_durations[target_idx]))
                    with self._lock:
                        self._track_idx = target_idx
                        self._duration_sec = decode_durations[target_idx]
                        self._elapsed_sec = 0.0
                        self._spectrum = (0.0, 0.0, 0.0, 0.0)

                if not want_play:
                    if total_written > 0 and not hw_paused:
                        winmm.waveOutPause(hwo)
                        hw_paused = True
                    self._wake_event.clear()
                    self._wake_event.wait(timeout=0.05)
                    continue

                if hw_paused:
                    winmm.waveOutRestart(hwo)
                    hw_paused = False

                queued_any = False
                for slot_idx in range(num_slots):
                    slot = slots[slot_idx]
                    if slot is not None:
                        hdr, _cb_ref = slot
                        if hdr.dwFlags & whdr_inqueue:
                            continue
                        if hdr.dwFlags & whdr_prepared:
                            winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                        slots[slot_idx] = None

                    pcm_chunk, ended = read_next_pcm_chunk()
                    if self._stop_event.is_set():
                        break
                    if pcm_chunk:
                        cb_buf = ctypes.create_string_buffer(pcm_chunk, len(pcm_chunk))
                        hdr = WAVEHDR(
                            lpData=ctypes.addressof(cb_buf),
                            dwBufferLength=len(pcm_chunk),
                        )
                        if winmm.waveOutPrepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)) == 0:
                            if winmm.waveOutWrite(hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR)) == 0:
                                slots[slot_idx] = (hdr, cb_buf)
                                bands = _compute_pcm_4bands(pcm_chunk)
                                start_b = total_written
                                end_b = start_b + len(pcm_chunk)
                                inflight.append((start_b, end_b, bands))
                                total_written = end_b
                                queued_any = True
                            else:
                                winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                    if ended:
                        seg_bytes = total_written - seg_start_bytes
                        if seg_bytes > 0 and decode_durations[decode_idx] <= 0.0:
                            decode_durations[decode_idx] = float(seg_bytes) / bytes_per_sec
                        num_tracks = len(self._tracks)
                        if num_tracks == 1:
                            pv_zero = PROPVARIANT(vt=vt_i8, val=0)
                            vcall(reader, 8, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(guid_null)), (ctypes.POINTER(PROPVARIANT), ctypes.byref(pv_zero)))
                        else:
                            switched = False
                            for offset in range(1, num_tracks + 1):
                                cand_idx = (decode_idx + offset) % num_tracks
                                if cand_idx == decode_idx:
                                    pv_zero = PROPVARIANT(vt=vt_i8, val=0)
                                    vcall(reader, 8, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(guid_null)), (ctypes.POINTER(PROPVARIANT), ctypes.byref(pv_zero)))
                                    switched = True
                                    break
                                try:
                                    next_reader = open_track_reader(self._tracks[cand_idx].path)
                                except Exception:
                                    continue
                                com_release(reader)
                                reader = next_reader
                                decode_idx = cand_idx
                                switched = True
                                break
                            if not switched:
                                pv_zero = PROPVARIANT(vt=vt_i8, val=0)
                                vcall(reader, 8, ctypes.c_long, (ctypes.POINTER(GUID), ctypes.byref(guid_null)), (ctypes.POINTER(PROPVARIANT), ctypes.byref(pv_zero)))
                        seg_start_bytes = total_written
                        track_segments.append(
                            (seg_start_bytes, decode_idx, decode_durations[decode_idx])
                        )

                mm.wType = time_bytes
                if winmm.waveOutGetPosition(hwo, ctypes.byref(mm), ctypes.sizeof(MMTIME)) == 0:
                    cb_val = int(mm.u.cb)
                    if cb_val < last_cb:
                        cb_wrap_offset += 0x100000000
                    last_cb = cb_val
                    played_bytes = cb_wrap_offset + cb_val
                    while len(track_segments) > 1 and played_bytes >= track_segments[1][0]:
                        track_segments.popleft()
                    seg_start, active_idx, active_dur = track_segments[0]
                    track_bytes = max(0, played_bytes - seg_start)
                    elapsed = float(track_bytes) / bytes_per_sec
                    while len(inflight) > 1 and played_bytes >= inflight[0][1]:
                        inflight.popleft()
                    cur_bands = inflight[0][2] if inflight else (0.0, 0.0, 0.0, 0.0)
                    with self._lock:
                        if self._want_playing:
                            self._track_idx = active_idx
                            self._duration_sec = active_dur
                            self._elapsed_sec = min(elapsed, active_dur) if active_dur > 0.0 else elapsed
                            self._spectrum = cur_bands

                if not queued_any:
                    kernel32.WaitForSingleObject(h_event, 25)
        except Exception:
            with self._lock:
                self._want_playing = False
                self._is_playing = False
                self._spectrum = (0.0, 0.0, 0.0, 0.0)
        finally:
            self._wave_event_handle = 0
            if hwo is not None and winmm is not None:
                try:
                    winmm.waveOutReset(hwo)
                    for slot in slots:
                        if slot is not None:
                            hdr, _cb_ref = slot
                            if hdr.dwFlags & whdr_prepared:
                                winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(WAVEHDR))
                    winmm.waveOutClose(hwo)
                except Exception:
                    pass
            if h_event is not None and kernel32 is not None:
                try:
                    kernel32.CloseHandle(h_event)
                except Exception:
                    pass
            com_release(reader)
            if mf_ok and mfplat is not None:
                try:
                    mfplat.MFShutdown()
                except Exception:
                    pass
            if com_ok and ole32 is not None:
                try:
                    ole32.CoUninitialize()
                except Exception:
                    pass


BGM_BUTTON_KEYS: tuple[str, ...] = ("play_pause", "prev", "next")


@dataclass(frozen=True, slots=True)
class BgmPillLayout:
    """Measured layout and button hit geometry for the top-left BGM player pill."""

    pill_width: int
    pill_height: int
    compact_time: bool
    playing: bool
    title_text: str
    title_x_offset: float
    viz_bar_xs: tuple[float, ...]
    time_x_offset: float
    time_sample: str
    item_positions: tuple[tuple[str, int, int, str], ...]
    local_hit_spans: tuple[tuple[str, str, float, float, str, float], ...]
    show_labels: bool = False
    button_segments: tuple[tuple[str, float, str], ...] = ()
    separators: tuple[tuple[float, str], ...] = ()

    @property
    def icon_signature(self) -> tuple[tuple[str, int], ...]:
        return tuple((icon_name, rel_x) for icon_name, rel_x, _rt, _lbl in self.item_positions)


def _measure_bgm_pill_tier(
    title: str,
    duration_sec: float,
    playing: bool,
    title_font: tkfont.Font,
    time_font: tkfont.Font,
    *,
    pad_x: int,
    elem_gap: int,
    btn_gap: int,
    compact_time: bool,
    show_labels: bool,
    short_btn_labels: bool,
    max_width: int | None,
    height: int,
    play_slot_w_override: int | None = None,
) -> BgmPillLayout:
    play_icon = "pause" if playing else "play"
    viz_w = (
        BGM_VIZ_BAR_COUNT * BGM_VIZ_BAR_WIDTH
        + max(0, BGM_VIZ_BAR_COUNT - 1) * BGM_VIZ_BAR_GAP
    )
    time_sample = _bgm_time_template(duration_sec, compact=compact_time)
    time_w = int(time_font.measure(time_sample))

    sep_text = "·"
    sep_w = int(title_font.measure(sep_text))
    icon_label_gap = 4 if pad_x >= 9 else 3
    sep_gap = 6 if pad_x >= 9 else 4

    if show_labels:
        play_label = "A: Pause" if playing else "A: Resume"
        play_slot_w = (
            max(0, int(play_slot_w_override))
            if play_slot_w_override is not None
            else int(title_font.measure(play_label))
        )
        prev_label = "S: Prev" if short_btn_labels else "S: Previous"
        next_label = "D: Next"
        btn_specs = (
            ("play_pause", play_icon, play_label, play_slot_w),
            ("prev", "skip_previous", prev_label, int(title_font.measure(prev_label))),
            ("next", "skip_next", next_label, int(title_font.measure(next_label))),
        )
        ctrl_gap = elem_gap + 3
        buttons_w = 0
        for idx, (_bk, iname, _lbl, slot_w) in enumerate(btn_specs):
            if idx > 0:
                buttons_w += sep_gap + sep_w + sep_gap
            iw = _load_rgba_icon(iname)[0]
            buttons_w += iw + icon_label_gap + slot_w
        non_title_w = pad_x * 2 + elem_gap * 2 + ctrl_gap + viz_w + time_w + buttons_w
    else:
        btn_specs = (
            ("play_pause", play_icon, "", 0),
            ("prev", "skip_previous", "", 0),
            ("next", "skip_next", "", 0),
        )
        ctrl_gap = elem_gap
        icon_w = _load_rgba_icon(play_icon)[0]
        buttons_w = len(btn_specs) * icon_w + max(0, len(btn_specs) - 1) * btn_gap
        non_title_w = pad_x * 2 + elem_gap * 3 + viz_w + time_w + buttons_w

    display_title = title
    if max_width is not None:
        avail_title = max(32, int(max_width) - non_title_w)
        display_title = _truncate_label_to_px(title, title_font, avail_title)
    title_w = int(title_font.measure(display_title))

    title_px = pad_x
    viz_px = title_px + title_w + elem_gap
    time_px = viz_px + viz_w + elem_gap
    btn_start_px = time_px + time_w + ctrl_gap
    pill_w = btn_start_px + buttons_w + pad_x
    half_pill = pill_w * 0.5

    viz_xs = tuple(
        (viz_px + i * (BGM_VIZ_BAR_WIDTH + BGM_VIZ_BAR_GAP) + BGM_VIZ_BAR_WIDTH * 0.5)
        - half_pill
        for i in range(BGM_VIZ_BAR_COUNT)
    )

    btn_positions: list[tuple[str, str, int, int, str]] = []
    item_positions: list[tuple[str, int, int, str]] = []
    button_segments: list[tuple[str, float, str]] = []
    separators: list[tuple[float, str]] = []
    cursor = btn_start_px
    for idx, (btn_key, icon_name, label, slot_w) in enumerate(btn_specs):
        if idx > 0:
            if show_labels:
                cursor += sep_gap
                separators.append(((cursor - half_pill) + 1.0, sep_text))
                cursor += sep_w + sep_gap
            else:
                cursor += btn_gap
        iw, _ih, _ = _load_rgba_icon(icon_name)
        rel_icon_px = cursor
        if show_labels:
            rel_text_px = rel_icon_px + iw + icon_label_gap
            end_px = rel_text_px + slot_w
            button_segments.append((btn_key, (rel_text_px - half_pill) + 1.0, label))
        else:
            rel_text_px = rel_icon_px + iw
            end_px = rel_text_px
        btn_positions.append((btn_key, icon_name, rel_icon_px, end_px, label))
        item_positions.append((icon_name, rel_icon_px, rel_text_px, btn_key))
        cursor = end_px

    local_hits: list[tuple[str, str, float, float, str, float]] = []
    for idx, (btn_key, icon_name, ix_px, _end_px, _lbl) in enumerate(btn_positions):
        if idx == 0:
            xmin_px = float(ix_px) - min(4.0, ctrl_gap * 0.4)
        else:
            prev_end = btn_positions[idx - 1][3]
            xmin_px = (prev_end + ix_px) * 0.5
        if idx == len(btn_positions) - 1:
            xmax_px = float(pill_w)
        else:
            next_start = btn_positions[idx + 1][2]
            xmax_px = (btn_positions[idx][3] + next_start) * 0.5
        local_hits.append(
            (btn_key, btn_key, xmin_px - half_pill, xmax_px - half_pill, icon_name, ix_px - half_pill)
        )

    return BgmPillLayout(
        pill_width=pill_w,
        pill_height=height,
        compact_time=compact_time,
        playing=playing,
        title_text=display_title,
        title_x_offset=(title_px - half_pill) + 1.0,
        viz_bar_xs=viz_xs,
        time_x_offset=(time_px - half_pill) + 1.0,
        time_sample=time_sample,
        item_positions=tuple(item_positions),
        local_hit_spans=tuple(local_hits),
        show_labels=show_labels,
        button_segments=tuple(button_segments),
        separators=tuple(separators),
    )


def resolve_bgm_pill_layout(
    title: str,
    duration_sec: float,
    playing: bool,
    title_font: tkfont.Font,
    time_font: tkfont.Font,
    *,
    show_labels: bool = False,
    max_width: int | None = None,
    height: int = BGM_HUD_HEIGHT,
    play_slot_w_override: int | None = None,
) -> BgmPillLayout:
    """Measure the top-left BGM pill with responsive title, time, and label sizing."""
    if show_labels:
        tier_specs: tuple[tuple[int, int, int, bool, bool], ...] = (
            (10, 7, 4, False, False),
            (9, 6, 4, False, True),
            (8, 5, 3, True, True),
        )
    else:
        tier_specs = (
            (10, 7, 4, False, False),
            (9, 6, 4, False, False),
            (8, 5, 3, True, False),
        )
    chosen: BgmPillLayout | None = None
    for pad_x, elem_gap, btn_gap, compact_time, short_btn_labels in tier_specs:
        full_probe = _measure_bgm_pill_tier(
            title,
            duration_sec,
            playing,
            title_font,
            time_font,
            pad_x=pad_x,
            elem_gap=elem_gap,
            btn_gap=btn_gap,
            compact_time=compact_time,
            show_labels=show_labels,
            short_btn_labels=short_btn_labels,
            max_width=None,
            height=height,
            play_slot_w_override=play_slot_w_override,
        )
        if max_width is None or full_probe.pill_width <= max_width:
            return full_probe
        capped = _measure_bgm_pill_tier(
            title,
            duration_sec,
            playing,
            title_font,
            time_font,
            pad_x=pad_x,
            elem_gap=elem_gap,
            btn_gap=btn_gap,
            compact_time=compact_time,
            show_labels=show_labels,
            short_btn_labels=short_btn_labels,
            max_width=max_width,
            height=height,
            play_slot_w_override=play_slot_w_override,
        )
        chosen = capped
        if not compact_time and capped.pill_width <= max_width and len(capped.title_text) >= 12:
            return capped
    assert chosen is not None
    return chosen


def place_bgm_hit_rects(
    bgm_x: float,
    bgm_y: float,
    layout: BgmPillLayout,
) -> tuple[SegmentHitRect, ...]:
    """Compute clickable hit rectangles for BGM transport buttons ('play_pause', 'prev', 'next')."""
    y_min = bgm_y - layout.pill_height * 0.5
    y_max = bgm_y + layout.pill_height * 0.5
    return tuple(
        SegmentHitRect(
            key=key,
            label=label,
            x_min=bgm_x + rel_xmin,
            x_max=bgm_x + rel_xmax,
            y_min=y_min,
            y_max=y_max,
            text_x=bgm_x + rel_icon_x,
            icon_name=icon_name,
            icon_x=bgm_x + rel_icon_x,
        )
        for key, label, rel_xmin, rel_xmax, icon_name, rel_icon_x in layout.local_hit_spans
    )


def hit_test_bgm_pill(
    cx: float, cy: float, hit_rects: Sequence[SegmentHitRect]
) -> str | None:
    """Return BGM button key ('play_pause'|'prev'|'next') at canvas (cx, cy), or None."""
    return _hit_test_rects(cx, cy, hit_rects)


def build_tooltip_pill_photo(
    text: str,
    font: tkfont.Font,
    *,
    height: int = BGM_TOOLTIP_HEIGHT,
    master: tk.Misc | None = None,
    mood: MoodSpec | str = DEFAULT_MOOD,
) -> tuple[tk.PhotoImage, int]:
    """Build a compact frosted tooltip pill ``PhotoImage`` and return ``(photo, width)``."""
    pad_x = 9
    pill_w = max(24, int(font.measure(text)) + pad_x * 2)
    rows = build_pill_rows(pill_w, height, mood=mood, enabled=True)
    png_bytes = _encode_rgba_rows_png(pill_w, height, rows)
    photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
    if master is not None:
        photo_kwargs["master"] = master
    return (tk.PhotoImage(**photo_kwargs), pill_w)


# ---------------------------------------------------------------------------
# Pure-Turtle Renderer, Growable Polygon Pool & Interactive Viewer App
# ---------------------------------------------------------------------------

class PolygonPool:
    """Reusable, growable canvas polygon pool with fill/visibility dirty tracking."""

    def __init__(
        self,
        screen: turtle._Screen,
        initial_capacity: int = 0,
        on_grow: Callable[[], None] | None = None,
    ) -> None:
        self._screen = screen
        self._canvas = screen.getcanvas()
        self._on_grow = on_grow
        self._items: list[int] = []
        self._fills: list[str] = []
        self._visible: list[bool] = []
        if initial_capacity > 0:
            self.ensure_capacity(initial_capacity)

    @property
    def capacity(self) -> int:
        return len(self._items)

    def ensure_capacity(self, required: int) -> bool:
        """Grow the pool to hold at least ``required`` items; return True if grown."""
        if required <= len(self._items):
            return False

        create_poly = self._screen._createpoly
        itemcfg = self._canvas.itemconfigure
        deficit = required - len(self._items)
        for _ in range(deficit):
            item = create_poly()
            itemcfg(item, state="hidden")
            self._items.append(item)
            self._fills.append("")
            self._visible.append(False)

        if self._on_grow is not None:
            self._on_grow()
        return True

    def render(
        self,
        draw_list: Sequence[tuple[float, str, tuple[tuple[float, float], ...]]],
    ) -> None:
        """Update canvas polygon coordinates/fills for ``draw_list`` and hide surplus items."""
        needed = len(draw_list)
        if needed > len(self._items):
            self.ensure_capacity(needed)

        coords = self._canvas.coords
        itemcfg = self._canvas.itemconfigure
        items = self._items
        fills = self._fills
        visible = self._visible

        for idx, (_z, fill_hex, pts) in enumerate(draw_list):
            item = items[idx]
            n_pts = len(pts)
            if n_pts == 4:
                p0, p1, p2, p3 = pts
                coords(item, p0[0], -p0[1], p1[0], -p1[1], p2[0], -p2[1], p3[0], -p3[1])
            elif n_pts == 3:
                p0, p1, p2 = pts
                coords(item, p0[0], -p0[1], p1[0], -p1[1], p2[0], -p2[1])
            else:
                flat: list[float] = []
                for px, py in pts:
                    flat.append(px)
                    flat.append(-py)
                coords(item, *flat)

            if not visible[idx]:
                if fills[idx] != fill_hex:
                    itemcfg(item, fill=fill_hex, state="normal")
                    fills[idx] = fill_hex
                else:
                    itemcfg(item, state="normal")
                visible[idx] = True
            elif fills[idx] != fill_hex:
                itemcfg(item, fill=fill_hex)
                fills[idx] = fill_hex

        for idx in range(needed, len(items)):
            if visible[idx]:
                itemcfg(items[idx], state="hidden")
                visible[idx] = False

    def clear(self) -> None:
        """Delete all pooled canvas items and reset capacity to zero."""
        for item in self._items:
            try:
                self._canvas.delete(item)
            except tk.TclError:
                pass
        self._items.clear()
        self._fills.clear()
        self._visible.clear()


class _SliderHUD:
    """Manages one interactive frosted slider pill (Speed or Bloom)."""

    def __init__(
        self,
        *,
        icon_name: str,
        label_text: str,
        sample_values: Sequence[str],
        value_align: str,
        initial_text: str,
        initial_fraction: float,
        root: tk.Misc,
        canvas: turtle.ScrolledCanvas,
        tk_canvas: tk.Canvas,
        label_font_obj: tkfont.Font,
        value_font_obj: tkfont.Font,
        label_font_tuple: tuple[str, int, str],
        value_font_tuple: tuple[str, int, str],
        mood: MoodSpec,
        cultivar: CultivarSpec,
        blend: float,
    ) -> None:
        self.icon_name = icon_name
        self.label_text = label_text
        self.sample_values = tuple(sample_values)
        self.value_align = value_align
        self.root = root
        self.canvas = canvas
        self.tk_canvas = tk_canvas
        self.label_font_obj = label_font_obj
        self.value_font_obj = value_font_obj
        self.label_font_tuple = label_font_tuple
        self.value_font_tuple = value_font_tuple

        self.x = 0.0
        self.y = HUD_Y + HUD_HEIGHT * 0.5 + SLIDER_STACK_GAP + SLIDER_HUD_HEIGHT * 0.5
        self.text_y = compute_hud_text_y(self.y, self.label_font_obj)

        self.pill_cache: dict[str, list[tk.PhotoImage]] = {}
        self.transition_pills: list[tk.PhotoImage] = []
        self.layout: SliderPillLayout | None = None
        self.track_photo: tk.PhotoImage | None = None
        self.applied_step = -1
        self.applied_track_key: tuple[int, int, str, str] | None = None
        self.applied_color = ""
        self.applied_text = initial_text

        self.pen = turtle.Turtle(undobuffersize=0, visible=False)
        self.pen.speed(0)
        self.pen.penup()
        self.pen.hideturtle()

        self.bg_item: int | None = None
        self.track_item: int | None = None
        self.label_item: int | None = None
        self.value_item: int | None = None

        self._init_items(initial_text, initial_fraction, mood, cultivar, blend)

    def _get_pills_for_mood(self, mood: MoodSpec) -> list[tk.PhotoImage]:
        cached = self.pill_cache.get(mood.key)
        if cached is not None:
            return cached
        pills, layout = build_slider_transition_pills(
            self.icon_name,
            self.label_text,
            self.sample_values,
            self.label_font_obj,
            self.value_font_obj,
            value_align=self.value_align,
            height=SLIDER_HUD_HEIGHT,
            master=self.root,
            mood=mood,
        )
        self.layout = layout
        self.pill_cache[mood.key] = pills
        return pills

    def _init_items(
        self,
        initial_text: str,
        initial_fraction: float,
        mood: MoodSpec,
        cultivar: CultivarSpec,
        blend: float,
    ) -> None:
        self.transition_pills = self._get_pills_for_mood(mood)
        layout = self.layout
        assert layout is not None

        eased = _smootherstep(blend)
        max_step = max(0, len(self.transition_pills) - 1)
        step_idx = min(max_step, max(0, int(round(eased * max_step))))
        self.applied_step = step_idx
        self.bg_item = self.tk_canvas.create_image(
            self.x, -self.y, image=self.transition_pills[step_idx], anchor="center"
        )

        self.track_photo = build_slider_track_photo(
            initial_fraction,
            blend,
            cultivar.accent_rgba,
            cultivar.accent_disabled_rgba,
            mood,
            width=layout.track_width,
            height=layout.track_height,
            pad=layout.track_pad,
            master=self.root,
        )
        self.applied_track_key = self._track_key(initial_fraction, blend, cultivar, mood)
        self.track_item = self.tk_canvas.create_image(
            self.x + layout.track_x_offset,
            -self.y,
            image=self.track_photo,
            anchor="center",
        )

        ink_color = hud_ink_hex(eased, mood)
        self.applied_color = ink_color
        self.pen.pencolor(ink_color)
        self.pen.goto(self.x + layout.label_x_offset, self.text_y)
        self.pen.write(self.label_text, move=False, align="left", font=self.label_font_tuple)
        self.label_item = self.pen.items[-1]

        self.pen.goto(self.x + layout.value_x_offset, self.text_y)
        self.pen.write(
            initial_text,
            move=False,
            align=layout.value_align,
            font=self.value_font_tuple,
        )
        self.value_item = self.pen.items[-1]

    @staticmethod
    def _track_key(
        fraction: float,
        blend: float,
        cultivar: CultivarSpec,
        mood: MoodSpec,
    ) -> tuple[int, int, str, str]:
        return (
            int(round(_clamp(fraction, 0.0, 1.0) * 200.0)),
            int(round(_clamp(blend, 0.0, 1.0) * 100.0)),
            cultivar.key,
            mood.key,
        )

    def apply_mood(self, mood: MoodSpec) -> None:
        self.transition_pills = self._get_pills_for_mood(mood)
        self.applied_step = -1

    def contains(self, cx: float, cy: float) -> bool:
        layout = self.layout
        if layout is None:
            return False
        return (
            abs(cx - self.x) <= layout.pill_width * 0.5
            and abs(cy - self.y) <= layout.pill_height * 0.5
        )

    def canvas_x_to_fraction(self, cx: float) -> float:
        layout = self.layout
        if layout is None:
            return 0.0
        track_center_x = self.x + layout.track_x_offset
        half_travel = max(1.0, layout.track_width * 0.5 - layout.track_pad)
        return _clamp((cx - (track_center_x - half_travel)) / (2.0 * half_travel), 0.0, 1.0)

    def set_position(self, x: float, y: float) -> None:
        self.x = x
        self.y = y
        self.text_y = compute_hud_text_y(y, self.label_font_obj)

    def reposition(self) -> None:
        layout = self.layout
        if self.bg_item is not None:
            self.canvas.coords(self.bg_item, self.x, -self.y)
        if layout is None:
            return
        if self.track_item is not None:
            self.canvas.coords(
                self.track_item, self.x + layout.track_x_offset, -self.y
            )
        if self.label_item is not None:
            self.canvas.coords(
                self.label_item, self.x + layout.label_x_offset - 1.0, -self.text_y
            )
        if self.value_item is not None:
            self.canvas.coords(
                self.value_item, self.x + layout.value_x_offset - 1.0, -self.text_y
            )

    def raise_items(self) -> None:
        for item_id in (self.bg_item, self.track_item, self.label_item, self.value_item):
            if item_id is not None:
                self.canvas.tag_raise(item_id)

    def update_visual(
        self,
        *,
        fraction: float,
        value_text: str,
        blend: float,
        step_idx: int,
        ink_color: str,
        cultivar: CultivarSpec,
        mood: MoodSpec,
    ) -> None:
        if self.bg_item is not None and self.transition_pills:
            clamped_step = min(len(self.transition_pills) - 1, max(0, step_idx))
            if clamped_step != self.applied_step:
                self.canvas.itemconfigure(
                    self.bg_item, image=self.transition_pills[clamped_step]
                )
                self.applied_step = clamped_step

        if value_text != self.applied_text and self.value_item is not None:
            self.canvas.itemconfigure(self.value_item, text=value_text)
            self.applied_text = value_text

        if ink_color != self.applied_color:
            for item_id in (self.label_item, self.value_item):
                if item_id is not None:
                    self.canvas.itemconfigure(item_id, fill=ink_color)
            self.applied_color = ink_color

        layout = self.layout
        if self.track_item is not None and layout is not None:
            key = self._track_key(fraction, blend, cultivar, mood)
            if key != self.applied_track_key:
                self.track_photo = build_slider_track_photo(
                    fraction,
                    blend,
                    cultivar.accent_rgba,
                    cultivar.accent_disabled_rgba,
                    mood,
                    width=layout.track_width,
                    height=layout.track_height,
                    pad=layout.track_pad,
                    master=self.root,
                )
                self.canvas.itemconfigure(self.track_item, image=self.track_photo)
                self.applied_track_key = key

    def cleanup(self) -> None:
        for attr in ("bg_item", "track_item"):
            item_id = getattr(self, attr, None)
            if item_id is not None:
                try:
                    self.canvas.delete(item_id)
                except tk.TclError:
                    pass
                setattr(self, attr, None)
        try:
            self.pen.clear()
        except (turtle.Terminator, tk.TclError):
            pass
        self.label_item = None
        self.value_item = None
        self.transition_pills.clear()
        self.pill_cache.clear()
        self.track_photo = None


class FlowerViewerApp:
    """Interactive 3D rotating botanical viewer built with pure Python turtle."""

    def __init__(self) -> None:
        self._species_idx = 0
        self.species: SpeciesSpec = SPECIES[self._species_idx]
        self._cultivar_idx_by_species: dict[str, int] = {s.key: 0 for s in SPECIES}
        self._cultivar_idx = 0
        self._mood_idx = 0
        self.cultivar: CultivarSpec = self.species.cultivars[self._cultivar_idx]
        self.mood: MoodSpec = MOODS[self._mood_idx]
        self.detail_tier: DetailTierSpec = STANDARD_TIER
        self.breeze_enabled = False
        self.breeze_time = 0.0

        self.screen = turtle.Screen()
        self.screen.setup(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.screen.screensize(200, 200)
        self.screen.bgcolor(self.mood.bg_hex)
        self.screen.title(WINDOW_TITLE)
        self.screen.tracer(0)

        self.yaw = self.species.default_yaw
        self.pitch = self.species.startup_pitch
        self.zoom = self.species.startup_zoom
        self.rotation_speed = DEFAULT_ROTATION_SPEED
        self.paused = False
        self.running = True
        self._controls_locked = True
        self._inertia = CameraInertia()

        self.current_bloom = 0.0
        self.bloom_elapsed = 0.0
        self.bloom_done = False
        self._camera_tween_active = True
        self._tween_elapsed = 0.0
        self._tween_start_pitch = self.species.startup_pitch
        self._tween_start_zoom = self.species.startup_zoom

        self._species_entry_active = False
        self._species_entry_elapsed = 0.0
        self._species_entry_start_yaw = self.species.default_yaw
        self._species_entry_target_yaw = self.species.default_yaw
        self._species_entry_start_pitch = self.species.startup_pitch
        self._species_entry_start_zoom = self.species.startup_zoom

        self._reset_active = False
        self._reset_elapsed = 0.0
        self._reset_start_yaw = self.species.default_yaw
        self._reset_target_yaw = self.species.default_yaw
        self._reset_start_pitch = self.species.startup_pitch
        self._reset_start_zoom = self.species.startup_zoom
        self._reset_start_bloom = 0.0

        self.mesh = FlowerMesh(
            bloom=0.0, detail_tier=self.detail_tier, species=self.species
        )

        self._canvas = self.screen.getcanvas()
        self._tk_canvas = self._canvas._canvas
        self._root = self._canvas.winfo_toplevel()
        self._root.minsize(360, 320)
        self._app_icon_photo = apply_window_icon(self._root)

        self._hud_ready = False
        self._poly_pool = PolygonPool(
            self.screen,
            initial_capacity=len(self.mesh.faces),
            on_grow=self._on_pool_grow,
        )
        self._after_id: str | None = None
        self._resize_after_id: str | None = None
        self._last_viewport: tuple[int, int, float, float, float, float] | None = None
        self._last_expanded_mode: bool | None = None
        self.fullscreen = False
        self._windowed_geometry: str | None = None
        self._viewport_fov_scale = FOV_SCALE

        self._dragging = False
        self._dragging_speed = False
        self._dragging_bloom = False
        self._canvas_cursor = ""
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._last_frame_time = time.perf_counter()

        self._fps_window_start = self._last_frame_time
        self._fps_frames = 0
        self._next_frame_deadline = self._last_frame_time

        self._hud_font_tuple = get_hud_font(size=9, weight="normal")
        self._fps_font_tuple = get_hud_font(size=9, weight="medium")
        self._hud_font_obj = tkfont.Font(
            root=self._root,
            family=self._hud_font_tuple[0],
            size=self._hud_font_tuple[1],
            weight=self._hud_font_tuple[2],
        )
        self._fps_font_obj = tkfont.Font(
            root=self._root,
            family=self._fps_font_tuple[0],
            size=self._fps_font_tuple[1],
            weight=self._fps_font_tuple[2],
        )

        # Bottom control HUD pill state (cached per mood + resolved width + compact)
        self._hud_pill_cache: dict[
            tuple[str, int, bool],
            tuple[list[tk.PhotoImage], tk.PhotoImage, BottomHudLayout, BottomHudLayout],
        ] = {}
        self._hud_transition_pills: list[tk.PhotoImage] = []
        self._hud_pill_playing: tk.PhotoImage | None = None
        self._hud_pill_paused: tk.PhotoImage | None = None
        self._hud_pill_disabled: tk.PhotoImage | None = None
        self._hud_layout_playing: BottomHudLayout | None = None
        self._hud_layout_paused: BottomHudLayout | None = None
        self._hud_hit_rects_playing: tuple[SegmentHitRect, ...] = ()
        self._hud_hit_rects_paused: tuple[SegmentHitRect, ...] = ()
        self._hud_segments_playing: list[tuple[float, str]] = []
        self._hud_segments_paused: list[tuple[float, str]] = []
        self._hud_is_compact = False
        self._hud_max_w: int | None = max(240, WINDOW_WIDTH - 24)
        self._hud_enable_blend = 0.0 if self._controls_locked else 1.0
        self._hud_applied_step = -1
        self._hud_applied_color = ""
        self._hud_segments_is_paused = False
        self._hud_bg_item: int | None = None
        self._hud_text_items: list[int] = []
        self._hud_x = 0.0
        self._hud_y = HUD_Y
        self._hud_text_y = HUD_Y
        self._hud_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._hud_pen.speed(0)
        self._hud_pen.penup()
        self._hud_pen.hideturtle()

        # Top-left FPS badge state (cached per mood.key + fps_tier)
        self._fps_photo_cache: dict[tuple[str, str], tuple[tk.PhotoImage, float]] = {}
        self._fps_photo: tk.PhotoImage | None = None
        self._fps_bg_item: int | None = None
        self._fps_text_item: int | None = None
        self._fps_x = 0.0
        self._fps_y = 0.0
        self._fps_text_x_offset = 0.0
        self._fps_text_y = 0.0
        self._fps_tier = "init"
        self._fps_applied_tier = ""
        self._fps_applied_ink = ""
        self._fps_applied_text = "-- FPS"
        self._fps_applied_mood_key = ""
        self._fps_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._fps_pen.speed(0)
        self._fps_pen.penup()
        self._fps_pen.hideturtle()

        # Top-left mesh Faces badge state (to the right of FPS badge, cached per mood + faces)
        self._faces_photo_cache: dict[tuple[str, int], tuple[tk.PhotoImage, float, int]] = {}
        self._faces_photo: tk.PhotoImage | None = None
        self._faces_bg_item: int | None = None
        self._faces_text_item: int | None = None
        self._faces_x = 0.0
        self._faces_y = 0.0
        self._faces_text_x_offset = 0.0
        self._faces_text_y = 0.0
        self._faces_applied_count = -1
        self._faces_applied_mood_key = ""
        self._faces_applied_ink = ""
        self._faces_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._faces_pen.speed(0)
        self._faces_pen.penup()
        self._faces_pen.hideturtle()

        # Top-right compact switcher pill state
        self._switcher_pill_cache: dict[
            tuple[str, int, int, tuple[tuple[str, int], ...]], list[tk.PhotoImage]
        ] = {}
        self._switcher_transition_pills: list[tk.PhotoImage] = []
        self._switcher_layout: SwitcherLayout | None = None
        self._switcher_hit_rects: tuple[SegmentHitRect, ...] = ()
        self._switcher_bg_item: int | None = None
        self._switcher_text_items: list[tuple[float, int]] = []
        self._switcher_applied_step = -1
        self._switcher_applied_color = ""
        self._switcher_applied_signature: tuple[str, str, bool, bool, int, str, int] | None = None
        self._switcher_x = 0.0
        self._switcher_y = 0.0
        self._switcher_text_y = 0.0
        self._switcher_max_w = max(120, WINDOW_WIDTH - 140)
        self._switcher_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._switcher_pen.speed(0)
        self._switcher_pen.penup()
        self._switcher_pen.hideturtle()

        # Top-right Species switcher pill state (directly below Switcher pill)
        self._species_pill_cache: dict[
            tuple[str, str, str, int, int, int], list[tk.PhotoImage]
        ] = {}
        self._species_transition_pills: list[tk.PhotoImage] = []
        self._species_layout: SpeciesPillLayout | None = None
        self._species_hit_rects: tuple[SegmentHitRect, ...] = ()
        self._species_bg_item: int | None = None
        self._species_text_items: list[tuple[float, int]] = []
        self._species_applied_step = -1
        self._species_applied_color = ""
        self._species_applied_signature: tuple[str, str, int, str, int] | None = None
        self._species_x = 0.0
        self._species_y = 0.0
        self._species_text_y = 0.0
        self._species_max_w = max(120, WINDOW_WIDTH - int(HUD_MARGIN_X * 2))
        self._species_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._species_pen.speed(0)
        self._species_pen.penup()
        self._species_pen.hideturtle()

        # Top-left BGM audio player & pill state (directly below FPS badge)
        self._bgm_player = BgmPlayer(auto_play=True)
        track = self._bgm_player.current_track
        self._bgm_known_duration = track.duration_sec if track is not None else 0.0
        self._bgm_applied_track_key = str(track.path) if track is not None else ""
        self._bgm_step_cache: dict[
            tuple[str, int, int, tuple[tuple[str, int], ...], bool, int], tk.PhotoImage
        ] = {}
        self._bgm_layout: BgmPillLayout | None = None
        self._bgm_hit_rects: tuple[SegmentHitRect, ...] = ()
        self._bgm_bg_item: int | None = None
        self._bgm_title_item: int | None = None
        self._bgm_time_item: int | None = None
        self._bgm_btn_text_items: dict[str, int] = {}
        self._bgm_sep_items: list[tuple[float, int]] = []
        self._bgm_viz_items: list[int] = []
        self._bgm_viz_levels: list[float] = [BGM_VIZ_MIN_HALF_H] * BGM_VIZ_BAR_COUNT
        self._bgm_viz_applied_levels: list[float] = [-1.0] * BGM_VIZ_BAR_COUNT
        self._bgm_label_blend = 0.0 if self._bgm_player.is_playing else 1.0
        self._bgm_applied_step = -1
        self._bgm_applied_playing: bool | None = None
        self._bgm_applied_play_label = ""
        self._bgm_applied_color = ""
        self._bgm_applied_viz_color = ""
        self._bgm_applied_time_text = ""
        self._bgm_applied_text_signature: (
            tuple[str, str, bool, tuple[str, ...], int, str, int] | None
        ) = None
        self._bgm_applied_geom_signature: (
            tuple[int, tuple[tuple[str, int], ...], bool, int, str, int] | None
        ) = None
        self._bgm_x = 0.0
        self._bgm_y = 0.0
        self._bgm_text_y = 0.0
        self._bgm_max_w: int | None = max(160, WINDOW_WIDTH - int(HUD_MARGIN_X * 2))
        self._bgm_tooltip_cache: dict[tuple[str, str], tuple[tk.PhotoImage, int]] = {}
        self._bgm_tooltip_hover_key: str | None = None
        self._bgm_tooltip_bg_item: int | None = None
        self._bgm_tooltip_text_item: int | None = None
        self._bgm_tooltip_applied_state: tuple[str, str, str, float, float] | None = None
        self._bgm_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._bgm_pen.speed(0)
        self._bgm_pen.penup()
        self._bgm_pen.hideturtle()

        # Dual sliders: Speed & Bloom scrubber
        self._speed_slider = _SliderHUD(
            icon_name="speed",
            label_text="Speed",
            sample_values=tuple(f"{s:.1f}x" for s in (1.0, 2.0, 3.0, 4.0, 5.0)),
            value_align="left",
            initial_text=f"{self.rotation_speed:.1f}x",
            initial_fraction=self._speed_fraction(),
            root=self._root,
            canvas=self._canvas,
            tk_canvas=self._tk_canvas,
            label_font_obj=self._hud_font_obj,
            value_font_obj=self._fps_font_obj,
            label_font_tuple=self._hud_font_tuple,
            value_font_tuple=self._fps_font_tuple,
            mood=self.mood,
            cultivar=self.cultivar,
            blend=self._hud_enable_blend,
        )
        self._bloom_slider = _SliderHUD(
            icon_name="bloom",
            label_text="Bloom",
            sample_values=("0%", "50%", "100%"),
            value_align="right",
            initial_text="0%",
            initial_fraction=0.0,
            root=self._root,
            canvas=self._canvas,
            tk_canvas=self._tk_canvas,
            label_font_obj=self._hud_font_obj,
            value_font_obj=self._fps_font_obj,
            label_font_tuple=self._hud_font_tuple,
            value_font_tuple=self._fps_font_tuple,
            mood=self.mood,
            cultivar=self.cultivar,
            blend=self._hud_enable_blend,
        )

        self._init_hud()
        self._init_fps_badge()
        self._init_faces_badge()
        self._init_switcher_hud()
        self._bgm_max_w, self._species_max_w = self._resolve_row2_budgets(WINDOW_WIDTH)
        self._init_bgm_hud()
        self._init_species_hud()
        self._hud_ready = True
        self._sync_hud_to_viewport()
        self._raise_overlays()
        self._bind_events()

    # -- Bottom HUD & FPS Badge Setup ----------------------------------------

    def _rebuild_hud_pills(
        self,
        max_hud_w: int | None,
        *,
        layout_playing: BottomHudLayout | None = None,
    ) -> None:
        if layout_playing is None:
            layout_playing = resolve_bottom_hud_layout(
                False, self._hud_font_obj, max_width=max_hud_w
            )
        cache_key = (self.mood.key, layout_playing.pill_width, layout_playing.compact)
        cached = self._hud_pill_cache.get(cache_key)
        if cached is None:
            pills = _bake_transition_pills(
                layout_playing.pill_width,
                HUD_HEIGHT,
                layout_playing.content_left_px,
                layout_playing.item_positions,
                self._root,
                HUD_TRANSITION_STEPS,
                mood=self.mood,
            )
            layout_paused = resolve_bottom_hud_layout(
                True, self._hud_font_obj, max_width=max_hud_w
            )
            rows_geom = _compute_pill_geometry(layout_paused.pill_width, HUD_HEIGHT)
            paused_pill = _bake_pill_photo_from_geometry(
                layout_paused.pill_width,
                HUD_HEIGHT,
                rows_geom,
                layout_paused.content_left_px,
                layout_paused.item_positions,
                self.mood.pill_fill_rgba,
                self.mood.pill_edge_rgba,
                1.0,
                self._root,
                icon_tint_rgb=self.mood.icon_enabled_rgb,
            )
            cached = (pills, paused_pill, layout_playing, layout_paused)
            self._hud_pill_cache[cache_key] = cached

        pills, paused_pill, layout_playing, layout_paused = cached
        self._hud_transition_pills = pills
        self._hud_pill_disabled = pills[0]
        self._hud_pill_playing = pills[-1]
        self._hud_pill_paused = paused_pill
        self._hud_layout_playing = layout_playing
        self._hud_layout_paused = layout_paused
        self._hud_segments_playing = list(layout_playing.segments)
        self._hud_segments_paused = list(layout_paused.segments)
        self._hud_is_compact = layout_playing.compact
        self._hud_applied_step = -1
        self._recompute_bottom_hud_hit_rects()

    def _recompute_bottom_hud_hit_rects(self) -> None:
        if self._hud_layout_playing is not None:
            self._hud_hit_rects_playing = place_bottom_hud_hit_rects(
                self._hud_x, self._hud_y, self._hud_layout_playing
            )
        if self._hud_layout_paused is not None:
            self._hud_hit_rects_paused = place_bottom_hud_hit_rects(
                self._hud_x, self._hud_y, self._hud_layout_paused
            )

    def _current_hud_hit_rects(self) -> tuple[SegmentHitRect, ...]:
        return (
            self._hud_hit_rects_paused
            if self._hud_segments_is_paused
            else self._hud_hit_rects_playing
        )

    def _init_hud(self) -> None:
        self._hud_text_y = compute_hud_text_y(self._hud_y, self._hud_font_obj)
        max_hud_w = max(240, WINDOW_WIDTH - 24)
        self._hud_max_w = max_hud_w
        self._rebuild_hud_pills(max_hud_w)

        initial_pill = self._hud_pill_disabled if self._controls_locked else self._hud_pill_playing
        self._hud_bg_item = self._tk_canvas.create_image(
            self._hud_x, -self._hud_y, image=initial_pill, anchor="center"
        )
        self._update_hud_text(force_rebuild_text=True)

    def _warm_fps_badge_cache_for_mood(self, mood: MoodSpec) -> None:
        for tier in FPS_TIERS:
            key = (mood.key, tier)
            if key not in self._fps_photo_cache:
                self._fps_photo_cache[key] = build_fps_badge_photo(
                    sample_text="99 FPS",
                    font=self._fps_font_obj,
                    height=FPS_BADGE_HEIGHT,
                    master=self._root,
                    mood=mood,
                    fps_tier=tier,
                )

    def _get_fps_badge(
        self, mood: MoodSpec, fps_tier: str = "init"
    ) -> tuple[tk.PhotoImage, float]:
        key = (mood.key, fps_tier)
        cached = self._fps_photo_cache.get(key)
        if cached is not None:
            return cached
        built = build_fps_badge_photo(
            sample_text="99 FPS",
            font=self._fps_font_obj,
            height=FPS_BADGE_HEIGHT,
            master=self._root,
            mood=mood,
            fps_tier=fps_tier,
        )
        self._fps_photo_cache[key] = built
        return built

    def _init_fps_badge(self) -> None:
        self._warm_fps_badge_cache_for_mood(self.mood)
        self._fps_photo, self._fps_text_x_offset = self._get_fps_badge(self.mood, "init")
        badge_w = self._fps_photo.width()
        self._fps_x = -WINDOW_WIDTH * 0.5 + HUD_MARGIN_X + badge_w * 0.5
        self._fps_y = WINDOW_HEIGHT * 0.5 - HUD_MARGIN_Y - FPS_BADGE_HEIGHT * 0.5
        self._fps_text_y = compute_hud_text_y(self._fps_y, self._fps_font_obj)

        self._fps_bg_item = self._tk_canvas.create_image(
            self._fps_x, -self._fps_y, image=self._fps_photo, anchor="center"
        )
        ink = fps_badge_ink_hex(self.mood, "init")
        self._fps_pen.pencolor(ink)
        self._fps_pen.goto(self._fps_x + self._fps_text_x_offset, self._fps_text_y)
        self._fps_pen.write("-- FPS", move=False, align="left", font=self._fps_font_tuple)
        self._fps_text_item = self._fps_pen.items[-1]
        self._fps_tier = "init"
        self._fps_applied_tier = "init"
        self._fps_applied_ink = ink
        self._fps_applied_text = "-- FPS"
        self._fps_applied_mood_key = self.mood.key

    def _apply_fps_reading(self, fps_val: float | None) -> None:
        tier = fps_tier_for_value(fps_val)
        text = "-- FPS" if fps_val is None else f"{fps_val:.0f} FPS"
        self._fps_tier = tier
        if tier != self._fps_applied_tier or self.mood.key != self._fps_applied_mood_key:
            self._fps_photo, self._fps_text_x_offset = self._get_fps_badge(self.mood, tier)
            if self._fps_bg_item is not None:
                self._canvas.itemconfigure(self._fps_bg_item, image=self._fps_photo)
            self._fps_applied_tier = tier
            self._fps_applied_mood_key = self.mood.key

        ink = fps_badge_ink_hex(self.mood, tier)
        if self._fps_text_item is not None:
            if ink != self._fps_applied_ink:
                self._canvas.itemconfigure(self._fps_text_item, fill=ink)
                self._fps_applied_ink = ink
            if text != self._fps_applied_text:
                self._canvas.itemconfigure(self._fps_text_item, text=text)
                self._fps_applied_text = text

    # -- Top-Left Mesh Faces Badge -------------------------------------------

    def _get_faces_badge(
        self, mood: MoodSpec | str, face_count: int
    ) -> tuple[tk.PhotoImage, float, int]:
        mood_spec = get_mood(mood)
        count = max(0, int(face_count))
        key = (mood_spec.key, count)
        cached = self._faces_photo_cache.get(key)
        if cached is not None:
            return cached
        built = build_faces_badge_photo(
            count,
            self._fps_font_obj,
            height=FACES_BADGE_HEIGHT,
            master=self._root,
            mood=mood_spec,
        )
        self._faces_photo_cache[key] = built
        return built

    def _reposition_faces_items(self) -> None:
        if self._faces_bg_item is not None:
            self._canvas.coords(self._faces_bg_item, self._faces_x, -self._faces_y)
        if self._faces_text_item is not None:
            self._canvas.coords(
                self._faces_text_item,
                self._faces_x + self._faces_text_x_offset - 1.0,
                -self._faces_text_y,
            )

    def _row1_switcher_max_w(self, cw: int) -> int:
        fps_w = self._fps_photo.width() if self._fps_photo is not None else 79
        faces_w = self._faces_photo.width() if self._faces_photo is not None else 0
        left_w = fps_w + (FACES_BADGE_GAP + faces_w if faces_w > 0 else 0.0)
        return max(
            120,
            int(cw - HUD_MARGIN_X - left_w - SWITCHER_MIN_GAP - HUD_MARGIN_X),
        )

    def _init_faces_badge(self) -> None:
        face_count = len(self.mesh.faces)
        self._faces_photo, self._faces_text_x_offset, faces_w = self._get_faces_badge(
            self.mood, face_count
        )
        fps_w = self._fps_photo.width() if self._fps_photo is not None else 79
        self._faces_x = self._fps_x + fps_w * 0.5 + FACES_BADGE_GAP + faces_w * 0.5
        self._faces_y = self._fps_y
        self._faces_text_y = compute_hud_text_y(self._faces_y, self._fps_font_obj)

        self._faces_bg_item = self._tk_canvas.create_image(
            self._faces_x, -self._faces_y, image=self._faces_photo, anchor="center"
        )
        ink = hud_ink_hex(1.0, self.mood)
        text = format_faces_text(face_count)
        self._faces_pen.pencolor(ink)
        self._faces_pen.goto(self._faces_x + self._faces_text_x_offset, self._faces_text_y)
        self._faces_pen.write(text, move=False, align="left", font=self._fps_font_tuple)
        self._faces_text_item = self._faces_pen.items[-1]
        self._faces_applied_count = face_count
        self._faces_applied_mood_key = self.mood.key
        self._faces_applied_ink = ink

    def _update_faces_badge(self) -> None:
        face_count = len(self.mesh.faces)
        if (
            face_count == self._faces_applied_count
            and self.mood.key == self._faces_applied_mood_key
        ):
            return
        old_w = self._faces_photo.width() if self._faces_photo is not None else 0
        self._faces_photo, self._faces_text_x_offset, faces_w = self._get_faces_badge(
            self.mood, face_count
        )
        if self._faces_bg_item is not None:
            self._canvas.itemconfigure(self._faces_bg_item, image=self._faces_photo)
        ink = hud_ink_hex(1.0, self.mood)
        text = format_faces_text(face_count)
        if self._faces_text_item is not None:
            if ink != self._faces_applied_ink:
                self._canvas.itemconfigure(self._faces_text_item, fill=ink)
                self._faces_applied_ink = ink
            self._canvas.itemconfigure(self._faces_text_item, text=text)
        self._faces_applied_count = face_count
        self._faces_applied_mood_key = self.mood.key

        fps_w = self._fps_photo.width() if self._fps_photo is not None else 79
        self._faces_x = self._fps_x + fps_w * 0.5 + FACES_BADGE_GAP + faces_w * 0.5
        self._faces_y = self._fps_y
        self._faces_text_y = compute_hud_text_y(self._faces_y, self._fps_font_obj)
        self._reposition_faces_items()
        if faces_w != old_w and self._hud_ready:
            cw = self._last_viewport[0] if self._last_viewport is not None else WINDOW_WIDTH
            self._switcher_max_w = self._row1_switcher_max_w(cw)

    # -- Top-Right Compact Switcher Pill -------------------------------------

    def _current_switcher_state(self) -> SwitcherState:
        return SwitcherState(
            cultivar_label=self.cultivar.name,
            cultivar_short=self.cultivar.short_name,
            mood_label=self.mood.name,
            mood_short=self.mood.short_name,
            breeze_enabled=self.breeze_enabled,
            detail_lush=(self.detail_tier.key == "lush"),
            mood_is_dark=self.mood.is_dark,
        )

    def _get_switcher_pills(self, layout: SwitcherLayout) -> list[tk.PhotoImage]:
        key = (self.mood.key, layout.pill_width, layout.pill_height, layout.icon_signature)
        cached = self._switcher_pill_cache.get(key)
        if cached is not None:
            return cached
        pills = _bake_transition_pills(
            layout.pill_width,
            layout.pill_height,
            layout.content_left_px,
            layout.item_positions,
            self._root,
            HUD_TRANSITION_STEPS,
            mood=self.mood,
        )
        self._switcher_pill_cache[key] = pills
        return pills

    def _init_switcher_hud(self) -> None:
        assert self._fps_photo is not None
        self._switcher_max_w = self._row1_switcher_max_w(WINDOW_WIDTH)
        self._switcher_bg_item = self._tk_canvas.create_image(
            self._switcher_x, -self._switcher_y, anchor="center"
        )
        self._update_switcher_visual(force_rebuild=True)

    def _update_switcher_visual(self, *, force_rebuild: bool = False) -> None:
        state = self._current_switcher_state()
        layout = resolve_switcher_layout(
            state,
            self._hud_font_obj,
            max_width=self._switcher_max_w,
            height=SWITCHER_HUD_HEIGHT,
        )
        signature = (
            state.cultivar_label,
            state.mood_label,
            state.breeze_enabled,
            state.detail_lush,
            layout.pill_width,
            self.mood.key,
            self._switcher_max_w,
        )

        eased = _smootherstep(self._hud_enable_blend)
        desired_color = hud_ink_hex(eased, self.mood)

        if force_rebuild or signature != self._switcher_applied_signature:
            self._switcher_layout = layout
            self._switcher_transition_pills = self._get_switcher_pills(layout)
            self._switcher_applied_step = -1
            self._switcher_applied_signature = signature

            # Position at top-right based on current viewport right edge
            if self._last_viewport is not None:
                _cw, _ch, _x0, x1, y_top, _y_bot = self._last_viewport
            else:
                x1 = WINDOW_WIDTH * 0.5
                y_top = WINDOW_HEIGHT * 0.5

            self._switcher_x = x1 - HUD_MARGIN_X - layout.pill_width * 0.5
            self._switcher_y = y_top - HUD_MARGIN_Y - layout.pill_height * 0.5
            self._switcher_text_y = compute_hud_text_y(self._switcher_y, self._hud_font_obj)
            self._switcher_hit_rects = place_switcher_hit_rects(
                self._switcher_x, self._switcher_y, layout
            )

            self._switcher_pen.clear()
            self._switcher_pen.pencolor(desired_color)
            rel_entries: list[tuple[float, str]] = [
                (rel_x, label) for _k, rel_x, label in layout.segments
            ]
            rel_entries.extend(layout.separators)
            for rel_x, txt in rel_entries:
                self._switcher_pen.goto(self._switcher_x + rel_x, self._switcher_text_y)
                self._switcher_pen.write(
                    txt, move=False, align="left", font=self._hud_font_tuple
                )
            text_ids = list(self._switcher_pen.items[1:])
            self._switcher_text_items = [
                (rel_x, item_id) for (rel_x, _txt), item_id in zip(rel_entries, text_ids)
            ]
            self._switcher_applied_color = desired_color
            if self._switcher_bg_item is not None:
                self._canvas.coords(
                    self._switcher_bg_item, self._switcher_x, -self._switcher_y
                )
            self._raise_overlays()

        if self._switcher_bg_item is not None and self._switcher_transition_pills:
            max_step = len(self._switcher_transition_pills) - 1
            step_idx = min(max_step, max(0, int(round(eased * max_step))))
            if step_idx != self._switcher_applied_step:
                self._canvas.itemconfigure(
                    self._switcher_bg_item,
                    image=self._switcher_transition_pills[step_idx],
                )
                self._switcher_applied_step = step_idx

        if desired_color != self._switcher_applied_color:
            for _rel_x, item_id in self._switcher_text_items:
                self._canvas.itemconfigure(item_id, fill=desired_color)
            self._switcher_applied_color = desired_color

    # -- Top-Right Species Switcher Pill -------------------------------------

    def _get_species_pills(self, layout: SpeciesPillLayout) -> list[tk.PhotoImage]:
        key = (
            self.mood.key,
            self.species.key,
            self.cultivar.key,
            layout.pill_width,
            layout.pill_height,
            layout.compact_tier,
        )
        cached = self._species_pill_cache.get(key)
        if cached is not None:
            return cached
        pills = _bake_species_transition_pills(
            layout,
            self.cultivar.accent_rgba,
            self.cultivar.accent_disabled_rgba,
            self._root,
            HUD_TRANSITION_STEPS,
            mood=self.mood,
        )
        self._species_pill_cache[key] = pills
        return pills

    def _init_species_hud(self) -> None:
        self._species_max_w = max(120, int(WINDOW_WIDTH - HUD_MARGIN_X * 2))
        self._species_bg_item = self._tk_canvas.create_image(
            self._species_x, -self._species_y, anchor="center"
        )
        self._update_species_visual(force_rebuild=True)

    def _update_species_visual(self, *, force_rebuild: bool = False) -> None:
        layout = resolve_species_pill_layout(
            self.species,
            self._hud_font_obj,
            self._fps_font_obj,
            max_width=self._species_max_w,
            height=SPECIES_HUD_HEIGHT,
        )
        signature = (
            self.species.key,
            self.cultivar.key,
            layout.pill_width,
            self.mood.key,
            self._species_max_w,
        )

        eased = _smootherstep(self._hud_enable_blend)
        desired_color = hud_ink_hex(eased, self.mood)

        if force_rebuild or signature != self._species_applied_signature:
            self._species_layout = layout
            self._species_transition_pills = self._get_species_pills(layout)
            self._species_applied_step = -1
            self._species_applied_signature = signature

            if self._last_viewport is not None:
                _cw, _ch, _x0, x1, y_top, _y_bot = self._last_viewport
            else:
                x1 = WINDOW_WIDTH * 0.5
                y_top = WINDOW_HEIGHT * 0.5

            switcher_h = (
                self._switcher_layout.pill_height
                if self._switcher_layout is not None
                else SWITCHER_HUD_HEIGHT
            )
            switcher_y = (
                self._switcher_y
                if self._switcher_layout is not None
                else (y_top - HUD_MARGIN_Y - switcher_h * 0.5)
            )
            self._species_x = x1 - HUD_MARGIN_X - layout.pill_width * 0.5
            self._species_y = (
                switcher_y - switcher_h * 0.5 - SPECIES_STACK_GAP - layout.pill_height * 0.5
            )
            self._species_text_y = compute_hud_text_y(self._species_y, self._hud_font_obj)
            self._species_hit_rects = place_species_hit_rects(
                self._species_x, self._species_y, layout
            )

            self._species_pen.clear()
            self._species_pen.pencolor(desired_color)
            rel_entries: list[tuple[float, str, tuple[str, int, str]]] = [
                (
                    rel_x,
                    label,
                    self._fps_font_tuple if is_active else self._hud_font_tuple,
                )
                for _k, rel_x, label, is_active in layout.segments
            ]
            for rel_sep_x, sep_txt in layout.separators:
                rel_entries.append((rel_sep_x, sep_txt, self._hud_font_tuple))

            for rel_x, txt, font_tuple in rel_entries:
                self._species_pen.goto(self._species_x + rel_x, self._species_text_y)
                self._species_pen.write(txt, move=False, align="left", font=font_tuple)
            text_ids = list(self._species_pen.items[1:])
            self._species_text_items = [
                (rel_x, item_id) for (rel_x, _txt, _ft), item_id in zip(rel_entries, text_ids)
            ]
            self._species_applied_color = desired_color
            if self._species_bg_item is not None:
                self._canvas.coords(
                    self._species_bg_item, self._species_x, -self._species_y
                )
            self._raise_overlays()

        if self._species_bg_item is not None and self._species_transition_pills:
            max_step = len(self._species_transition_pills) - 1
            step_idx = min(max_step, max(0, int(round(eased * max_step))))
            if step_idx != self._species_applied_step:
                self._canvas.itemconfigure(
                    self._species_bg_item,
                    image=self._species_transition_pills[step_idx],
                )
                self._species_applied_step = step_idx

        if desired_color != self._species_applied_color:
            for _rel_x, item_id in self._species_text_items:
                self._canvas.itemconfigure(item_id, fill=desired_color)
            self._species_applied_color = desired_color

    # -- Top-Left BGM Player Pill --------------------------------------------

    def _get_bgm_pill_step(
        self, layout: BgmPillLayout, step_idx: int, *, playing: bool
    ) -> tk.PhotoImage:
        step = max(0, min(HUD_TRANSITION_STEPS, int(step_idx)))
        key = (
            self.mood.key,
            layout.pill_width,
            layout.pill_height,
            layout.icon_signature,
            playing,
            step,
        )
        cached = self._bgm_step_cache.get(key)
        if cached is not None:
            return cached
        rows_geom = _compute_pill_geometry(layout.pill_width, layout.pill_height)
        photo = _bake_transition_pill_step(
            layout.pill_width,
            layout.pill_height,
            rows_geom,
            0,
            layout.item_positions,
            self._root,
            step,
            HUD_TRANSITION_STEPS,
            self.mood,
        )
        self._bgm_step_cache[key] = photo
        return photo

    def _bgm_visualizer_hex(self, is_playing: bool, eased: float) -> str:
        if is_playing and not self._controls_locked:
            accent_rgb = self.cultivar.accent_rgba[:3]
            if self.mood.is_dark:
                accent_rgb = _lerp_rgb(accent_rgb, (242, 238, 232), 0.30)
            r, g, b = _lerp_rgb(self.mood.ink_disabled_rgb, accent_rgb, eased)
            return f"#{r:02x}{g:02x}{b:02x}"
        return hud_ink_hex(eased, self.mood)

    def _init_bgm_hud(self) -> None:
        self._bgm_bg_item = self._tk_canvas.create_image(
            self._bgm_x, -self._bgm_y, anchor="center"
        )
        viz_color = self._bgm_visualizer_hex(
            self._bgm_player.is_playing, _smootherstep(self._hud_enable_blend)
        )
        self._bgm_applied_viz_color = viz_color
        self._bgm_viz_items = [
            self._tk_canvas.create_line(
                0.0,
                0.0,
                0.0,
                0.0,
                width=BGM_VIZ_BAR_WIDTH,
                capstyle="round",
                fill=viz_color,
            )
            for _ in range(BGM_VIZ_BAR_COUNT)
        ]
        self._bgm_tooltip_bg_item = self._tk_canvas.create_image(
            0.0, 0.0, anchor="center", state="hidden"
        )
        self._bgm_tooltip_text_item = self._tk_canvas.create_text(
            0.0,
            0.0,
            text="",
            font=self._hud_font_tuple,
            fill=hud_ink_hex(1.0, self.mood),
            anchor="s",
            state="hidden",
        )
        self._update_bgm_visual(force_rebuild=True)

    def _is_expanded_window_mode(self) -> bool:
        if self.fullscreen:
            return True
        try:
            if str(self._root.state()).lower() == "zoomed":
                return True
        except tk.TclError:
            pass
        for attr in ("-fullscreen", "-zoomed"):
            try:
                if bool(self._root.attributes(attr)):
                    return True
            except tk.TclError:
                pass
        return False

    def _bgm_tooltip_label(self, key: str) -> str:
        if key == "play_pause":
            return "A: Pause" if self._bgm_player.is_playing else "A: Resume"
        if key == "prev":
            return "S: Previous"
        if key == "next":
            return "D: Next"
        return ""

    def _update_bgm_tooltip(self) -> None:
        bg_item = self._bgm_tooltip_bg_item
        txt_item = self._bgm_tooltip_text_item
        if bg_item is None or txt_item is None:
            return

        hover_key = self._bgm_tooltip_hover_key
        hidden = (
            hover_key is None
            or self._controls_locked
            or self._dragging
            or self._dragging_speed
            or self._dragging_bloom
            or self._is_expanded_window_mode()
        )
        target_rect: SegmentHitRect | None = None
        if not hidden:
            for rect in self._bgm_hit_rects:
                if rect.key == hover_key:
                    target_rect = rect
                    break
        if target_rect is None:
            if self._bgm_tooltip_applied_state is not None:
                self._canvas.itemconfigure(bg_item, state="hidden")
                self._canvas.itemconfigure(txt_item, state="hidden")
                self._bgm_tooltip_applied_state = None
            return

        label = self._bgm_tooltip_label(target_rect.key)
        if not label:
            return
        cache_key = (self.mood.key, label)
        cached = self._bgm_tooltip_cache.get(cache_key)
        if cached is None:
            cached = build_tooltip_pill_photo(
                label,
                self._hud_font_obj,
                height=BGM_TOOLTIP_HEIGHT,
                master=self._root,
                mood=self.mood,
            )
            self._bgm_tooltip_cache[cache_key] = cached
        photo, tip_w = cached

        if self._last_viewport is not None:
            _cw, _ch, x0, x1, _y_top, _y_bot = self._last_viewport
        else:
            x0 = -WINDOW_WIDTH * 0.5
            x1 = WINDOW_WIDTH * 0.5

        anchor_x = target_rect.icon_x + 7.0
        min_cx = x0 + HUD_MARGIN_X + tip_w * 0.5
        max_cx = x1 - HUD_MARGIN_X - tip_w * 0.5
        tip_x = _clamp(anchor_x, min_cx, max(min_cx, max_cx))
        tip_y = (
            self._bgm_y
            - BGM_HUD_HEIGHT * 0.5
            - BGM_TOOLTIP_GAP
            - BGM_TOOLTIP_HEIGHT * 0.5
        )
        tip_text_y = compute_hud_text_y(tip_y, self._hud_font_obj)
        ink_hex = hud_ink_hex(1.0, self.mood)

        state = (target_rect.key, label, self.mood.key, round(tip_x, 2), round(tip_y, 2))
        if state != self._bgm_tooltip_applied_state:
            self._canvas.itemconfigure(bg_item, image=photo, state="normal")
            self._canvas.coords(bg_item, tip_x, -tip_y)
            self._canvas.itemconfigure(
                txt_item, text=label, fill=ink_hex, state="normal"
            )
            self._canvas.coords(txt_item, tip_x, -tip_text_y)
            self._canvas.tag_raise(bg_item)
            self._canvas.tag_raise(txt_item)
            self._bgm_tooltip_applied_state = state

    def _update_bgm_visual(self, *, force_rebuild: bool = False) -> None:
        track = self._bgm_player.current_track
        title = track.title if track is not None else "No Audio"
        track_key = str(track.path) if track is not None else ""
        is_playing, elapsed_sec, duration_sec, _bands = self._bgm_player.snapshot()
        if track_key != self._bgm_applied_track_key:
            self._bgm_known_duration = duration_sec
            self._bgm_applied_track_key = track_key
        elif duration_sec > 0.0:
            self._bgm_known_duration = duration_sec
        dur = self._bgm_known_duration

        show_labels = self._is_expanded_window_mode()
        if not show_labels:
            self._bgm_label_blend = 0.0 if is_playing else 1.0
            slot_w_override: int | None = None
            resize_step = 0
            play_btn_label = ""
        else:
            w_pause = int(self._hud_font_obj.measure("A: Pause"))
            w_resume = int(self._hud_font_obj.measure("A: Resume"))
            eased_resize = _smootherstep(self._bgm_label_blend)
            resize_step = min(
                BGM_RESIZE_STEPS,
                max(0, int(round(eased_resize * BGM_RESIZE_STEPS))),
            )
            slot_w_override = int(
                round(_lerp(w_pause, w_resume, resize_step / float(BGM_RESIZE_STEPS)))
            )
            play_btn_label = (
                "A: Pause" if (is_playing or eased_resize < 0.78) else "A: Resume"
            )

        active_layout = resolve_bgm_pill_layout(
            title,
            dur,
            is_playing,
            self._hud_font_obj,
            self._fps_font_obj,
            show_labels=show_labels,
            max_width=self._bgm_max_w,
            height=BGM_HUD_HEIGHT,
            play_slot_w_override=slot_w_override,
        )
        text_signature = (
            active_layout.title_text,
            active_layout.time_sample,
            active_layout.show_labels,
            tuple(btn_key for btn_key, _rx, _lbl in active_layout.button_segments),
            len(active_layout.separators),
            self.mood.key,
            int(self._bgm_max_w or 0),
        )

        eased = _smootherstep(self._hud_enable_blend)
        step_idx = min(
            HUD_TRANSITION_STEPS,
            max(0, int(round(eased * HUD_TRANSITION_STEPS))),
        )
        desired_color = hud_ink_hex(eased, self.mood)
        time_text = format_bgm_time(elapsed_sec, dur, compact=active_layout.compact_time)

        geom_signature = (
            active_layout.pill_width,
            active_layout.icon_signature,
            is_playing,
            resize_step,
            self.mood.key,
            step_idx,
        )

        if self._last_viewport is not None:
            _cw, _ch, x0, _x1, y_top, _y_bot = self._last_viewport
        else:
            x0 = -WINDOW_WIDTH * 0.5
            y_top = WINDOW_HEIGHT * 0.5
        fps_y = (
            self._fps_y
            if self._fps_bg_item is not None
            else (y_top - HUD_MARGIN_Y - FPS_BADGE_HEIGHT * 0.5)
        )

        if force_rebuild or text_signature != self._bgm_applied_text_signature:
            self._bgm_layout = active_layout
            self._bgm_applied_text_signature = text_signature
            self._bgm_applied_geom_signature = None
            self._bgm_applied_step = -1
            self._bgm_applied_playing = is_playing
            self._bgm_applied_play_label = play_btn_label

            self._bgm_x = x0 + HUD_MARGIN_X + active_layout.pill_width * 0.5
            self._bgm_y = (
                fps_y - FPS_BADGE_HEIGHT * 0.5 - BGM_STACK_GAP - active_layout.pill_height * 0.5
            )
            self._bgm_text_y = compute_hud_text_y(self._bgm_y, self._hud_font_obj)
            self._bgm_hit_rects = place_bgm_hit_rects(
                self._bgm_x, self._bgm_y, active_layout
            )

            self._bgm_pen.clear()
            self._bgm_pen.pencolor(desired_color)
            self._bgm_btn_text_items.clear()
            self._bgm_sep_items.clear()

            self._bgm_pen.goto(self._bgm_x + active_layout.title_x_offset, self._bgm_text_y)
            self._bgm_pen.write(
                active_layout.title_text,
                move=False,
                align="left",
                font=self._hud_font_tuple,
            )
            self._bgm_title_item = self._bgm_pen.items[-1]

            self._bgm_pen.goto(self._bgm_x + active_layout.time_x_offset, self._bgm_text_y)
            self._bgm_pen.write(
                time_text, move=False, align="left", font=self._fps_font_tuple
            )
            self._bgm_time_item = self._bgm_pen.items[-1]

            for btn_key, rel_x, btn_label in active_layout.button_segments:
                rendered_label = play_btn_label if btn_key == "play_pause" else btn_label
                self._bgm_pen.goto(self._bgm_x + rel_x, self._bgm_text_y)
                self._bgm_pen.write(
                    rendered_label, move=False, align="left", font=self._hud_font_tuple
                )
                self._bgm_btn_text_items[btn_key] = self._bgm_pen.items[-1]

            for rel_x, sep_txt in active_layout.separators:
                self._bgm_pen.goto(self._bgm_x + rel_x, self._bgm_text_y)
                self._bgm_pen.write(
                    sep_txt, move=False, align="left", font=self._hud_font_tuple
                )
                self._bgm_sep_items.append((rel_x, self._bgm_pen.items[-1]))

            self._bgm_applied_time_text = time_text
            self._bgm_applied_color = desired_color
            self._bgm_viz_applied_levels = [-1.0] * BGM_VIZ_BAR_COUNT

            if self._bgm_bg_item is not None:
                self._canvas.coords(self._bgm_bg_item, self._bgm_x, -self._bgm_y)
            self._reposition_bgm_viz_items()
            self._raise_overlays()
        elif geom_signature != self._bgm_applied_geom_signature:
            prev_layout = self._bgm_layout
            self._bgm_layout = active_layout
            self._bgm_applied_playing = is_playing
            if play_btn_label != self._bgm_applied_play_label:
                play_txt_id = self._bgm_btn_text_items.get("play_pause")
                if play_txt_id is not None:
                    self._canvas.itemconfigure(play_txt_id, text=play_btn_label)
                self._bgm_applied_play_label = play_btn_label
            if (
                prev_layout is None
                or active_layout.pill_width != prev_layout.pill_width
                or active_layout.button_segments != prev_layout.button_segments
                or active_layout.separators != prev_layout.separators
            ):
                self._bgm_x = x0 + HUD_MARGIN_X + active_layout.pill_width * 0.5
                self._bgm_y = (
                    fps_y
                    - FPS_BADGE_HEIGHT * 0.5
                    - BGM_STACK_GAP
                    - active_layout.pill_height * 0.5
                )
                self._bgm_text_y = compute_hud_text_y(self._bgm_y, self._hud_font_obj)
                self._bgm_hit_rects = place_bgm_hit_rects(
                    self._bgm_x, self._bgm_y, active_layout
                )
                self._reposition_bgm_items()

        if self._bgm_bg_item is not None and geom_signature != self._bgm_applied_geom_signature:
            pill_photo = self._get_bgm_pill_step(active_layout, step_idx, playing=is_playing)
            self._canvas.itemconfigure(self._bgm_bg_item, image=pill_photo)
            self._bgm_applied_step = step_idx
            self._bgm_applied_geom_signature = geom_signature

        if desired_color != self._bgm_applied_color:
            for item_id in (self._bgm_title_item, self._bgm_time_item):
                if item_id is not None:
                    self._canvas.itemconfigure(item_id, fill=desired_color)
            for item_id in self._bgm_btn_text_items.values():
                self._canvas.itemconfigure(item_id, fill=desired_color)
            for _rel_x, item_id in self._bgm_sep_items:
                self._canvas.itemconfigure(item_id, fill=desired_color)
            self._bgm_applied_color = desired_color

        viz_color = self._bgm_visualizer_hex(is_playing, eased)
        if viz_color != self._bgm_applied_viz_color:
            for bar_id in self._bgm_viz_items:
                self._canvas.itemconfigure(bar_id, fill=viz_color)
            self._bgm_applied_viz_color = viz_color

    def _reposition_bgm_items(self) -> None:
        if self._bgm_bg_item is not None:
            self._canvas.coords(self._bgm_bg_item, self._bgm_x, -self._bgm_y)
        if self._bgm_layout is None:
            return
        if self._bgm_title_item is not None:
            self._canvas.coords(
                self._bgm_title_item,
                self._bgm_x + self._bgm_layout.title_x_offset - 1.0,
                -self._bgm_text_y,
            )
        if self._bgm_time_item is not None:
            self._canvas.coords(
                self._bgm_time_item,
                self._bgm_x + self._bgm_layout.time_x_offset - 1.0,
                -self._bgm_text_y,
            )
        for btn_key, rel_x, _btn_lbl in self._bgm_layout.button_segments:
            item_id = self._bgm_btn_text_items.get(btn_key)
            if item_id is not None:
                self._canvas.coords(
                    item_id, self._bgm_x + rel_x - 1.0, -self._bgm_text_y
                )
        for (rel_x, _sep_txt), (_old_rel_x, item_id) in zip(
            self._bgm_layout.separators, self._bgm_sep_items
        ):
            self._canvas.coords(
                item_id, self._bgm_x + rel_x - 1.0, -self._bgm_text_y
            )
        self._reposition_bgm_viz_items()

    def _reposition_bgm_viz_items(self) -> None:
        layout = self._bgm_layout
        if layout is None:
            return
        for idx, bar_id in enumerate(self._bgm_viz_items):
            rel_vx = layout.viz_bar_xs[idx]
            vx = self._bgm_x + rel_vx
            half_h = self._bgm_viz_levels[idx]
            self._canvas.coords(bar_id, vx, -self._bgm_y - half_h, vx, -self._bgm_y + half_h)
            self._bgm_viz_applied_levels[idx] = half_h

    def _update_bgm_frame(self, dt: float) -> None:
        layout = self._bgm_layout
        if layout is None:
            return
        track = self._bgm_player.current_track
        track_key = str(track.path) if track is not None else ""
        is_playing, elapsed_sec, duration_sec, bands = self._bgm_player.snapshot()
        if track_key != self._bgm_applied_track_key or (
            duration_sec > 0.0 and abs(duration_sec - self._bgm_known_duration) > 1.0
        ):
            self._bgm_known_duration = duration_sec
            self._bgm_applied_track_key = track_key
            if self._last_viewport is not None:
                self._bgm_max_w, self._species_max_w = self._resolve_row2_budgets(
                    self._last_viewport[0],
                    show_labels=self._is_expanded_window_mode(),
                )
                self._update_species_visual(force_rebuild=False)
            self._update_bgm_visual(force_rebuild=True)
            self._update_bgm_tooltip()
            layout = self._bgm_layout
            if layout is None:
                return

        show_labels = self._is_expanded_window_mode()
        target_label_blend = 0.0 if is_playing else 1.0
        blend_changed = False
        if not show_labels:
            if self._bgm_label_blend != target_label_blend:
                self._bgm_label_blend = target_label_blend
                blend_changed = True
        elif self._bgm_label_blend != target_label_blend:
            if BGM_RESIZE_DURATION <= 0.0:
                self._bgm_label_blend = target_label_blend
            else:
                delta = dt / BGM_RESIZE_DURATION
                if self._bgm_label_blend < target_label_blend:
                    self._bgm_label_blend = min(
                        target_label_blend, self._bgm_label_blend + delta
                    )
                else:
                    self._bgm_label_blend = max(
                        target_label_blend, self._bgm_label_blend - delta
                    )
            blend_changed = True

        if blend_changed or is_playing != self._bgm_applied_playing:
            self._update_bgm_visual(force_rebuild=False)
            layout = self._bgm_layout
            if layout is None:
                return

        time_text = format_bgm_time(
            elapsed_sec, self._bgm_known_duration, compact=layout.compact_time
        )
        if time_text != self._bgm_applied_time_text and self._bgm_time_item is not None:
            self._canvas.itemconfigure(self._bgm_time_item, text=time_text)
            self._bgm_applied_time_text = time_text

        eased = _smootherstep(self._hud_enable_blend)
        viz_color = self._bgm_visualizer_hex(is_playing, eased)
        if viz_color != self._bgm_applied_viz_color:
            for bar_id in self._bgm_viz_items:
                self._canvas.itemconfigure(bar_id, fill=viz_color)
            self._bgm_applied_viz_color = viz_color

        attack = 1.0 - math.exp(-22.0 * dt)
        decay = 1.0 - math.exp(-9.0 * dt)
        for idx, bar_id in enumerate(self._bgm_viz_items):
            energy = bands[idx] if is_playing else 0.0
            target_h = _lerp(BGM_VIZ_MIN_HALF_H, BGM_VIZ_MAX_HALF_H, energy)
            cur_h = self._bgm_viz_levels[idx]
            rate = attack if target_h > cur_h else decay
            new_h = cur_h + (target_h - cur_h) * rate
            self._bgm_viz_levels[idx] = new_h
            if abs(new_h - self._bgm_viz_applied_levels[idx]) >= 0.03:
                vx = self._bgm_x + layout.viz_bar_xs[idx]
                self._canvas.coords(
                    bar_id, vx, -self._bgm_y - new_h, vx, -self._bgm_y + new_h
                )
                self._bgm_viz_applied_levels[idx] = new_h

    # -- HUD Positioning & Viewport Sync -------------------------------------

    def _speed_fraction(self) -> float:
        span = ROTATION_SPEED_MAX - ROTATION_SPEED_MIN
        if span <= 1e-9:
            return 0.0
        return _clamp((self.rotation_speed - ROTATION_SPEED_MIN) / span, 0.0, 1.0)

    def _reposition_hud_items(self) -> None:
        if self._hud_bg_item is not None:
            self._canvas.coords(self._hud_bg_item, self._hud_x, -self._hud_y)

        segments = (
            self._hud_segments_paused
            if self._hud_segments_is_paused
            else self._hud_segments_playing
        )
        for item_id, (seg_x, _label) in zip(self._hud_text_items, segments):
            self._canvas.coords(item_id, self._hud_x + seg_x - 1.0, -self._hud_text_y)

        if self._fps_bg_item is not None:
            self._canvas.coords(self._fps_bg_item, self._fps_x, -self._fps_y)
        if self._fps_text_item is not None:
            self._canvas.coords(
                self._fps_text_item,
                self._fps_x + self._fps_text_x_offset - 1.0,
                -self._fps_text_y,
            )

        self._reposition_faces_items()

        if self._switcher_bg_item is not None:
            self._canvas.coords(self._switcher_bg_item, self._switcher_x, -self._switcher_y)
        for rel_x, item_id in self._switcher_text_items:
            self._canvas.coords(
                item_id, self._switcher_x + rel_x - 1.0, -self._switcher_text_y
            )

        self._reposition_bgm_items()

        if self._species_bg_item is not None:
            self._canvas.coords(self._species_bg_item, self._species_x, -self._species_y)
        for rel_x, item_id in self._species_text_items:
            self._canvas.coords(
                item_id, self._species_x + rel_x - 1.0, -self._species_text_y
            )

        self._speed_slider.reposition()
        self._bloom_slider.reposition()

    def _resolve_row2_budgets(
        self, cw: int, *, show_labels: bool = False
    ) -> tuple[int, int]:
        """Compute non-overlapping Row 2 max widths for the BGM (left) and Species (right) pills."""
        row2_avail = max(120, int(cw - HUD_MARGIN_X * 2))
        full_species_w = resolve_species_pill_layout(
            self.species,
            self._hud_font_obj,
            self._fps_font_obj,
            max_width=None,
            height=SPECIES_HUD_HEIGHT,
        ).pill_width
        tier2_species_w = resolve_species_pill_layout(
            self.species,
            self._hud_font_obj,
            self._fps_font_obj,
            max_width=320,
            height=SPECIES_HUD_HEIGHT,
        ).pill_width
        track = self._bgm_player.current_track
        title = track.title if track is not None else "No Audio"
        full_bgm_w = resolve_bgm_pill_layout(
            title,
            self._bgm_known_duration,
            False,
            self._hud_font_obj,
            self._fps_font_obj,
            show_labels=show_labels,
            max_width=None,
            height=BGM_HUD_HEIGHT,
        ).pill_width

        if full_bgm_w + SWITCHER_MIN_GAP + full_species_w <= row2_avail:
            return (full_bgm_w, full_species_w)

        tier2_bgm_budget = int(row2_avail - SWITCHER_MIN_GAP - tier2_species_w)
        min_comfortable = 380 if show_labels else 250
        if tier2_bgm_budget >= min_comfortable:
            return (max(210, tier2_bgm_budget), tier2_species_w)

        species_probe = resolve_species_pill_layout(
            self.species,
            self._hud_font_obj,
            self._fps_font_obj,
            max_width=max(84, int(row2_avail * 0.28)),
            height=SPECIES_HUD_HEIGHT,
        )
        bgm_budget = max(140, int(row2_avail - SWITCHER_MIN_GAP - species_probe.pill_width))
        return (bgm_budget, species_probe.pill_width)

    def _sync_hud_to_viewport(self) -> None:
        self._resize_after_id = None
        if not self.running:
            return
        try:
            cw = self._tk_canvas.winfo_width()
            ch = self._tk_canvas.winfo_height()
            if cw <= 1 or ch <= 1:
                return
            x0 = float(self._tk_canvas.canvasx(0))
            x1 = float(self._tk_canvas.canvasx(cw))
            y_top = -float(self._tk_canvas.canvasy(0))
            y_bottom = -float(self._tk_canvas.canvasy(ch))
        except tk.TclError:
            return

        viewport = (cw, ch, x0, x1, y_top, y_bottom)
        expanded = self._is_expanded_window_mode()
        if viewport == self._last_viewport and expanded == self._last_expanded_mode:
            return
        self._last_viewport = viewport
        self._last_expanded_mode = expanded
        self._viewport_fov_scale = FOV_SCALE * _clamp(
            min(cw, ch) / float(WINDOW_SIZE), 0.4, 4.0
        )

        cx_mid = (x0 + x1) * 0.5
        self._hud_x = cx_mid
        self._hud_y = y_bottom + HUD_MARGIN_Y + HUD_HEIGHT * 0.5
        self._hud_text_y = compute_hud_text_y(self._hud_y, self._hud_font_obj)

        # Top-left FPS & mesh Faces badges
        fps_w = self._fps_photo.width() if self._fps_photo is not None else 79
        faces_w = self._faces_photo.width() if self._faces_photo is not None else 96
        self._fps_x = x0 + HUD_MARGIN_X + fps_w * 0.5
        self._fps_y = y_top - HUD_MARGIN_Y - FPS_BADGE_HEIGHT * 0.5
        self._fps_text_y = compute_hud_text_y(self._fps_y, self._fps_font_obj)
        self._faces_x = self._fps_x + fps_w * 0.5 + FACES_BADGE_GAP + faces_w * 0.5
        self._faces_y = self._fps_y
        self._faces_text_y = compute_hud_text_y(self._faces_y, self._fps_font_obj)

        # Top-right compact switcher pill & Row 2 pills (BGM left, Species right)
        self._switcher_max_w = self._row1_switcher_max_w(cw)
        self._update_switcher_visual(force_rebuild=True)
        self._bgm_max_w, self._species_max_w = self._resolve_row2_budgets(
            cw, show_labels=expanded
        )
        self._update_bgm_visual(force_rebuild=True)
        self._update_species_visual(force_rebuild=True)

        # Bottom HUD pill responsive width
        desired_max_w = max(240, cw - 24)
        self._hud_max_w = desired_max_w
        desired_layout = resolve_bottom_hud_layout(
            False, self._hud_font_obj, max_width=desired_max_w
        )
        cur_pill_w = self._hud_pill_playing.width() if self._hud_pill_playing else 0
        if (
            desired_layout.pill_width != cur_pill_w
            or desired_layout.compact != self._hud_is_compact
        ):
            self._rebuild_hud_pills(desired_max_w, layout_playing=desired_layout)
            self._update_hud_text(force_rebuild_text=True)

        # Dual slider row (side-by-side when wide enough, stacked Bloom-over-Speed when narrow)
        speed_layout = self._speed_slider.layout
        bloom_layout = self._bloom_slider.layout
        if speed_layout is not None and bloom_layout is not None:
            side_by_side_w = speed_layout.pill_width + SLIDER_ROW_GAP + bloom_layout.pill_width
            max_row_w = cw - 24
            if side_by_side_w <= max_row_w:
                row_y = self._hud_y + HUD_HEIGHT * 0.5 + SLIDER_STACK_GAP + SLIDER_HUD_HEIGHT * 0.5
                group_left = cx_mid - side_by_side_w * 0.5
                self._speed_slider.set_position(
                    group_left + speed_layout.pill_width * 0.5, row_y
                )
                self._bloom_slider.set_position(
                    group_left
                    + speed_layout.pill_width
                    + SLIDER_ROW_GAP
                    + bloom_layout.pill_width * 0.5,
                    row_y,
                )
            else:
                speed_y = (
                    self._hud_y
                    + HUD_HEIGHT * 0.5
                    + SLIDER_STACK_GAP
                    + speed_layout.pill_height * 0.5
                )
                bloom_y = (
                    speed_y
                    + speed_layout.pill_height * 0.5
                    + SLIDER_STACK_GAP
                    + bloom_layout.pill_height * 0.5
                )
                self._speed_slider.set_position(cx_mid, speed_y)
                self._bloom_slider.set_position(cx_mid, bloom_y)

        self._reposition_hud_items()
        self._recompute_bottom_hud_hit_rects()
        self._update_bgm_tooltip()

    def _on_canvas_configure(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_after_id is None and self.running:
            self._resize_after_id = self._root.after_idle(self._sync_hud_to_viewport)

    def _on_pool_grow(self) -> None:
        if self._hud_ready:
            self._raise_overlays()

    def _raise_overlays(self) -> None:
        if self._hud_bg_item is not None:
            self._canvas.tag_raise(self._hud_bg_item)
        for item_id in self._hud_text_items:
            self._canvas.tag_raise(item_id)
        self._speed_slider.raise_items()
        self._bloom_slider.raise_items()
        for item_id in (
            self._fps_bg_item,
            self._fps_text_item,
            self._faces_bg_item,
            self._faces_text_item,
            self._switcher_bg_item,
            self._bgm_bg_item,
            self._bgm_title_item,
            self._bgm_time_item,
            self._species_bg_item,
        ):
            if item_id is not None:
                self._canvas.tag_raise(item_id)
        for bar_id in self._bgm_viz_items:
            self._canvas.tag_raise(bar_id)
        for item_id in self._bgm_btn_text_items.values():
            self._canvas.tag_raise(item_id)
        for _rel_x, item_id in self._bgm_sep_items:
            self._canvas.tag_raise(item_id)
        for _rel_x, item_id in self._switcher_text_items:
            self._canvas.tag_raise(item_id)
        for _rel_x, item_id in self._species_text_items:
            self._canvas.tag_raise(item_id)
        for item_id in (self._bgm_tooltip_bg_item, self._bgm_tooltip_text_item):
            if item_id is not None:
                self._canvas.tag_raise(item_id)

    def _update_hud_text(self, *, force_rebuild_text: bool = False) -> None:
        max_step = max(0, len(self._hud_transition_pills) - 1)
        eased = _smootherstep(self._hud_enable_blend)
        step_idx = min(max_step, max(0, int(round(eased * max_step))))
        use_paused_layout = (
            self.paused and not self._controls_locked and step_idx >= max_step
        )
        desired_color = hud_ink_hex(eased, self.mood)

        if use_paused_layout:
            pill_photo = self._hud_pill_paused
            segments = self._hud_segments_paused
            target_step = -2
        else:
            pill_photo = (
                self._hud_transition_pills[step_idx]
                if self._hud_transition_pills
                else None
            )
            segments = self._hud_segments_playing
            target_step = step_idx

        if self._hud_bg_item is not None and pill_photo is not None:
            if force_rebuild_text or target_step != self._hud_applied_step:
                self._canvas.itemconfigure(self._hud_bg_item, image=pill_photo)
                self._hud_applied_step = target_step

        if force_rebuild_text or use_paused_layout != self._hud_segments_is_paused:
            self._hud_pen.clear()
            self._hud_pen.pencolor(desired_color)
            for x_pos, label in segments:
                self._hud_pen.goto(self._hud_x + x_pos, self._hud_text_y)
                self._hud_pen.write(label, move=False, align="left", font=self._hud_font_tuple)
            self._hud_text_items = list(self._hud_pen.items[1:])
            self._hud_segments_is_paused = use_paused_layout
            self._hud_applied_color = desired_color
            self._raise_overlays()
        elif desired_color != self._hud_applied_color:
            for item_id in self._hud_text_items:
                self._canvas.itemconfigure(item_id, fill=desired_color)
            self._hud_applied_color = desired_color

        self._speed_slider.update_visual(
            fraction=self._speed_fraction(),
            value_text=f"{self.rotation_speed:.1f}x",
            blend=self._hud_enable_blend,
            step_idx=step_idx,
            ink_color=desired_color,
            cultivar=self.cultivar,
            mood=self.mood,
        )
        self._sync_bloom_slider_visual(step_idx=step_idx, ink_color=desired_color)
        if self._switcher_bg_item is not None:
            self._update_switcher_visual(force_rebuild=False)
        if self._bgm_bg_item is not None:
            self._update_bgm_visual(force_rebuild=False)
        if self._species_bg_item is not None:
            self._update_species_visual(force_rebuild=False)

    def _sync_bloom_slider_visual(
        self,
        *,
        step_idx: int | None = None,
        ink_color: str | None = None,
    ) -> None:
        eased = _smootherstep(self._hud_enable_blend)
        if step_idx is None:
            max_step = max(0, len(self._bloom_slider.transition_pills) - 1)
            step_idx = min(max_step, max(0, int(round(eased * max_step))))
        if ink_color is None:
            ink_color = hud_ink_hex(eased, self.mood)
        frac = _clamp(self.current_bloom, BLOOM_MIN, BLOOM_MAX)
        pct_text = f"{int(round(frac * 100.0))}%"
        self._bloom_slider.update_visual(
            fraction=frac,
            value_text=pct_text,
            blend=self._hud_enable_blend,
            step_idx=step_idx,
            ink_color=ink_color,
            cultivar=self.cultivar,
            mood=self.mood,
        )

    # -- Event Binding & Interaction Handlers --------------------------------

    def _bind_events(self) -> None:
        canvas = self._canvas
        self._root.protocol("WM_DELETE_WINDOW", self.close)

        canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        canvas.bind("<B1-Motion>", self._on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        canvas.bind("<Motion>", self._on_mouse_motion)
        canvas.bind("<Leave>", self._on_mouse_leave)
        canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        canvas.bind("<Shift-MouseWheel>", self._on_shift_mouse_wheel)
        canvas.bind("<Button-4>", lambda _e: self._adjust_zoom(1.08))
        canvas.bind("<Button-5>", lambda _e: self._adjust_zoom(1.0 / 1.08))
        canvas.bind("<Shift-Button-4>", lambda _e: self._nudge_bloom(BLOOM_WHEEL_STEP))
        canvas.bind("<Shift-Button-5>", lambda _e: self._nudge_bloom(-BLOOM_WHEEL_STEP))

        self.screen.listen()
        self._bind_key("space", self.toggle_pause)
        self._bind_key("a", self.toggle_bgm)
        self._bind_key("A", self.toggle_bgm)
        self._bind_key("s", self.prev_bgm)
        self._bind_key("S", self.prev_bgm)
        self._bind_key("d", self.next_bgm)
        self._bind_key("D", self.next_bgm)
        self._bind_key("b", self.replay_bloom)
        self._bind_key("B", self.replay_bloom)
        self._bind_key("r", self.reset_view)
        self._bind_key("R", self.reset_view)
        self._bind_key("f", self.cycle_species)
        self._bind_key("F", self.cycle_species)
        for sp_idx in range(len(SPECIES)):
            key_num = str(sp_idx + 1)
            self._bind_key(key_num, lambda idx=sp_idx: self.select_species_index(idx))
            self._bind_key(f"KP_{key_num}", lambda idx=sp_idx: self.select_species_index(idx))
        self._bind_key("c", self.cycle_cultivar)
        self._bind_key("C", self.cycle_cultivar)
        self._bind_key("m", self.cycle_mood)
        self._bind_key("M", self.cycle_mood)
        self._bind_key("w", self.toggle_breeze)
        self._bind_key("W", self.toggle_breeze)
        self._bind_key("t", self.toggle_detail_tier)
        self._bind_key("T", self.toggle_detail_tier)
        self._bind_key("F11", self.toggle_fullscreen)
        self._bind_key("Escape", self._on_escape)
        self._bind_key("plus", lambda: self._adjust_zoom(1.1))
        self._bind_key("equal", lambda: self._adjust_zoom(1.1))
        self._bind_key("minus", lambda: self._adjust_zoom(1.0 / 1.1))
        self._bind_key("Left", lambda: self._nudge_camera(dyaw=-0.12, dpitch=0.0))
        self._bind_key("Right", lambda: self._nudge_camera(dyaw=0.12, dpitch=0.0))
        self._bind_key("Up", lambda: self._nudge_camera(dyaw=0.0, dpitch=0.08))
        self._bind_key("Down", lambda: self._nudge_camera(dyaw=0.0, dpitch=-0.08))

    def _bind_key(self, key: str, callback: Callable[[], None]) -> None:
        self.screen.onkeypress(callback, key)

    def _cancel_camera_transitions(self) -> None:
        self._camera_tween_active = False
        self._species_entry_active = False
        if self._reset_active:
            self._reset_active = False
            self.bloom_done = self.current_bloom >= 1.0
            if not self.bloom_done:
                raw_t = 1.0 - (1.0 - _clamp(self.current_bloom, 0.0, 1.0)) ** (1.0 / 2.4)
                self.bloom_elapsed = raw_t * BLOOM_DURATION

    def _event_to_canvas_coords(self, event: tk.Event[tk.Misc]) -> tuple[float, float]:
        return (
            float(self._tk_canvas.canvasx(event.x)),
            -float(self._tk_canvas.canvasy(event.y)),
        )

    def _set_canvas_cursor(self, cursor: str) -> None:
        if cursor != self._canvas_cursor:
            self._tk_canvas.configure(cursor=cursor)
            self._canvas_cursor = cursor

    def _is_interactive_hud_hit(self, cx: float, cy: float) -> bool:
        return (
            self._speed_slider.contains(cx, cy)
            or self._bloom_slider.contains(cx, cy)
            or (hit_test_switcher(cx, cy, self._switcher_hit_rects) is not None)
            or (hit_test_bgm_pill(cx, cy, self._bgm_hit_rects) is not None)
            or (hit_test_species_pill(cx, cy, self._species_hit_rects) is not None)
            or (hit_test_bottom_hud(cx, cy, self._current_hud_hit_rects()) is not None)
        )

    def toggle_bgm(self) -> None:
        if self._controls_locked:
            return
        self._bgm_player.toggle()
        self._update_bgm_visual(force_rebuild=False)
        self._update_bgm_tooltip()

    def prev_bgm(self) -> None:
        if self._controls_locked:
            return
        self._bgm_player.previous()
        self._bgm_viz_levels = [BGM_VIZ_MIN_HALF_H] * BGM_VIZ_BAR_COUNT

    def next_bgm(self) -> None:
        if self._controls_locked:
            return
        self._bgm_player.next()
        self._bgm_viz_levels = [BGM_VIZ_MIN_HALF_H] * BGM_VIZ_BAR_COUNT

    # -- Botanical Species & Customization Actions ---------------------------

    def set_species(
        self,
        species: SpeciesSpec | str,
        *,
        animate: bool = True,
        force_replay: bool = False,
    ) -> None:
        """Switch active botanical species, restore its cultivar, and replay bloom/framing."""
        spec = get_species(species)
        if spec == self.species and not force_replay:
            return

        self._cultivar_idx_by_species[self.species.key] = self._cultivar_idx
        self.species = spec
        self._species_idx = SPECIES.index(spec)
        self._cultivar_idx = self._cultivar_idx_by_species.get(spec.key, 0) % len(
            spec.cultivars
        )
        self.cultivar = spec.cultivars[self._cultivar_idx]

        bloom_init = 0.0 if animate else self.current_bloom
        self.mesh.set_species(spec, detail_tier=self.detail_tier, bloom=bloom_init)
        self._poly_pool.ensure_capacity(len(self.mesh.faces))

        if animate:
            self._reset_active = False
            self._dragging = False
            self._dragging_speed = False
            self._dragging_bloom = False
            self._inertia.cancel()

            delta_yaw = (spec.default_yaw - self.yaw + math.pi) % (2.0 * math.pi) - math.pi
            self._species_entry_start_yaw = self.yaw
            self._species_entry_target_yaw = self.yaw + delta_yaw
            self._species_entry_start_pitch = self.pitch
            self._species_entry_start_zoom = self.zoom
            self._species_entry_elapsed = 0.0
            self._species_entry_active = True

            self.current_bloom = 0.0
            self.bloom_elapsed = 0.0
            self.bloom_done = False
            self._camera_tween_active = True
            self._tween_elapsed = 0.0
            self._tween_start_pitch = spec.startup_pitch
            self._tween_start_zoom = spec.startup_zoom
            self._sync_bloom_slider_visual()

        self._update_faces_badge()
        self._update_hud_text()

    def cycle_species(self) -> None:
        if self._controls_locked:
            return
        next_idx = (self._species_idx + 1) % len(SPECIES)
        self.set_species(SPECIES[next_idx], animate=True)

    def select_species_index(self, idx: int) -> None:
        if self._controls_locked:
            return
        if 0 <= idx < len(SPECIES):
            self.set_species(SPECIES[idx], animate=True)

    def set_cultivar(self, cultivar: CultivarSpec | str) -> None:
        spec = get_cultivar(cultivar, species=self.species)
        self.cultivar = spec
        self._cultivar_idx = self.species.cultivars.index(spec)
        self._cultivar_idx_by_species[self.species.key] = self._cultivar_idx
        self._update_hud_text()

    def cycle_cultivar(self) -> None:
        if self._controls_locked:
            return
        cultivars = self.species.cultivars
        self._cultivar_idx = (self._cultivar_idx + 1) % len(cultivars)
        self.cultivar = cultivars[self._cultivar_idx]
        self._cultivar_idx_by_species[self.species.key] = self._cultivar_idx
        self._update_hud_text()

    def set_mood(self, mood: MoodSpec | str) -> None:
        spec = get_mood(mood)
        self.mood = spec
        self._mood_idx = MOODS.index(spec)
        self.screen.bgcolor(spec.bg_hex)

        # Warm and apply mood-aware FPS badge preserving current FPS tier
        self._warm_fps_badge_cache_for_mood(spec)
        self._fps_photo, self._fps_text_x_offset = self._get_fps_badge(spec, self._fps_tier)
        if self._fps_bg_item is not None:
            self._canvas.itemconfigure(self._fps_bg_item, image=self._fps_photo)
        ink = fps_badge_ink_hex(spec, self._fps_tier)
        if self._fps_text_item is not None:
            self._canvas.itemconfigure(self._fps_text_item, fill=ink)
        self._fps_applied_tier = self._fps_tier
        self._fps_applied_ink = ink
        self._fps_applied_mood_key = spec.key
        self._update_faces_badge()

        self._rebuild_hud_pills(self._hud_max_w)
        self._speed_slider.apply_mood(spec)
        self._bloom_slider.apply_mood(spec)
        self._update_hud_text(force_rebuild_text=False)
        self._reposition_hud_items()
        self._recompute_bottom_hud_hit_rects()
        self._update_bgm_tooltip()

    def cycle_mood(self) -> None:
        if self._controls_locked:
            return
        next_idx = (self._mood_idx + 1) % len(MOODS)
        self.set_mood(MOODS[next_idx])

    def toggle_breeze(self) -> None:
        if self._controls_locked:
            return
        self.breeze_enabled = not self.breeze_enabled
        self._update_switcher_visual()

    def set_detail_tier(self, detail_tier: DetailTierSpec | str) -> None:
        spec = resolve_detail_tier(detail_tier)
        if spec == self.detail_tier:
            return
        self.detail_tier = spec
        self.mesh.set_detail_tier(spec, bloom=self.current_bloom)
        self._poly_pool.ensure_capacity(len(self.mesh.faces))
        self._update_faces_badge()
        self._update_switcher_visual()

    def toggle_detail_tier(self) -> None:
        if self._controls_locked:
            return
        next_tier = STANDARD_TIER if self.detail_tier.key == "lush" else LUSH_TIER
        self.set_detail_tier(next_tier)

    # -- Sliders & Mouse/Key Handlers ----------------------------------------

    def set_rotation_speed(self, speed: float) -> None:
        """Set auto-rotation speed multiplier within ``[1.0, 5.0]`` and refresh HUD."""
        clamped = _clamp(float(speed), ROTATION_SPEED_MIN, ROTATION_SPEED_MAX)
        if abs(clamped - self.rotation_speed) < 1e-6:
            return
        self.rotation_speed = clamped
        eased = _smootherstep(self._hud_enable_blend)
        max_step = max(0, len(self._speed_slider.transition_pills) - 1)
        step_idx = min(max_step, max(0, int(round(eased * max_step))))
        self._speed_slider.update_visual(
            fraction=self._speed_fraction(),
            value_text=f"{self.rotation_speed:.1f}x",
            blend=self._hud_enable_blend,
            step_idx=step_idx,
            ink_color=hud_ink_hex(eased, self.mood),
            cultivar=self.cultivar,
            mood=self.mood,
        )

    def set_bloom(self, bloom: float, *, from_user: bool = True) -> None:
        """Set bloom openness in ``[0.0, 1.0]``; manual scrub halts auto-bloom tween."""
        clamped = _clamp(float(bloom), BLOOM_MIN, BLOOM_MAX)
        if from_user:
            self._reset_active = False
            self.bloom_done = True
        if abs(clamped - self.current_bloom) < 1e-6:
            self._sync_bloom_slider_visual()
            return
        self.current_bloom = clamped
        self.mesh.update_bloom(clamped)
        self._sync_bloom_slider_visual()

    def _nudge_bloom(self, delta: float) -> None:
        if self._controls_locked:
            return
        self.set_bloom(self.current_bloom + delta, from_user=True)

    def _set_speed_from_canvas_x(self, cx: float) -> None:
        frac = self._speed_slider.canvas_x_to_fraction(cx)
        self.set_rotation_speed(
            ROTATION_SPEED_MIN + frac * (ROTATION_SPEED_MAX - ROTATION_SPEED_MIN)
        )

    def _set_bloom_from_canvas_x(self, cx: float) -> None:
        frac = self._bloom_slider.canvas_x_to_fraction(cx)
        self.set_bloom(BLOOM_MIN + frac * (BLOOM_MAX - BLOOM_MIN), from_user=True)

    def _on_mouse_leave(self, _event: tk.Event[tk.Misc]) -> None:
        if self._bgm_tooltip_hover_key is not None:
            self._bgm_tooltip_hover_key = None
            self._update_bgm_tooltip()

    def _on_mouse_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self._controls_locked:
            self._set_canvas_cursor("")
            if self._bgm_tooltip_hover_key is not None:
                self._bgm_tooltip_hover_key = None
                self._update_bgm_tooltip()
            return
        if self._dragging_speed or self._dragging_bloom:
            self._set_canvas_cursor("hand2")
            return
        cx, cy = self._event_to_canvas_coords(event)
        bgm_hover = hit_test_bgm_pill(cx, cy, self._bgm_hit_rects)
        if bgm_hover != self._bgm_tooltip_hover_key:
            self._bgm_tooltip_hover_key = bgm_hover
            self._update_bgm_tooltip()
        self._set_canvas_cursor("hand2" if self._is_interactive_hud_hit(cx, cy) else "")

    def _on_mouse_down(self, event: tk.Event[tk.Misc]) -> None:
        self.screen.listen()
        if self._controls_locked:
            return
        cx, cy = self._event_to_canvas_coords(event)

        if self._speed_slider.contains(cx, cy):
            self._dragging_speed = True
            self._dragging_bloom = False
            self._dragging = False
            self._set_canvas_cursor("hand2")
            self._set_speed_from_canvas_x(cx)
            return

        if self._bloom_slider.contains(cx, cy):
            self._dragging_bloom = True
            self._dragging_speed = False
            self._dragging = False
            self._set_canvas_cursor("hand2")
            self._set_bloom_from_canvas_x(cx)
            return

        seg_key = hit_test_switcher(cx, cy, self._switcher_hit_rects)
        if seg_key is not None:
            self._set_canvas_cursor("hand2")
            if seg_key == "cultivar":
                self.cycle_cultivar()
            elif seg_key == "mood":
                self.cycle_mood()
            elif seg_key == "breeze":
                self.toggle_breeze()
            elif seg_key == "detail":
                self.toggle_detail_tier()
            return

        bgm_key = hit_test_bgm_pill(cx, cy, self._bgm_hit_rects)
        if bgm_key is not None:
            self._set_canvas_cursor("hand2")
            if bgm_key == "play_pause":
                self.toggle_bgm()
            elif bgm_key == "prev":
                self.prev_bgm()
            elif bgm_key == "next":
                self.next_bgm()
            return

        sp_key = hit_test_species_pill(cx, cy, self._species_hit_rects)
        if sp_key is not None:
            self._set_canvas_cursor("hand2")
            if self._species_layout is not None and self._species_layout.compact_tier >= 3:
                self.cycle_species()
            else:
                self.set_species(sp_key, animate=True)
            return

        hud_key = hit_test_bottom_hud(cx, cy, self._current_hud_hit_rects())
        if hud_key is not None:
            if hud_key == "pause":
                self.toggle_pause()
            elif hud_key == "bloom":
                self.replay_bloom()
            elif hud_key == "reset":
                self.reset_view()
            if not self._controls_locked:
                self._set_canvas_cursor(
                    "hand2" if self._is_interactive_hud_hit(cx, cy) else ""
                )
            return

        self._cancel_camera_transitions()
        if self._bgm_tooltip_hover_key is not None:
            self._bgm_tooltip_hover_key = None
            self._update_bgm_tooltip()
        self._dragging = True
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y
        self._inertia.begin_drag()

    def _on_mouse_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._controls_locked:
            return
        if self._dragging_speed:
            cx, _cy = self._event_to_canvas_coords(event)
            self._set_speed_from_canvas_x(cx)
            return
        if self._dragging_bloom:
            cx, _cy = self._event_to_canvas_coords(event)
            self._set_bloom_from_canvas_x(cx)
            return
        if not self._dragging:
            return

        dx = event.x - self._last_mouse_x
        dy = event.y - self._last_mouse_y
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y

        dyaw = dx * 0.009
        dpitch = dy * 0.008
        self.yaw += dyaw
        self.pitch = _clamp(self.pitch + dpitch, PITCH_MIN, PITCH_MAX)
        self._inertia.record_drag(dyaw, dpitch)

    def _on_mouse_up(self, event: tk.Event[tk.Misc]) -> None:
        if self._dragging:
            self._dragging = False
            self._inertia.end_drag()
        if self._dragging_speed or self._dragging_bloom:
            self._dragging_speed = False
            self._dragging_bloom = False
            cx, cy = self._event_to_canvas_coords(event)
            hovering = not self._controls_locked and self._is_interactive_hud_hit(cx, cy)
            self._set_canvas_cursor("hand2" if hovering else "")

    def _on_mouse_wheel(self, event: tk.Event[tk.Misc]) -> None:
        if self._controls_locked:
            return
        # Fallback Shift check for platforms routing Shift+Wheel through <MouseWheel>
        state_bits = int(getattr(event, "state", 0))
        if state_bits & 0x0001:
            self._on_shift_mouse_wheel(event)
            return
        factor = 1.08 if event.delta > 0 else (1.0 / 1.08)
        self._adjust_zoom(factor)

    def _on_shift_mouse_wheel(self, event: tk.Event[tk.Misc]) -> str | None:
        if self._controls_locked:
            return "break"
        delta = getattr(event, "delta", 0)
        steps = delta / 120.0 if abs(delta) >= 120 else (1.0 if delta > 0 else -1.0)
        self._nudge_bloom(BLOOM_WHEEL_STEP * steps)
        return "break"

    def _adjust_zoom(self, factor: float) -> None:
        if self._controls_locked:
            return
        self._cancel_camera_transitions()
        self._inertia.impulse_zoom(factor)

    def _nudge_camera(self, dyaw: float, dpitch: float) -> None:
        if self._controls_locked:
            return
        self._cancel_camera_transitions()
        self._inertia.impulse_angles(dyaw=dyaw, dpitch=dpitch)

    def toggle_pause(self) -> None:
        if self._controls_locked:
            return
        self.paused = not self.paused
        self._update_hud_text()

    def replay_bloom(self) -> None:
        if self._controls_locked:
            return
        self._reset_active = False
        self.current_bloom = 0.0
        self.bloom_elapsed = 0.0
        self.bloom_done = False
        self.mesh.update_bloom(0.0)
        self._sync_bloom_slider_visual()

    def set_fullscreen(self, enabled: bool) -> None:
        if enabled == self.fullscreen:
            return
        if enabled:
            self._windowed_geometry = self._root.geometry()
            self.fullscreen = True
            self._root.attributes("-fullscreen", True)
        else:
            self.fullscreen = False
            self._root.attributes("-fullscreen", False)
            if self._windowed_geometry:
                self._root.geometry(self._windowed_geometry)
        self.screen.listen()
        if self._resize_after_id is None and self.running:
            self._resize_after_id = self._root.after_idle(self._sync_hud_to_viewport)

    def toggle_fullscreen(self) -> None:
        self.set_fullscreen(not self.fullscreen)

    def _on_escape(self) -> None:
        if self.fullscreen:
            self.set_fullscreen(False)
        else:
            self.close()

    def _start_startup_sequence(self) -> None:
        self._inertia.cancel()
        self._species_entry_active = False
        self.yaw = self.species.default_yaw
        self.pitch = self.species.startup_pitch
        self.zoom = self.species.startup_zoom
        self.current_bloom = 0.0
        self.bloom_elapsed = 0.0
        self.bloom_done = False
        self._camera_tween_active = True
        self._tween_elapsed = 0.0
        self._tween_start_pitch = self.species.startup_pitch
        self._tween_start_zoom = self.species.startup_zoom
        self.mesh.update_bloom(0.0)
        self._sync_bloom_slider_visual()

    def reset_view(self) -> None:
        """Smoothly transition back to the startup overhead bud, then replay startup."""
        if self._controls_locked:
            return
        self._controls_locked = True
        self._dragging = False
        self._dragging_speed = False
        self._dragging_bloom = False
        self._species_entry_active = False
        self._inertia.cancel()
        self._set_canvas_cursor("")
        self._bgm_tooltip_hover_key = None
        self._update_bgm_tooltip()
        self.paused = False
        self._update_hud_text()
        self._camera_tween_active = False

        delta_yaw = (self.species.default_yaw - self.yaw + math.pi) % (2.0 * math.pi) - math.pi
        nearly_there = (
            abs(delta_yaw) < 1e-3
            and abs(self.pitch - self.species.startup_pitch) < 1e-3
            and abs(self.zoom - self.species.startup_zoom) < 1e-3
            and self.current_bloom < 1e-3
        )
        if nearly_there:
            self._reset_active = False
            self._start_startup_sequence()
            return

        self._reset_start_yaw = self.yaw
        self._reset_target_yaw = self.yaw + delta_yaw
        self._reset_start_pitch = self.pitch
        self._reset_start_zoom = self.zoom
        self._reset_start_bloom = self.current_bloom
        self._reset_elapsed = 0.0
        self._reset_active = True

    def close(self) -> None:
        self.running = False
        self._bgm_player.close()
        for after_attr in ("_after_id", "_resize_after_id"):
            after_id = getattr(self, after_attr, None)
            if after_id is not None:
                try:
                    self._root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, after_attr, None)

        self._poly_pool.clear()
        self._speed_slider.cleanup()
        self._bloom_slider.cleanup()

        for bar_id in self._bgm_viz_items:
            try:
                self._canvas.delete(bar_id)
            except tk.TclError:
                pass
        self._bgm_viz_items.clear()

        for attr in (
            "_hud_bg_item",
            "_fps_bg_item",
            "_faces_bg_item",
            "_switcher_bg_item",
            "_bgm_bg_item",
            "_bgm_tooltip_bg_item",
            "_bgm_tooltip_text_item",
            "_species_bg_item",
        ):
            item_id = getattr(self, attr, None)
            if item_id is not None:
                try:
                    self._canvas.delete(item_id)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

        for pen in (
            self._hud_pen,
            self._fps_pen,
            self._faces_pen,
            self._switcher_pen,
            self._bgm_pen,
            self._species_pen,
        ):
            try:
                pen.clear()
            except (turtle.Terminator, tk.TclError):
                pass

        self._hud_text_items.clear()
        self._switcher_text_items.clear()
        self._species_text_items.clear()
        self._bgm_btn_text_items.clear()
        self._bgm_sep_items.clear()
        self._bgm_title_item = None
        self._bgm_time_item = None
        self._fps_text_item = None
        self._faces_text_item = None
        self._hud_pill_cache.clear()
        self._fps_photo_cache.clear()
        self._faces_photo_cache.clear()
        self._switcher_pill_cache.clear()
        self._bgm_step_cache.clear()
        self._bgm_tooltip_cache.clear()
        self._species_pill_cache.clear()
        self._hud_transition_pills.clear()
        self._switcher_transition_pills.clear()
        self._species_transition_pills.clear()
        self._hud_pill_playing = None
        self._hud_pill_paused = None
        self._hud_pill_disabled = None
        self._fps_photo = None
        self._faces_photo = None
        self._app_icon_photo = None

        try:
            self.screen.bye()
        except (turtle.Terminator, tk.TclError):
            pass

    def _render_frame(self) -> None:
        self._sync_hud_to_viewport()
        draw_list = build_draw_list(
            self.mesh,
            self.yaw,
            self.pitch,
            self.zoom,
            fov_scale=self._viewport_fov_scale,
            cultivar=self.cultivar,
            mood=self.mood,
            breeze_enabled=self.breeze_enabled,
            breeze_time=self.breeze_time,
        )
        self._poly_pool.render(draw_list)
        self._root.update_idletasks()

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
            return

        now = time.perf_counter()
        dt = min(now - self._last_frame_time, 0.08)
        self._last_frame_time = now

        if self.breeze_enabled:
            self.breeze_time += dt

        if self._reset_active:
            self._reset_elapsed += dt
            raw_r = _clamp(self._reset_elapsed / RESET_TRANSITION_DURATION, 0.0, 1.0)
            eased_r = _smootherstep(raw_r)
            self.yaw = _lerp(self._reset_start_yaw, self._reset_target_yaw, eased_r)
            self.pitch = _lerp(
                self._reset_start_pitch, self.species.startup_pitch, eased_r
            )
            self.zoom = _lerp(self._reset_start_zoom, self.species.startup_zoom, eased_r)
            self.current_bloom = _lerp(self._reset_start_bloom, 0.0, eased_r)
            self.mesh.update_bloom(self.current_bloom)
            self._sync_bloom_slider_visual()
            if raw_r >= 1.0:
                self._reset_active = False
                self._start_startup_sequence()
        else:
            if self._species_entry_active:
                self._species_entry_elapsed += dt
                raw_e = _clamp(
                    self._species_entry_elapsed / SPECIES_ENTRY_DURATION, 0.0, 1.0
                )
                eased_e = _smootherstep(raw_e)
                self.yaw = _lerp(
                    self._species_entry_start_yaw, self._species_entry_target_yaw, eased_e
                )
                self.pitch = _lerp(
                    self._species_entry_start_pitch, self.species.startup_pitch, eased_e
                )
                self.zoom = _lerp(
                    self._species_entry_start_zoom, self.species.startup_zoom, eased_e
                )
                if raw_e >= 1.0:
                    self._species_entry_active = False
            elif not self._dragging:
                if not self.paused:
                    self.yaw += AUTO_ROTATE_SPEED * self.rotation_speed * dt
                if self._inertia.is_active:
                    self.yaw, self.pitch, self.zoom = self._inertia.step(
                        self.yaw, self.pitch, self.zoom, dt
                    )

            if not self.bloom_done:
                self.bloom_elapsed += dt
                raw_t = _clamp(self.bloom_elapsed / BLOOM_DURATION, 0.0, 1.0)
                self.current_bloom = 1.0 - (1.0 - raw_t) ** 2.4
                self.mesh.update_bloom(self.current_bloom)
                self._sync_bloom_slider_visual()
                if raw_t >= 1.0:
                    self.bloom_done = True
            elif not self._species_entry_active and self._camera_tween_active:
                self._tween_elapsed += dt
                raw_c = _clamp(self._tween_elapsed / CAMERA_TWEEN_DURATION, 0.0, 1.0)
                eased_c = _smootherstep(raw_c)
                self.pitch = _lerp(
                    self._tween_start_pitch, self.species.default_pitch, eased_c
                )
                self.zoom = _lerp(
                    self._tween_start_zoom, self.species.default_zoom, eased_c
                )
                if raw_c >= 1.0:
                    self._camera_tween_active = False
                    self._controls_locked = False

        target_blend = 0.0 if self._controls_locked else 1.0
        if self._hud_enable_blend != target_blend:
            if HUD_COLOR_TRANSITION_DURATION <= 0.0:
                self._hud_enable_blend = target_blend
            else:
                delta = dt / HUD_COLOR_TRANSITION_DURATION
                if self._hud_enable_blend < target_blend:
                    self._hud_enable_blend = min(target_blend, self._hud_enable_blend + delta)
                else:
                    self._hud_enable_blend = max(target_blend, self._hud_enable_blend - delta)
            self._update_hud_text()

        self._update_bgm_frame(dt)

        try:
            self._render_frame()
            self._fps_frames += 1
            after_render = time.perf_counter()
            fps_dt = after_render - self._fps_window_start
            if fps_dt >= FPS_UPDATE_INTERVAL and self._fps_text_item is not None:
                fps_val = min(float(TARGET_FPS), self._fps_frames / fps_dt)
                self._apply_fps_reading(fps_val)
                self._fps_window_start = after_render
                self._fps_frames = 0

            if self.running:
                self._next_frame_deadline += TARGET_FRAME_INTERVAL
                if self._next_frame_deadline < after_render - TARGET_FRAME_INTERVAL:
                    self._next_frame_deadline = after_render
                remaining = self._next_frame_deadline - after_render
                delay_ms = max(1, int(remaining * 1000.0))
                self._after_id = self._root.after(delay_ms, self._tick)
        except (turtle.Terminator, tk.TclError):
            self.running = False

    def run(self) -> None:
        """Start the animation loop and enter the Tk event loop."""
        winmm = None
        time_period_set = False
        if sys.platform == "win32":
            try:
                import ctypes

                winmm = ctypes.WinDLL("winmm")
                time_period_set = winmm.timeBeginPeriod(1) == 0
            except Exception:
                winmm = None
                time_period_set = False

        self._last_frame_time = time.perf_counter()
        self._fps_window_start = self._last_frame_time
        self._next_frame_deadline = self._last_frame_time
        self._fps_frames = 0
        self._after_id = self._root.after(1, self._tick)
        try:
            turtle.mainloop()
        except (turtle.Terminator, tk.TclError, KeyboardInterrupt):
            self.running = False
        finally:
            if winmm is not None and time_period_set:
                try:
                    winmm.timeEndPeriod(1)
                except Exception:
                    pass


RoseViewerApp = FlowerViewerApp


def _relaunch_windowless_if_needed() -> bool:
    """On Windows, relaunch via pythonw.exe so no terminal/console remains open."""
    if sys.platform != "win32":
        return False
    if (
        "--no-detach" in sys.argv
        or os.environ.get("FLOWERS_DETACHED") == "1"
        or os.environ.get("ROSE_DETACHED") == "1"
    ):
        return False

    exe_path = Path(os.path.abspath(sys.executable))
    if exe_path.name.lower() == "pythonw.exe":
        return False

    candidate = exe_path.with_name("pythonw.exe")
    if not candidate.exists() or candidate.is_symlink() or not candidate.is_file():
        return False

    env = os.environ.copy()
    env["FLOWERS_DETACHED"] = "1"
    flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    )
    script_path = os.path.abspath(__file__)
    try:
        subprocess.Popen(
            [str(candidate), script_path],
            cwd=os.path.dirname(script_path),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=flags,
        )
        return True
    except OSError:
        return False


def _hide_console_window() -> tuple[int, bool]:
    """Fallback console hide when pythonw.exe is unavailable."""
    if sys.platform != "win32":
        return (0, False)
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = int(kernel32.GetConsoleWindow())
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return (0, False)

        pid_buf = (ctypes.c_uint32 * 4)()
        proc_count = int(kernel32.GetConsoleProcessList(pid_buf, 4))
        user32.ShowWindow(hwnd, 0)  # SW_HIDE
        return (hwnd, proc_count > 1)
    except Exception:
        return (0, False)


def _restore_console_window(hwnd: int) -> None:
    """Restore an interactive Windows console window when the GUI closes."""
    if not hwnd or sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
    except Exception:
        pass


def main() -> None:
    if _relaunch_windowless_if_needed():
        return

    skip_hide = "--no-detach" in sys.argv
    console_hwnd, should_restore = (0, False) if skip_hide else _hide_console_window()
    _set_windows_app_id()
    try:
        app = FlowerViewerApp()
        app.run()
    finally:
        if should_restore:
            _restore_console_window(console_hwnd)


if __name__ == "__main__":
    main()
