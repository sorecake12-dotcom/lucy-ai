"""
core/animated_shapes.py — Procedural 3D shape point-cloud builders.

Pure-python / no deps. Each builder returns (points, groups) where:
  • points : list[(x, y, z)] in a NORMALIZED box — roughly [-1, 1] per axis,
             already scaled so the shape fills the space correctly.
  • groups : list[int] — one entry per point. The particle renderer maps each
             group to its own colour, so multi-part objects (car body vs
             windows vs wheels, tree trunk vs leaves) read clearly.

Every shape is sampled ON/NEAR THE SURFACE of real 3D geometry (lofted
cross-sections, revolved profiles, boxes) with evenly spaced rings — not a
random spray — so silhouettes stay recognizable from the default 3/4 camera.

Shape conventions (used by the renderer's 3/4 camera):
  +X = front of the object,  +Y = up,  +Z = toward the default camera.
"""
from __future__ import annotations

import math
import random

_TAU = 2.0 * math.pi


# ── helpers ─────────────────────────────────────────────────────────────────

def _ring(points, groups, group, cx, cy, cz, rx, rz, count,
          fill=0.0, rng=None):
    """Append one horizontal ring (ellipse) of points. fill>0 adds interior
    points (that fraction of `count`) for solid-looking caps."""
    rng = rng or random
    for i in range(count):
        a = _TAU * i / count
        x = cx + rx * math.cos(a)
        z = cz + rz * math.sin(a)
        points.append((x, cy, z))
        groups.append(group)
    if fill > 0.0:
        for i in range(int(count * fill)):
            a = _TAU * i / max(1, int(count * fill))
            rr = rng.uniform(0.0, 0.92)
            x = cx + rx * rr * math.cos(a)
            z = cz + rz * rr * math.sin(a)
            points.append((x, cy, z))
            groups.append(group)


def _loft(points, groups, group, profiles, rings_per=8, closed=False,
          fill_ends=0.0, rng=None):
    """Sweep through `profiles` — each profile is (y, [(rx, rz), ...]) sampled
    around the vertical axis. Smoothly interpolates between profiles so the
    surface is continuous (this is what makes shapes read as SOLID, not as
    disconnected point clusters)."""
    rng = rng or random
    total = len(profiles) - 1
    for pi in range(total):
        y0, rxs0 = profiles[pi]
        y1, rxs1 = profiles[pi + 1]
        for s in range(rings_per):
            f = s / rings_per
            y = y0 + (y1 - y0) * f
            # interpolate the (rx, rz) ring between the two profiles
            r0 = rxs0[min(len(rxs0) - 1, int(f * len(rxs0)))] if False else rxs0[0]
            r1 = rxs1[0]
            rx = r0 + (r1 - r0) * f
            rz = r0 + (r1 - r0) * f
            _ring(points, groups, group, 0.0, y, 0.0, rx, rz, 18,
                  fill=fill_ends if (pi == 0 and s == 0) else 0.0, rng=rng)
    # final cap
    yf, rxf = profiles[-1]
    _ring(points, groups, group, 0.0, yf, 0.0, rxf[0], rxf[0], 18,
          fill=fill_ends, rng=rng)


def _revolve(points, groups, group, profile_xy, steps=44, fill=0.0, rng=None):
    """Revolve a 2D profile [(x, y), ...] (x = radius >= 0) around the Y axis —
    the clean way to build spheres/hearts/vases where every ring is even."""
    rng = rng or random
    m = len(profile_xy)
    for i in range(steps):
        a = _TAU * i / steps
        ca, sa = math.cos(a), math.sin(a)
        for j, (rx, y) in enumerate(profile_xy):
            # Even 3D spacing: distribute the profile points around each ring.
            x = rx * ca
            z = rx * sa
            points.append((x, y, z))
            groups.append(group)
    if fill > 0.0:
        for i in range(int(steps * fill)):
            a = _TAU * i / max(1, int(steps * fill))
            rr = rng.uniform(0.0, 0.9)
            j = rng.randrange(m)
            rx, y = profile_xy[j]
            points.append((rr * rx * math.cos(a), y, rr * rx * math.sin(a)))
            groups.append(group)


def _box_surface(points, groups, group, cx, cy, cz, hx, hy, hz, n, rng,
                 skip_bottom=False):
    """Even sampling over the 6 faces of a box (optionally without the bottom)."""
    faces = 5 if skip_bottom else 6
    per = max(1, n // faces)
    for _ in range(per):
        u, v = rng.uniform(-1, 1), rng.uniform(-1, 1)
        face = rng.randrange(faces)
        if face == 0:   p = (cx + hx, cy + hy * u, cz + hz * v)
        elif face == 1: p = (cx - hx, cy + hy * u, cz + hz * v)
        elif face == 2: p = (cx + hx * u, cy + hy, cz + hz * v)
        elif face == 3: p = (cx + hx * u, cy - hy, cz + hz * v)
        else:           p = (cx + hx * u, cy + hy * v, cz + hz)
        points.append(p)
        groups.append(group)


def _wheel(points, groups, group_tyre, group_hub, wx, wy, wz, R, half_w, rng,
           n):
    """One car wheel, in the X-Y plane (axle along Z): tyre ring + hub disc."""
    for i in range(n):
        a = _TAU * i / n
        # tyre: two circles (outer edges) + tread between them
        for dz in (-half_w, half_w):
            points.append((wx + R * math.cos(a), wy + R * math.sin(a), wz + dz))
            groups.append(group_tyre)
        if i % 2 == 0:
            rr = R * rng.uniform(0.78, 0.95)
            points.append((wx + rr * math.cos(a), wy + rr * math.sin(a),
                           wz + rng.uniform(-half_w, half_w)))
            groups.append(group_tyre)
    # hub
    for i in range(max(6, n // 3)):
        a = _TAU * i / max(6, n // 3)
        rr = R * rng.uniform(0.0, 0.45)
        points.append((wx + rr * math.cos(a), wy + rr * math.sin(a),
                       wz + half_w * 0.9))
        groups.append(group_hub)


# ── builders ────────────────────────────────────────────────────────────────

GROUP_BODYSHELL = 0
GROUP_WINDOWS = 1
GROUP_WHEELS = 2
GROUP_LIGHTS = 3

def build_car(n):
    """Sports-car silhouette: low wedge body, raked cabin (windows), 4 wheels,
    front lights. Recognizable from the standard 3/4 view. Groups:
    0 body, 1 windows/cabin, 2 wheels, 3 headlights."""
    rng = random.Random(7)
    pts: list = []
    grp: list = []

    # ── body: lofted cross-sections nose → tail (x = length axis) ──
    # sections: (x, half_width, y_bottom, y_top)
    L = 1.45
    sections = [
        (-L,        0.18, -0.28, -0.10),   # tail tip
        (-L + 0.15, 0.42, -0.30,  0.00),
        (-L + 0.5,  0.55, -0.30,  0.06),
        (-0.35,     0.62, -0.30,  0.10),   # cabin start / rear haunch
        ( 0.05,     0.64, -0.30,  0.10),   # widest at the doors
        ( 0.55,     0.58, -0.30,  0.08),   # front fender
        ( 0.95,     0.45, -0.28,  0.02),   # nose
        ( L,        0.30, -0.26, -0.08),   # front tip
    ]
    rings = max(10, int(n * 0.42) // (len(sections) * 14))
    for i in range(len(sections) - 1):
        x0, w0, b0, t0 = sections[i]
        x1, w1, b1, t1 = sections[i + 1]
        for s in range(rings):
            f = s / rings
            x = x0 + (x1 - x0) * f
            w = w0 + (w1 - w0) * f
            b = b0 + (b1 - b0) * f
            t = t0 + (t1 - t0) * f
            for k in range(14):
                a = math.pi * k / 13.0          # 0..pi: full loop bottom → top
                y = b + (t - b) * 0.5 * (1.0 - math.cos(a))
                z = w * math.sin(a) * (0.92 + 0.08 * math.cos(a))
                pts.append((x, y, z))
                grp.append(GROUP_BODYSHELL)

    # ── cabin / greenhouse: raked windshield, roof, rear glass (group 1) ──
    cab = [
        (0.55, 0.30, 0.10),    # base of windshield
        (0.30, 0.42, 0.38),    # windshield top
        (-0.05, 0.46, 0.46),   # roof front
        (-0.45, 0.44, 0.44),   # roof rear
        (-0.80, 0.36, 0.18),   # rear glass bottom
    ]
    rings = max(8, int(n * 0.22) // (len(cab) * 14))
    for i in range(len(cab) - 1):
        x0, w0, y0 = cab[i]
        x1, w1, y1 = cab[i + 1]
        for s in range(rings):
            f = s / rings
            x = x0 + (x1 - x0) * f
            w = w0 + (w1 - w0) * f
            y = y0 + (y1 - y0) * f
            for k in range(14):
                a = math.pi * k / 13.0
                yy = y * math.sin(a)
                z = w * math.sin(a)
                pts.append((x, y0 * (1 - math.sin(a)) + yy, z))
                grp.append(GROUP_WINDOWS)

    # ── wheels (group 2) ──
    nw = max(24, int(n * 0.18) // 4)
    for wx in (0.82, -0.85):
        for wz in (0.60, -0.60):
            _wheel(pts, grp, GROUP_WHEELS, GROUP_WHEELS, wx, -0.30, wz,
                   0.26, 0.09, rng, nw)

    # ── headlights (group 3) ──
    nl = max(10, int(n * 0.02))
    for _ in range(nl):
        u = rng.uniform(-0.75, 0.75)
        pts.append((1.30, -0.12 + 0.06 * u, 0.34 + 0.10 * rng.random()))
        grp.append(GROUP_LIGHTS)
        pts.append((1.30, -0.12 + 0.06 * u, -0.34 - 0.10 * rng.random()))
        grp.append(GROUP_LIGHTS)

    return pts, grp


GROUP_TRUNK = 0
GROUP_LEAVES = 1

def build_tree(n):
    """Conifer-ish tree: tapered trunk + 3 stacked foliage cones. Groups:
    0 trunk, 1 leaves."""
    rng = random.Random(5)
    pts: list = []
    grp: list = []

    # trunk: tapered cylinder rings
    nt = max(8, int(n * 0.22))
    rings = 8
    per = max(6, nt // rings)
    for i in range(rings):
        f = i / (rings - 1)
        y = -1.0 + f * 0.62
        r = 0.13 * (1.0 - 0.35 * f)
        for k in range(per):
            a = _TAU * k / per
            pts.append((r * math.cos(a), y, r * math.sin(a)))
            grp.append(GROUP_TRUNK)

    # foliage: 3 stacked cones (surface rings, dense) — the classic tree read
    cones = [
        (-0.30, 0.30, 0.62, 0.10),   # (base_y, base_r, top_y, top_r)
        ( 0.10, 0.40, 0.72, 0.08),
        ( 0.48, 0.30, 0.98, 0.02),
    ]
    nl = int(n * 0.78)
    for (by, br, ty, tr) in cones:
        rings = 9
        per = max(8, nl // (3 * rings))
        for i in range(rings):
            f = i / (rings - 1)
            y = by + f * (ty - by)
            r = br + (tr - br) * f
            for k in range(per):
                a = _TAU * k / per + 0.13 * i   # stagger rings for even look
                pts.append((r * math.cos(a), y, r * math.sin(a)))
                grp.append(GROUP_LEAVES)

    return pts, grp


GROUP_OCEAN = 0
GROUP_LAND = 1
GROUP_CLOUDS = 2

def build_planet(n):
    """Earth: sphere surface (group 0) with rough continent patches (group 1)
    and a couple of cloud bands (group 2). Recognizable as a planet. Groups:
    0 ocean, 1 land, 2 clouds."""
    pts: list = []
    grp: list = []

    # even sphere via latitude rings (clean, no polar clustering)
    rings = max(14, int(math.sqrt(n * 0.78)))
    per = max(10, int(n * 0.78 / rings))
    for i in range(rings):
        v = (i + 0.5) / rings
        y = 1.0 - 2.0 * v
        rr = math.sqrt(max(0.0, 1.0 - y * y))
        for k in range(per):
            a = _TAU * k / per
            pts.append((rr * math.cos(a), y, rr * math.sin(a)))
            grp.append(GROUP_OCEAN)

    # continents: pseudo-random blobs, projected onto the sphere (group 1)
    rng = random.Random(31)
    nl = int(n * 0.14)
    blobs = [((rng.uniform(-1, 1)), rng.uniform(-0.55, 0.75),
              rng.uniform(0.22, 0.45)) for _ in range(7)]
    for _ in range(nl):
        by, bz, br = blobs[rng.randrange(len(blobs))]
        u = rng.uniform(0, _TAU)
        # point near blob centre, snapped to sphere surface
        px = math.cos(u) * rng.uniform(0.0, br)
        pz = math.sin(u) * rng.uniform(0.0, br)
        py = by + rng.uniform(-br * 0.5, br * 0.5)
        ln = math.sqrt(px * px + py * py + pz * pz) or 1.0
        pts.append((px / ln, py / ln, pz / ln))
        grp.append(GROUP_LAND)

    # cloud bands (group 2): thin latitude streaks hovering above surface
    nc = int(n * 0.08)
    for _ in range(nc):
        band = rng.choice((-0.35, 0.05, 0.42))
        y = band + rng.uniform(-0.05, 0.05)
        rr = 1.06 * math.sqrt(max(0.0, 1.0 - y * y))
        a = rng.uniform(0, _TAU)
        pts.append((rr * math.cos(a), y, rr * math.sin(a)))
        grp.append(GROUP_CLOUDS)

    return pts, grp


GROUP_BODY = 0
GROUP_GLOW = 1

def build_heart(n):
    """3D heart: the classic heart OUTLINE revolved with a depth profile that
    is plump at the top lobes and pointed at the bottom — a real volume, not a
    flat shape. Groups: 0 body, 1 inner glow core."""
    rng = random.Random(3)
    pts: list = []
    grp: list = []

    # heart outline parametric (t: 0..2π), normalized to about [-1, 1]
    def outline(t):
        x = 16.0 * math.sin(t) ** 3
        y = (13.0 * math.cos(t) - 5.0 * math.cos(2 * t)
             - 2.0 * math.cos(3 * t) - math.cos(4 * t))
        return x / 17.0, y / 17.0 + 0.12

    # surface: sweep the outline with a half-thickness profile
    steps = 60
    depth_steps = 12
    for i in range(steps):
        t = _TAU * i / steps
        hx, hy = outline(t)
        # thickness: max at the top lobes (t near π/2, 3π/2 … actually top of
        # the heart is around t = π), tapering to 0 at the bottom point.
        # Use |sin(t)| shaped by height: plump top, pointy bottom.
        th = (0.30 * max(0.0, math.sin(t)) + 0.14) * (0.45 + 0.55 * max(0.0, hy))
        for j in range(depth_steps):
            f = j / (depth_steps - 1)
            dz = th * math.cos(math.pi * f)      # -th..th, max at centre
            # scale outline inward near the depth extremes so it rounds off
            s = 0.55 + 0.45 * math.sin(math.pi * f)
            pts.append((hx * s, hy, dz))
            grp.append(GROUP_BODY)

    # inner glow core (group 1): small sphere inside the top lobes
    nc = max(20, int(n * 0.10))
    rings = 6
    per = max(5, nc // rings)
    for i in range(rings):
        v = (i + 0.5) / rings
        y = 1.0 - 2.0 * v
        rr = 0.16 * math.sqrt(max(0.0, 1.0 - y * y))
        for k in range(per):
            a = _TAU * k / per
            pts.append((rr * math.cos(a), 0.42 + 0.35 * y, rr * math.sin(a)))
            grp.append(GROUP_GLOW)

    return pts, grp


GROUP_HULL = 0
GROUP_FLAME = 1
GROUP_FINS = 2

def build_rocket(n):
    """Rocket: nose cone + body + 3 fins + engine flame ring. Groups:
    0 hull, 1 flame, 2 fins."""
    rng = random.Random(11)
    pts: list = []
    grp: list = []

    # hull profile (radius, y): nose → body → skirt
    prof = [
        (0.02, 1.05),
        (0.10, 0.85),
        (0.17, 0.55),
        (0.20, 0.30),
        (0.20, -0.55),
        (0.24, -0.75),
        (0.24, -0.85),
    ]
    steps = 36
    for j in range(len(prof) - 1):
        (r0, y0), (r1, y1) = prof[j], prof[j + 1]
        seg = 3
        for s in range(seg):
            f = s / seg
            r = r0 + (r1 - r0) * f
            y = y0 + (y1 - y0) * f
            for k in range(steps):
                a = _TAU * k / steps
                pts.append((r * math.cos(a), y, r * math.sin(a)))
                grp.append(GROUP_HULL)

    # fins: 3 thin swept plates
    nf = max(24, int(n * 0.10) // 3)
    for fi in range(3):
        base = fi * _TAU / 3.0 + math.pi / 6
        for _ in range(nf):
            u = rng.random()          # radial span
            v = rng.random()          # vertical span
            r = 0.21 + u * 0.30
            y = -0.85 + v * 0.50 * (1.0 - 0.4 * u)
            pts.append((r * math.cos(base), y, r * math.sin(base)))
            grp.append(GROUP_FINS)

    # flame ring under the skirt (group 1)
    nfl = max(16, int(n * 0.08))
    for _ in range(nfl):
        u = rng.random()
        y = -0.88 - u * 0.30
        r = 0.20 * (1.0 - u * 0.75) * (1.0 + 0.12 * math.sin(u * 9.0))
        a = rng.uniform(0, _TAU)
        pts.append((r * math.cos(a), y, r * math.sin(a)))
        grp.append(GROUP_FLAME)

    return pts, grp


def build_cat(n):
    """Cat: body + head + ears + tail + legs. Group 0 body, 1 details."""
    rng = random.Random(9)
    pts: list = []
    grp: list = []

    def ball(cx, cy, cz, rx, ry, rz, count, group):
        rings = max(4, int(math.sqrt(count / 2)))
        per = max(4, count // rings)
        for i in range(rings):
            v = (i + 0.5) / rings
            y = 1.0 - 2.0 * v
            rr = math.sqrt(max(0.0, 1.0 - y * y))
            for k in range(per):
                a = _TAU * k / per
                pts.append((cx + rx * rr * math.cos(a),
                            cy + ry * y,
                            cz + rz * rr * math.sin(a)))
                grp.append(group)

    ball(0.0, -0.05, 0.0, 0.62, 0.34, 0.36, int(n * 0.38), 0)   # body
    ball(0.55, 0.35, 0.0, 0.28, 0.26, 0.27, int(n * 0.24), 0)   # head
    # ears
    for dz in (-0.15, 0.15):
        for i in range(max(8, int(n * 0.02))):
            u = rng.random()
            y = 0.55 + u * 0.20
            r = 0.10 * (1.0 - u)
            a = rng.uniform(0, _TAU)
            pts.append((0.55 + r * math.cos(a) * 0.8, y, dz + r * math.sin(a) * 0.8))
            grp.append(1)
    # tail: curve up behind
    for i in range(16):
        f = i / 15.0
        x = -0.62 - 0.15 * f
        y = -0.05 + 0.55 * f
        z = 0.18 * math.sin(f * 3.0)
        for k in range(4):
            a = _TAU * k / 4
            pts.append((x + 0.045 * math.cos(a), y, z + 0.045 * math.sin(a)))
            grp.append(1)
    # legs
    for sx in (-0.32, 0.32):
        for sz in (-0.20, 0.20):
            for i in range(max(6, int(n * 0.012))):
                y = -0.62 + rng.random() * 0.32
                a = rng.uniform(0, _TAU)
                pts.append((sx + 0.06 * math.cos(a), y, sz + 0.06 * math.sin(a)))
                grp.append(1)

    return pts, grp


GROUP_WALLS = 0
GROUP_ROOF = 1
GROUP_WINDOWS = 2

def build_house(n):
    """House: walls box + pitched roof + glowing windows. Groups:
    0 walls, 1 roof, 2 windows."""
    rng = random.Random(13)
    pts: list = []
    grp: list = []

    # walls
    _box_surface(pts, grp, GROUP_WALLS, 0, -0.35, 0, 0.55, 0.55, 0.42,
                 int(n * 0.45), rng, skip_bottom=True)

    # roof: pitched prism, ridge along z
    nr = int(n * 0.35)
    for _ in range(nr):
        side = rng.randrange(2)
        u = rng.uniform(-0.62, 0.62)      # along ridge (z)
        v = rng.random()                  # up the slope
        if side == 0:
            x = -0.65 * (1 - v)
            y = 0.20 + v * 0.62
        else:
            x = 0.65 * (1 - v)
            y = 0.20 + v * 0.62
        pts.append((x, y, u))
        grp.append(GROUP_ROOF)
    # ridge line (denser, reads as the roof edge)
    for i in range(max(8, int(n * 0.02))):
        pts.append((0.0, 0.82, -0.62 + 1.24 * i / max(8, int(n * 0.02))))
        grp.append(GROUP_ROOF)

    # windows/door (group 2): rectangles on the front face (+z)
    nw = int(n * 0.20)
    wins = [(-0.28, -0.25), (0.18, -0.25), (-0.05, -0.72)]
    sizes = [(0.14, 0.14), (0.14, 0.14), (0.11, 0.22)]
    for (wx, wy), (hw, hh) in zip(wins, sizes):
        for _ in range(max(6, nw // 3)):
            pts.append((wx + rng.uniform(-hw, hw),
                        wy + rng.uniform(-hh, hh),
                        0.43))
            grp.append(GROUP_WINDOWS)

    return pts, grp


GROUP_CHROME = 0
GROUP_ACCENT = 1

def build_robot(n):
    """Boxy humanoid robot. Groups: 0 chrome shell, 1 eyes/antenna accents."""
    rng = random.Random(17)
    pts: list = []
    grp: list = []

    def box(cx, cy, cz, hx, hy, hz, count, group):
        _box_surface(pts, grp, group, cx, cy, cz, hx, hy, hz, count, rng)

    box(0.0, 0.72, 0.0, 0.26, 0.22, 0.24, int(n * 0.20), GROUP_CHROME)   # head
    box(0.0, 0.05, 0.0, 0.34, 0.42, 0.20, int(n * 0.30), GROUP_CHROME)   # torso
    for sx in (-0.46, 0.46):
        box(sx, 0.02, 0.0, 0.09, 0.40, 0.09, int(n * 0.08), GROUP_CHROME)
    for sx in (-0.17, 0.17):
        box(sx, -0.80, 0.0, 0.11, 0.36, 0.11, int(n * 0.09), GROUP_CHROME)
    # eyes (accent)
    for sx in (-0.10, 0.10):
        for i in range(max(6, int(n * 0.01))):
            pts.append((sx + rng.uniform(-0.035, 0.035),
                        0.76 + rng.uniform(-0.035, 0.035),
                        0.24))
            grp.append(GROUP_ACCENT)
    # antenna
    for i in range(max(8, int(n * 0.012))):
        pts.append((0.0, 0.96 + rng.random() * 0.22, 0.0))
        grp.append(GROUP_ACCENT)

    return pts, grp


GROUP_BALL = 0
GROUP_RING = 1

def build_saturn(n):
    """Saturn: sphere + tilted ring. Groups: 0 planet, 1 ring."""
    pts: list = []
    grp: list = []
    rings = max(12, int(math.sqrt(n * 0.55)))
    per = max(8, int(n * 0.55 / rings))
    for i in range(rings):
        v = (i + 0.5) / rings
        y = 1.0 - 2.0 * v
        rr = math.sqrt(max(0.0, 1.0 - y * y))
        for k in range(per):
            a = _TAU * k / per
            pts.append((0.72 * rr * math.cos(a), 0.72 * y, 0.72 * rr * math.sin(a)))
            grp.append(GROUP_BALL)
    # tilted ring
    tilt = 0.40
    ct, st = math.cos(tilt), math.sin(tilt)
    nr = n - len(pts)
    radii = [(0.95, 1.15, 0.75), (1.22, 1.32, 0.25)]  # (rmin, rmax, share)
    for _ in range(max(20, nr)):
        pick = rng = random.random()
        if pick < radii[0][2]:
            rmin, rmax = radii[0][0], radii[0][1]
        else:
            rmin, rmax = radii[1][0], radii[1][1]
        a = random.uniform(0, _TAU)
        r = random.uniform(rmin, rmax)
        x0 = r * math.cos(a)
        z0 = r * math.sin(a)
        pts.append((x0, -z0 * st, z0 * ct))
        grp.append(GROUP_RING)

    return pts, grp


def build_cube(n):
    """Cube shell with edge highlights. Group 0 faces, 1 edges."""
    rng = random.Random(23)
    pts: list = []
    grp: list = []
    E = 0.8
    _box_surface(pts, grp, 0, 0, 0, 0, E, E, E, int(n * 0.8), rng)
    for i in range(max(12, int(n * 0.2))):
        # edge points
        axis = rng.randrange(3)
        sign = 1 if rng.random() < 0.5 else -1
        t = rng.uniform(-E, E)
        if axis == 0:   p = (sign * E, sign * E, t)
        elif axis == 1: p = (sign * E, t, sign * E)
        else:           p = (t, sign * E, sign * E)
        pts.append(p)
        grp.append(1)
    return pts, grp


def build_sphere(n):
    """Plain sphere surface. Group 0."""
    pts: list = []
    grp: list = []
    rings = max(12, int(math.sqrt(n)))
    per = max(8, n // rings)
    for i in range(rings):
        v = (i + 0.5) / rings
        y = 1.0 - 2.0 * v
        rr = math.sqrt(max(0.0, 1.0 - y * y))
        for k in range(per):
            a = _TAU * k / per
            pts.append((rr * math.cos(a), y, rr * math.sin(a)))
            grp.append(0)
    return pts, grp


def build_star(n):
    """3D 5-pointed faceted star. Groups: 0 star body facets, 1 glowing perimeter edges."""
    rng = random.Random(42)
    pts: list = []
    grp: list = []

    verts = []
    for k in range(10):
        ang = math.pi / 2.0 + k * _TAU / 10.0
        r = 0.95 if (k % 2 == 0) else 0.40
        verts.append((r * math.cos(ang), r * math.sin(ang)))

    n_facets = int(n * 0.75) // 20
    for k in range(10):
        v1 = verts[k]
        v2 = verts[(k + 1) % 10]
        for z_sign in (1.0, -1.0):
            apex = (0.0, 0.0, 0.22 * z_sign)
            for _ in range(max(10, n_facets)):
                r1 = math.sqrt(rng.random())
                r2 = rng.random()
                u = 1.0 - r1
                v = r1 * (1.0 - r2)
                w = r1 * r2
                px = u * apex[0] + v * v1[0] + w * v2[0]
                py = u * apex[1] + v * v1[1] + w * v2[1]
                pz = u * apex[2]
                pts.append((px, py, pz))
                grp.append(0)

    n_edge = int(n * 0.25) // 10
    for k in range(10):
        v1 = verts[k]
        v2 = verts[(k + 1) % 10]
        for i in range(max(8, n_edge)):
            t = i / max(8, n_edge)
            px = v1[0] + (v2[0] - v1[0]) * t
            py = v1[1] + (v2[1] - v1[1]) * t
            pts.append((px, py, rng.uniform(-0.04, 0.04)))
            grp.append(1)

    return pts, grp


def build_flower(n):
    """3D blossoming flower. Groups: 0 stem/leaves, 1 center disc, 2 petals."""
    rng = random.Random(55)
    pts: list = []
    grp: list = []

    # 1. Stem
    n_stem = int(n * 0.18)
    for _ in range(n_stem):
        y = rng.uniform(-0.85, -0.05)
        a = rng.uniform(0, _TAU)
        r = rng.uniform(0.02, 0.05)
        curv = 0.06 * math.sin((y + 0.85) * 2.5)
        pts.append((curv + r * math.cos(a), y, r * math.sin(a)))
        grp.append(0)

    # Leaves
    for side, y_leaf in ((-1, -0.50), (1, -0.32)):
        n_leaf = int(n * 0.06)
        for _ in range(n_leaf):
            u = rng.random()
            w = math.sin(u * math.pi) * 0.12 * (rng.random() ** 0.5)
            lx = side * (0.04 + u * 0.32)
            ly = y_leaf + u * 0.12 - (u ** 2) * 0.08
            pts.append((lx, ly, w))
            grp.append(0)

    # 2. Disc
    n_center = int(n * 0.20)
    for _ in range(n_center):
        a = rng.uniform(0, _TAU)
        r = 0.18 * math.sqrt(rng.random())
        y = 0.05 + 0.08 * math.cos((r / 0.18) * (math.pi / 2))
        pts.append((r * math.cos(a), y, r * math.sin(a)))
        grp.append(1)

    # 3. Petals
    num_petals = 6
    n_petals = int(n * 0.50)
    pts_per_petal = n_petals // num_petals
    for p in range(num_petals):
        p_ang = p * _TAU / num_petals
        ca = math.cos(p_ang)
        sa = math.sin(p_ang)
        for _ in range(pts_per_petal):
            u = rng.uniform(0.12, 0.72)
            w_max = 0.22 * math.sin(((u - 0.12) / 0.60) * math.pi)
            v = rng.uniform(-w_max, w_max)
            cup = 0.14 * math.sin(((u - 0.12) / 0.60) * math.pi)
            px = u * ca - v * sa
            pz = u * sa + v * ca
            py = 0.04 + cup
            pts.append((px, py, pz))
            grp.append(2)

    return pts, grp


def build_human(n):
    """3D human silhouette. Groups: 0 head/limbs, 1 torso/legs."""
    rng = random.Random(77)
    pts: list = []
    grp: list = []

    def ball(cx, cy, cz, rx, ry, rz, count, group):
        rings = max(8, int(math.sqrt(count)))
        per = max(6, count // rings)
        for i in range(rings):
            v = (i + 0.5) / rings
            y = 1.0 - 2.0 * v
            rr = math.sqrt(max(0.0, 1.0 - y * y))
            for k in range(per):
                a = _TAU * k / per
                pts.append((cx + rx * rr * math.cos(a),
                            cy + ry * y,
                            cz + rz * rr * math.sin(a)))
                grp.append(group)

    # Head
    ball(0.0, 0.72, 0.0, 0.13, 0.16, 0.14, int(n * 0.14), 0)

    # Torso
    n_torso = int(n * 0.32)
    for _ in range(n_torso):
        y = rng.uniform(-0.05, 0.52)
        fy = (y - (-0.05)) / 0.57
        rx = 0.20 + 0.06 * math.cos((1.0 - fy) * math.pi)
        rz = 0.11 + 0.03 * math.cos(fy * math.pi)
        a = rng.uniform(0, _TAU)
        pts.append((rx * math.cos(a), y, rz * math.sin(a)))
        grp.append(1)

    # Arms
    n_arms = int(n * 0.22) // 2
    for sx in (-1, 1):
        for _ in range(n_arms):
            t = rng.random()
            y = 0.46 - t * 0.50
            x = sx * (0.25 + t * 0.08)
            z = rng.uniform(-0.05, 0.05)
            r = 0.05 * (1.0 - t * 0.3)
            a = rng.uniform(0, _TAU)
            pts.append((x + r * math.cos(a), y, z + r * math.sin(a)))
            grp.append(0)

    # Legs
    n_legs = int(n * 0.32) // 2
    for sx in (-0.11, 0.11):
        for _ in range(n_legs):
            t = rng.random()
            y = -0.05 - t * 0.80
            r = 0.075 * (1.0 - t * 0.35)
            a = rng.uniform(0, _TAU)
            pts.append((sx + r * math.cos(a), y, r * math.sin(a)))
            grp.append(1)

    return pts, grp


# ── registry + per-shape default camera ─────────────────────────────────────
# (pitch, yaw_offset): the renderer applies these once so the object reads
# instantly from the default view. Cars/planes get a 3/4 view; hearts face
# the camera flat-on (the heart outline is in the X-Y plane); planets need none.

SHAPE_CAMERA = {
    "car":    (0.30, math.radians(-52)),   # 3/4 front-left, slightly from above
    "cat":    (0.22, math.radians(-35)),
    "house":  (0.26, math.radians(-38)),
    "rocket": (0.18, math.radians(0)),
    "robot":  (0.16, math.radians(-22)),
    "tree":   (0.10, 0.0),
    "planet": (0.20, 0.0),
    "earth":  (0.20, 0.0),
    "saturn": (0.32, math.radians(-18)),
    "heart":  (0.02, 0.0),                  # face-on so the lobes read
    "cube":   (0.30, math.radians(-40)),
    "sphere": (0.10, 0.0),
    "star":   (0.02, 0.0),                  # face-on 5-pointed star
    "flower": (0.32, math.radians(-15)),    # top-3/4 blossom view
    "human":  (0.10, math.radians(-20)),    # standing human silhouette
    "person": (0.10, math.radians(-20)),
}

SHAPE_BUILDERS = {
    "car":    build_car,
    "tree":   build_tree,
    "planet": build_planet,
    "earth":  build_planet,
    "heart":  build_heart,
    "rocket": build_rocket,
    "cat":    build_cat,
    "house":  build_house,
    "robot":  build_robot,
    "saturn": build_saturn,
    "cube":   build_cube,
    "sphere": build_sphere,
    "star":   build_star,
    "flower": build_flower,
    "human":  build_human,
    "person": build_human,
}



def available_shapes() -> list[str]:
    return sorted(SHAPE_BUILDERS.keys())


def build(shape: str, n: int):
    """Build (points, groups) for `shape` with roughly `n` points.
    Raises KeyError for unsupported shapes — callers must treat that as
    'not supported' rather than guessing."""
    fn = SHAPE_BUILDERS.get(shape)
    if fn is None:
        raise KeyError(f"unsupported shape: {shape}")
    pts, grp = fn(int(max(400, n)))
    if not pts:
        raise KeyError(f"shape '{shape}' produced no geometry")
    # normalize: centre + fit inside a unit-ish box, preserving proportions
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    cx, cy, cz = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2
    mr = max(math.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
             for x, y, z in pts) or 1.0
    s = 0.95 / mr
    pts = [((x - cx) * s, (y - cy) * s, (z - cz) * s) for x, y, z in pts]
    return pts, grp
