"""
Esoteric Language Engine — Piet image-based & Befunge stack code synthesis + execution.

NO hardcoded app-specific logic. Uses file-format knowledge to synthesize images/text
that esolang interpreters consume, then executes headlessly on hidden desktop via subprocess.
"""

import os
import re
import json
import subprocess
import tempfile
import time
import math
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Piet Color Map (hue x lightness → RGB) ────────────────────────────
# Piet uses 18 colors: 6 hues × 3 lightness levels
PIET_COLORS = {
    # (hue_index, lightness) → RGB
    # Hue order: red, yellow, green, cyan, blue, magenta
    # Lightness: light(0), normal(1), dark(2)
    (0, 0): (255, 192, 192),  # light red
    (0, 1): (255, 0, 0),      # normal red
    (0, 2): (192, 0, 0),      # dark red
    (1, 0): (255, 255, 192),  # light yellow
    (1, 1): (255, 255, 0),    # normal yellow
    (1, 2): (192, 192, 0),    # dark yellow
    (2, 0): (192, 255, 192),  # light green
    (2, 1): (0, 255, 0),      # normal green
    (2, 2): (0, 192, 0),      # dark green
    (3, 0): (192, 255, 255),  # light cyan
    (3, 1): (0, 255, 255),    # normal cyan
    (3, 2): (0, 192, 192),    # dark cyan
    (4, 0): (192, 192, 255),  # light blue
    (4, 1): (0, 0, 255),      # normal blue
    (4, 2): (0, 0, 192),      # dark blue
    (5, 0): (255, 192, 255),  # light magenta
    (5, 1): (255, 0, 255),    # normal magenta
    (5, 2): (192, 0, 192),    # dark magenta
}

# Piet operation encoding: (hue_change, lightness_change) → operation
PIET_OPS = {
    # (Δhue, Δlight) → op
    (1, 0): "nop",           # same color = no operation (but move)
    (2, 0): "push",          # push number
    (0, 1): "pop",           # pop stack top
    (1, 1): "add",           # pop a, pop b, push b+a
    (2, 1): "subtract",      # pop a, pop b, push b-a
    (0, 2): "multiply",      # pop a, pop b, push b*a
    (1, 2): "divide",        # pop a, pop b, push b/a
    (2, 2): "mod",           # pop a, pop b, push b%a
}

# Befunge standard ops (single-char instructions)
BEFUNGE_OPS = {
    '0': "push 0", '1': "push 1", '2': "push 2", '3': "push 3",
    '4': "push 4", '5': "push 5", '6': "push 6", '7': "push 7",
    '8': "push 8", '9': "push 9",
    '+': "add", '-': "subtract", '*': "multiply", '/': "divide", '%': "mod",
    '!': "not", '`': "greater",
    '>': "go right", '<': "go left", '^': "go up", 'v': "go down",
    '?': "random direction",
    '_': "horizontal if", '|': "vertical if",
    '"': "string mode", ':': "duplicate", '\\': "swap",
    '$': "pop discard", '.': "print int", ',': "print char",
    '#': "bridge", 'g': "get", 'p': "put",
    '&': "input int", '~': "input char",
    '@': "end",
}


class EsolangEngine:
    """Generates and executes esoteric language programs (Piet images, Befunge grids).
    
    Uses LLM to understand the DESIRED computation, then generates the correct
    file format (PNG bitmap for Piet, text grid for Befunge) and executes headlessly.
    """

    def __init__(self):
        self.work_dir = Path(os.path.expanduser("~/.jarvis/esoteric"))
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # ─── Piet Image Generation ───────────────────────────────────────
    def generate_piet_from_payload(self, hex_payload: str, output_path: str = None,
                                   width: int = 32, cell_size: int = 10) -> str:
        """Convert a hex payload into a Piet bitmap image.
        
        Each byte maps to a color cell. The hue transitions encode operations.
        Returns path to generated .png file.
        """
        try:
            from PIL import Image
        except ImportError:
            # Install Pillow if needed
            subprocess.run(["pip", "install", "Pillow"], capture_output=True)
            from PIL import Image

        if not output_path:
            output_path = str(self.work_dir / "piet_generated.png")

        data_bytes = bytes.fromhex(hex_payload.replace(" ", ""))
        rows = max(1, math.ceil(len(data_bytes) / width))
        img = Image.new("RGB", (width * cell_size, rows * cell_size))

        for i, byte_val in enumerate(data_bytes):
            x = (i % width) * cell_size
            y = (i // width) * cell_size
            # Map byte to hue (0-5) and lightness (0-2)
            hue = byte_val % 6
            lightness = (byte_val // 6) % 3
            rgb = PIET_COLORS.get((hue, lightness), (255, 255, 255))
            for dx in range(cell_size):
                for dy in range(cell_size):
                    img.putpixel((x + dx, y + dy), rgb)

        img.save(output_path)
        logger.info(f"Generated Piet image: {output_path} ({width}x{rows} cells)")
        return output_path

    def generate_piet_from_computation(self, operations: List[str],
                                       output_path: str = None,
                                       cell_size: int = 10) -> str:
        """Generate a Piet image from a list of abstract operations.
        
        Operations: ["push 42", "push 7", "multiply", "print"]
        Each op maps to a color transition in the Piet grid.
        Returns path to generated .png file.
        """
        try:
            from PIL import Image
        except ImportError:
            subprocess.run(["pip", "install", "Pillow"], capture_output=True)
            from PIL import Image

        if not output_path:
            output_path = str(self.work_dir / "piet_computation.png")

        # Map operations to color cells
        op_to_color = {
            "push": (0, 1), "pop": (0, 1),
            "add": (1, 1), "subtract": (2, 1),
            "multiply": (0, 2), "divide": (1, 2),
            "mod": (2, 2), "not": (0, 0),
            "print": (1, 0), "nop": (0, 1),
            "dup": (1, 1), "swap": (2, 1),
        }

        cells = []
        for op in operations:
            base_op = op.split()[0].lower() if op.split() else "nop"
            color_key = op_to_color.get(base_op, (0, 1))
            cells.append(color_key)
            # Add number push if present
            if len(op.split()) > 1 and op.split()[1].isdigit():
                num = int(op.split()[1])
                # Encode number as repeated push cells
                for digit in str(num):
                    cells.append((0, 1))  # push digit

        cols = max(1, math.ceil(math.sqrt(len(cells))))
        rows = max(1, math.ceil(len(cells) / cols))
        img = Image.new("RGB", (cols * cell_size, rows * cell_size))

        for i, (hue, light) in enumerate(cells):
            x = (i % cols) * cell_size
            y = (i // cols) * cell_size
            rgb = PIET_COLORS.get((hue, light), (255, 255, 255))
            for dx in range(cell_size):
                for dy in range(cell_size):
                    img.putpixel((x + dx, y + dy), rgb)

        img.save(output_path)
        logger.info(f"Generated Piet computation: {output_path} ({len(cells)} ops)")
        return output_path

    def run_piet(self, image_path: str, timeout: int = 30) -> Dict:
        """Execute a Piet image headlessly via npiet CLI.
        
        Returns: {success, output, returncode, stderr}
        """
        if not os.path.isfile(image_path):
            return {"success": False, "error": f"Image not found: {image_path}"}

        # Try npiet first, then fall back to Python piet interpreter
        npiet = self._find_executable("npiet")
        if npiet:
            cmd = [npiet, image_path]
        else:
            # Use Python-based Piet interpreter as fallback
            return self._run_piet_python(image_path, timeout)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "returncode": result.returncode,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Piet execution timed out ({timeout}s)"}
        except FileNotFoundError:
            return self._run_piet_python(image_path, timeout)

    def _run_piet_python(self, image_path: str, timeout: int) -> Dict:
        """Pure Python Piet interpreter — reads the image and simulates execution."""
        try:
            from PIL import Image
        except ImportError:
            return {"success": False, "error": "Pillow not installed for Python Piet interpreter"}

        try:
            img = Image.open(image_path)
            img = img.convert("RGB")
            width, height = img.size

            stack = []
            dp = 0  # direction pointer: 0=right, 1=down, 2=left, 3=up
            cc = 0  # codel chooser: 0=left, 1=right (relative to dp)
            output_chars = []
            output_nums = []

            # Parse image into color grid (1 pixel per codel)
            grid = []
            for y in range(height):
                row = []
                for x in range(width):
                    r, g, b = img.getpixel((x, y))
                    # Quantize to nearest Piet color
                    hue, light = self._closest_piet_color(r, g, b)
                    row.append((hue, light))
                grid.append(row)

            # Walk the image executing Piet operations
            y, x = 0, 0
            visited = set()
            steps = 0
            max_steps = 10000

            while steps < max_steps:
                steps += 1
                if y >= height or x >= width or y < 0 or x < 0:
                    break

                current = grid[y][x]
                next_x = x + [1, 0, -1, 0][dp]
                next_y = y + [0, 1, 0, -1][dp]

                if next_x < 0 or next_x >= width or next_y < 0 or next_y >= height:
                    # Hit wall — bounce
                    dp = (dp + 2) % 4
                    continue

                next_color = grid[next_y][next_x]
                dh = (next_color[0] - current[0]) % 6
                dl = (next_color[1] - current[1]) % 3

                # Execute operation based on color transition
                op_key = (dh, dl)
                if op_key == (0, 0):
                    pass  # Same color = no op
                elif op_key == (2, 0):
                    # push — count contiguous same-color codels
                    count = self._count_codels(grid, x, y, current, width, height)
                    stack.append(count)
                elif op_key == (0, 1):
                    if stack:
                        stack.pop()
                elif op_key == (1, 1):
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b + a)
                elif op_key == (2, 1):
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b - a)
                elif op_key == (0, 2):
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b * a)
                elif op_key == (1, 2):
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b // a if a != 0 else 0)
                elif op_key == (2, 2):
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b % a if a != 0 else 0)
                elif op_key == (1, 0):
                    # print number
                    if stack:
                        output_nums.append(stack.pop())
                elif op_key == (0, 0) and dh == 0 and dl == 1:
                    pass

                # Special: check for "print" operations (hue transitions to same row)
                if dh in (1, 0) and dl == 0 and stack:
                    # Simple print detection based on color transition
                    pass

                x, y = next_x, next_y
                visited.add((x, y))

            return {
                "success": True,
                "output": "".join(output_chars) if output_chars else str(output_nums),
                "stack": stack,
                "steps": steps,
                "nums": output_nums,
                "chars": output_chars,
            }

        except Exception as e:
            return {"success": False, "error": f"Python Piet interpreter error: {e}"}

    def _closest_piet_color(self, r: int, g: int, b: int) -> Tuple[int, int]:
        """Find closest Piet color to given RGB."""
        best = (0, 1)
        best_dist = float('inf')
        for (hue, light), rgb in PIET_COLORS.items():
            dist = (r - rgb[0]) ** 2 + (g - rgb[1]) ** 2 + (b - rgb[2]) ** 2
            if dist < best_dist:
                best_dist = dist
                best = (hue, light)
        return best

    def _count_codels(self, grid, x, y, color, width, height) -> int:
        """Count contiguous same-color codels (for Piet push value)."""
        visited = set()
        count = 0
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            if cx < 0 or cx >= width or cy < 0 or cy >= height:
                continue
            if grid[cy][cx] != color:
                continue
            visited.add((cx, cy))
            count += 1
            stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
        return count

    # ─── Befunge Code Generation ─────────────────────────────────────
    def generate_befunge(self, operations: List[str], width: int = 80, height: int = 25) -> str:
        """Generate a Befunge-93 program from abstract operations.
        
        Returns path to generated .bfunge file.
        """
        output_path = str(self.work_dir / "generated.befunge")

        grid = [[' ' for _ in range(width)] for _ in range(height)]

        # Fill with no-ops first
        for y in range(height):
            for x in range(width):
                grid[y][x] = ' '  # space = no-op

        # Place operations in sequence
        px, py = 0, 0
        for op in operations:
            parts = op.split()
            cmd = parts[0].lower()

            if cmd == "push" and len(parts) > 1:
                val = parts[1]
                # Befunge-93 pushes one digit per instruction cell (0-9).
                # For multi-digit values, push each digit individually.
                # Callers should combine via add/multiply or use print with ASCII.
                if val.isdigit():
                    for ch in val:
                        if py < height and px < width:
                            grid[py][px] = ch
                            px += 1
                elif ch := val[0]:  # Single character
                    if py < height and px < width:
                        grid[py][px] = ch
                        px += 1
            elif cmd == "add":
                if py < height and px < width:
                    grid[py][px] = '+'
                    px += 1
            elif cmd == "subtract":
                if py < height and px < width:
                    grid[py][px] = '-'
                    px += 1
            elif cmd == "multiply":
                if py < height and px < width:
                    grid[py][px] = '*'
                    px += 1
            elif cmd == "divide":
                if py < height and px < width:
                    grid[py][px] = '/'
                    px += 1
            elif cmd == "mod":
                if py < height and px < width:
                    grid[py][px] = '%'
                    px += 1
            elif cmd == "print_int":
                if py < height and px < width:
                    grid[py][px] = '.'
                    px += 1
            elif cmd == "print_char":
                if py < height and px < width:
                    grid[py][px] = ','
                    px += 1
            elif cmd == "dup":
                if py < height and px < width:
                    grid[py][px] = ':'
                    px += 1
            elif cmd == "swap":
                if py < height and px < width:
                    grid[py][px] = '\\'
                    px += 1
            elif cmd == "pop":
                if py < height and px < width:
                    grid[py][px] = '$'
                    px += 1
            elif cmd == "random":
                if py < height and px < width:
                    grid[py][px] = '?'
                    px += 1
            elif cmd == "end":
                if py < height and px < width:
                    grid[py][px] = '@'
                    px += 1
            elif cmd == "go_right":
                if py < height and px < width:
                    grid[py][px] = '>'
                    px += 1
            elif cmd == "go_left":
                if py < height and px < width:
                    grid[py][px] = '<'
                    px += 1
            elif cmd == "go_up":
                if py < height and px < width:
                    grid[py][px] = '^'
                    px += 1
            elif cmd == "go_down":
                if py < height and px < width:
                    grid[py][px] = 'v'
                    px += 1

            # Wrap to next line every 20 chars
            if px >= width - 2:
                px = 0
                py = min(py + 1, height - 1)

        # Add final @
        if py < height and px < width:
            grid[py][px] = '@'

        with open(output_path, "w") as f:
            for row in grid:
                f.write("".join(row) + "\n")

        logger.info(f"Generated Befunge program: {output_path}")
        return output_path

    def run_befunge(self, program_path: str, timeout: int = 30) -> Dict:
        """Execute a Befunge-93 program headlessly.
        
        Uses a built-in Python Befunge interpreter (no external deps needed).
        Returns: {success, output, returncode, stack}
        """
        if not os.path.isfile(program_path):
            return {"success": False, "error": f"Program not found: {program_path}"}

        # Try funge interpreter first
        funge = self._find_executable("funge") or self._find_executable("befunge")
        if funge:
            try:
                result = subprocess.run(
                    [funge, program_path], capture_output=True, text=True, timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "returncode": result.returncode,
                    "stderr": result.stderr,
                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Fall back to Python interpreter
        return self._run_befunge_python(program_path, timeout)

    def _run_befunge_python(self, program_path: str, timeout: int) -> Dict:
        """Pure Python Befunge-93 interpreter."""
        import random

        try:
            with open(program_path, "r") as f:
                lines = f.readlines()

            # Parse grid
            max_w = max(len(line.rstrip('\n')) for line in lines) if lines else 80
            max_h = len(lines)
            grid = []
            for line in lines:
                row = list(line.rstrip('\n').ljust(max_w))
                grid.append(row)
            while len(grid) < 25:
                grid.append([' '] * max_w)

            stack = []
            output = []
            x, y = 0, 0
            dx, dy = 1, 0  # direction: right
            string_mode = False
            steps = 0
            max_steps = 50000

            while steps < max_steps:
                steps += 1
                ch = grid[y][x]

                if string_mode:
                    if ch == '"':
                        string_mode = False
                    else:
                        stack.append(ord(ch))
                elif ch.isdigit():
                    stack.append(int(ch))
                elif ch == '"':
                    string_mode = True
                elif ch == '+':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b + a)
                elif ch == '-':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b - a)
                elif ch == '*':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b * a)
                elif ch == '/':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b // a if a else 0)
                elif ch == '%':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(b % a if a else 0)
                elif ch == '!':
                    if stack:
                        stack.append(0 if stack.pop() else 1)
                elif ch == '`':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(1 if b > a else 0)
                elif ch == '>':
                    dx, dy = 1, 0
                elif ch == '<':
                    dx, dy = -1, 0
                elif ch == '^':
                    dx, dy = 0, -1
                elif ch == 'v':
                    dx, dy = 0, 1
                elif ch == '?':
                    d = random.randint(0, 3)
                    dx, dy = [(1, 0), (-1, 0), (0, -1), (0, 1)][d]
                elif ch == '_':
                    val = stack.pop() if stack else 0
                    dx, dy = (-1, 0) if val else (1, 0)
                elif ch == '|':
                    val = stack.pop() if stack else 0
                    dx, dy = (0, -1) if val else (0, 1)
                elif ch == ':':
                    stack.append(stack[-1] if stack else 0)
                elif ch == '\\':
                    if len(stack) >= 2:
                        a, b = stack.pop(), stack.pop()
                        stack.append(a)
                        stack.append(b)
                elif ch == '$':
                    if stack:
                        stack.pop()
                elif ch == '.':
                    val = stack.pop() if stack else 0
                    output.append(str(val))
                elif ch == ',':
                    val = stack.pop() if stack else 0
                    output.append(chr(val))
                elif ch == '#':
                    # Bridge: skip next cell
                    x += dx
                    y += dy
                elif ch == 'g':
                    if len(stack) >= 2:
                        gy, gx = stack.pop(), stack.pop()
                        if 0 <= gx < max_w and 0 <= gy < max_h:
                            stack.append(ord(grid[gy][gx]))
                        else:
                            stack.append(0)
                elif ch == 'p':
                    if len(stack) >= 3:
                        val, gy, gx = stack.pop(), stack.pop(), stack.pop()
                        if 0 <= gx < max_w and 0 <= gy < max_h:
                            grid[gy][gx] = chr(val)
                elif ch == '&':
                    stack.append(0)  # No stdin in headless
                elif ch == '~':
                    stack.append(0)
                elif ch == '@':
                    break

                # Move
                x += dx
                y += dy

                # Wrap
                x %= max_w
                y %= max_h

            return {
                "success": True,
                "output": "".join(output),
                "stack": stack,
                "steps": steps,
            }

        except Exception as e:
            return {"success": False, "error": f"Befunge interpreter error: {e}"}

    def _find_executable(self, name: str) -> Optional[str]:
        """Find an executable on PATH."""
        import shutil
        return shutil.which(name)

    # ─── Unified Compute Interface ───────────────────────────────────
    def compute(self, lang: str, operations: List[str] = None,
                hex_payload: str = None, **kwargs) -> Dict:
        """Unified interface: generate + execute an esolang program.
        
        lang: "piet" or "befunge"
        operations: list of abstract ops like ["push 42", "push 7", "multiply", "print_int"]
        hex_payload: raw hex to encode (for Piet)
        """
        if lang == "piet":
            if hex_payload:
                img_path = self.generate_piet_from_payload(hex_payload, **kwargs)
            elif operations:
                img_path = self.generate_piet_from_computation(operations, **kwargs)
            else:
                return {"success": False, "error": "Need hex_payload or operations for Piet"}
            return self.run_piet(img_path)

        elif lang in ("befunge", "befunge93", "bf"):
            if not operations:
                operations = ["push 1", "push 2", "add", "print_int", "end"]
            prog_path = self.generate_befunge(operations, **kwargs)
            return self.run_befunge(prog_path)

        else:
            return {"success": False, "error": f"Unknown esolang: {lang}. Supported: piet, befunge"}

    def pipeline_from_hex(self, hex_payload: str, lang: str = "piet") -> Dict:
        """Full pipeline: hex payload → esolang program → execute → return output.
        
        This is the main entry point for the orchestration directive.
        """
        logger.info(f"Esolang pipeline: {len(hex_payload)} hex chars → {lang}")

        # Generate operations from hex payload
        operations = []
        for i in range(0, len(hex_payload), 2):
            byte_val = int(hex_payload[i:i+2], 16)
            operations.append(f"push {byte_val}")
            if i > 0 and i % 4 == 0:
                operations.append("add")

        operations.extend(["print_int", "end"])

        result = self.compute(lang, operations=operations)
        result["hex_input"] = hex_payload[:100] + ("..." if len(hex_payload) > 100 else "")
        result["lang"] = lang
        result["operations_count"] = len(operations)
        return result


# Module-level singleton
_esolang_engine = None

def get_esolang_engine() -> EsolangEngine:
    global _esolang_engine
    if _esolang_engine is None:
        _esolang_engine = EsolangEngine()
    return _esolang_engine
