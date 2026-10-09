"""
actions/particle_visualizer.py — Dynamic 3D particle object mode for the HUD blob.

When the user asks LUCY to "make a 3D car", "show a tree", "create a heart"…
the existing HUD particle blob morphs (same particles, same renderer) into a
recognizable 3D point-cloud of that object, using an intelligent colour
palette for the request. Saying "stop"/"normal blob" (or a shape that is not
supported, reported honestly) restores the living particle sphere.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

from core.animated_shapes import SHAPE_BUILDERS, available_shapes


# ── Colour intelligence ─────────────────────────────────────────────────────
# Each supported object carries a default, LUCY-styled palette (vertical
# gradient, bottom → top). Named colours from the request override it.

_NAMED_COLOURS: dict[str, tuple[int, int, int]] = {
    "red":        (255, 45, 85),
    "crimson":    (220, 20, 60),
    "orange":     (255, 140, 30),
    "amber":      (255, 190, 30),
    "yellow":     (255, 230, 60),
    "gold":       (255, 200, 40),
    "green":      (0, 255, 136),
    "emerald":    (0, 220, 120),
    "cyan":       (0, 220, 255),
    "blue":       (60, 130, 255),
    "deep blue":  (30, 60, 220),
    "navy":       (20, 40, 160),
    "purple":     (150, 60, 255),
    "violet":     (140, 70, 255),
    "magenta":    (245, 55, 185),
    "pink":       (255, 90, 190),
    "white":      (235, 245, 255),
    "silver":     (200, 220, 240),
    "black":      (40, 40, 60),
    "brown":      (150, 90, 40),
}

_DEFAULT_PALETTES: dict[str, tuple[tuple[int, int, int], ...]] = {
    "car":          ((0, 200, 255), (140, 70, 255), (245, 55, 185)),   # LUCY signature
    "sports car":   ((255, 45, 85), (0, 220, 255), (40, 40, 60), (255, 230, 60)), # red body, cyan glass, wheels, lights
    "television":   ((40, 40, 60), (0, 220, 255), (140, 70, 255)),     # frame, emissive screen, stand
    "laptop":       ((180, 200, 220), (0, 220, 255), (100, 120, 150)), # silver body, cyan screen, keyboard
    "fan":          ((150, 170, 200), (0, 255, 136), (100, 110, 130)), # stand, neon green blades, motor
    "chair":        ((160, 100, 50), (200, 130, 70), (120, 70, 30)),   # wood seat, backrest, legs
    "table":        ((150, 95, 45), (180, 120, 60), (110, 65, 25)),    # polished wood top, apron, legs
    "bird":         ((0, 200, 255), (255, 160, 40), (245, 55, 185)),   # blue wings, golden beak, magenta
    "animal":       ((220, 140, 60), (255, 200, 120), (80, 50, 30)),   # warm fur tones, ears, paws
    "heart":        ((255, 45, 85), (255, 120, 160)),                  # warm red → pink
    "planet":       ((0, 180, 255), (0, 255, 136), (235, 245, 255)),   # ocean → land → ice
    "earth":        ((0, 180, 255), (0, 255, 136), (235, 245, 255)),
    "rocket":       ((235, 245, 255), (0, 220, 255), (255, 140, 30)),  # hull → window → flame
    "tree":         ((150, 90, 40), (0, 255, 136), (0, 200, 120)),     # trunk → leaves
    "cat":          ((255, 160, 60), (255, 200, 120)),                 # warm fur tones
    "house":        ((0, 220, 255), (140, 70, 255), (255, 190, 30)),   # walls → roof → windows
    "robot":        ((200, 220, 240), (0, 220, 255), (255, 45, 85)),   # chrome → eyes
    "saturn":       ((255, 220, 140), (255, 190, 30), (200, 220, 240)),
    "sphere":       ((0, 220, 255), (140, 70, 255)),
    "cube":         ((0, 220, 255), (140, 70, 255)),
    "star":         ((255, 200, 40), (255, 240, 120), (255, 255, 255)),
    "flower":       ((0, 220, 120), (255, 200, 40), (255, 90, 190)),
    "human":        ((0, 220, 255), (140, 70, 255), (235, 245, 255)),
    "person":       ((0, 220, 255), (140, 70, 255), (235, 245, 255)),
    "human head":   ((0, 220, 255), (245, 55, 185), (140, 70, 255)),
    "head":         ((0, 220, 255), (245, 55, 185), (140, 70, 255)),
    "detailed face":((0, 220, 255), (245, 55, 185), (255, 230, 60)),
    "face":         ((0, 220, 255), (245, 55, 185), (255, 230, 60)),
}

# Synonyms and alias resolution for natural-language visualization requests
_SHAPE_ALIASES: dict[str, str] = {
    "sportscar": "sports car",
    "sports_car": "sports car",
    "racing car": "sports car",
    "supercar": "sports car",
    "tv": "television",
    "monitor": "television",
    "screen": "television",
    "laptop with screen": "laptop",
    "notebook": "laptop",
    "macbook": "laptop",
    "standing fan": "fan",
    "pedestal fan": "fan",
    "desk fan": "fan",
    "armchair": "chair",
    "wooden chair": "chair",
    "desk chair": "chair",
    "seat": "chair",
    "desk": "table",
    "dining table": "table",
    "flying bird": "bird",
    "eagle": "bird",
    "dove": "bird",
    "dog": "animal",
    "puppy": "animal",
    "hound": "animal",
    "horse": "animal",
    "human head": "human head",
    "skull": "human head",
    "detailed face": "detailed face",
    "human face": "detailed face",
    "face": "detailed face",
    "portrait": "detailed face",
    "human silhouette": "human",
    "man": "human",
    "woman": "human",
    "earth": "planet",
    "globe": "planet",
    "world": "planet",
}


def _normalize_shape_name(raw: str) -> str:
    cleaned = raw.strip().lower()
    if cleaned in _SHAPE_ALIASES:
        return _SHAPE_ALIASES[cleaned]
    # Check word inclusions
    for alias, canonical in _SHAPE_ALIASES.items():
        if alias in cleaned:
            return canonical
    return cleaned


def _pick_palette(shape: str, colour_words: list[str]) -> list[tuple[int, int, int]]:
    """Multi-colour palette for the request. Explicit colour words win; a
    single named colour becomes a two-tone ramp (colour → glow-friendly
    lighter top) so gradients/glows stay part of the LUCY look."""
    named = [_NAMED_COLOURS[w] for w in colour_words if w in _NAMED_COLOURS]
    if named:
        if len(named) == 1:
            r, g, b = named[0]
            return [named[0], (min(255, r + 70), min(255, g + 70), min(255, b + 70))]
        return named
    return list(_DEFAULT_PALETTES.get(shape, ((0, 220, 255), (140, 70, 255))))


def _find_blob():
    """Locate the live ParticleBlob instance from the HUD widget, walking the
    QApplication's top-level widgets. Returns None when blob mode is off."""
    try:
        from PyQt6.QtWidgets import QApplication
    except Exception:
        return None
    app = QApplication.instance()
    if app is None:
        return None
    for w in app.allWidgets():
        step = getattr(w, "_blob", None)
        if step is not None and hasattr(step, "set_object"):
            return step
    return None


# ── Handlers ────────────────────────────────────────────────────────────────

def visualize_object(parameters=None, player=None, **_ctx) -> str:
    params = parameters or {}
    raw = str(params.get("object", "")).strip().lower()
    colour_words = [str(c).strip().lower()
                    for c in (params.get("colors") or []) if str(c).strip()]

    if not raw:
        return "No object specified."

    blob = _find_blob()
    if blob is None:
        return ("The particle HUD is not in blob mode right now, so I can't "
                "visualize it. Switch the HUD style to the particle blob first.")

    # Stop / restore the normal blob.
    if raw in ("none", "stop", "clear", "off", "blob", "normal", "default"):
        blob.clear_object()
        return "Returning to the normal particle blob."

    shape = _normalize_shape_name(raw)
    if shape not in SHAPE_BUILDERS:
        # Do NOT fake unsupported objects — report honestly and keep the blob.
        supported = ", ".join(available_shapes())
        return (f"'{raw}' is not currently supported by my particle visualizer. "
                f"I can show: {supported}.")

    colors = _pick_palette(shape, colour_words)
    ok = blob.set_object(shape, colors=colors, label=shape)
    if ok:
        if player is not None and hasattr(player, "write_log"):
            player.write_log(f"SYS: Particle visualizer — {shape} ({', '.join(c for c in colour_words) or 'LUCY palette'})")
        return (f"Showing a 3D {shape} in particles."
                + (f" Colours: {', '.join(colour_words)}." if colour_words else ""))
    return f"Could not build the 3D {shape}."


# ── Tool declaration (auto-discovered by core/action_loader.py) ─────────────
TOOL = {
    "name": "particle_visualizer",
    "description": (
        "Transforms LUCY's HUD particle blob into a rotating 3D particle object — "
        "call when the user asks to make/show/create/visualize something in particles "
        "or as a 3D object (e.g. 'make a 3D car', 'make a red sports car', 'show a television', "
        "'create a laptop with screen', 'show a fan', 'make a chair', 'make a table', "
        "'show a tree', 'create a heart', 'show a bird', 'show an animal', 'show a human silhouette', "
        "'show a human head', 'make a detailed face', 'show a rotating Earth', 'show a star', 'make a flower'). "
        "Supported objects: car, sports car, television, laptop, fan, chair, table, tree, heart, "
        "planet/earth, rocket, bird, animal, cat, house, robot, saturn, cube, sphere, star, flower, "
        "human, human head, detailed face. If the requested object is not "
        "in the list, do NOT call this tool with a made-up object — instead tell the user "
        "it is not currently supported. Call with object 'none' to return to the normal blob "
        "(e.g. 'stop showing that', 'go back to normal')."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "object": {
                "type": "STRING",
                "description": (
                    "Object to visualize: car, sports car, television, laptop, fan, chair, table, "
                    "tree, heart, planet, rocket, bird, animal, cat, house, robot, saturn, cube, sphere, "
                    "star, flower, human, human head, detailed face — or 'none' to restore normal blob."
                ),
            },
            "colors": {
                "type": "ARRAY",
                "description": (
                    "Optional colour words for the particles, e.g. ['red'], "
                    "['green','blue'], ['cyan']. Supported: red, orange, amber, yellow, "
                    "gold, green, emerald, cyan, blue, navy, purple, violet, magenta, "
                    "pink, white, silver, brown."
                ),
                "items": {"type": "STRING"},
            },
        },
        "required": ["object"],
    },
    "handler": visualize_object,
}
