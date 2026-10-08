"""
Particle Blob visual mode for LUCY's HUD.

A living 3D particle sphere / deformed organic blob constructed from thousands
of small glowing particles that continuously undulate, deform and breathe.

Visual targets:
- 3D particle sphere with ordered lattice rows (similar to high-tech digital generative art)
- Organic wave undulations, flowing harmonic displacement
- LUCY signature electric cyan, violet/purple, neon magenta, and emerald green styling
- Full reactive states:
    - IDLE: subtle slow breathing motion and gentle 3D drift
    - LISTENING: responsive wave motion, emerald/cyan highlight
    - THINKING: faster internal harmonic morphing and swirl displacement
    - SPEAKING: organic pulsing reacting smoothly to audio amplitude
    - INTERRUPTED: smooth relaxation to idle without sudden snapping
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QRadialGradient

if TYPE_CHECKING:
    pass


def _clamp(v: float, low: float, high: float) -> float:
    return max(low, min(high, v))


def _lerp(a: float, b: float, f: float) -> float:
    return a + (b - a) * f


def _col_lerp(c1: tuple[int, int, int], c2: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    f = _clamp(f, 0.0, 1.0)
    return (
        int(c1[0] + (c2[0] - c1[0]) * f),
        int(c1[1] + (c2[1] - c1[1]) * f),
        int(c1[2] + (c2[2] - c1[2]) * f),
    )


class ParticleBlob:
    """Organic 3D particle sphere / blob centerpiece."""

    def __init__(self, num_lat: int = 34, num_lon: int = 46) -> None:
        self.num_lat = num_lat
        self.num_lon = num_lon

        # Precompute base spherical coordinates for lattice points
        # to ensure ultra-fast per-frame calculations.
        self._base_points: list[tuple[float, float, float, float, float]] = []
        for i in range(num_lat):
            # Latitude theta from -pi/2 to +pi/2
            v = (i + 0.5) / num_lat
            theta = (v - 0.5) * math.pi
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            for j in range(num_lon):
                # Longitude phi from 0 to 2*pi
                u = j / num_lon
                phi = u * 2.0 * math.pi
                cos_p = math.cos(phi)
                sin_p = math.sin(phi)

                x = cos_t * cos_p
                y = sin_t
                z = cos_t * sin_p
                self._base_points.append((x, y, z, theta, phi))

        # Add a scattering of inner floating energetic dust particles (core depth)
        self._core_dust: list[tuple[float, float, float, float, float]] = []
        rng = random.Random(42)
        for _ in range(140):
            r = rng.uniform(0.18, 0.72)
            th = rng.uniform(-math.pi / 2, math.pi / 2)
            ph = rng.uniform(0, math.pi * 2)
            x = r * math.cos(th) * math.cos(ph)
            y = r * math.sin(th)
            z = r * math.cos(th) * math.sin(ph)
            speed = rng.uniform(0.6, 1.8)
            seed = rng.uniform(0, 100.0)
            self._core_dust.append((x, y, z, speed, seed))

        # Dynamic state & timing
        self._time = 0.0
        self._yaw = 0.0
        self._pitch = 0.32  # gentle fixed tilt (~18 deg) for optimal 3D perspective

        # Smooth activity and audio envelope
        self._activity = 0.15       # 0.0 (quiet idle) to 1.0 (energetic)
        self._target_activity = 0.15
        self._amp_disp = 0.0
        self._speaking = False
        self._muted = False
        self._state = "IDLE"

        # Smooth state morphing (0.0 = Circle, 1.0 = Speaking Blob)
        self._morph_t = 0.0
        self._morph = 0.0

        # Wave displacement phases
        self._phase_wave1 = 0.0
        self._phase_wave2 = 0.0
        self._phase_wave3 = 0.0
        self._phase_rot = 0.0

        # ── Dynamic 3D object mode (particle_visualizer) ────────────────
        # Import lazily so a missing module can never break the plain blob.
        self._obj_cloud: list[tuple[float, float, float]] = []   # target x,y,z (unit scale)
        self._obj_colors: list[int] = []                          # per-point colour-bin index
        self._obj_bin_colors: list[tuple[int, int, int]] = []     # colour per bin
        self._obj_groups: list[int] = []                          # per-point part group
        self._obj_home: list[tuple[float, float, float]] = []     # sphere-lattice homes
        self._obj_pitch = 0.2                                     # per-shape camera pitch
        self._obj_active = False
        self._obj_mode = 0.0                                      # smoothed 0→1 object mode
        self._obj_yaw_phase = 0.0                                 # object slow-spin phase
        self._obj_t = 0.0                                         # time inside object mode
        self._obj_label = ""
        self._obj_seq = 0                                         # bumped on each new visual
        self._sway_phase = 0.0                                    # slow left↔right yaw sway

        # Base color scheme (LUCY purple, magenta, cyan, green)
        self._cyan_rgb = (0, 220, 255)
        self._violet_rgb = (140, 70, 255)
        self._magenta_rgb = (245, 55, 185)
        self._green_rgb = (0, 255, 136)
        self._amber_rgb = (255, 190, 30)
        self._muted_rgb = (255, 60, 100)

    def step(self, dt: float, amp: float, speaking: bool = False,
             muted: bool = False, state: str = "") -> None:
        """Advance blob animation and fluid deformation."""
        dt = _clamp(float(dt), 0.001, 0.08)
        self._time += dt

        self._speaking = bool(speaking)
        self._muted = bool(muted)
        self._state = str(state or "").upper()

        # Audio amplitude smoothing (fast attack, smooth release)
        raw_amp = _clamp(float(amp), 0.0, 1.0)
        if raw_amp > self._amp_disp:
            self._amp_disp += (raw_amp - self._amp_disp) * _clamp(dt * 22.0, 0.0, 1.0)
        else:
            self._amp_disp += (raw_amp - self._amp_disp) * _clamp(dt * 9.0, 0.0, 1.0)

        # Smooth morph progression (400-700ms duration: ~550ms = 0.55s)
        # In 3D-object mode the shape keeps "living": obj_t drives its own
        # breathing/shimmer clock while the sphere branch keeps its states.
        if self._obj_active:
            self._obj_t += dt
        is_speaking = bool(self._speaking or self._state == "SPEAKING")
        if self._muted:
            tgt_morph = 0.0
        elif is_speaking:
            tgt_morph = 1.0
        elif self._state in ("THINKING", "PROCESSING"):
            tgt_morph = 0.75
        else:
            tgt_morph = 0.0  # LISTENING / IDLE / INTERRUPTED

        transition_speed = 1.0 / 0.55
        if tgt_morph > self._morph_t:
            self._morph_t = min(tgt_morph, self._morph_t + dt * transition_speed)
        elif tgt_morph < self._morph_t:
            self._morph_t = max(tgt_morph, self._morph_t - dt * transition_speed)

        # Smoothstep easing: S(t) = 3t^2 - 2t^3
        mt = _clamp(self._morph_t, 0.0, 1.0)
        self._morph = mt * mt * (3.0 - 2.0 * mt)

        # Activity level based on LUCY state and morph
        if self._muted:
            tgt_act = 0.05
        elif self._state in ("THINKING", "PROCESSING"):
            tgt_act = 0.85
        else:
            circ_act = 0.16
            spk_act = 0.65 + self._amp_disp * 0.55
            tgt_act = _lerp(circ_act, spk_act, self._morph)

        self._target_activity = tgt_act
        # Smooth interpolation to target activity — when interrupted or changing state,
        # gracefully glides rather than jarring snaps
        decay_rate = 5.5 if (tgt_act < self._activity) else 10.0
        self._activity += (self._target_activity - self._activity) * _clamp(dt * decay_rate, 0.0, 1.0)

        act = self._activity

        # Phase progression speeds keyed to activity
        rot_speed = 0.22 + act * 0.55
        w1_speed = 0.95 + act * 2.20
        w2_speed = 1.35 + act * 2.80
        w3_speed = 1.80 + act * 3.40

        self._phase_rot += dt * rot_speed
        self._phase_wave1 += dt * w1_speed
        self._phase_wave2 += dt * w2_speed
        self._phase_wave3 += dt * w3_speed

        # ── Dynamic 3D object mode timing ────────────────────────────────────
        # Normal blob: a slow sinusoidal yaw sway (left ↔ right, ±~22°, never
        # snapping). Object mode: a slow continuous spin. The two yaw sources
        # are blended by the eased object-mode weight in paint(), so switching
        # modes is itself just a smooth rotation, never a jump.
        self._sway_phase += dt * 0.45

        # Ease object-mode weight in/out over ~0.9s each way.
        tgt_obj = 1.0 if self._obj_active else 0.0
        obj_speed = dt / 0.9
        if tgt_obj > self._obj_mode:
            self._obj_mode = min(tgt_obj, self._obj_mode + obj_speed)
        elif tgt_obj < self._obj_mode:
            self._obj_mode = max(tgt_obj, self._obj_mode - obj_speed)
        if self._obj_mode <= 0.0 and not self._obj_active:
            # Transition finished — free the cloud (GC-friendly, back to blob).
            self._obj_cloud = []
            self._obj_colors = []
            self._obj_bin_colors = []
            self._obj_home = []

        if self._obj_active:
            # Gentle cinematic drift, ±0.45 rad around the shape's hero yaw,
            # so the object keeps its recognizable silhouette while turning.
            self._obj_yaw_phase += dt * 0.16 * math.sin(self._obj_t * 0.5 + 1.2)

    # ── Dynamic 3D object mode API (used by actions/particle_visualizer) ─────

    def set_object(self, shape: str, colors=None, label: str = "") -> bool:
        """Morph the blob into a 3D point-cloud object.

        colors: list of (r, g, b) tuples used as a vertical gradient over the
        object (chosen intelligently by the caller for the requested object).
        Returns True if the shape exists and was scheduled; returns False
        (blob untouched) when the shape is not supported — the caller should
        tell the user the object is not currently supported.
        """
        try:
            from core.animated_shapes import build, SHAPE_CAMERA
            pts, groups = build(shape, len(self._base_points))
        except Exception:
            return False
        if not pts:
            return False

        # Normalize the cloud to fit inside ~0.92 of the blob radius.
        mr = max(math.sqrt(x * x + y * y + z * z) for x, y, z in pts) or 1.0
        s = 0.92 / mr
        self._obj_cloud = [(x * s, y * s, z * s) for x, y, z in pts]
        self._obj_groups = list(groups)
        n_groups = max(self._obj_groups) + 1 if self._obj_groups else 1

        # Per-shape default camera: a 3/4 view (pitch + starting yaw offset)
        # so cars/houses read immediately, hearts face the camera, etc.
        cam_pitch, cam_yaw = SHAPE_CAMERA.get(shape, (0.2, 0.0))
        self._obj_pitch = cam_pitch
        self._obj_yaw_phase = cam_yaw

        # Particle identity: every object point inherits a HOME on the current
        # sphere lattice (cycling through the lattice points). During the
        # morph each point eases from its own home on the living blob to its
        # target on the object — the same particles visibly re-form, no
        # cross-fade of two unrelated clouds.
        n_base = len(self._base_points)
        self._obj_home = [
            self._base_points[i % n_base][:3] for i in range(len(self._obj_cloud))
        ]

        # Colour assignment is PER GROUP (part of the object), not per
        # height: requested colour(s) are distributed across the object's
        # named parts so a 'red car' gets a red body with its own window/wheel
        # tones, a tree gets trunk + leaf colours, and so on.
        pal = list(colors) if colors else [self._cyan_rgb, self._violet_rgb]
        pal = [(int(_clamp(c[0], 0, 255)), int(_clamp(c[1], 0, 255)),
                int(_clamp(c[2], 0, 255))) for c in pal if isinstance(c, (tuple, list))]
        if not pal:
            pal = [self._cyan_rgb]

        # Build one luminance ramp per palette colour (dark → base → light),
        # then one colour BIN per (group, ramp-level). Every bin is a single
        # batched draw call, so multi-part coloured objects stay cheap.
        def ramp(c):
            r, g, b = c
            return (max(0, int(r * 0.45)), max(0, int(g * 0.45)), max(0, int(b * 0.45))), \
                   c, \
                   (min(255, int(r * 1.45 + 18)), min(255, int(g * 1.45 + 18)),
                    min(255, int(b * 1.45 + 18)))

        rng = random.Random(self._obj_seq)
        self._obj_seq += 1
        bin_colors: list[tuple[int, int, int]] = []
        group_bins: list[list[int]] = []      # per group: [dark, base, light] bin ids
        for gi in range(n_groups):
            base = pal[min(gi, len(pal) - 1)]
            dark, base_c, light = ramp(base)
            ids = []
            for c in (dark, base_c, light):
                ids.append(len(bin_colors))
                bin_colors.append(c)
            group_bins.append(ids)

        cis = []
        for (x, y, z), gi in zip(self._obj_cloud, self._obj_groups):
            ids = group_bins[gi] if gi < len(group_bins) else group_bins[0]
            # shade by height + a little sparkle for a lively holographic feel
            f = _clamp(0.5 + 0.35 * y + rng.uniform(-0.12, 0.12), 0.0, 1.0)
            lvl = 0 if f < 0.4 else (2 if f > 0.72 else 1)
            cis.append(ids[lvl])
        self._obj_bin_colors = bin_colors
        self._obj_colors = cis
        self._obj_label = label
        if not hasattr(self, "_obj_home"):
            self._obj_home = []
        self._obj_active = True
        return True

    def clear_object(self) -> None:
        """Smoothly morph whatever object is showing back into the normal blob."""
        self._obj_active = False

    def object_active(self) -> bool:
        return self._obj_active

    def paint(self, p: QPainter, cx: float, cy: float, r: float,
              primary: QColor, accent: QColor, bg: QColor | None = None) -> None:
        """Render the 3D particle blob on the given QPainter."""
        if r < 10:
            return

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        act = self._activity
        amp = self._amp_disp
        t = self._time
        morph = self._morph

        # ── 1. Atmosphere / Radial ambient back-glow ──────────────────────────
        # Gives the particle blob presence and a glowing digital backdrop
        glow_amp = amp * morph
        glow_r = r * (1.35 + 0.12 * act + 0.10 * glow_amp)
        glow_grad = QRadialGradient(cx, cy, glow_r)

        if self._muted:
            c_glow = self._muted_rgb
            base_alpha = 35
        elif self._state in ("THINKING", "PROCESSING"):
            c_glow = self._violet_rgb
            base_alpha = 55
        else:
            # Smoothly interpolate back-glow between circle (cyan, alpha 30)
            # and speaking blob (magenta, alpha 45 + 50 * amp)
            c_glow = _col_lerp(self._cyan_rgb, self._magenta_rgb, morph)
            base_alpha = int(_lerp(30.0, 45.0 + 50.0 * amp, morph))

        glow_grad.setColorAt(0.00, QColor(c_glow[0], c_glow[1], c_glow[2], base_alpha))
        glow_grad.setColorAt(0.40, QColor(c_glow[0], c_glow[1], c_glow[2], int(base_alpha * 0.5)))
        glow_grad.setColorAt(0.75, QColor(c_glow[0], c_glow[1], c_glow[2], int(base_alpha * 0.15)))
        glow_grad.setColorAt(1.00, QColor(c_glow[0], c_glow[1], c_glow[2], 0))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow_grad))
        p.drawEllipse(QRectF(cx - glow_r, cy - glow_r, glow_r * 2.0, glow_r * 2.0))

        # ── 2. Particle deformation & 3D projection ───────────────────────────
        # Yaw motion, always smooth, never snapping:
        #   • Normal blob  — slow sinusoidal left↔right sway (±~22°, ~14 s
        #     period) so the sphere gently turns like it is looking around.
        #   • Object mode  — slow continuous cinematic spin of the object.
        #   The active yaw is a blend of the two, weighted by the eased
        #   object-mode weight (om), so entering/leaving object mode is itself
        #   just a smooth rotation hand-off.
        om = self._obj_mode
        sway_yaw = 0.38 * math.sin(self._sway_phase)
        if om > 0.001:
            yaw = _lerp(sway_yaw, self._obj_yaw_phase, om)
        else:
            yaw = sway_yaw
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)
        # In object mode the camera pitch eases to the shape's hero pitch so
        # e.g. cars get their 3/4-from-above view; normal blob keeps its tilt.
        obj_pitch = getattr(self, "_obj_pitch", self._pitch)
        pitch = _lerp(self._pitch, obj_pitch, om)
        cos_pitch = math.cos(pitch)
        sin_pitch = math.sin(pitch)

        # Organic wave parameters based on state & audio
        # Breaths slightly even at rest
        breath = 0.98 + 0.03 * math.sin(t * 1.4)
        base_radius = r * 0.88 * breath

        # Deform amplitude coefficients:
        # Normal circular sphere (LISTENING/IDLE): stable, calm surface shimmer
        circ_amp1, circ_amp2, circ_amp3 = 0.02, 0.012, 0.006
        # Speaking blob: organic undulations reacting to activity and voice
        spk_amp1 = 0.12 + 0.14 * act
        spk_amp2 = 0.07 + 0.09 * act
        spk_amp3 = 0.03 + 0.06 * act

        # Smooth interpolation between circle and speaking blob
        amp1 = _lerp(circ_amp1, spk_amp1, morph)
        amp2 = _lerp(circ_amp2, spk_amp2, morph)
        amp3 = _lerp(circ_amp3, spk_amp3, morph)
        amp_voice = (amp * 0.22) * morph

        w1_ph = self._phase_wave1
        w2_ph = self._phase_wave2
        w3_ph = self._phase_wave3

        # Camera depth parameter for perspective projection
        d_cam = 3.6

        # Bucket particles into discrete rendering layers for batched Qt drawing
        # Buckets:
        # 0: Deep back (small, dark indigo/magenta, low opacity)
        # 1: Mid back (medium, violet/magenta, moderate opacity)
        # 2: Mid front (medium-large, cyan/violet, good opacity)
        # 3: Front surface (large, bright cyan/magenta, high opacity)
        # 4: Crest highlights (largest, luminous electric cyan/white highlight)
        buckets_core: list[list[QPointF]] = [[] for _ in range(5)]
        buckets_glow: list[list[QPointF]] = [[] for _ in range(5)]

        # Theme color overrides
        if self._muted:
            c_top = self._muted_rgb
            c_mid = (120, 30, 60)
            c_bot = (80, 20, 40)
        elif self._state in ("THINKING", "PROCESSING"):
            c_top = self._amber_rgb
            c_mid = self._violet_rgb
            c_bot = self._magenta_rgb
        else:
            # Circle (LISTENING/IDLE): subtle blue/cyan tones on HUD background
            # Speaking blob: electric cyan top, electric violet mid, neon magenta base
            c_top = self._cyan_rgb
            c_mid = self._violet_rgb
            c_bot = _col_lerp((70, 95, 210), self._magenta_rgb, morph)

        # In object mode the sphere particles cross-fade out while the object's
        # own particles cross-fade in — the SAME renderer, pens and buckets.
        sphere_a = 1.0 - om

        # ── 2b. Dynamic 3D object particles (object mode) ─────────────────────
        # The object is rendered by the SAME particles: each object point
        # starts at its home on the living sphere lattice and eases to its
        # target on the object's point cloud as the object-mode weight rises
        # (smoothstep on om). The cloud is re-sampled against a fresh sphere
        # each frame, so the morph flows instead of cross-fading.
        obj_bins = len(self._obj_bin_colors)
        obj_buckets_core: list[list[QPointF]] = []
        obj_buckets_glow: list[list[QPointF]] = []

        if om > 0.001 and obj_bins and len(self._obj_cloud) == len(self._obj_colors):
            obj_buckets_core = [[] for _ in range(obj_bins * 4)]
            obj_buckets_glow = [[] for _ in range(obj_bins * 4)]
            # Gentle living shimmer so the object breathes like the blob does,
            # kept subtle enough that the shape always reads clearly.
            o_shim = 0.012 + 0.045 * act
            o_voice = amp * 0.10
            cloud = self._obj_cloud
            colors = self._obj_colors
            homes = self._obj_home
            n_base = len(self._base_points)
            # Smoothstep easing on the mode weight: the flight from the sphere
            # home to the object target accelerates then settles.
            mf = om * om * (3.0 - 2.0 * om)
            for idx in range(len(cloud)):
                tx, ty, tz = cloud[idx]
                hx, hy, hz = homes[idx] if idx < len(homes) else self._base_points[idx % n_base][:3]
                # Home point rides the same gentle sphere deformation as the
                # blob (cheap approximation: the same harmonic on the sphere
                # direction), so departure happens from the living surface.
                sh_home = math.sin(2.0 * math.asin(max(-1.0, min(1.0, hy)))
                                   + 2.0 * math.atan2(hz, hx) + w1_ph) \
                    * math.cos(2.0 * math.atan2(hz, hx) - w2_ph)
                h_rad = base_radius * (1.0 + 0.02 * sh_home)

                # Target shimmer keeps the object alive once formed.
                sh = math.sin(ty * 4.0 + tx * 3.0 + w1_ph) * math.cos(tz * 3.5 - w2_ph)
                t_rad = base_radius * (1.0 + o_shim * sh + o_voice * math.sin(4.0 * ty + w3_ph))

                # Interpolate the 3D position home → target (in model space,
                # BEFORE rotation, so the shape rotates as one solid object).
                px = (hx * h_rad) + (tx * t_rad - hx * h_rad) * mf
                py = (hy * h_rad) + (ty * t_rad - hy * h_rad) * mf
                pz = (hz * h_rad) + (tz * t_rad - hz * h_rad) * mf

                # Same yaw/pitch pipeline as the sphere (blended yaw above).
                x1 = px * cos_yaw + pz * sin_yaw
                z1 = -px * sin_yaw + pz * cos_yaw
                y1 = py

                y2 = y1 * cos_pitch - z1 * sin_pitch
                z2 = y1 * sin_pitch + z1 * cos_pitch
                x2 = x1

                denom = d_cam + (z2 / (base_radius + 1e-4))
                k = d_cam / max(1.2, denom)

                sx = cx + x2 * k
                sy = cy - y2 * k

                norm_z = _clamp(z2 / (base_radius + 1e-4), -1.0, 1.0)
                if norm_z < -0.4:
                    b_idx = 0
                elif norm_z < 0.0:
                    b_idx = 1
                else:
                    b_idx = 2

                pt = QPointF(sx, sy)
                key = colors[idx] * 4 + b_idx
                obj_buckets_core[key].append(pt)
                if b_idx >= 1:
                    obj_buckets_glow[key].append(pt)

        for x0, y0, z0, th, ph in self._base_points:
            # 3D harmonic displacement
            # Harmonic 1: broad dual lobes
            h1 = math.sin(2.0 * th + 2.0 * ph + w1_ph) * math.cos(2.0 * th - 2.0 * ph + w2_ph)
            # Harmonic 2: ripples across surface
            h2 = math.sin(3.5 * x0 + 3.0 * y0 + w2_ph) * math.cos(3.0 * z0 - w3_ph)
            # Harmonic 3: longitudinal twists
            h3 = math.sin(4.0 * ph + w3_ph) * math.cos(3.0 * th)
            # Voice pulse
            h_v = math.sin(7.0 * th + 5.0 * ph - w1_ph * 2.5) * amp_voice

            dr = amp1 * h1 + amp2 * h2 + amp3 * h3 + h_v
            rad = base_radius * (1.0 + dr)

            px = rad * x0
            py = rad * y0
            pz = rad * z0

            # 3D Yaw rotation (horizontal rotation)
            x1 = px * cos_yaw + pz * sin_yaw
            z1 = -px * sin_yaw + pz * cos_yaw
            y1 = py

            # 3D Pitch tilt (look slightly from above for 3D depth)
            y2 = y1 * cos_pitch - z1 * sin_pitch
            z2 = y1 * sin_pitch + z1 * cos_pitch
            x2 = x1

            # Perspective projection
            # z2 ranges approx -rad to +rad.
            # Perspective factor k:
            denom = d_cam + (z2 / (base_radius + 1e-4))
            k = d_cam / max(1.2, denom)

            sx = cx + x2 * k
            sy = cy - y2 * k

            # Depth metric: -1.0 (far back) to +1.0 (closest to camera)
            norm_z = _clamp(z2 / (base_radius + 1e-4), -1.0, 1.0)
            # Elevation metric for color gradient (y2 from bottom to top)
            norm_elev = _clamp((y2 / (base_radius + 1e-4) + 1.0) * 0.5, 0.0, 1.0)

            # Assign to bucket based on depth and displacement
            if norm_z < -0.4:
                b_idx = 0
            elif norm_z < 0.0:
                b_idx = 1
            elif norm_z < 0.45:
                b_idx = 2
            elif dr < 0.08:
                b_idx = 3
            else:
                b_idx = 4  # protruding front wave crest

            pt = QPointF(sx, sy)
            if sphere_a > 0.01:
                buckets_core[b_idx].append(pt)
                if b_idx >= 2:
                    buckets_glow[b_idx].append(pt)

        # ── 3. Internal floating energy dust particles ────────────────────────
        core_dust_pts: list[QPointF] = []
        for x0, y0, z0, sp, seed in self._core_dust:
            ang = t * sp * 0.6 + seed
            ca, sa = math.cos(ang), math.sin(ang)
            dx = x0 * ca - z0 * sa
            dz = x0 * sa + z0 * ca
            dy = y0 + 0.08 * math.sin(t * sp + seed)
            drad = base_radius * 0.65
            sx = cx + dx * drad * cos_yaw
            sy = cy - (dy * drad * cos_pitch - dz * drad * sin_pitch)
            core_dust_pts.append(QPointF(sx, sy))

        # ── 4. Render batches with calibrated pens (depth/color layers) ───────
        # Bucket configurations: (color, core_width, core_alpha, glow_width, glow_alpha)
        # Bottom/Back uses magenta/violet; Front uses cyan and bright highlight
        b_styles = [
            # Bucket 0: Deep back
            (c_bot, 1.4, 60, 0.0, 0),
            # Bucket 1: Mid back
            (_col_lerp(c_bot, c_mid, 0.5), 1.8, 110, 0.0, 0),
            # Bucket 2: Mid front
            (c_mid, 2.3, 175, 4.2, 40),
            # Bucket 3: Front surface
            (_col_lerp(c_mid, c_top, 0.6), 2.9, 220, 5.4, 65),
            # Bucket 4: Front crest highlights
            (c_top, 3.4, 255, 6.8, 90),
        ]

        # First pass: Soft glow on foreground particles
        for idx in (2, 3, 4):
            pts = buckets_glow[idx]
            if not pts:
                continue
            col, _, _, gw, ga = b_styles[idx]
            pen_g = QPen(QColor(col[0], col[1], col[2], ga))
            pen_g.setWidthF(gw)
            pen_g.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_g)
            p.drawPoints(pts)

        # Second pass: Core particles (sharp, distinct points)
        for idx in range(5):
            pts = buckets_core[idx]
            if not pts:
                continue
            col, cw, ca, _, _ = b_styles[idx]
            # Extra white luminance on highest crests
            if idx == 4:
                # Add white tint to the crest point cores for holographic shine
                col_c = _col_lerp(col, (240, 250, 255), 0.55)
            else:
                col_c = col
            pen_c = QPen(QColor(col_c[0], col_c[1], col_c[2], ca))
            pen_c.setWidthF(cw)
            pen_c.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_c)
            p.drawPoints(pts)

        # Third pass: Internal core floating dust
        if core_dust_pts:
            dust_col = _col_lerp(c_mid, c_top, 0.3)
            pen_d = QPen(QColor(dust_col[0], dust_col[1], dust_col[2], int(130 + 80 * act)))
            pen_d.setWidthF(1.5)
            pen_d.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen_d)
            p.drawPoints(core_dust_pts)

        # ── 5. Object-mode batches (same renderer language as the sphere) ─────
        # One glow pass and one core pass per (colour-bin × depth-bucket), so
        # multi-colour 3D objects still cost only a few dozen draw calls.
        if obj_buckets_core:
            fade = om
            for key, pts in enumerate(obj_buckets_core):
                if not pts:
                    continue
                ci = key // 4
                b_idx = key % 4
                col = self._obj_bin_colors[ci]
                # Depth cues: back points smaller/dimmer, front brighter and
                # thicker — mirroring the sphere's bucket styling exactly.
                if b_idx == 0:
                    cw, ca, gw, ga = 1.4, int(60 * fade), 0.0, 0
                elif b_idx == 1:
                    cw, ca, gw, ga = 2.0, int(150 * fade), 0.0, 0
                else:
                    # Front surface: bright core + glow, with a white-hot tint
                    # for the holographic shine the sphere's crests carry.
                    cw, ca, gw, ga = 2.6, int(225 * fade), 5.0, int(70 * fade)
                col_c = (_col_lerp(col, (240, 250, 255), 0.35)
                         if b_idx == 2 else col)
                if gw > 0:
                    pen_g = QPen(QColor(col[0], col[1], col[2], ga))
                    pen_g.setWidthF(gw)
                    pen_g.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen_g)
                    p.drawPoints(obj_buckets_glow[key])
                pen_c = QPen(QColor(col_c[0], col_c[1], col_c[2], ca))
                pen_c.setWidthF(cw)
                pen_c.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen_c)
                p.drawPoints(pts)

        p.restore()
