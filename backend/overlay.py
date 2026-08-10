"""
Full-screen desktop mesh overlay for J.A.R.V.I.S.
Shows an animated neon mesh grid covering all displays, blocks user input,
and dismisses when the user types "stop".

Usage:
  python overlay.py "Status text here"
  python overlay.py --status "Working..."
  
The overlay reads dynamic status from /tmp/jarvis_overlay_status.txt
(relay agent writes to this file to update the status text in real-time)
"""

import math
import os
import random
import signal
import sys
import threading
import time

try:
    import tkinter as tk
except ImportError:
    import Tkinter as tk


class MeshOverlay:
    def __init__(self, status_text="J.A.R.V.I.S. is working..."):
        self.root = tk.Tk()
        self.root.title("JARVIS Overlay")
        self.status_message = status_text

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        self.root.overrideredirect(True)
        self.root.geometry(f"{screen_w}x{screen_h}+0+0")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.35)
        self.root.configure(bg="#000008")
        self.root.focus_force()

        self.canvas = tk.Canvas(
            self.root,
            width=screen_w,
            height=screen_h,
            highlightthickness=0,
            bg="#000008",
        )
        self.canvas.pack()

        self.screen_w = screen_w
        self.screen_h = screen_h
        self.grid_spacing = 60
        self.wave_offset = 0.0
        self.particles = []
        self.running = True
        self._status_file = "/tmp/jarvis_overlay_status.txt"
        self._last_status_read = ""

        self._create_mesh()
        self._create_particles()
        self._create_ui()
        self._block_input()

        self.root.after(50, self._animate)
        self.root.protocol("WM_DELETE_WINDOW", self._exit)

    def _create_mesh(self):
        self.mesh_hlines = []
        self.mesh_vlines = []
        gs = self.grid_spacing
        w, h = self.screen_w, self.screen_h

        for x in range(0, w + gs, gs):
            line = self.canvas.create_line(
                x, 0, x, h,
                fill="#00ddff", width=1, tags="mesh_v"
            )
            self.mesh_vlines.append(line)

        for y in range(0, h + gs, gs):
            line = self.canvas.create_line(
                0, y, w, y,
                fill="#00ddff", width=1, tags="mesh_h"
            )
            self.mesh_hlines.append(line)

    def _create_particles(self):
        for _ in range(60):
            self.particles.append({
                "x": random.randint(0, self.screen_w),
                "y": random.randint(0, self.screen_h),
                "vx": random.uniform(-1.5, 1.5),
                "vy": random.uniform(-1.5, 1.5),
                "size": random.randint(2, 5),
                "alpha": random.uniform(0.3, 1.0),
            })

    def _create_ui(self):
        cx, cy = self.screen_w // 2, self.screen_h // 2

        self.canvas.create_text(
            cx, cy - 80,
            text="J.A.R.V.I.S.",
            fill="#00ffff",
            font=("Helvetica", 56, "bold"),
            tags="logo",
        )
        self.canvas.create_text(
            cx, cy - 20,
            text="Autonomous System Control",
            fill="#00aaff",
            font=("Helvetica", 18, "light"),
            tags="subtitle",
        )

        h = self.screen_h - 60
        self.status_item = self.canvas.create_text(
            cx, h,
            text=f"▸ {self.status_message}",
            fill="#88ddff",
            font=("Helvetica", 18),
            tags="status",
        )

        self.canvas.create_text(
            cx, h + 40,
            text="Type 'stop' to cancel",
            fill="#4488aa",
            font=("Helvetica", 13),
            tags="hint",
        )

        self._draw_corner_accents()

    def _draw_corner_accents(self):
        w, h = self.screen_w, self.screen_h
        accent_color = "#00ffff"
        for cx, cy, xdir, ydir in [
            (30, 30, 1, 1),
            (w - 30, 30, -1, 1),
            (30, h - 30, 1, -1),
            (w - 30, h - 30, -1, -1),
        ]:
            self.canvas.create_line(
                cx, cy, cx + xdir * 60, cy,
                fill=accent_color, width=3, tags="accent"
            )
            self.canvas.create_line(
                cx, cy, cx, cy + ydir * 60,
                fill=accent_color, width=3, tags="accent"
            )

    def _block_input(self):
        try:
            self.root.grab_set_global()
        except Exception:
            try:
                self.root.grab_set()
            except Exception:
                pass

        self.root.bind_all("<Key>", self._on_key, add="+")
        self.root.bind_all("<Button>", lambda e: "break", add="+")
        self.root.bind_all("<Motion>", lambda e: "break", add="+")
        self.root.bind_all("<MouseWheel>", lambda e: "break", add="+")
        self.root.bind_all("<Button-4>", lambda e: "break", add="+")
        self.root.bind_all("<Button-5>", lambda e: "break", add="+")

        self._refocus_loop()

    def _refocus_loop(self):
        if self.running:
            try:
                self.root.focus_force()
                self.root.lift()
                self.root.attributes("-topmost", True)
            except Exception:
                pass
            self.root.after(200, self._refocus_loop)

    def _on_key(self, event):
        if not hasattr(self, "_key_buf"):
            self._key_buf = []
        ch = getattr(event, "char", "") or ""
        if ch:
            self._key_buf.append(ch.lower())
            if len(self._key_buf) > 6:
                self._key_buf.pop(0)
            seq = "".join(self._key_buf)
            if seq == "stop":
                self._exit()
        return "break"

    def _exit(self):
        self.running = False
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _animate(self):
        if not self.running:
            return

        self.wave_offset += 0.08
        gs = self.grid_spacing
        w, h = self.screen_w, self.screen_h

        for i, line_id in enumerate(self.mesh_vlines):
            x = i * gs
            wave = math.sin(self.wave_offset + i * 0.3) * 8
            self.canvas.coords(line_id, x, 0, x + wave, h)
            brightness = int(120 + 80 * math.sin(self.wave_offset + i * 0.5))
            color = f"#00{brightness:02x}ff"
            self.canvas.itemconfig(line_id, fill=color)

        for i, line_id in enumerate(self.mesh_hlines):
            y = i * gs
            wave = math.sin(self.wave_offset * 0.7 + i * 0.25) * 6
            self.canvas.coords(line_id, 0, y + wave, w, y + wave)
            brightness = int(100 + 80 * math.sin(self.wave_offset * 0.6 + i * 0.4))
            color = f"#00{brightness:02x}ff"
            self.canvas.itemconfig(line_id, fill=color)

        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            if p["x"] < 0 or p["x"] > w:
                p["vx"] *= -1
            if p["y"] < 0 or p["y"] > h:
                p["vy"] *= -1

        p_color = f"#00ddff"
        self.canvas.delete("particle")
        for p in self.particles:
            alpha = int(p["alpha"] * 255)
            self.canvas.create_oval(
                p["x"] - p["size"] / 2,
                p["y"] - p["size"] / 2,
                p["x"] + p["size"] / 2,
                p["y"] + p["size"] / 2,
                fill=p_color,
                outline="",
                tags="particle",
            )

        pulse = int(150 + 105 * math.sin(time.time() * 2))
        self.canvas.itemconfig("logo", fill=f"#00{pulse:02x}ff")
        self.canvas.itemconfig("status", fill=f"#{pulse:02x}ddff")

        colors = ["#00ffff", "#00ddff", "#88ddff", "#00ffff"]
        idx = int(time.time() * 2) % len(colors)
        self.canvas.itemconfig("subtitle", fill=colors[idx])

        self._poll_status_file()

        self.root.after(50, self._animate)

    def _poll_status_file(self):
        try:
            if os.path.isfile(self._status_file):
                with open(self._status_file, "r") as f:
                    content = f.read().strip()
                if content and content != self._last_status_read:
                    self._last_status_read = content
                    self.canvas.itemconfig("status", text=f"▸ {content}")
        except Exception:
            pass

    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._exit()


def main():
    status = "J.A.R.V.I.S. is working..."
    if len(sys.argv) > 1:
        if sys.argv[1] == "--status" and len(sys.argv) > 2:
            status = sys.argv[2]
        else:
            status = " ".join(sys.argv[1:])

    overlay = MeshOverlay(status)
    overlay.run()


if __name__ == "__main__":
    main()
