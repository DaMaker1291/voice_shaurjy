"""
Synthetic Ink Engine — Converts text to realistic handwritten strokes.

Uses vector font mapping + Bezier interpolation + human jitter
to simulate real pen/pencil/marker input on any Windows canvas
(OneNote, Paint, Whiteboard, PDF annotators, etc.)

Works via OS-level mouse drag vectors — no API needed.
"""

import math
import random
import time
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

log = logging.getLogger("jarvis-ink")

try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


# ═══════════════════════════════════════════════════════════════════════════
# VECTOR FONT — Each character is a list of strokes, each stroke is a list
# of (x, y) control points in a 20x24 unit cell.
# ═══════════════════════════════════════════════════════════════════════════

VECTOR_FONT = {
    "A": [[(10,0),(0,24)], [(10,0),(20,24)], [(4,14),(16,14)]],
    "B": [[(2,0),(2,24)], [(2,0),(12,0),(14,6),(12,12),(2,12)], [(12,12),(16,14),(14,20),(2,24)]],
    "C": [[(18,2),(10,0),(4,6),(2,12),(4,18),(10,24),(18,22)]],
    "D": [[(2,0),(2,24)], [(2,0),(10,0),(16,8),(10,16),(2,24)]],
    "E": [[(18,0),(2,0),(2,24),(18,24)], [(2,12),(12,12)]],
    "F": [[(18,0),(2,0),(2,24)], [(2,12),(12,12)]],
    "G": [[(18,2),(10,0),(4,6),(2,12),(4,18),(10,24),(18,22),(18,14),(12,14)]],
    "H": [[(2,0),(2,24)], [(18,0),(18,24)], [(2,12),(18,12)]],
    "I": [[(10,0),(10,24)], [(6,0),(14,0)], [(6,24),(14,24)]],
    "J": [[(18,0),(18,18),(14,22),(8,24),(2,20)]],
    "K": [[(2,0),(2,24)], [(18,0),(2,14)], [(2,14),(18,24)]],
    "L": [[(2,0),(2,24),(18,24)]],
    "M": [[(0,24),(0,0),(10,12),(20,0),(20,24)]],
    "N": [[(2,24),(2,0),(18,24),(18,0)]],
    "O": [[(10,0),(4,4),(2,12),(4,20),(10,24),(16,20),(18,12),(16,4),(10,0)]],
    "P": [[(2,0),(2,24)], [(2,0),(12,0),(16,4),(12,8),(2,8)]],
    "Q": [[(10,0),(4,4),(2,12),(4,20),(10,24),(16,20),(18,12),(16,4),(10,0)], [(14,18),(20,26)]],
    "R": [[(2,0),(2,24)], [(2,0),(12,0),(16,4),(12,8),(2,8)], [(8,12),(18,24)]],
    "S": [[(18,2),(10,0),(4,4),(6,10),(14,14),(16,20),(10,24),(2,22)]],
    "T": [[(0,0),(20,0)], [(10,0),(10,24)]],
    "U": [[(2,0),(2,18),(6,22),(10,24),(14,22),(18,18),(18,0)]],
    "V": [[(0,0),(10,24),(20,0)]],
    "W": [[(0,0),(5,24),(10,12),(15,24),(20,0)]],
    "X": [[(0,0),(20,24)], [(20,0),(0,24)]],
    "Y": [[(0,0),(10,12)], [(20,0),(10,12),(10,24)]],
    "Z": [[(0,0),(20,0),(0,24),(20,24)]],
    "0": [[(10,0),(4,4),(2,12),(4,20),(10,24),(16,20),(18,12),(16,4),(10,0)]],
    "1": [[(6,2),(10,0),(10,24)], [(6,24),(14,24)]],
    "2": [[(4,6),(10,0),(16,4),(10,12),(2,24),(18,24)]],
    "3": [[(2,2),(10,0),(16,6),(10,12),(16,18),(10,24),(2,22)]],
    "4": [[(14,0),(2,14),(18,14)], [(14,0),(14,24)]],
    "5": [[(16,0),(4,0),(2,10),(12,8),(18,14),(14,20),(6,24),(2,22)]],
    "6": [[(18,4),(10,0),(4,6),(2,14),(4,20),(10,24),(16,20),(18,14),(12,8)]],
    "7": [[(2,0),(18,0),(10,24)]],
    "8": [[(10,0),(4,4),(4,8),(10,12),(16,16),(16,8),(10,12),(4,16),(4,20),(10,24),(16,20),(16,16)]],
    "9": [[(18,20),(10,24),(4,18),(2,10),(4,4),(10,0),(16,4),(18,10),(12,16)]],
    " ": [],
    ".": [[(10,22),(10,24)]],
    ",": [[(10,20),(8,24)]],
    "!": [[(10,0),(10,18)], [(10,22),(10,24)]],
    "?": [[(4,6),(10,0),(16,6),(10,12),(10,18)], [(10,22),(10,24)]],
    ":": [[(10,8),(10,10)], [(10,16),(10,18)]],
    ";": [[(10,8),(10,10)], [(10,18),(8,22)]],
    "-": [[(4,12),(16,12)]],
    "+": [[(10,6),(10,18)], [(4,12),(16,12)]],
    "=": [[(4,9),(16,9)], [(4,15),(16,15)]],
    "(": [[(12,0),(6,8),(4,12),(6,16),(12,24)]],
    ")": [[(8,0),(14,8),(16,12),(14,16),(8,24)]],
    "/": [[(16,0),(4,24)]],
    "@": [[(16,8),(10,0),(4,6),(2,14),(4,20),(10,24),(16,18),(16,8),(10,12),(10,10)]],
    "#": [[(6,0),(4,24)], [(14,0),(16,24)], [(0,8),(20,8)], [(0,16),(20,16)]],
    "'": [[(10,0),(10,4)]],
    '"': [[(7,0),(7,4)], [(13,0),(13,4)]],
    "_": [[(2,24),(18,24)]],
    "~": [[(2,12),(6,8),(10,12),(14,8),(18,12)]],
    "<": [[(16,4),(4,12),(16,20)]],
    ">": [[(4,4),(16,12),(4,20)]],
    "[": [[(12,0),(4,0),(4,24),(12,24)]],
    "]": [[(8,0),(16,0),(16,24),(8,24)]],
    "a": [[(18,10),(12,0),(4,4),(2,10),(2,18),(18,18),(18,10),(2,10)]],
    "b": [[(2,0),(2,24)], [(2,10),(10,0),(16,4),(18,10),(16,18),(10,24),(2,18)]],
    "c": [[(18,10),(10,0),(4,4),(2,10),(4,18),(10,24),(18,20)]],
    "d": [[(18,0),(18,24)], [(18,10),(10,0),(4,4),(2,10),(2,18),(18,18)]],
    "e": [[(2,12),(18,10),(10,0),(4,4),(2,10),(2,18),(10,24),(18,20)]],
    "f": [[(12,0),(8,4),(8,24)], [(4,8),(16,6)]],
    "g": [[(18,10),(10,0),(4,4),(2,10),(2,18),(18,18),(18,10),(2,10)], [(18,18),(14,24),(6,26),(2,22)]],
    "h": [[(2,0),(2,24)], [(2,10),(10,0),(16,4),(18,10),(18,18)]],
    "i": [[(8,0),(8,2),(10,4),(10,24)], [(8,18),(10,20)]],
    "j": [[(10,2),(12,4),(12,24),(8,26),(4,22)], [(10,18),(12,20)]],
    "k": [[(2,0),(2,24)], [(18,0),(2,12)], [(6,12),(18,24)]],
    "l": [[(10,0),(10,22),(14,24),(16,24)]],
    "m": [[(0,18),(0,10),(4,0),(8,10),(8,18)], [(8,18),(8,10),(12,0),(16,10),(16,18)]],
    "n": [[(2,18),(2,10),(8,0),(14,4),(18,10),(18,18)]],
    "o": [[(10,0),(4,4),(2,10),(4,18),(10,24),(16,18),(18,10),(16,4),(10,0)]],
    "p": [[(2,10),(10,0),(16,4),(18,10),(16,18),(10,24),(2,18)], [(2,10),(2,26)]],
    "q": [[(18,10),(10,0),(4,4),(2,10),(4,18),(10,24),(18,18)], [(18,10),(18,26)]],
    "r": [[(2,18),(2,10),(8,0),(14,4),(18,10)]],
    "s": [[(18,4),(10,0),(4,4),(8,10),(16,14),(18,20),(10,24),(2,20)]],
    "t": [[(8,0),(8,22),(12,24),(16,24)], [(4,6),(14,4)]],
    "u": [[(2,0),(2,14),(6,20),(10,24),(14,20),(18,14),(18,0)]],
    "v": [[(0,0),(10,24),(20,0)]],
    "w": [[(0,0),(5,18),(10,10),(15,18),(20,0)]],
    "x": [[(0,0),(20,24)], [(20,0),(0,24)]],
    "y": [[(0,0),(10,12)], [(20,0),(10,12),(6,20),(2,24)]],
    "z": [[(0,0),(20,0),(0,24),(20,24)]],
}


@dataclass
class InkStyle:
    """Controls the visual style of the handwriting."""
    char_width: int = 14        # Width of one character cell in pixels
    char_height: int = 18       # Height of one character cell in pixels
    line_spacing: int = 24      # Vertical distance between lines
    char_spacing: int = 3       # Horizontal gap between characters
    jitter_px: int = 1          # Max random pixel jitter (human shake)
    stroke_speed: float = 0.008 # Seconds per point (pen speed)
    pressure_variance: float = 0.3  # Simulated pen pressure variation
    word_pause: float = 0.15    # Pause between words
    line_pause: float = 0.4     # Pause between lines


class SyntheticInkEngine:
    """
    Converts text into realistic pen strokes and injects them
    via OS-level mouse drag vectors.

    Works in ANY app that accepts pen/mouse input:
    OneNote, Paint, Whiteboard, PDF annotators, etc.
    """

    def __init__(self, style: InkStyle = None):
        self.style = style or InkStyle()

    # ═══════════════════════════════════════════════════════════════
    # CORE: Draw a single pen stroke through a list of points
    # ═══════════════════════════════════════════════════════════════

    def _draw_stroke(self, points: List[Tuple[int, int]], speed: float = None):
        """Execute a smooth pen stroke with human jitter and eased movement."""
        if not _HAS_PYAUTOGUI or len(points) < 2:
            return

        speed = speed or self.style.stroke_speed
        s = self.style

        # Move to start without drawing
        px, py = points[0]
        pyautogui.moveTo(px, py, duration=0.01)

        # Pen down
        pyautogui.mouseDown(button="left")
        time.sleep(0.01)

        for i, (nx, ny) in enumerate(points[1:]):
            # Human micro-jitter
            jx = nx + random.randint(-s.jitter_px, s.jitter_px)
            jy = ny + random.randint(-s.jitter_px, s.jitter_px)

            # Velocity curve: slow at start/end, fast in middle
            t = (i + 1) / max(len(points) - 1, 1)
            ease = math.sin(t * math.pi)  # easeInOut sine
            dur = speed * (1.2 - 0.4 * ease)

            pyautogui.moveTo(jx, jy, duration=dur, tween=pyautogui.easeInOutQuad)

        # Pen up
        pyautogui.mouseUp(button="left")
        time.sleep(0.01)

    # ═══════════════════════════════════════════════════════════════
    # BEZIER INTERPOLATION between control points
    # ═══════════════════════════════════════════════════════════════

    def _bezier_points(self, control: List[Tuple[int, int]], num_points: int = 12) -> List[Tuple[int, int]]:
        """Generate smooth points along a cubic Bezier curve through control points."""
        if len(control) < 2:
            return control

        result = []
        for i in range(len(control) - 1):
            p0 = control[max(i - 1, 0)]
            p1 = control[i]
            p2 = control[min(i + 1, len(control) - 1)]
            p3 = control[min(i + 2, len(control) - 1)]

            for t_i in range(num_points):
                t = t_i / num_points
                t2 = t * t
                t3 = t2 * t

                # Catmull-Rom to Bezier conversion
                x = int(0.5 * (
                    (2 * p1[0]) +
                    (-p0[0] + p2[0]) * t +
                    (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                    (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                ))
                y = int(0.5 * (
                    (2 * p1[1]) +
                    (-p0[1] + p2[1]) * t +
                    (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                    (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                ))
                result.append((x, y))

        result.append(control[-1])
        return result

    # ═══════════════════════════════════════════════════════════════
    # CHARACTER RENDERING
    # ═══════════════════════════════════════════════════════════════

    def _get_strokes(self, char: str) -> List[List[Tuple[int, int]]]:
        """Get vector strokes for a character, scaled to style dimensions."""
        s = self.style
        strokes_raw = VECTOR_FONT.get(char.upper(), VECTOR_FONT.get(char, []))
        if not strokes_raw:
            return []

        scale_x = s.char_width / 20.0
        scale_y = s.char_height / 24.0

        scaled = []
        for stroke in strokes_raw:
            scaled.append([
                (int(x * scale_x), int(y * scale_y))
                for x, y in stroke
            ])
        return scaled

    def write_character(self, origin_x: int, origin_y: int, char: str, scale: float = 1.0):
        """Draw a single character at screen coordinates."""
        strokes = self._get_strokes(char)
        if not strokes:
            return

        for stroke in strokes:
            points = [
                (origin_x + int(px * scale), origin_y + int(py * scale))
                for px, py in stroke
            ]
            # Apply Bezier smoothing
            smooth = self._bezier_points(points)
            self._draw_stroke(smooth)
            time.sleep(0.01)

    # ═══════════════════════════════════════════════════════════════
    # TEXT RENDERING
    # ═══════════════════════════════════════════════════════════════

    def write_text(self, origin_x: int, origin_y: int, text: str, scale: float = 1.0):
        """Write a full string of text at screen coordinates."""
        s = self.style
        cx = origin_x
        cy = origin_y

        for char in text:
            if char == "\n":
                cx = origin_x
                cy += int(s.line_spacing * scale)
                time.sleep(s.line_pause)
                continue

            self.write_character(cx, cy, char, scale)
            cx += int((s.char_width + s.char_spacing) * scale)

            if char == " ":
                time.sleep(s.word_pause * 0.5)
            elif char in ".!?,;:":
                time.sleep(s.word_pause)

    def write_text_at_cursor(self, text: str, scale: float = 1.0):
        """Write text starting from the current mouse position."""
        x, y = pyautogui.position()
        self.write_text(x, y, text, scale)

    # ═══════════════════════════════════════════════════════════════
    # DRAWING PRIMITIVES
    # ═══════════════════════════════════════════════════════════════

    def draw_line(self, x1: int, y1: int, x2: int, y2: int):
        """Draw a straight line."""
        num_points = max(int(math.hypot(x2 - x1, y2 - y1) / 3), 5)
        points = [
            (int(x1 + (x2 - x1) * i / num_points),
             int(y1 + (y2 - y1) * i / num_points))
            for i in range(num_points + 1)
        ]
        self._draw_stroke(points)

    def draw_circle(self, cx: int, cy: int, radius: int):
        """Draw a circle."""
        points = []
        for i in range(33):
            angle = 2 * math.pi * i / 32
            x = int(cx + radius * math.cos(angle))
            y = int(cy + radius * math.sin(angle))
            points.append((x, y))
        self._draw_stroke(points)

    def draw_rectangle(self, x1: int, y1: int, x2: int, y2: int):
        """Draw a rectangle."""
        self.draw_line(x1, y1, x2, y1)
        self.draw_line(x2, y1, x2, y2)
        self.draw_line(x2, y2, x1, y2)
        self.draw_line(x1, y2, x1, y1)

    def draw_arrow(self, x1: int, y1: int, x2: int, y2: int, head_size: int = 12):
        """Draw an arrow from (x1,y1) to (x2,y2)."""
        self.draw_line(x1, y1, x2, y2)
        angle = math.atan2(y2 - y1, x2 - x1)
        for da in [0.4, -0.4]:
            hx = int(x2 - head_size * math.cos(angle + da))
            hy = int(y2 - head_size * math.sin(angle + da))
            self.draw_line(x2, y2, hx, hy)

    def draw_checkbox(self, x: int, y: int, size: int = 16, checked: bool = False):
        """Draw a checkbox, optionally with a checkmark."""
        self.draw_rectangle(x, y, x + size, y + size)
        if checked:
            self.draw_line(x + 3, y + int(size * 0.55), x + int(size * 0.4), y + size - 3)
            self.draw_line(x + int(size * 0.4), y + size - 3, x + size - 3, y + 3)


# ═══════════════════════════════════════════════════════════════════════════
# PRESET STYLES
# ═══════════════════════════════════════════════════════════════════════════

STYLE_NEAT = InkStyle(char_width=12, char_height=16, line_spacing=22, stroke_speed=0.006, jitter_px=0)
STYLE_NORMAL = InkStyle(char_width=14, char_height=18, line_spacing=24, stroke_speed=0.008, jitter_px=1)
STYLE_MESSY = InkStyle(char_width=16, char_height=20, line_spacing=26, stroke_speed=0.012, jitter_px=2)
STYLE_SMALL = InkStyle(char_width=8, char_height=10, line_spacing=14, stroke_speed=0.005, jitter_px=1)
STYLE_LARGE = InkStyle(char_width=20, char_height=26, line_spacing=34, stroke_speed=0.010, jitter_px=1)


def get_ink(style: str = "normal") -> SyntheticInkEngine:
    """Get an ink engine with a named style."""
    styles = {
        "neat": STYLE_NEAT,
        "normal": STYLE_NORMAL,
        "messy": STYLE_MESSY,
        "small": STYLE_SMALL,
        "large": STYLE_LARGE,
    }
    return SyntheticInkEngine(style=styles.get(style, STYLE_NORMAL))
