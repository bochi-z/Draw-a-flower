"""3D Rotating Rose rendered with the Python standard-library turtle module.

Features:
- Layered 3D rose geometry built from golden-angle spiral petals, floral
  receptacle, reflexed calyx sepals, curved stem, thorns, and folded leaves.
- Unfurling bloom intro animation from tight rosebud to full bloom.
- Smooth directional + fill + ambient-occlusion shading rendered with pure
  turtle drawing primitives (begin_fill / end_fill / goto) and Painter's
  algorithm depth sorting.
- Interactive 3D camera controls (mouse drag to orbit, scroll to zoom, Space
  to pause/resume, B to replay bloom, R to reset view).
"""

from __future__ import annotations

import atexit
import math
import os
import struct
import subprocess
import sys
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
BACKGROUND_COLOR = "#FAF5EC"  # Soft warm cream botanical canvas
WINDOW_TITLE = "3D Rose"

HUD_Y = -268.0
HUD_INK_COLOR = "#4A4239"
HUD_TEXT_COLOR = HUD_INK_COLOR
HUD_DISABLED_INK_COLOR = "#64625F"
HUD_ENABLED_INK_RGB = (74.0, 66.0, 57.0)
HUD_DISABLED_INK_RGB = (100.0, 98.0, 95.0)
HUD_HEIGHT = 32
HUD_PILL_FILL_RGBA = (245, 238, 226, 194)
HUD_PILL_EDGE_RGBA = (190, 178, 160, 212)
HUD_DISABLED_FILL_RGBA = (196, 196, 198, 196)
HUD_DISABLED_EDGE_RGBA = (158, 158, 162, 212)
HUD_COLOR_TRANSITION_DURATION = 0.35
HUD_TRANSITION_STEPS = 10

SPEED_HUD_HEIGHT = 28
SPEED_HUD_GAP = 8.0
SPEED_TRACK_WIDTH = 112
SPEED_TRACK_HEIGHT = 16
SPEED_TRACK_PAD = 7.0
ROTATION_SPEED_MIN = 1.0
ROTATION_SPEED_MAX = 5.0
DEFAULT_ROTATION_SPEED = 1.0

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

GOLDEN_ANGLE = math.pi * (3.0 - math.sqrt(5.0))

# Mesh resolution tuned for ~630-670 polygons with pooled canvas rendering
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

# Camera & Animation defaults
DEFAULT_YAW = 0.35
DEFAULT_PITCH = 0.50  # ~28.6 deg 3/4 view looking gently into the rose cup
DEFAULT_ZOOM = 1.0
STARTUP_PITCH = 1.42  # Overhead view looking down into the opening rosebud
STARTUP_ZOOM = 1.18
PIVOT_Y = -0.22
CAMERA_DISTANCE = 6.2
FOV_SCALE = 1100.0

AUTO_ROTATE_SPEED = 0.55        # radians per second
BLOOM_DURATION = 2.6            # seconds for bud-to-bloom intro
CAMERA_TWEEN_DURATION = 1.6     # seconds to glide from overhead to default angle
RESET_TRANSITION_DURATION = 0.8 # seconds to smoothly glide back to startup state

# Lighting directions (normalized in camera/view space)
def _normalize(vx: float, vy: float, vz: float) -> tuple[float, float, float]:
    length = math.sqrt(vx * vx + vy * vy + vz * vz)
    if length < 1e-12:
        return (0.0, 0.0, 1.0)
    return (vx / length, vy / length, vz / length)


KEY_LIGHT = _normalize(0.55, 0.72, 0.58)
FILL_LIGHT = _normalize(-0.62, 0.20, 0.36)


# ---------------------------------------------------------------------------
# Math & Color Utilities
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 3D Mesh Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FaceSpec:
    """Topology and botanical shading metadata for one mesh polygon."""

    indices: tuple[int, ...]
    material: str  # "petal", "foliage", or "thorn"
    v_frac: float = 0.5
    layer_frac: float = 0.5
    double_sided: bool = True


class RoseMesh:
    """Holds mutable 3D vertices and fixed polygon topology for the rose."""

    def __init__(self, bloom: float = 1.0) -> None:
        self.vertices: list[tuple[float, float, float]] = []
        self.faces: list[FaceSpec] = []
        self._build_topology_and_vertices(bloom)

    def update_bloom(self, bloom: float) -> None:
        """Recompute vertex positions for a given bloom factor in [0, 1]."""
        self.vertices.clear()
        self._populate_vertices(bloom, build_faces=False)

    def _build_topology_and_vertices(self, bloom: float) -> None:
        self.vertices.clear()
        self.faces.clear()
        self._populate_vertices(bloom, build_faces=True)

    def _add_grid_surface(
        self,
        grid: list[list[int]],
        material: str,
        layer_frac: float,
        double_sided: bool,
        v_max: int,
        u_max: int,
    ) -> None:
        for iv in range(v_max):
            v_mid = (iv + 0.5) / v_max
            for iu in range(u_max):
                i0 = grid[iv][iu]
                i1 = grid[iv][iu + 1]
                i2 = grid[iv + 1][iu + 1]
                i3 = grid[iv + 1][iu]
                self.faces.append(
                    FaceSpec(
                        indices=(i0, i1, i2, i3),
                        material=material,
                        v_frac=v_mid,
                        layer_frac=layer_frac,
                        double_sided=double_sided,
                    )
                )

    def _populate_vertices(self, bloom: float, build_faces: bool) -> None:
        b = _clamp(bloom, 0.0, 1.0)
        self._build_petals(b, build_faces)
        self._build_receptacle(build_faces)
        self._build_sepals(b, build_faces)
        self._build_stem_and_thorns(build_faces)
        self._build_leaves(build_faces)

    # -- Petals --------------------------------------------------------------

    def _build_petals(self, bloom: float, build_faces: bool) -> None:
        for idx in range(NUM_PETALS):
            t = idx / (NUM_PETALS - 1)  # 0 = innermost bud, 1 = outermost petal

            # Outer petals peel open slightly earlier than the inner spiral core
            lag = 0.34 * (1.0 - t)
            local_b = _smoothstep(lag, 1.0, bloom)

            theta_center = idx * GOLDEN_ANGLE
            r_base = 0.036 + 0.195 * (t ** 1.10)
            y_base = 0.23 - 0.10 * (t ** 1.15)
            petal_len = 0.45 + 0.42 * (t ** 0.72)

            # Inner petals spiral steeply around center; outer petals form a lush cup
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
            for iv in range(PETAL_V_STEPS + 1):
                v = iv / PETAL_V_STEPS
                # Width envelope: narrow attachment claw -> broad belly -> rounded apex
                w_env = 0.26 + 0.74 * math.sin(math.pi * (0.08 + 0.79 * v))
                row: list[int] = []
                for iu in range(PETAL_U_STEPS + 1):
                    u = -1.0 + 2.0 * (iu / PETAL_U_STEPS)
                    u2 = u * u

                    # Round off upper corners smoothly into a natural petal crown
                    s = v * (1.0 - 0.14 * u2 * v)
                    # Subtle delicate center cleft on middle/outer petals
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
                grid.append(row)

            if build_faces:
                self._add_grid_surface(
                    grid=grid,
                    material="petal",
                    layer_frac=t,
                    double_sided=True,
                    v_max=PETAL_V_STEPS,
                    u_max=PETAL_U_STEPS,
                )

    # -- Receptacle (floral cup under petals) --------------------------------

    def _build_receptacle(self, build_faces: bool) -> None:
        # Profile rings ordered top-to-bottom so outward normals face away from center
        profile = (
            (0.11, 0.268),
            (0.05, 0.285),
            (-0.04, 0.215),
            (-0.14, 0.062),
        )
        grid: list[list[int]] = []
        for y, r in profile:
            row: list[int] = []
            for iu in range(RECEPTACLE_RADIAL_STEPS + 1):
                ang = 2.0 * math.pi * (iu % RECEPTACLE_RADIAL_STEPS) / RECEPTACLE_RADIAL_STEPS
                row.append(len(self.vertices))
                self.vertices.append((r * math.cos(ang), y, r * math.sin(ang)))
            grid.append(row)

        # Inner floral floor disc matching the receptacle rim to seal any rim gaps
        disc_start = len(self.vertices)
        for iu in range(RECEPTACLE_RADIAL_STEPS):
            ang = 2.0 * math.pi * iu / RECEPTACLE_RADIAL_STEPS
            self.vertices.append((0.268 * math.cos(ang), 0.108, 0.268 * math.sin(ang)))

        if build_faces:
            self._add_grid_surface(
                grid=grid,
                material="foliage",
                layer_frac=0.35,
                double_sided=False,
                v_max=RECEPTACLE_HEIGHT_STEPS,
                u_max=RECEPTACLE_RADIAL_STEPS,
            )
            self.faces.append(
                FaceSpec(
                    indices=tuple(range(disc_start, disc_start + RECEPTACLE_RADIAL_STEPS)),
                    material="petal",
                    v_frac=0.02,
                    layer_frac=0.0,
                    double_sided=True,
                )
            )

    # -- Sepals (5 green calyx leaves) ---------------------------------------

    def _build_sepals(self, bloom: float, build_faces: bool) -> None:
        b = _smoothstep(0.0, 0.85, bloom)
        for idx in range(NUM_SEPALS):
            theta_center = idx * (2.0 * math.pi / NUM_SEPALS) + 0.35
            r_base = 0.272
            y_base = 0.095
            sepal_len = 0.48

            # Cradles outside the closed bud; reflexes gracefully outward when bloomed
            tilt = _lerp(0.36, 1.80, b)

            grid: list[list[int]] = []
            for iv in range(SEPAL_V_STEPS + 1):
                v = iv / SEPAL_V_STEPS
                # Broad base tapering smoothly to a sharp sepal tip
                half_w = 0.105 * (1.0 - v ** 0.95) * (0.85 + 0.35 * math.sin(math.pi * v))
                if iv == SEPAL_V_STEPS:
                    half_w = 0.0

                row: list[int] = []
                for iu in range(SEPAL_U_STEPS + 1):
                    u = -1.0 + 2.0 * (iu / SEPAL_U_STEPS)
                    arch = _lerp(0.11, 0.14, b) * math.sin(math.pi * v)
                    # Outward curl at the pointed tip when open
                    tip_curl = b * 0.11 * max(0.0, v - 0.45) ** 2

                    r_mid = r_base + sepal_len * (
                        math.sin(tilt) * v + arch - tip_curl * 0.35
                    )
                    y_mid = y_base + sepal_len * (
                        math.cos(tilt) * v - tip_curl + 0.04 * (1.0 - abs(u)) * (1.0 - v)
                    )

                    # Local radial/tangent vectors
                    cx = math.cos(theta_center)
                    cz = math.sin(theta_center)
                    tx = -cz
                    tz = cx

                    x = r_mid * cx + u * half_w * tx
                    z = r_mid * cz + u * half_w * tz
                    row.append(len(self.vertices))
                    self.vertices.append((x, y_mid, z))
                grid.append(row)

            if build_faces:
                # Top row tapers to tip point: emit triangles on the final row
                for iv in range(SEPAL_V_STEPS):
                    v_mid = (iv + 0.5) / SEPAL_V_STEPS
                    for iu in range(SEPAL_U_STEPS):
                        i0 = grid[iv][iu]
                        i1 = grid[iv][iu + 1]
                        i2 = grid[iv + 1][iu + 1]
                        i3 = grid[iv + 1][iu]
                        if iv == SEPAL_V_STEPS - 1:
                            verts = (i0, i1, i2)
                        else:
                            verts = (i0, i1, i2, i3)
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
        """Return (x, y, z, radius) along the stem for s in [0 (top), 1 (bottom)]."""
        y = -0.13 - 1.24 * s
        x = 0.075 * math.sin(s * 2.8)
        z = 0.040 * (1.0 - math.cos(s * 2.3))
        radius = _lerp(0.062, 0.045, s)
        return (x, y, z, radius)

    def _build_stem_and_thorns(self, build_faces: bool) -> None:
        grid: list[list[int]] = []
        for iv in range(STEM_HEIGHT_STEPS + 1):
            s = iv / STEM_HEIGHT_STEPS
            cx, cy, cz, r = self._stem_center(s)
            row: list[int] = []
            for iu in range(STEM_RADIAL_STEPS + 1):
                ang = 2.0 * math.pi * (iu % STEM_RADIAL_STEPS) / STEM_RADIAL_STEPS
                row.append(len(self.vertices))
                self.vertices.append((cx + r * math.cos(ang), cy, cz + r * math.sin(ang)))
            grid.append(row)

        if build_faces:
            self._add_grid_surface(
                grid=grid,
                material="foliage",
                layer_frac=0.25,
                double_sided=False,
                v_max=STEM_HEIGHT_STEPS,
                u_max=STEM_RADIAL_STEPS,
            )
            # Bottom stem cap so tilting underneath looks closed
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

        # Three sculpted curved thorns along the stem
        thorn_specs = (
            (0.28, 1.9),
            (0.54, 4.1),
            (0.76, 0.6),
        )
        for s_pos, ang in thorn_specs:
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
            if build_faces:
                self.faces.extend(
                    (
                        FaceSpec((idx_base, idx_base + 1, idx_base + 3), "thorn", 0.6, 0.5, True),
                        FaceSpec((idx_base + 1, idx_base + 2, idx_base + 3), "thorn", 0.5, 0.5, True),
                        FaceSpec((idx_base + 2, idx_base, idx_base + 3), "thorn", 0.6, 0.5, True),
                    )
                )

    # -- 3D Folded Rose Leaves -----------------------------------------------

    def _build_leaves(self, build_faces: bool) -> None:
        # (stem_s, azimuth, length, width, pitch_down, bank_roll)
        leaf_specs = (
            (0.25, 0.45, 0.70, 0.24, 0.34, 0.16),
            (0.49, 2.60, 0.78, 0.27, 0.40, -0.18),
            (0.71, 4.70, 0.64, 0.22, 0.44, 0.12),
        )
        for s_pos, az, leaf_len, leaf_w, pitch_down, bank in leaf_specs:
            cx, cy, cz, r_stem = self._stem_center(s_pos)
            dx = math.cos(az)
            dz = math.sin(az)
            tx = -dz
            tz = dx

            # Anchor leaf root directly inside the stem surface so there is zero gap
            r_anchor = r_stem * 0.65
            root_x = cx + r_anchor * dx
            root_y = cy
            root_z = cz + r_anchor * dz

            # Leaf blade 4x5 grid emerging seamlessly from the stem with V-fold midrib
            grid: list[list[int]] = []
            for iv in range(LEAF_V_STEPS + 1):
                v = iv / LEAF_V_STEPS
                # Narrow sturdy stem collar at v=0 widening into ovate blade, tapering to tip
                if iv == LEAF_V_STEPS:
                    width_profile = 0.0
                else:
                    width_profile = 0.08 * (1.0 - v) + 0.96 * math.sin(math.pi * (v ** 0.72))

                row: list[int] = []
                for iu in range(LEAF_U_STEPS + 1):
                    u = -1.0 + 2.0 * (iu / LEAF_U_STEPS)
                    dist_along = v * leaf_len
                    # Graceful downward arch + slight tip droop
                    arch_y = -pitch_down * dist_along - 0.12 * (v ** 2.1)
                    # V-fold crease along central midrib
                    v_fold = 0.048 * abs(u) * math.sin(math.pi * v)
                    # Gentle bank roll across leaf width
                    roll_y = bank * u * (width_profile - 0.08 * (1.0 - v)) * leaf_w

                    lateral = u * width_profile * leaf_w
                    vx = root_x + dist_along * dx + lateral * tx
                    vz = root_z + dist_along * dz + lateral * tz
                    vy = root_y + arch_y + v_fold + roll_y

                    row.append(len(self.vertices))
                    self.vertices.append((vx, vy, vz))
                grid.append(row)

            if build_faces:
                for iv in range(LEAF_V_STEPS):
                    v_mid = (iv + 0.5) / LEAF_V_STEPS
                    for iu in range(LEAF_U_STEPS):
                        i0 = grid[iv][iu]
                        i1 = grid[iv][iu + 1]
                        i2 = grid[iv + 1][iu + 1]
                        i3 = grid[iv + 1][iu]
                        if iv == LEAF_V_STEPS - 1:
                            verts = (i0, i1, i2)
                        else:
                            verts = (i0, i1, i2, i3)
                        self.faces.append(
                            FaceSpec(
                                indices=verts,
                                material="foliage",
                                v_frac=0.35 + 0.65 * v_mid,
                                layer_frac=0.75,
                                double_sided=True,
                            )
                        )


# ---------------------------------------------------------------------------
# 3D Transform, Shading & Painter's Algorithm Pipeline
# ---------------------------------------------------------------------------

def shade_polygon(
    face: FaceSpec,
    nx: float,
    ny: float,
    nz: float,
    vx: float,
    vy: float,
    vz: float,
) -> str:
    """Compute wrap-diffuse + bounce + ambient-occlusion hex color for a face."""
    # Determine whether we are viewing the front (inner) or back (outer) side
    view_dot = nx * vx + ny * vy + nz * vz
    is_outer_side = view_dot < 0.0
    if face.double_sided and is_outer_side:
        nx, ny, nz = -nx, -ny, -nz

    raw_key = nx * KEY_LIGHT[0] + ny * KEY_LIGHT[1] + nz * KEY_LIGHT[2]
    raw_fill = nx * FILL_LIGHT[0] + ny * FILL_LIGHT[1] + nz * FILL_LIGHT[2]

    # Wrapped diffuse simulates soft petal translucency and daytime sky scattering
    key_wrap = max(0.0, (raw_key + 0.45) / 1.45)
    fill_wrap = max(0.0, (raw_fill + 0.35) / 1.35)
    # Warm cream canvas bounce light gently lifts downward-facing undersides
    canvas_bounce = max(0.0, -ny) * 0.24

    # Half-vector specular for soft velvety sheen
    hx, hy, hz = _normalize(KEY_LIGHT[0] + vx, KEY_LIGHT[1] + vy, KEY_LIGHT[2] + vz)
    half_dot = max(0.0, nx * hx + ny * hy + nz * hz)

    if face.material == "petal":
        # Deep inner crevice occlusion softening outward and upward toward tips
        ao = 0.50 + 0.50 * _smoothstep(0.0, 0.90, 0.42 * face.layer_frac + 0.58 * face.v_frac)
        diffuse = 0.34 + 0.56 * key_wrap + 0.16 * fill_wrap + canvas_bounce
        light = _clamp(ao * diffuse, 0.24, 1.18)
        spec = (half_dot ** 10) * (0.14 * ao)

        # Natural Scarlet Rose palette: deep ruby-burgundy in crevices, luminous
        # scarlet-crimson on lit curves, soft vermilion-coral sheen on crests
        if is_outer_side:
            base_r, base_g, base_b = 208.0, 34.0, 48.0
        else:
            base_r, base_g, base_b = 222.0, 24.0, 36.0

        # Subtle depth richness near petal claw; brighter sun-kissed petal margins
        tip_lift = 0.86 + 0.24 * face.v_frac
        r = base_r * light * tip_lift + 252.0 * spec
        g = base_g * (light ** 1.08) * tip_lift + 128.0 * spec
        b = base_b * (light ** 1.10) * tip_lift + 102.0 * spec
        return _rgb_to_hex(r, g, b)

    if face.material == "thorn":
        diffuse = 0.42 + 0.52 * key_wrap + 0.16 * fill_wrap + 0.12 * canvas_bounce
        return _rgb_to_hex(124.0 * diffuse, 88.0 * diffuse, 60.0 * diffuse)

    # Botanical foliage (receptacle, sepals, stem, leaves)
    ao = 0.62 + 0.38 * face.v_frac
    diffuse = (0.38 + 0.56 * key_wrap + 0.16 * fill_wrap + 0.16 * canvas_bounce) * ao
    spec = (half_dot ** 14) * 0.11
    r = 76.0 * diffuse + 168.0 * spec
    g = 136.0 * diffuse + 198.0 * spec
    b = 56.0 * diffuse + 96.0 * spec
    return _rgb_to_hex(r, g, b)


def build_draw_list(
    mesh: RoseMesh,
    yaw: float,
    pitch: float,
    zoom: float,
    fov_scale: float = FOV_SCALE,
) -> list[tuple[float, str, tuple[tuple[float, float], ...]]]:
    """Transform all vertices, shade faces, and sort back-to-front."""
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    cos_p = math.cos(pitch)
    sin_p = math.sin(pitch)
    fov = fov_scale * zoom
    pivot_y = PIVOT_Y
    cam_dist = CAMERA_DISTANCE
    sqrt = math.sqrt

    # Transform every vertex once per frame into camera space + screen projection
    verts = mesh.vertices
    n_verts = len(verts)
    tx = [0.0] * n_verts
    ty = [0.0] * n_verts
    tz = [0.0] * n_verts
    spx = [0.0] * n_verts
    spy = [0.0] * n_verts

    for i, (x, y, z) in enumerate(verts):
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
    shade = shade_polygon

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
            pts = (
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

        append_item((cz, shade(face, nx, ny, nz, vx, vy, vz), pts))

    # Painter's algorithm: smallest z (farthest) drawn first, largest z last
    draw_items.sort(key=lambda item: item[0])
    return draw_items


# ---------------------------------------------------------------------------
# HUD Typography, Material Symbols Icons & Frosted Pill Helpers
# ---------------------------------------------------------------------------

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_FONTS_DIR = _ASSETS_DIR / "fonts"
_ICONS_DIR = _ASSETS_DIR / "icons"
_APP_ICON_PNG = _ASSETS_DIR / "rose_icon.png"
_APP_ICON_ICO = _ASSETS_DIR / "rose_icon.ico"

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
}

_FR_PRIVATE = 0x10
_MAX_FONT_BYTES = 2 * 1024 * 1024
_MAX_ICON_BYTES = 64 * 1024
_MAX_ICON_DIM = 128
_MAX_APP_ICON_BYTES = 2 * 1024 * 1024
_WINDOWS_APP_ID = "DrawAFlower.Rose3D"

_LOADED_FONT_PATHS: list[str] = []
_LOADED_MEM_HANDLES: list[int] = []
_REGISTERED_FONT_PATHS: set[str] = set()
_FONT_CLEANUP_REGISTERED = False
_VERIFIED_FAMILY: str | None = None
_RAW_ICON_CACHE: dict[str, tuple[int, int, list[bytearray]]] = {}


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

        # Restricted environments may deny fontdrvhost disk access; load from memory
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
        for path in font_paths:
            if not path.is_file():
                continue
            path_str = str(path)
            if path_str in _LOADED_FONT_PATHS:
                continue
            raw = path_str.encode("utf-8")
            url = cf.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
            if url:
                try:
                    # kCTFontManagerScopeProcess == 1
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


def load_icon_photo(name: str, master: tk.Misc | None = None) -> tk.PhotoImage:
    """Load an official Material Symbols RGBA PNG icon as a ``tk.PhotoImage``."""
    path = _resolve_icon_path(name)
    kwargs: dict[str, object] = {"file": str(path), "format": "png"}
    if master is not None:
        kwargs["master"] = master
    return tk.PhotoImage(**kwargs)


def load_fps_icon(master: tk.Misc | None = None) -> tk.PhotoImage:
    """Load the crisp Material Symbols ``speed`` icon for the FPS badge."""
    return load_icon_photo("speed", master=master)


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
    """Set the 1:1 rose window and taskbar icon from ``assets/`` with graceful fallback."""
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
        src = decompressed[offset : offset + stride]
        offset += stride
        row = bytearray(src)
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


def _build_pill_rgba_rows(
    width: int,
    height: int,
    fill_rgba: tuple[int, int, int, int] = HUD_PILL_FILL_RGBA,
    edge_rgba: tuple[int, int, int, int] = HUD_PILL_EDGE_RGBA,
) -> list[bytearray]:
    """Render an anti-aliased frosted translucent rounded-pill RGBA buffer."""
    rows_geom = _compute_pill_geometry(width, height)
    return _fill_pill_rows_from_geometry(width, rows_geom, fill_rgba, edge_rgba)


def build_pill_png(
    width: int,
    height: int,
    fill_rgba: tuple[int, int, int, int] = HUD_PILL_FILL_RGBA,
    edge_rgba: tuple[int, int, int, int] = HUD_PILL_EDGE_RGBA,
) -> bytes:
    """Create an anti-aliased frosted translucent rounded-pill PNG in memory."""
    rows = _build_pill_rgba_rows(width, height, fill_rgba=fill_rgba, edge_rgba=edge_rgba)
    return _encode_rgba_rows_png(width, height, rows)


def _composite_icon_over_rows(
    dst_rows: list[bytearray],
    dst_width: int,
    dst_height: int,
    icon_name: str,
    dest_x: int,
    dest_y: int,
    alpha_scale: float = 1.0,
) -> None:
    """Alpha-composite a straight-RGBA icon onto the destination pill RGBA buffer."""
    icon_w, icon_h, icon_rows = _load_rgba_icon(icon_name)
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
            dst_row[d_off] = int(
                (src_row[s_off] * sa_f + dst_row[d_off] * da_f * inv_sa) / out_a + 0.5
            )
            dst_row[d_off + 1] = int(
                (src_row[s_off + 1] * sa_f + dst_row[d_off + 1] * da_f * inv_sa) / out_a + 0.5
            )
            dst_row[d_off + 2] = int(
                (src_row[s_off + 2] * sa_f + dst_row[d_off + 2] * da_f * inv_sa) / out_a + 0.5
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


def _hud_control_items(paused: bool) -> tuple[tuple[str, str], ...]:
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
        icon_x = cursor
        text_x = cursor + icon_w + icon_gap
        item_positions.append((icon_name, icon_x, text_x, label))
        cursor = text_x + int(font.measure(label))

    max_icon_h = max(_load_rgba_icon(icon_name)[1] for icon_name, _ in items)
    return (cursor, max_icon_h, item_positions, sep_positions)


def _resolve_hud_layout(
    paused: bool,
    font: tkfont.Font,
    max_width: int | None,
) -> tuple[int, int, list[tuple[str, int, int, str]], list[tuple[float, str]]]:
    """Measure HUD width, icon positions, and turtle-centered text segments."""
    icon_gap = 4
    sep_gap = 7
    pad_x = 18

    playing_w, _, _, _ = _measure_hud_layout(
        _hud_control_items(False), font, icon_gap=icon_gap, sep_gap=sep_gap
    )
    paused_w, _, _, _ = _measure_hud_layout(
        _hud_control_items(True), font, icon_gap=icon_gap, sep_gap=sep_gap
    )
    max_content_w = max(playing_w, paused_w)

    if max_width is not None and max_content_w + pad_x * 2 > max_width:
        sep_gap = 5
        pad_x = 12
        playing_w, _, _, _ = _measure_hud_layout(
            _hud_control_items(False), font, icon_gap=icon_gap, sep_gap=sep_gap
        )
        paused_w, _, _, _ = _measure_hud_layout(
            _hud_control_items(True), font, icon_gap=icon_gap, sep_gap=sep_gap
        )
        max_content_w = max(playing_w, paused_w)

    pill_w = max_content_w + pad_x * 2
    if max_width is not None:
        pill_w = min(max_width, pill_w)

    active_items = _hud_control_items(paused)
    content_w, _, item_positions, sep_positions = _measure_hud_layout(
        active_items, font, icon_gap=icon_gap, sep_gap=sep_gap
    )
    content_left_px = round((pill_w - content_w) * 0.5)

    # TurtleScreen._write places canvas text at (x - 1, -y); add +1.0 to align cleanly
    half_pill = pill_w * 0.5
    raw_segments: list[tuple[float, str]] = []
    for _icon_name, _rel_icon_x, rel_text_x, label in item_positions:
        canvas_x = (content_left_px + rel_text_x) - half_pill
        raw_segments.append((canvas_x + 1.0, label))
    for rel_sep_x, sep_text in sep_positions:
        canvas_x = (content_left_px + rel_sep_x) - half_pill
        raw_segments.append((canvas_x + 1.0, sep_text))
    raw_segments.sort(key=lambda item: item[0])
    return (pill_w, content_left_px, item_positions, raw_segments)


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
    fill_rgba: tuple[int, int, int, int] = HUD_PILL_FILL_RGBA,
    edge_rgba: tuple[int, int, int, int] = HUD_PILL_EDGE_RGBA,
    icon_alpha_scale: float = 1.0,
) -> tuple[tk.PhotoImage, list[tuple[float, str]]]:
    """Build the frosted HUD pill ``PhotoImage`` with icons and text positions."""
    pill_w, content_left_px, item_positions, raw_segments = _resolve_hud_layout(
        paused, font, max_width
    )
    rows_geom = _compute_pill_geometry(pill_w, height)
    pill_photo = _bake_pill_photo_from_geometry(
        pill_w,
        height,
        rows_geom,
        content_left_px,
        item_positions,
        fill_rgba,
        edge_rgba,
        icon_alpha_scale,
        master,
    )
    return (pill_photo, raw_segments)


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


def _bake_transition_pills(
    pill_w: int,
    height: int,
    content_left_px: int,
    item_positions: Sequence[tuple[str, int, int, str]],
    master: tk.Misc | None,
    steps: int,
) -> list[tk.PhotoImage]:
    """Pre-bake ``steps + 1`` frosted pill images from disabled grey (0) to cream (1)."""
    step_count = max(1, int(steps))
    rows_geom = _compute_pill_geometry(pill_w, height)
    pills: list[tk.PhotoImage] = []
    for idx in range(step_count + 1):
        t = idx / float(step_count)
        fill_rgba = _lerp_rgba(HUD_DISABLED_FILL_RGBA, HUD_PILL_FILL_RGBA, t)
        edge_rgba = _lerp_rgba(HUD_DISABLED_EDGE_RGBA, HUD_PILL_EDGE_RGBA, t)
        icon_alpha = _lerp(0.65, 1.0, t)
        pills.append(
            _bake_pill_photo_from_geometry(
                pill_w,
                height,
                rows_geom,
                content_left_px,
                item_positions,
                fill_rgba,
                edge_rgba,
                icon_alpha,
                master,
            )
        )
    return pills


def build_hud_transition_pills(
    font: tkfont.Font,
    *,
    height: int = HUD_HEIGHT,
    max_width: int | None = None,
    master: tk.Misc | None = None,
    steps: int = HUD_TRANSITION_STEPS,
) -> tuple[list[tk.PhotoImage], list[tuple[float, str]]]:
    """Pre-bake ``steps + 1`` HUD pill images from disabled grey (0) to enabled cream (1)."""
    pill_w, content_left_px, item_positions, raw_segments = _resolve_hud_layout(
        False, font, max_width
    )
    pills = _bake_transition_pills(
        pill_w, height, content_left_px, item_positions, master, steps
    )
    return (pills, raw_segments)


@dataclass(frozen=True, slots=True)
class SpeedSliderLayout:
    """Pixel geometry and relative offsets for the rotation speed slider HUD pill."""

    pill_width: int
    pill_height: int
    label_x_offset: float
    track_x_offset: float
    track_width: int
    track_height: int
    track_pad: float
    value_x_offset: float


def build_speed_slider_transition_pills(
    label_font: tkfont.Font,
    value_font: tkfont.Font,
    *,
    height: int = SPEED_HUD_HEIGHT,
    track_width: int = SPEED_TRACK_WIDTH,
    track_height: int = SPEED_TRACK_HEIGHT,
    track_pad: float = SPEED_TRACK_PAD,
    master: tk.Misc | None = None,
    steps: int = HUD_TRANSITION_STEPS,
) -> tuple[list[tk.PhotoImage], SpeedSliderLayout]:
    """Pre-bake frosted speed slider pill frames and return layout geometry."""
    icon_w, _icon_h, _ = _load_rgba_icon("speed")
    pad_x = 12
    icon_gap = 5
    track_gap = 9
    value_gap = 8
    label_w = int(label_font.measure("Speed"))
    value_w = max(int(value_font.measure(f"{s:.1f}x")) for s in (1.0, 2.0, 3.0, 4.0, 5.0))

    label_rel_x = pad_x + icon_w + icon_gap
    track_rel_x = label_rel_x + label_w + track_gap
    value_rel_x = track_rel_x + track_width + value_gap
    pill_w = value_rel_x + value_w + pad_x
    half_pill = pill_w * 0.5

    layout = SpeedSliderLayout(
        pill_width=pill_w,
        pill_height=height,
        label_x_offset=(label_rel_x - half_pill) + 1.0,
        track_x_offset=(track_rel_x + track_width * 0.5) - half_pill,
        track_width=track_width,
        track_height=track_height,
        track_pad=track_pad,
        value_x_offset=(value_rel_x - half_pill) + 1.0,
    )
    item_positions = (("speed", pad_x, label_rel_x, "Speed"),)
    pills = _bake_transition_pills(pill_w, height, 0, item_positions, master, steps)
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


def build_speed_track_photo(
    fraction: float,
    blend: float,
    *,
    width: int = SPEED_TRACK_WIDTH,
    height: int = SPEED_TRACK_HEIGHT,
    pad: float = SPEED_TRACK_PAD,
    master: tk.Misc | None = None,
) -> tk.PhotoImage:
    """Render an anti-aliased RGBA slider track + scarlet circular thumb."""
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
        SPEED_TRACK_GROOVE_DISABLED_RGBA, SPEED_TRACK_GROOVE_ENABLED_RGBA, t
    )
    active_rgba = _lerp_rgba(
        SPEED_TRACK_ACTIVE_DISABLED_RGBA, SPEED_TRACK_ACTIVE_ENABLED_RGBA, t
    )
    core_rgba = _lerp_rgba(
        SPEED_THUMB_CORE_DISABLED_RGBA, SPEED_THUMB_CORE_ENABLED_RGBA, t
    )
    shadow_rgba = (74, 66, 57, int(_lerp(28.0, 52.0, t) + 0.5))

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


def build_fps_badge_photo(
    sample_text: str = "60 FPS",
    font: tkfont.Font | None = None,
    *,
    height: int = 26,
    master: tk.Misc | None = None,
) -> tuple[tk.PhotoImage, float]:
    """Build a matching frosted FPS badge ``PhotoImage`` with the ``speed`` icon."""
    if font is None:
        family, size, weight = get_hud_font(size=9, weight="medium")
        font = tkfont.Font(root=master or tk._default_root, family=family, size=size, weight=weight)

    icon_w, icon_h, _ = _load_rgba_icon("speed")
    pad_x = 11
    icon_gap = 5
    text_w = int(font.measure(sample_text))
    badge_w = pad_x + icon_w + icon_gap + text_w + pad_x

    rows = _build_pill_rgba_rows(badge_w, height)
    _composite_icon_over_rows(
        rows,
        badge_w,
        height,
        "speed",
        dest_x=pad_x,
        dest_y=(height - icon_h) // 2,
    )
    png_bytes = _encode_rgba_rows_png(badge_w, height, rows)
    photo_kwargs: dict[str, object] = {"data": png_bytes, "format": "png"}
    if master is not None:
        photo_kwargs["master"] = master
    badge_photo = tk.PhotoImage(**photo_kwargs)

    canvas_text_x = (pad_x + icon_w + icon_gap) - badge_w * 0.5
    return (badge_photo, canvas_text_x + 1.0)


def _hud_ink_hex(blend: float) -> str:
    """Return the interpolated HUD ink hex color between disabled (0) and enabled (1)."""
    t = _clamp(blend, 0.0, 1.0)
    r = int(_lerp(HUD_DISABLED_INK_RGB[0], HUD_ENABLED_INK_RGB[0], t) + 0.5)
    g = int(_lerp(HUD_DISABLED_INK_RGB[1], HUD_ENABLED_INK_RGB[1], t) + 0.5)
    b = int(_lerp(HUD_DISABLED_INK_RGB[2], HUD_ENABLED_INK_RGB[2], t) + 0.5)
    return f"#{r:02x}{g:02x}{b:02x}"


# ---------------------------------------------------------------------------
# Pure-Turtle Renderer & Interactive Viewer Application
# ---------------------------------------------------------------------------

class RoseViewerApp:
    """Interactive 3D rotating rose viewer built with pure Python turtle."""

    def __init__(self) -> None:
        self.screen = turtle.Screen()
        self.screen.setup(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.screen.screensize(200, 200)
        self.screen.bgcolor(BACKGROUND_COLOR)
        self.screen.title(WINDOW_TITLE)
        self.screen.tracer(0)

        self.yaw = DEFAULT_YAW
        self.pitch = STARTUP_PITCH
        self.zoom = STARTUP_ZOOM
        self.rotation_speed = DEFAULT_ROTATION_SPEED
        self.paused = False
        self.running = True
        self._controls_locked = True

        self.current_bloom = 0.0
        self.bloom_elapsed = 0.0
        self.bloom_done = False
        self._camera_tween_active = True
        self._tween_elapsed = 0.0
        self._tween_start_pitch = STARTUP_PITCH
        self._tween_start_zoom = STARTUP_ZOOM

        self._reset_active = False
        self._reset_elapsed = 0.0
        self._reset_start_yaw = DEFAULT_YAW
        self._reset_target_yaw = DEFAULT_YAW
        self._reset_start_pitch = STARTUP_PITCH
        self._reset_start_zoom = STARTUP_ZOOM
        self._reset_start_bloom = 0.0

        self.mesh = RoseMesh(bloom=0.0)

        # Pre-allocate reusable turtle polygon items to avoid per-frame clear/create churn
        self._canvas = self.screen.getcanvas()
        self._tk_canvas = self._canvas._canvas
        self._root = self._canvas.winfo_toplevel()
        self._root.minsize(360, 320)
        self._app_icon_photo = apply_window_icon(self._root)
        self._poly_pool = [self.screen._createpoly() for _ in range(len(self.mesh.faces))]
        self._pool_fills = [""] * len(self._poly_pool)
        self._pool_visible = [True] * len(self._poly_pool)
        self._after_id: str | None = None
        self._resize_after_id: str | None = None
        self._last_viewport: tuple[int, int, float, float, float, float] | None = None
        self.fullscreen = False
        self._windowed_geometry: str | None = None
        self._viewport_fov_scale = FOV_SCALE

        self._dragging = False
        self._dragging_speed = False
        self._canvas_cursor = ""
        self._last_mouse_x = 0
        self._last_mouse_y = 0
        self._last_frame_time = time.perf_counter()

        # Rolling FPS window and 60 FPS pacer state
        self._fps_window_start = self._last_frame_time
        self._fps_frames = 0
        self._next_frame_deadline = self._last_frame_time

        # Load Google Sans privately before measuring or creating HUD text
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

        self._hud_transition_pills: list[tk.PhotoImage] = []
        self._hud_pill_playing: tk.PhotoImage | None = None
        self._hud_pill_paused: tk.PhotoImage | None = None
        self._hud_pill_disabled: tk.PhotoImage | None = None
        self._hud_segments_playing: list[tuple[float, str]] = []
        self._hud_segments_paused: list[tuple[float, str]] = []
        self._hud_natural_w = 0
        self._hud_is_compact = False
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

        self._fps_photo: tk.PhotoImage | None = None
        self._fps_bg_item: int | None = None
        self._fps_text_item: int | None = None
        self._fps_x = 0.0
        self._fps_y = 0.0
        self._fps_text_x_offset = 0.0
        self._fps_text_y = 0.0
        self._fps_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._fps_pen.speed(0)
        self._fps_pen.penup()
        self._fps_pen.hideturtle()

        self._speed_transition_pills: list[tk.PhotoImage] = []
        self._speed_layout: SpeedSliderLayout | None = None
        self._speed_track_photo: tk.PhotoImage | None = None
        self._speed_applied_step = -1
        self._speed_applied_track_key: tuple[int, int] | None = None
        self._speed_applied_color = ""
        self._speed_bg_item: int | None = None
        self._speed_track_item: int | None = None
        self._speed_label_item: int | None = None
        self._speed_value_item: int | None = None
        self._speed_x = 0.0
        self._speed_y = HUD_Y + HUD_HEIGHT * 0.5 + SPEED_HUD_GAP + SPEED_HUD_HEIGHT * 0.5
        self._speed_text_y = self._speed_y
        self._speed_pen = turtle.Turtle(undobuffersize=0, visible=False)
        self._speed_pen.speed(0)
        self._speed_pen.penup()
        self._speed_pen.hideturtle()

        self._init_hud()
        self._init_speed_hud()
        self._init_fps_badge()
        self._sync_hud_to_viewport()
        self._raise_overlays()
        self._bind_events()

    def _rebuild_hud_pills(self, max_hud_w: int | None) -> None:
        self._hud_transition_pills, self._hud_segments_playing = build_hud_transition_pills(
            self._hud_font_obj, max_width=max_hud_w, master=self._root
        )
        self._hud_pill_disabled = self._hud_transition_pills[0]
        self._hud_pill_playing = self._hud_transition_pills[-1]
        self._hud_pill_paused, self._hud_segments_paused = build_hud_pill_with_icons(
            True, self._hud_font_obj, max_width=max_hud_w, master=self._root
        )
        if self._hud_natural_w > 0:
            self._hud_is_compact = self._hud_pill_playing.width() < self._hud_natural_w

    def _init_hud(self) -> None:
        self._hud_text_y = compute_hud_text_y(self._hud_y, self._hud_font_obj)

        # Build once unconstrained to know natural pill width for resize clamping
        self._rebuild_hud_pills(None)
        assert self._hud_pill_playing is not None
        self._hud_natural_w = self._hud_pill_playing.width()
        max_hud_w = max(260, WINDOW_WIDTH - 24)
        if self._hud_natural_w > max_hud_w:
            old_pills = self._hud_transition_pills
            self._rebuild_hud_pills(max_hud_w)
            old_pills.clear()

        initial_pill = self._hud_pill_disabled if self._controls_locked else self._hud_pill_playing
        self._hud_bg_item = self._tk_canvas.create_image(
            self._hud_x, -self._hud_y, image=initial_pill, anchor="center"
        )

        self._update_hud_text(force_rebuild_text=True)

    def _init_speed_hud(self) -> None:
        self._speed_transition_pills, self._speed_layout = build_speed_slider_transition_pills(
            self._hud_font_obj,
            self._fps_font_obj,
            height=SPEED_HUD_HEIGHT,
            master=self._root,
        )
        layout = self._speed_layout
        self._speed_y = self._hud_y + HUD_HEIGHT * 0.5 + SPEED_HUD_GAP + SPEED_HUD_HEIGHT * 0.5
        self._speed_text_y = compute_hud_text_y(self._speed_y, self._hud_font_obj)

        eased = _smootherstep(self._hud_enable_blend)
        max_step = max(0, len(self._speed_transition_pills) - 1)
        step_idx = min(max_step, max(0, int(round(eased * max_step))))
        initial_pill = self._speed_transition_pills[step_idx]
        self._speed_applied_step = step_idx
        self._speed_bg_item = self._tk_canvas.create_image(
            self._speed_x, -self._speed_y, image=initial_pill, anchor="center"
        )

        frac = self._speed_fraction()
        self._speed_track_photo = build_speed_track_photo(
            frac,
            self._hud_enable_blend,
            width=layout.track_width,
            height=layout.track_height,
            pad=layout.track_pad,
            master=self._root,
        )
        self._speed_applied_track_key = self._speed_track_cache_key(frac, self._hud_enable_blend)
        self._speed_track_item = self._tk_canvas.create_image(
            self._speed_x + layout.track_x_offset,
            -self._speed_y,
            image=self._speed_track_photo,
            anchor="center",
        )

        ink_color = _hud_ink_hex(eased)
        self._speed_applied_color = ink_color
        self._speed_pen.pencolor(ink_color)
        self._speed_pen.goto(self._speed_x + layout.label_x_offset, self._speed_text_y)
        self._speed_pen.write("Speed", move=False, align="left", font=self._hud_font_tuple)
        self._speed_label_item = self._speed_pen.items[-1]

        self._speed_pen.goto(self._speed_x + layout.value_x_offset, self._speed_text_y)
        self._speed_pen.write(
            f"{self.rotation_speed:.1f}x", move=False, align="left", font=self._fps_font_tuple
        )
        self._speed_value_item = self._speed_pen.items[-1]

    def _speed_fraction(self) -> float:
        span = ROTATION_SPEED_MAX - ROTATION_SPEED_MIN
        if span <= 1e-9:
            return 0.0
        return _clamp((self.rotation_speed - ROTATION_SPEED_MIN) / span, 0.0, 1.0)

    def _speed_track_cache_key(self, fraction: float, blend: float) -> tuple[int, int]:
        return (int(round(fraction * 500.0)), int(round(blend * 100.0)))

    def _update_speed_slider_visual(self, *, step_idx: int, ink_color: str) -> None:
        if self._speed_bg_item is not None and self._speed_transition_pills:
            clamped_step = min(len(self._speed_transition_pills) - 1, max(0, step_idx))
            if clamped_step != self._speed_applied_step:
                self._canvas.itemconfigure(
                    self._speed_bg_item, image=self._speed_transition_pills[clamped_step]
                )
                self._speed_applied_step = clamped_step

        if ink_color != self._speed_applied_color:
            for item_id in (self._speed_label_item, self._speed_value_item):
                if item_id is not None:
                    self._canvas.itemconfigure(item_id, fill=ink_color)
            self._speed_applied_color = ink_color

        layout = self._speed_layout
        if self._speed_track_item is not None and layout is not None:
            frac = self._speed_fraction()
            key = self._speed_track_cache_key(frac, self._hud_enable_blend)
            if key != self._speed_applied_track_key:
                self._speed_track_photo = build_speed_track_photo(
                    frac,
                    self._hud_enable_blend,
                    width=layout.track_width,
                    height=layout.track_height,
                    pad=layout.track_pad,
                    master=self._root,
                )
                self._canvas.itemconfigure(self._speed_track_item, image=self._speed_track_photo)
                self._speed_applied_track_key = key

    def _init_fps_badge(self) -> None:
        self._fps_photo, self._fps_text_x_offset = build_fps_badge_photo(
            sample_text="99 FPS",
            font=self._fps_font_obj,
            height=FPS_BADGE_HEIGHT,
            master=self._root,
        )
        badge_w = self._fps_photo.width()
        self._fps_x = -WINDOW_WIDTH * 0.5 + 14.0 + badge_w * 0.5
        self._fps_y = WINDOW_HEIGHT * 0.5 - 14.0 - FPS_BADGE_HEIGHT * 0.5
        self._fps_text_y = compute_hud_text_y(self._fps_y, self._fps_font_obj)

        self._fps_bg_item = self._tk_canvas.create_image(
            self._fps_x, -self._fps_y, image=self._fps_photo, anchor="center"
        )

        self._fps_pen.pencolor(HUD_TEXT_COLOR)
        self._fps_pen.goto(self._fps_x + self._fps_text_x_offset, self._fps_text_y)
        self._fps_pen.write("-- FPS", move=False, align="left", font=self._fps_font_tuple)
        self._fps_text_item = self._fps_pen.items[-1]

    def _reposition_hud_items(self) -> None:
        if self._hud_bg_item is not None:
            self._canvas.coords(self._hud_bg_item, self._hud_x, -self._hud_y)

        segments = (
            self._hud_segments_paused
            if self._hud_segments_is_paused
            else self._hud_segments_playing
        )
        for item_id, (seg_x, _label) in zip(self._hud_text_items, segments):
            # TurtleScreen._write places text at (x - 1, -y)
            self._canvas.coords(item_id, self._hud_x + seg_x - 1.0, -self._hud_text_y)

        if self._fps_bg_item is not None:
            self._canvas.coords(self._fps_bg_item, self._fps_x, -self._fps_y)
        if self._fps_text_item is not None:
            self._canvas.coords(
                self._fps_text_item,
                self._fps_x + self._fps_text_x_offset - 1.0,
                -self._fps_text_y,
            )

        if self._speed_bg_item is not None:
            self._canvas.coords(self._speed_bg_item, self._speed_x, -self._speed_y)
        if self._speed_track_item is not None and self._speed_layout is not None:
            self._canvas.coords(
                self._speed_track_item,
                self._speed_x + self._speed_layout.track_x_offset,
                -self._speed_y,
            )
        if self._speed_label_item is not None and self._speed_layout is not None:
            self._canvas.coords(
                self._speed_label_item,
                self._speed_x + self._speed_layout.label_x_offset - 1.0,
                -self._speed_text_y,
            )
        if self._speed_value_item is not None and self._speed_layout is not None:
            self._canvas.coords(
                self._speed_value_item,
                self._speed_x + self._speed_layout.value_x_offset - 1.0,
                -self._speed_text_y,
            )

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
        if viewport == self._last_viewport:
            return
        self._last_viewport = viewport
        self._viewport_fov_scale = FOV_SCALE * _clamp(
            min(cw, ch) / float(WINDOW_SIZE), 0.4, 4.0
        )

        self._hud_x = (x0 + x1) * 0.5
        self._hud_y = y_bottom + 14.0 + HUD_HEIGHT * 0.5
        self._hud_text_y = compute_hud_text_y(self._hud_y, self._hud_font_obj)

        self._speed_x = self._hud_x
        self._speed_y = self._hud_y + HUD_HEIGHT * 0.5 + SPEED_HUD_GAP + SPEED_HUD_HEIGHT * 0.5
        self._speed_text_y = compute_hud_text_y(self._speed_y, self._hud_font_obj)

        if self._fps_photo is not None:
            self._fps_x = x0 + 14.0 + self._fps_photo.width() * 0.5
        self._fps_y = y_top - 14.0 - FPS_BADGE_HEIGHT * 0.5
        self._fps_text_y = compute_hud_text_y(self._fps_y, self._fps_font_obj)

        desired_max_w = max(260, cw - 24)
        cur_pill_w = self._hud_pill_playing.width() if self._hud_pill_playing else 0
        need_rebuild = (cur_pill_w > desired_max_w) or (
            self._hud_is_compact and desired_max_w >= self._hud_natural_w
        )
        if need_rebuild:
            old_pills = self._hud_transition_pills
            old_paused = self._hud_pill_paused
            self._rebuild_hud_pills(desired_max_w)
            self._update_hud_text(force_rebuild_text=True)
            old_pills.clear()
            del old_paused
        self._reposition_hud_items()

    def _on_canvas_configure(self, _event: tk.Event[tk.Misc]) -> None:
        if self._resize_after_id is None and self.running:
            self._resize_after_id = self._root.after_idle(self._sync_hud_to_viewport)

    def _raise_overlays(self) -> None:
        if self._hud_bg_item is not None:
            self._canvas.tag_raise(self._hud_bg_item)
        for item_id in self._hud_text_items:
            self._canvas.tag_raise(item_id)
        for item_id in (
            self._speed_bg_item,
            self._speed_track_item,
            self._speed_label_item,
            self._speed_value_item,
        ):
            if item_id is not None:
                self._canvas.tag_raise(item_id)
        for item_id in (self._fps_bg_item, self._fps_text_item):
            if item_id is not None:
                self._canvas.tag_raise(item_id)

    def _update_hud_text(self, *, force_rebuild_text: bool = False) -> None:
        max_step = max(0, len(self._hud_transition_pills) - 1)
        eased = _smootherstep(self._hud_enable_blend)
        step_idx = min(max_step, max(0, int(round(eased * max_step))))
        use_paused_layout = (
            self.paused and not self._controls_locked and step_idx >= max_step
        )
        desired_color = _hud_ink_hex(eased)

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
            # item[0] is the turtle's internal currentLineItem; text items follow it
            self._hud_text_items = list(self._hud_pen.items[1:])
            self._hud_segments_is_paused = use_paused_layout
            self._hud_applied_color = desired_color
            self._raise_overlays()
        elif desired_color != self._hud_applied_color:
            for item_id in self._hud_text_items:
                self._canvas.itemconfigure(item_id, fill=desired_color)
            self._hud_applied_color = desired_color

        self._update_speed_slider_visual(step_idx=step_idx, ink_color=desired_color)

    def _bind_events(self) -> None:
        canvas = self._canvas
        self._root.protocol("WM_DELETE_WINDOW", self.close)

        canvas.bind("<Configure>", self._on_canvas_configure, add="+")
        canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        canvas.bind("<B1-Motion>", self._on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        canvas.bind("<Motion>", self._on_mouse_motion)
        canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        canvas.bind("<Button-4>", lambda _e: self._adjust_zoom(1.08))
        canvas.bind("<Button-5>", lambda _e: self._adjust_zoom(1.0 / 1.08))

        self.screen.listen()
        self._bind_key("space", self.toggle_pause)
        self._bind_key("b", self.replay_bloom)
        self._bind_key("B", self.replay_bloom)
        self._bind_key("r", self.reset_view)
        self._bind_key("R", self.reset_view)
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

    def _is_in_speed_slider(self, cx: float, cy: float) -> bool:
        layout = self._speed_layout
        if layout is None:
            return False
        return (
            abs(cx - self._speed_x) <= layout.pill_width * 0.5
            and abs(cy - self._speed_y) <= layout.pill_height * 0.5
        )

    def _set_canvas_cursor(self, cursor: str) -> None:
        if cursor != self._canvas_cursor:
            self._tk_canvas.configure(cursor=cursor)
            self._canvas_cursor = cursor

    def set_rotation_speed(self, speed: float) -> None:
        """Set auto-rotation speed multiplier within ``[1.0, 5.0]`` and refresh HUD."""
        clamped = _clamp(float(speed), ROTATION_SPEED_MIN, ROTATION_SPEED_MAX)
        if abs(clamped - self.rotation_speed) < 1e-6:
            return
        self.rotation_speed = clamped
        if self._speed_value_item is not None:
            self._canvas.itemconfigure(
                self._speed_value_item, text=f"{self.rotation_speed:.1f}x"
            )
        eased = _smootherstep(self._hud_enable_blend)
        max_step = max(0, len(self._speed_transition_pills) - 1)
        step_idx = min(max_step, max(0, int(round(eased * max_step))))
        self._update_speed_slider_visual(step_idx=step_idx, ink_color=_hud_ink_hex(eased))

    def _set_speed_from_canvas_x(self, cx: float) -> None:
        layout = self._speed_layout
        if layout is None:
            return
        track_center_x = self._speed_x + layout.track_x_offset
        half_travel = max(1.0, layout.track_width * 0.5 - layout.track_pad)
        frac = _clamp((cx - (track_center_x - half_travel)) / (2.0 * half_travel), 0.0, 1.0)
        self.set_rotation_speed(
            ROTATION_SPEED_MIN + frac * (ROTATION_SPEED_MAX - ROTATION_SPEED_MIN)
        )

    def _on_mouse_motion(self, event: tk.Event[tk.Misc]) -> None:
        if self._controls_locked:
            self._set_canvas_cursor("")
            return
        if self._dragging_speed:
            self._set_canvas_cursor("hand2")
            return
        cx, cy = self._event_to_canvas_coords(event)
        self._set_canvas_cursor("hand2" if self._is_in_speed_slider(cx, cy) else "")

    def _on_mouse_down(self, event: tk.Event[tk.Misc]) -> None:
        self.screen.listen()
        if self._controls_locked:
            return
        cx, cy = self._event_to_canvas_coords(event)
        if self._is_in_speed_slider(cx, cy):
            self._dragging_speed = True
            self._dragging = False
            self._set_canvas_cursor("hand2")
            self._set_speed_from_canvas_x(cx)
            return
        self._cancel_camera_transitions()
        self._dragging = True
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y

    def _on_mouse_drag(self, event: tk.Event[tk.Misc]) -> None:
        if self._controls_locked:
            return
        if self._dragging_speed:
            cx, _cy = self._event_to_canvas_coords(event)
            self._set_speed_from_canvas_x(cx)
            return
        if not self._dragging:
            return
        dx = event.x - self._last_mouse_x
        dy = event.y - self._last_mouse_y
        self._last_mouse_x = event.x
        self._last_mouse_y = event.y

        self.yaw += dx * 0.009
        self.pitch = _clamp(self.pitch + dy * 0.008, -1.25, 1.45)

    def _on_mouse_up(self, event: tk.Event[tk.Misc]) -> None:
        self._dragging = False
        if self._dragging_speed:
            self._dragging_speed = False
            cx, cy = self._event_to_canvas_coords(event)
            hovering = not self._controls_locked and self._is_in_speed_slider(cx, cy)
            self._set_canvas_cursor("hand2" if hovering else "")

    def _on_mouse_wheel(self, event: tk.Event[tk.Misc]) -> None:
        if self._controls_locked:
            return
        factor = 1.08 if event.delta > 0 else (1.0 / 1.08)
        self._adjust_zoom(factor)

    def _adjust_zoom(self, factor: float) -> None:
        if self._controls_locked:
            return
        self._cancel_camera_transitions()
        self.zoom = _clamp(self.zoom * factor, 0.55, 2.35)

    def _nudge_camera(self, dyaw: float, dpitch: float) -> None:
        if self._controls_locked:
            return
        self._cancel_camera_transitions()
        self.yaw += dyaw
        self.pitch = _clamp(self.pitch + dpitch, -1.25, 1.45)

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
        self.yaw = DEFAULT_YAW
        self.pitch = STARTUP_PITCH
        self.zoom = STARTUP_ZOOM
        self.current_bloom = 0.0
        self.bloom_elapsed = 0.0
        self.bloom_done = False
        self._camera_tween_active = True
        self._tween_elapsed = 0.0
        self._tween_start_pitch = STARTUP_PITCH
        self._tween_start_zoom = STARTUP_ZOOM
        self.mesh.update_bloom(0.0)

    def reset_view(self) -> None:
        """Smoothly transition back to the startup overhead bud, then replay startup."""
        if self._controls_locked:
            return
        self._controls_locked = True
        self._dragging = False
        self._dragging_speed = False
        self._set_canvas_cursor("")
        self.paused = False
        self._update_hud_text()
        self._camera_tween_active = False

        # Wrap yaw along shortest angular path to DEFAULT_YAW
        delta_yaw = (DEFAULT_YAW - self.yaw + math.pi) % (2.0 * math.pi) - math.pi
        nearly_there = (
            abs(delta_yaw) < 1e-3
            and abs(self.pitch - STARTUP_PITCH) < 1e-3
            and abs(self.zoom - STARTUP_ZOOM) < 1e-3
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
        for after_attr in ("_after_id", "_resize_after_id"):
            after_id = getattr(self, after_attr, None)
            if after_id is not None:
                try:
                    self._root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(self, after_attr, None)

        for item in self._poly_pool:
            try:
                self._canvas.delete(item)
            except tk.TclError:
                pass
        self._poly_pool.clear()
        self._pool_fills.clear()
        self._pool_visible.clear()

        for attr in ("_hud_bg_item", "_fps_bg_item", "_speed_bg_item", "_speed_track_item"):
            item_id = getattr(self, attr, None)
            if item_id is not None:
                try:
                    self._canvas.delete(item_id)
                except tk.TclError:
                    pass
                setattr(self, attr, None)

        for pen in (self._hud_pen, self._fps_pen, self._speed_pen):
            try:
                pen.clear()
            except (turtle.Terminator, tk.TclError):
                pass

        self._hud_text_items.clear()
        self._fps_text_item = None
        self._speed_label_item = None
        self._speed_value_item = None
        self._hud_transition_pills.clear()
        self._speed_transition_pills.clear()
        self._hud_pill_playing = None
        self._hud_pill_paused = None
        self._hud_pill_disabled = None
        self._fps_photo = None
        self._speed_track_photo = None
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
        )
        coords = self._canvas.coords
        itemcfg = self._canvas.itemconfigure
        pool = self._poly_pool
        pool_fills = self._pool_fills
        pool_visible = self._pool_visible

        for idx, (_z, fill_hex, pts) in enumerate(draw_list):
            item = pool[idx]
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

            if not pool_visible[idx]:
                if pool_fills[idx] != fill_hex:
                    itemcfg(item, fill=fill_hex, state="normal")
                    pool_fills[idx] = fill_hex
                else:
                    itemcfg(item, state="normal")
                pool_visible[idx] = True
            elif pool_fills[idx] != fill_hex:
                itemcfg(item, fill=fill_hex)
                pool_fills[idx] = fill_hex

        for idx in range(len(draw_list), len(pool)):
            if pool_visible[idx]:
                itemcfg(pool[idx], state="hidden")
                pool_visible[idx] = False

        self._root.update_idletasks()

    def _tick(self) -> None:
        self._after_id = None
        if not self.running:
            return

        now = time.perf_counter()
        dt = min(now - self._last_frame_time, 0.08)
        self._last_frame_time = now

        if self._reset_active:
            self._reset_elapsed += dt
            raw_r = _clamp(self._reset_elapsed / RESET_TRANSITION_DURATION, 0.0, 1.0)
            eased_r = _smootherstep(raw_r)
            self.yaw = _lerp(self._reset_start_yaw, self._reset_target_yaw, eased_r)
            self.pitch = _lerp(self._reset_start_pitch, STARTUP_PITCH, eased_r)
            self.zoom = _lerp(self._reset_start_zoom, STARTUP_ZOOM, eased_r)
            self.current_bloom = _lerp(self._reset_start_bloom, 0.0, eased_r)
            self.mesh.update_bloom(self.current_bloom)
            if raw_r >= 1.0:
                self._reset_active = False
                self._start_startup_sequence()
        else:
            if not self.paused and not self._dragging:
                self.yaw += AUTO_ROTATE_SPEED * self.rotation_speed * dt

            if not self.bloom_done:
                self.bloom_elapsed += dt
                raw_t = _clamp(self.bloom_elapsed / BLOOM_DURATION, 0.0, 1.0)
                # Smooth ease-out curve for organic opening motion
                self.current_bloom = 1.0 - (1.0 - raw_t) ** 2.4
                self.mesh.update_bloom(self.current_bloom)
                if raw_t >= 1.0:
                    self.bloom_done = True
            elif self._camera_tween_active:
                self._tween_elapsed += dt
                raw_c = _clamp(self._tween_elapsed / CAMERA_TWEEN_DURATION, 0.0, 1.0)
                eased_c = _smootherstep(raw_c)
                self.pitch = _lerp(self._tween_start_pitch, DEFAULT_PITCH, eased_c)
                self.zoom = _lerp(self._tween_start_zoom, DEFAULT_ZOOM, eased_c)
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

        try:
            self._render_frame()
            self._fps_frames += 1
            after_render = time.perf_counter()
            fps_dt = after_render - self._fps_window_start
            if fps_dt >= FPS_UPDATE_INTERVAL and self._fps_text_item is not None:
                fps_val = min(float(TARGET_FPS), self._fps_frames / fps_dt)
                self._canvas.itemconfigure(self._fps_text_item, text=f"{fps_val:.0f} FPS")
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


def _relaunch_windowless_if_needed() -> bool:
    """On Windows, relaunch via pythonw.exe so no terminal/console remains open."""
    if sys.platform != "win32":
        return False
    if "--no-detach" in sys.argv or os.environ.get("ROSE_DETACHED") == "1":
        return False

    exe_path = Path(os.path.abspath(sys.executable))
    if exe_path.name.lower() == "pythonw.exe":
        return False

    candidate = exe_path.with_name("pythonw.exe")
    if not candidate.exists() or candidate.is_symlink() or not candidate.is_file():
        return False

    env = os.environ.copy()
    env["ROSE_DETACHED"] = "1"
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
        app = RoseViewerApp()
        app.run()
    finally:
        if should_restore:
            _restore_console_window(console_hwnd)


if __name__ == "__main__":
    main()
