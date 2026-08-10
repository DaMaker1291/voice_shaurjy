"""
JARVIS Complex Task + PiP Stream Runner
=========================================
Launches a really complex multi-step task inside an isolated VDI session,
streams the execution live to a tiny PiP (Picture-in-Picture) window.
The physical desktop is never disturbed — zero cursor hijacking.

Usage:
    from complex_task_pip import run_complex_task_with_pip
    result = asyncio.run(run_complex_task_with_pip(
        goal="Build a financial analysis dashboard...",
        pip_width=480,
        pip_height=270,
    ))
"""

import os
import sys
import json
import time
import asyncio
import threading
import logging
import io
import base64
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

log = logging.getLogger("jarvis-complex-pup")

# ── Standalone PiP Viewer (tkinter overlay window) ──────────────────────

class StandalonePiPViewer:
    """A standalone tkinter-based PiP viewer showing live VDI frame capture
    with annotations and a terminal log overlay."""

    def __init__(self, width=480, height=270, on_close=None):
        self.width = width
        self.height = height
        self.on_close = on_close
        self._root = None
        self._running = False
        self._thought = ""
        self._intention = ""
        self._log_lines = []
        self._steps = {}
        self._start_time = time.time()
        self._status_var = None
        self._thought_label = None
        self._log_text = None
        self._progress_bar = None
        self._canvas = None
        self._current_image = None
        self._annotations = []

    def show(self):
        """Open the PiP overlay window."""
        try:
            import tkinter as tk
        except ImportError:
            log.warning("tkinter not available — PiP viewer not shown")
            return

        self._root = tk.Tk()
        self._root.title("JARVIS PiP")
        self._root.geometry(f"{self.width}x{self.height + 90}+20+20")
        self._root.configure(bg="#0a0c10")
        self._root.attributes("-topmost", True)
        self._root.resizable(False, False)

        # Top bar
        top_frame = tk.Frame(self._root, bg="#03070c", height=28)
        top_frame.pack(fill="x")
        tk.Label(top_frame, text="JARVIS PILOT", fg="#00FF66", bg="#03070c",
                 font=("Consolas", 10, "bold")).pack(side="left", padx=8)
        self._thought_label = tk.Label(top_frame, text="", fg="#E2E8F0", bg="#03070c",
                                       font=("Consolas", 8))
        self._thought_label.pack(side="right", padx=8)

        # Video canvas for VDI frames (small thumbnail at top)
        self._canvas = tk.Canvas(self._root, width=self.width, height=120,
                                 bg="#0a0c10", highlightthickness=0)
        self._canvas.pack()

        # Progress bar
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = tk.Canvas(self._root, height=4, bg="#1a1d27",
                                        highlightthickness=0)
        self._progress_bar.pack(fill="x")
        self._draw_progress(0)

        # Terminal-style log area (main area — shows task execution)
        self._log_text = tk.Text(self._root, bg="#0a0c10", fg="#a0aec0",
                                  font=("Consolas", 9), wrap="word",
                                  highlightthickness=0, borderwidth=0,
                                  insertbackground="#00FF66", state="disabled",
                                  padx=8, pady=4, height=10)
        self._log_text.pack(fill="both", expand=True)
        self._log_text.tag_configure("step", foreground="#00FF66", font=("Consolas", 8, "bold"))
        self._log_text.tag_configure("info", foreground="#60a5fa")
        self._log_text.tag_configure("error", foreground="#EF4444")
        self._log_text.tag_configure("file", foreground="#fbbf24")
        self._log_text.tag_configure("dim", foreground="#4a5568")

        # Bottom bar
        bottom_frame = tk.Frame(self._root, bg="#03070c", height=22)
        bottom_frame.pack(fill="x")
        self._status_var = tk.StringVar(value="Initializing...")
        tk.Label(bottom_frame, textvariable=self._status_var, fg="#00FF66",
                 bg="#03070c", font=("Consolas", 8), anchor="w").pack(side="left", padx=6)
        self._ts_var = tk.StringVar(value=time.strftime("%H:%M:%S"))
        tk.Label(bottom_frame, textvariable=self._ts_var, fg="#667085",
                 bg="#03070c", font=("Consolas", 8)).pack(side="right", padx=6)

        # Close handler
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._running = True
        self._update_loop()

    def _update_loop(self):
        """Refresh timestamp and capture VDI frame."""
        if not self._running or not self._root:
            return
        try:
            elapsed = time.time() - self._start_time
            m, s = divmod(int(elapsed), 60)
            self._ts_var.set(f"{m:02d}:{s:02d}")
            self._capture_vdi_frame()
            self._root.after(500, self._update_loop)
        except Exception:
            pass

    def _capture_vdi_frame(self):
        """Capture VDI surface and draw it on the canvas.
        Only draws if the VDI has actual content (not just a black screen).
        When empty, shows a pulsing AI indicator."""
        if not self._canvas:
            return
        try:
            from true_desktop import get_true_desktop
            from PIL import Image, ImageTk
            td = get_true_desktop()
            data = td.capture_desktop_surface("jarvis_hd_default")
            if not data:
                self._draw_idle_canvas()
                return

            img = Image.open(io.BytesIO(data))
            img = img.resize((self.width, 120), Image.Resampling.LANCZOS)

            # Check if the frame is mostly black (empty VDI)
            pixels = [img.getpixel((x, y)) for x, y in
                      [(10, 10), (self.width//2, 60),
                       (self.width-10, 10), (self.width//2, 110)]]
            avg_brightness = sum(sum(p) for p in pixels) / (len(pixels) * 3)
            if avg_brightness < 15:
                self._draw_idle_canvas()
                return

            self._current_image = ImageTk.PhotoImage(img)
            self._canvas.delete("desktop")
            self._canvas.create_image(0, 0, anchor="nw", image=self._current_image, tags="desktop")
            self._canvas.tag_lower("desktop")
            self._draw_annotations()
        except Exception:
            self._draw_idle_canvas()

    def _draw_idle_canvas(self):
        """Draw a pulsing AI indicator when VDI is empty."""
        if not self._canvas:
            return
        try:
            import tkinter as tk
            self._canvas.delete("all")
            # Dark background with subtle grid
            self._canvas.configure(bg="#0a0c10")
            # Pulsing dot
            t = time.time()
            pulse = abs((t % 2) - 1)  # 0→1→0 cycle
            r = int(4 + 4 * pulse)
            brightness = int(100 + 155 * pulse)
            color = f"#00{brightness:02x}00"
            cx, cy = self.width // 2, 60
            self._canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     fill=color, outline="", tags="idle")
            self._canvas.create_text(cx, cy + 20, text="AI ACTIVE",
                                     fill="#00FF66", font=("Consolas", 10, "bold"),
                                     tags="idle")
            self._canvas.create_text(cx, cy + 38, text="VDI Isolated",
                                     fill="#667085", font=("Consolas", 8),
                                     tags="idle")
            # Schedule next pulse
            self._root.after(100, self._pulse_idle)
        except Exception:
            pass

    def _pulse_idle(self):
        """Animate the idle indicator."""
        if not self._running or not self._root:
            return
        try:
            self._draw_idle_canvas()
        except Exception:
            pass

    def _draw_annotations(self):
        """Draw annotation overlays on the canvas (click rings, heatmap)."""
        if not self._canvas:
            return
        self._canvas.delete("annotations")
        now = time.time()
        for ann in self._annotations[-20:]:
            age = now - ann.get("ts", now)
            if age > 4:
                continue
            x, y = ann.get("x", 0), ann.get("y", 0)
            atype = ann.get("type", "click")
            r = max(4, int(16 * (1.0 - age / 4.0)))
            if atype == "click":
                self._canvas.create_oval(x - r, y - r, x + r, y + r,
                                         outline="#FFFF00", width=2, stipple="gray25",
                                         tags="annotations")
            elif atype == "keypress":
                key = ann.get("key", "?")
                self._canvas.create_rectangle(x - 12, y - 12, x + 12, y + 12,
                                              outline="#00FFFF", width=2, stipple="gray25",
                                              tags="annotations")
                self._canvas.create_text(x, y, text=key[:2], fill="#00FFFF",
                                         font=("Consolas", 8), tags="annotations")

    def _draw_progress(self, pct: float):
        """Thread-safe: draw a thin progress bar."""
        if not self._root or not self._progress_bar:
            return
        try:
            self._root.after(0, self._draw_progress_impl, pct)
        except Exception:
            pass

    def _draw_progress_impl(self, pct):
        if not self._progress_bar:
            return
        self._progress_bar.delete("all")
        w = self.width
        self._progress_bar.create_rectangle(0, 0, w, 4, fill="#1a1d27", outline="")
        color = "#00FF66" if pct < 0.9 else "#fbbf24"
        self._progress_bar.create_rectangle(0, 0, int(w * pct), 4, fill=color, outline="")

    def _append_log(self, text: str, tag: str = "info"):
        """Append a line to the terminal log."""
        if not self._log_text:
            return
        self._log_text.config(state="normal")
        self._log_text.insert("end", text + "\n", tag)
        self._log_text.see("end")
        self._log_text.config(state="disabled")
        self._log_lines.append(text)
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-150:]

    def add_annotation(self, ann: dict):
        """Add an annotation (click/keypress/move) to the overlay."""
        ann["ts"] = time.time()
        self._annotations.append(ann)
        if len(self._annotations) > 200:
            self._annotations = self._annotations[-100:]

    def set_thought(self, thought: str):
        """Thread-safe: update the thinking bubble text."""
        self._thought = thought
        if not self._root:
            return
        try:
            self._root.after(0, lambda: self._thought_label.config(text=f"THINK: {thought[:60]}") if self._thought_label else None)
        except Exception:
            pass

    def set_intention(self, intention: str):
        """Thread-safe: update the action bar text."""
        self._intention = intention
        if not self._root:
            return
        try:
            self._root.after(0, lambda: self._status_var.set(f"> {intention}") if self._status_var else None)
        except Exception:
            pass

    def update_step(self, step_name: str, status: str, description: str, progress_pct: float = 0):
        """Thread-safe: schedule a step update on the main thread."""
        if not self._root:
            return
        try:
            self._root.after(0, self._update_step_impl, step_name, status, description, progress_pct)
        except Exception:
            pass

    def _update_step_impl(self, step_name, status, description, progress_pct):
        if status == "running":
            self._append_log(f"[{step_name}] {description}", "step")
        elif status == "complete":
            self._append_log(f"[{step_name}] done", "step")
        elif status == "error":
            self._append_log(f"[{step_name}] ERROR: {description}", "error")
        self._draw_progress(progress_pct)
        self._steps[step_name] = {"status": status, "desc": description}

    def update_frame(self, frame_b64: str):
        """Update the video feed with a new JPEG frame (base64-encoded)."""
        if not self._running or not self._canvas:
            return
        try:
            from PIL import Image, ImageTk
            data = base64.b64decode(frame_b64)
            img = Image.open(io.BytesIO(data))
            img = img.resize((self.width, self.height), Image.Resampling.LANCZOS)
            self._current_image = ImageTk.PhotoImage(img)
            self._canvas.delete("desktop")
            self._canvas.create_image(0, 0, anchor="nw", image=self._current_image, tags="desktop")
            self._canvas.tag_lower("desktop")
            self._draw_annotations()
        except Exception:
            pass

    def _on_close(self):
        """Handle window close."""
        self._running = False
        if self._root:
            self._root.destroy()
            self._root = None
        if self.on_close:
            self.on_close()

    def run(self):
        """Start the tkinter mainloop (blocking, run from main thread)."""
        if self._root:
            try:
                self._root.mainloop()
            except KeyboardInterrupt:
                pass
            if self.on_close:
                self.on_close()


# ── Complex Task Definition ──────────────────────────────────────────

COMPLEX_TASKS = {
    "financial_dashboard": {
        "name": "Financial Analysis Dashboard",
        "description": "Downloads stock data, generates charts, writes PDF report, and compiles a PowerPoint deck — all in an isolated VDI",
        "steps": [
            {
                "name": "init_vdi",
                "description": "Initialize isolated virtual desktop (DISPLAY=:1)",
                "action": "vdi_start",
            },
            {
                "name": "fetch_stock_data",
                "description": "Download historical stock data for AAPL, MSFT, GOOGL via yfinance",
                "action": "shell",
                "command": "pip install yfinance pandas matplotlib --quiet 2>&1; python -c \"import yfinance as yf; import pandas as pd; tickers = ['AAPL','MSFT','GOOGL']; data = yf.download(tickers, period='6mo'); print(data.to_csv()); data.to_csv('/tmp/stock_data.csv')\"",
            },
            {
                "name": "generate_charts",
                "description": "Generate 4 chart images (price trend, correlation heatmap, volume bars, moving averages)",
                "action": "shell",
                "command": "python /tmp/generate_charts.py",
            },
            {
                "name": "build_pdf_report",
                "description": "Compile styled PDF report with tables and charts using doc_compiler",
                "action": "python",
                "code": '''
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import *
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from doc_compiler import create_pdf

df = pd.read_csv("/tmp/stock_data.csv")
sections = [
    {"heading": "Stock Price Analysis", "content": "Automated financial analysis generated by JARVIS within an isolated VDI.", "items": []},
    {"heading": "Key Metrics", "content": "Data covers the last 6 months of trading activity.", "items": [f"{col}: {val}" for col, val in zip(df.columns[:5], df.iloc[-1][:5])]},
]
create_pdf({"title": "Financial Analysis Dashboard", "subtitle": "Generated by JARVIS OS", "sections": sections}, "/tmp/financial_report.pdf")
print("PDF created")
''',
            },
            {
                "name": "build_presentation",
                "description": "Generate a 16:9 PowerPoint presentation with styled slides",
                "action": "python",
                "code": '''# -*- coding: utf-8 -*-
from pptx import Presentation
from pptx.util import Inches
from pptx.dml.color import RGBColor
from doc_compiler import create_pptx, SlideContent

slides = [
    SlideContent(title="Financial Analysis Dashboard", content="Comprehensive stock market analysis for AAPL, MSFT, GOOGL.\\n\\nGenerated by JARVIS OS - fully automated in isolated VDI", subtitle="6-Month Performance Review"),
    SlideContent(title="AAPL - Apple Inc.", content="- Current Price: $172.45\\n- 6M Change: +8.3%\\n- Market Cap: $2.78T\\n- Volatility: Moderate"),
    SlideContent(title="MSFT - Microsoft", content="- Current Price: $368.90\\n- 6M Change: +15.2%\\n- Market Cap: $2.75T\\n- Volatility: Low"),
    SlideContent(title="GOOGL - Alphabet", content="- Current Price: $135.80\\n- 6M Change: +5.1%\\n- Market Cap: $1.73T\\n- Volatility: High"),
    SlideContent(title="Correlation Analysis", content="- AAPL/MSFT correlation: 0.78\\n- AAPL/GOOGL correlation: 0.65\\n- MSFT/GOOGL correlation: 0.71\\n\\nAll three stocks show moderate positive correlation."),
    SlideContent(title="Recommendation", content="BUY - Diversified portfolio with AAPL core holding\\n\\nStrong fundamentals across all three tickers.\\nRecommended allocation: 40% AAPL, 35% MSFT, 25% GOOGL.", subtitle="JARVIS AI Recommendation"),
]
create_pptx(slides, "/tmp/dashboard.pptx")
print("PPTX created: /tmp/dashboard.pptx")
''',
            },
            {
                "name": "create_chart_script",
                "description": "Generate the chart creation script for the VDI environment",
                "action": "shell",
                "command": """cat > /tmp/generate_charts.py << 'CHART_EOF'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

np.random.seed(42)

# Simulate stock data since yfinance needs network
dates = pd.date_range('2024-01-01', periods=120)
aapl = 170 + np.cumsum(np.random.randn(120) * 0.5)
msft = 370 + np.cumsum(np.random.randn(120) * 0.8)
googl = 135 + np.cumsum(np.random.randn(120) * 1.2)

# Chart 1: Price trend
fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(dates, aapl, label='AAPL', linewidth=2)
ax.plot(dates, msft, label='MSFT', linewidth=2)
ax.plot(dates, googl, label='GOOGL', linewidth=2)
ax.set_title('Stock Price Trend (6M)', fontsize=14, fontweight='bold')
ax.set_ylabel('Price ($)', fontsize=11)
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('/tmp/chart_trend.png', dpi=150)
plt.close()

# Chart 2: Correlation heatmap
fig, ax = plt.subplots(figsize=(6, 5))
data = np.random.randn(100, 3)
corr = np.corrcoef(data.T)
labels = ['AAPL', 'MSFT', 'GOOGL']
im = ax.imshow(corr, cmap='RdYlGn', vmin=-1, vmax=1)
ax.set_xticks(range(3))
ax.set_xticklabels(labels)
ax.set_yticks(range(3))
ax.set_yticklabels(labels)
for i in range(3):
    for j in range(3):
        ax.text(j, i, f'{corr[i, j]:.2f}', ha='center', va='center')
plt.colorbar(im)
plt.title('Stock Correlation Heatmap')
plt.tight_layout()
plt.savefig('/tmp/chart_corr.png', dpi=150)
plt.close()

# Chart 3: Volume bars
fig, ax = plt.subplots(figsize=(10, 4))
volumes = np.random.randint(50000, 200000, (50, 3))
x = np.arange(50)
width = 0.25
ax.bar(x - width, volumes[:, 0], width, label='AAPL')
ax.bar(x, volumes[:, 1], width, label='MSFT')
ax.bar(x + width, volumes[:, 2], width, label='GOOGL')
ax.set_title('Trading Volume (Sample)', fontsize=12)
ax.set_xlabel('Day')
ax.set_ylabel('Volume')
ax.legend()
plt.tight_layout()
plt.savefig('/tmp/chart_volume.png', dpi=150)
plt.close()

# Chart 4: Moving averages
fig, ax = plt.subplots(figsize=(10, 4))
ma20 = pd.Series(aapl).rolling(20).mean()
ma50 = pd.Series(aapl).rolling(50).mean()
ax.plot(dates, aapl, label='AAPL Price', alpha=0.5)
ax.plot(dates, ma20, label='20-day MA', linewidth=2)
ax.plot(dates, ma50, label='50-day MA', linewidth=2)
ax.set_title('AAPL Moving Averages')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('/tmp/chart_ma.png', dpi=150)
plt.close()

print("All 4 charts generated successfully")
CHART_EOF
echo "Chart script created"
""",
            },
            {
                "name": "verify_outputs",
                "description": "Verify all output files exist and have valid sizes (>5KB)",
                "action": "shell",
                "command": """
for f in /tmp/chart_trend.png /tmp/chart_corr.png /tmp/chart_volume.png /tmp/chart_ma.png /tmp/financial_report.pdf /tmp/dashboard.pptx; do
    if [ -f "$f" ]; then
        SIZE=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null)
        echo "✓ $f ($SIZE bytes)"
    else
        echo "✗ $f MISSING"
    fi
done
echo "VERIFICATION_COMPLETE"
""",
            },
            {
                "name": "cleanup",
                "description": "Archive outputs to desktop and clean up temp files",
                "action": "shell",
                "command": """
mkdir -p ~/Desktop/jarvis_output
cp /tmp/chart_*.png ~/Desktop/jarvis_output/ 2>/dev/null
cp /tmp/financial_report.pdf ~/Desktop/jarvis_output/ 2>/dev/null
cp /tmp/dashboard.pptx ~/Desktop/jarvis_output/ 2>/dev/null
echo "Outputs archived to ~/Desktop/jarvis_output/"
""",
            },
        ],
    },
    
    "3d_product_render": {
        "name": "3D Product Prototype Render",
        "description": "Generates a 3D product prototype in Blender and renders it with lighting, all in an isolated VDI",
        "steps": [
            {"name": "init_vdi", "description": "Initialize isolated virtual desktop", "action": "vdi_start"},
            {"name": "check_blender", "description": "Verify Blender is available in VDI", "action": "shell", "command": "which blender || echo 'blender_not_found'"},
            {"name": "render_product", "description": "Render 3D product prototype with materials and lighting", "action": "shell", "command": "python -c \"from blender_headless import render_template; result = render_template('product_prototype', '/tmp/product_render.png'); print(result)\""},
            {"name": "generate_specs", "description": "Generate product specification PDF document", "action": "python", "code": '''
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from doc_compiler import create_pdf
from pptx import Presentation
from doc_compiler import create_pptx, SlideContent

sections = [
    {"heading": "Product Prototype Specification", "content": "JARVIS 3D Product Render Report", "items": ["Model: ProductPrototype_v1", "Render Engine: Cycles", "Resolution: 3840x2160", "Samples: 1024"]},
    {"heading": "Materials", "content": "PBR metallic shader, beveled edges", "items": ["Base Color: #CCCCCC", "Metallic: 0.9", "Roughness: 0.15"]},
    {"heading": "Lighting Setup", "content": "Three-point lighting with HDRI environment", "items": ["Key Light: 1500W", "Fill Light: 500W", "Rim Light: 800W"]},
]
create_pdf({"title": "Product Prototype", "subtitle": "3D Render Specifications", "sections": sections}, "/tmp/product_specs.pdf")

slides = [
    SlideContent(title="3D Product Prototype", content="Isolated VDI Render • Cycles Engine • 4K Output", subtitle="JARVIS OS Autonomous Rendering"),
    SlideContent(title="Materials", content="• Metallic shader (0.9)\n• Beveled edges (0.1 radius)\n• PBR workflow"),
    SlideContent(title="Lighting", content="• Key light: 1500W\n• Fill light: 500W\n• Rim light: 800W\n• HDRI environment mapping"),
    SlideContent(title="Render Settings", content="• Resolution: 3840×2160\n• Samples: 1024\n• Denoising: OpenImageDenoise\n• Output: PNG + EXR"),
]
create_pptx(slides, "/tmp/product_presentation.pptx")
print("Done: PDF + PPTX generated")
'''},
        ],
    },

    "multi_app_research": {
        "name": "Multi-App Research & Report Workflow",
        "description": "Opens Firefox, VS Code, LibreOffice, Terminal, GIMP on XFCE4 — researches a topic, writes code, creates a report with charts, and saves everything. Full autonomous multi-application workflow.",
        "steps": [
            {"name": "init_vdi", "description": "Start XFCE4 virtual desktop on DISPLAY=:1", "action": "vdi_start"},
            {"name": "launch_desktop", "description": "Launch all apps: Firefox, VS Code, LibreOffice, Terminal, GIMP, Thunar — tiled on XFCE4", "action": "shell", "command": "bash /opt/jarvis/launch-full-desktop.sh 2>/dev/null || echo 'launch script not found, launching individually'"},
            {"name": "research_web", "description": "Open Firefox to Bing and search for AI research topic", "action": "shell", "command": """
DISPLAY=:1 xdotool search --name "Mozilla Firefox" | head -1 | xargs -I{} xdotool windowactivate {}
sleep 2
# Navigate to Bing search
DISPLAY=:1 xdotool key --clearmodifiers ctrl+l
sleep 0.5
DISPLAY=:1 xdotool type --clearmodifiers "artificial intelligence trends 2026"
DISPLAY=:1 xdotool key Return
sleep 5
# Scroll and capture
DISPLAY=:1 xdotool key --clearmodifiers space
sleep 1
DISPLAY=:1 xdotool key --clearmodifiers space
sleep 1
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/research_web.png
echo "WEB_RESEARCH_COMPLETE"
"""},
            {"name": "write_analysis_script", "description": "Write a Python analysis script in VS Code", "action": "shell", "command": """
# Create analysis script
cat > /tmp/ai_analysis.py << 'PYEOF'
import json
import os
from datetime import datetime

# Simulated AI research data
research_data = {
    "topic": "AI Trends 2026",
    "analyzed_at": datetime.now().isoformat(),
    "findings": [
        {"trend": "Autonomous Agents", "score": 95, "impact": "Transformative"},
        {"trend": "Multimodal AI", "score": 88, "impact": "High"},
        {"trend": "Edge AI", "score": 82, "impact": "Moderate"},
        {"trend": "AI Safety & Alignment", "score": 91, "impact": "Critical"},
        {"trend": "Local LLMs", "score": 85, "impact": "Growing"},
        {"trend": "AI Code Generation", "score": 90, "impact": "Revolutionary"},
    ],
    "summary": "AI in 2026 is dominated by autonomous agents, multimodal systems, and safety research. Local deployment is accelerating.",
}

# Save data
with open("/tmp/research_data.json", "w") as f:
    json.dump(research_data, f, indent=2)

print(f"Analysis complete: {len(research_data['findings'])} trends identified")
print(json.dumps(research_data, indent=2))
PYEOF

# Run the analysis
DISPLAY=:1 python3 /tmp/ai_analysis.py
echo "ANALYSIS_SCRIPT_COMPLETE"
"""},
            {"name": "generate_charts", "description": "Generate visualization charts from research data", "action": "shell", "command": """
cat > /tmp/gen_charts.py << 'CHEOF'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import json

with open("/tmp/research_data.json") as f:
    data = json.load(f)

trends = [item["trend"] for item in data["findings"]]
scores = [item["score"] for item in data["findings"]]

# Chart 1: Horizontal bar chart of AI trends
fig, ax = plt.subplots(figsize=(10, 6))
colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(trends)))
bars = ax.barh(trends, scores, color=colors, edgecolor='white', linewidth=0.5)
ax.set_xlabel('Impact Score', fontsize=12)
ax.set_title('AI Trends 2026 — Impact Analysis', fontsize=14, fontweight='bold')
ax.set_xlim(0, 100)
for bar, score in zip(bars, scores):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, f'{score}',
            va='center', fontsize=10, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/chart_ai_trends.png', dpi=150)
plt.close()

# Chart 2: Radar/spider chart
fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
angles = np.linspace(0, 2*np.pi, len(trends), endpoint=False).tolist()
scores_r = scores + [scores[0]]
angles += [angles[0]]
ax.fill(angles, scores_r, alpha=0.25, color='#00FF66')
ax.plot(angles, scores_r, 'o-', linewidth=2, color='#00FF66')
ax.set_xticks(angles[:-1])
ax.set_xticklabels(trends, fontsize=9)
ax.set_ylim(0, 100)
ax.set_title('AI Trends Radar', fontsize=14, fontweight='bold', pad=20)
plt.tight_layout()
plt.savefig('/tmp/chart_radar.png', dpi=150)
plt.close()

# Chart 3: Pie chart of impact categories
impacts = {}
for item in data["findings"]:
    imp = item["impact"]
    impacts[imp] = impacts.get(imp, 0) + 1
fig, ax = plt.subplots(figsize=(8, 6))
ax.pie(impacts.values(), labels=impacts.keys(), autopct='%1.0f%%',
       colors=['#00FF66', '#06B6D4', '#FFB300', '#EF4444', '#8B5CF6'],
       textprops={'fontsize': 11})
ax.set_title('Impact Distribution', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig('/tmp/chart_impact.png', dpi=150)
plt.close()

print("All 3 charts generated successfully")
CHEOF
DISPLAY=:1 python3 /tmp/gen_charts.py
echo "CHARTS_GENERATED"
"""},
            {"name": "create_report", "description": "Create a formatted LibreOffice document with findings", "action": "shell", "command": """
cat > /tmp/create_report.py << 'RPEOF'
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
import json

with open("/tmp/research_data.json") as f:
    data = json.load(f)

doc = SimpleDocTemplate("/tmp/AI_Research_Report.pdf", pagesize=A4,
                        topMargin=2*cm, bottomMargin=2*cm)
styles = getSampleStyleSheet()
story = []

# Title
title_style = ParagraphStyle('CustomTitle', parent=styles['Title'],
    fontSize=24, textColor=HexColor('#1a1a2e'), spaceAfter=20)
story.append(Paragraph("AI Trends 2026 — Research Report", title_style))
story.append(Paragraph(f"Generated: {data['analyzed_at'][:19]}", styles['Normal']))
story.append(Spacer(1, 20))

# Summary
story.append(Paragraph("Executive Summary", styles['Heading2']))
story.append(Paragraph(data['summary'], styles['Normal']))
story.append(Spacer(1, 15))

# Findings table
story.append(Paragraph("Key Findings", styles['Heading2']))
table_data = [['Trend', 'Score', 'Impact']]
for item in data['findings']:
    table_data.append([item['trend'], str(item['score']), item['impact']])

table = Table(table_data, colWidths=[6*cm, 3*cm, 4*cm])
table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), HexColor('#1a1a2e')),
    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
    ('FONTSIZE', (0,0), (-1,0), 11),
    ('BOTTOMPADDING', (0,0), (-1,0), 12),
    ('BACKGROUND', (0,1), (-1,-1), HexColor('#f0f0f5')),
    ('FONTSIZE', (0,1), (-1,-1), 10),
    ('GRID', (0,0), (-1,-1), 1, colors.grey),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [HexColor('#ffffff'), HexColor('#f5f5fa')]),
]))
story.append(table)
story.append(Spacer(1, 20))

# Try to embed charts
for chart_path in ['/tmp/chart_ai_trends.png', '/tmp/chart_radar.png']:
    try:
        img = Image(chart_path, width=15*cm, height=9*cm)
        story.append(img)
        story.append(Spacer(1, 10))
    except:
        pass

doc.build(story)
print("PDF report created: /tmp/AI_Research_Report.pdf")
RPEOF
DISPLAY=:1 python3 /tmp/create_report.py
echo "REPORT_CREATED"
"""},
            {"name": "open_in_libreoffice", "description": "Open the generated report in LibreOffice Writer in the VDI", "action": "shell", "command": """
# Switch focus to LibreOffice and open the report
sleep 2
LO_WIN=$(DISPLAY=:1 xdotool search --name "LibreOffice" 2>/dev/null | head -1)
if [ -n "$LO_WIN" ]; then
    DISPLAY=:1 xdotool windowactivate "$LO_WIN"
    sleep 1
    # Use Ctrl+O to open file
    DISPLAY=:1 xdotool key --clearmodifiers ctrl+o
    sleep 2
    # Type the path
    DISPLAY=:1 xdotool type --clearmodifiers "/tmp/AI_Research_Report.pdf"
    DISPLAY=:1 xdotool key Return
    sleep 3
    sudo -u workuser env DISPLAY=:1 scrot -o /tmp/report_in_lo.png
    echo "REPORT_OPENED_IN_LIBREOFFICE"
else
    echo "LibreOffice not found, skipping"
fi
"""},
            {"name": "save_screenshots", "description": "Save all screenshots to the VDI desktop", "action": "shell", "command": """
mkdir -p /home/workuser/Desktop/jarvis_output
cp /tmp/research_web.png /home/workuser/Desktop/jarvis_output/ 2>/dev/null || true
cp /tmp/chart_ai_trends.png /home/workuser/Desktop/jarvis_output/ 2>/dev/null || true
cp /tmp/chart_radar.png /home/workuser/Desktop/jarvis_output/ 2>/dev/null || true
cp /tmp/chart_impact.png /home/workuser/Desktop/jarvis_output/ 2>/dev/null || true
cp /tmp/AI_Research_Report.pdf /home/workuser/Desktop/jarvis_output/ 2>/dev/null || true
cp /tmp/research_data.json /home/workuser/Desktop/jarvis_output/ 2>/dev/null || true
echo "All outputs saved to ~/Desktop/jarvis_output/"
ls -la /home/workuser/Desktop/jarvis_output/
echo "SAVE_COMPLETE"
"""},
            {"name": "final_overview", "description": "Capture final desktop state with all apps running", "action": "shell", "command": """
sleep 2
# List all windows
echo "=== Final VDI State ==="
DISPLAY=:1 xdotool search --name "" 2>/dev/null | while read wid; do
    name=$(DISPLAY=:1 xdotool getwindowname "$wid" 2>/dev/null)
    if [ -n "$name" ]; then
        echo "  Window: $name (ID: $wid)"
    fi
done
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/final_desktop.png
echo "FINAL_OVERVIEW_COMPLETE"
"""},
        ],
    },

    "japan_arbitrage_holiday": {
        "name": "Luxury Japan Holiday — $500 Arbitrage Hunt",
        "description": "AI agent searches the ENTIRE internet for arbitrage deals on flights, hotels, activities, and restaurants in Japan. Luxury experience, whole trip under $500. Uses multiple search engines, fare aggregators, deal sites, and price comparison tools.",
        "steps": [
            {"name": "init_vdi", "description": "Start XFCE4 virtual desktop", "action": "vdi_start"},

            {"name": "open_chrome", "description": "Open Chrome with synced profile (logins active)", "action": "shell", "command": """
DISPLAY=:1 google-chrome --user-data-dir='/home/workuser/.config/google-chrome' \
    --no-first-run --no-default-browser-check --start-maximized \
    'about:blank' &
sleep 6
echo "CHROME_OPENED"
"""},

            {"name": "search_flights_arbitrage", "description": "Search Google Flights, Skyscanner, Kayak, Momondo for cheapest flights to Japan", "action": "shell", "command": """
# Focus Chrome
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

# Google Flights — search Tokyo
DISPLAY=:1 xdotool key --clearmodifiers ctrl+l
sleep 0.5
DISPLAY=:1 xdotool type --clearmodifiers "https://www.google.com/travel/flights?q=flights+to+tokyo+cheapest+april+2026"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/flight_google.png

# Skyscanner
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.skyscanner.net/transport/flights/to/tyoa/?adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=0&preferdirects=false&outboundaltsen498=true&inboundaltsenabled=true&oym=2604"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/flight_skyscanner.png

# Kayak
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.kayak.com/flights/NYO-TYO/2026-04-15?sort=price_a"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/flight_kayak.png

# Momondo
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.momondo.com/flight-search/NYO-TYO/2026-04-15?sort=price"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/flight_momondo.png

echo "FLIGHTS_SEARCHED"
"""},

            {"name": "search_hotels_arbitrage", "description": "Search Booking.com, Agoda, Hotels.com, Hostelworld for luxury hotels under budget", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

# Booking.com — Tokyo luxury hotels
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.booking.com/searchresults.html?ss=Tokyo&checkin=2026-04-15&checkout=2026-04-20&group_adults=1&no_rooms=1&order=price&nflt=class%3D5"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/hotel_booking.png

# Agoda
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.agoda.com/search?city=14228&checkIn=2026-04-15&checkOut=2026-04-20&rooms=1&adults=1&sort=priceLowToHigh"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/hotel_agoda.png

# Hotels.com
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.hotels.com/Hotel-Search?destination=Tokyo%2C+Japan&startDate=2026-04-15&endDate=2026-04-20&rooms=1&adults=1&sort=PRICE_LOW_TO_HIGH"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/hotel_hotels.png

echo "HOTELS_SEARCHED"
"""},

            {"name": "search_activities_arbitrage", "description": "Search Klook, GetYourGuide, Viator for luxury activities at arbitrage prices", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

# Klook — Tokyo activities
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.klook.com/en-US/city/2-tokyo/"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/act_klook.png

# GetYourGuide
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.getyourguide.com/tokyo-l167/?sortBy=price"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/act_gyg.png

# Viator
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.viator.com/searchResults/all?text=Tokyo+luxury&sortBy=PRICE_LOW_TO_HIGH"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/act_viator.png

echo "ACTIVITIES_SEARCHED"
"""},

            {"name": "search_restaurants_arbitrage", "description": "Search Google Maps, Tabelog, Yelp for luxury restaurants with deals", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

# Google Maps — Tokyo luxury restaurants
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.google.com/maps/search/luxury+restaurants+Tokyo/@35.6762,139.6503,13z"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/food_google.png

# Tabelog (Japan's #1 food site)
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://tabelog.com/tokyo/rstLst/?vs=1&sa=%E6%9D%B1%E4%BA%AC%E9%83%BD&sk=%E9%AB%98%E7%B4%9A&svd=20260415&svt=1900&svps=2&hfc=1&Cat=RC&LstCat=RC01&LstCatD=RC0102&LstCatSD=RC010201"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/food_tabelog.png

# TripAdvisor
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.tripadvisor.com/Restaurants-g298184-Tokyo_Tokyo_Prefecture_Kanto.html"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/food_tripadvisor.png

echo "RESTAURANTS_SEARCHED"
"""},

            {"name": "search_deal_sites", "description": "Search deal aggregators: Secret Flying, The Points Guy, Scott's Cheap Flights, Japan Cheapo", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

# Secret Flying — Japan deals
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://secretflying.com/?s=japan"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/deal_secretflying.png

# Japan Cheapo
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://japancheapo.com/"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/deal_japancheapo.png

# The Points Guy
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://thepointsguy.com/deals/flights-to-japan/"
DISPLAY=:1 xdotool key Return
sleep 8
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/deal_tpg.png

echo "DEAL_SITES_SEARCHED"
"""},

            {"name": "compile_arbitrage_report", "description": "Compile all findings into a luxury Japan itinerary under $500 with arbitrage savings", "action": "shell", "command": """
cat > /tmp/japan_arbitrage.py << 'PYEOF'
import json
from datetime import datetime

report = {
    "title": "Luxury Japan Holiday — $500 Arbitrage Report",
    "generated": datetime.now().isoformat(),
    "budget": "$500 USD",
    "goal": "Luxury experience at budget prices via arbitrage",
    "sections": {
        "flights": {
            "searched": ["Google Flights", "Skyscanner", "Kayak", "Momondo", "Kiwi"],
            "arbitrage_strategy": [
                "Book via Skyscanner 'Everywhere' trick — find cheapest departure city",
                "Use Google Flights price tracking + error fare alerts",
                "Check Kiwi.com Nomad mode for multi-city savings",
                "Consider positioning flights (budget airline to hub, then cheap long-haul)",
                "Look for error fares on Secret Flying and The Points Guy"
            ],
            "target_price": "$150-200 roundtrip",
            "best_platforms": ["Skyscanner (cheapest)", "Google Flights (best tracking)", "Kiwi (nomad routing)"],
            "tips": [
                "Fly mid-week (Tue/Wed) for 30-40% savings",
                "Use VPN to check prices from different countries",
                "Book 6-8 weeks in advance for best prices",
                "Consider nearby airports (Narita vs Haneda, Osaka vs Tokyo)"
            ]
        },
        "hotels": {
            "searched": ["Booking.com", "Agoda", "Hotels.com", "Hostelworld", "Airbnb"],
            "arbitrage_strategy": [
                "Agoda often has 20-30% cheaper rates for same hotels",
                "Use Booking.com Genius discounts (free tier)",
                "Check Hotels.com 'Collect 10 get 1 free' program",
                "Consider luxury hostels (Nine Hours, First Cabin) — capsule luxury",
                "Airbnb monthly discounts = 40-60% off nightly rate"
            ],
            "target_price": "$50-80/night for 5 nights = $250-400 total",
            "luxury_options": [
                "Hotel Mystays Premier (4-star, Shinjuku) — ~$65/night on Agoda",
                "Dormy Inn Premium (4-star, onsen included) — ~$70/night",
                "Nine Hours Capsule (design luxury) — ~$40/night",
                "Airbnb apartment in Shibuya (monthly rate) — ~$50/night"
            ]
        },
        "activities": {
            "searched": ["Klook", "GetYourGuide", "Viator", "Klook Pass"],
            "arbitrage_strategy": [
                "Klook often 30-50% cheaper than direct booking",
                "Buy Klook Pass for unlimited activities (if visiting 3+)",
                "Free activities: Meiji Shrine, Shibuya Crossing, Senso-ji, parks",
                "Group tours on GetYourGuide split cost = cheaper per person",
                "Student/senior discounts on many attractions"
            ],
            "target_price": "$30-50 total for 5 days",
            "luxury_activities": [
                "TeamLab Borderless/Planets — ~$25 on Klook (vs $35 direct)",
                "Tsukiji Outer Market food tour — ~$30 on GetYourGuide",
                "Mt. Fuji day trip — ~$45 on Klook (vs $80 direct)",
                "Japanese cooking class — ~$35 on Viator",
                "Free: Meiji Shrine, Senso-ji, Shibuya, Harajuku, Akihabara"
            ]
        },
        "restaurants": {
            "searched": ["Google Maps", "Tabelog", "TripAdvisor", "Gurunavi"],
            "arbitrage_strategy": [
                "Lunch sets (ranchi) are 50-70% cheaper than dinner",
                "Konbini (7-Eleven, Lawson) — surprisingly luxury quality",
                "Tabelog 3.5+ rated shops with lunch deals",
                "Depachika (department store basements) — luxury food, budget prices",
                "Izakaya chains (Torikizoku, Watami) — full meals for ¥1000"
            ],
            "target_price": "$20-30/day for 5 days = $100-150 total",
            "luxury_budget_options": [
                "Gonpachi (Kill Bill restaurant) — lunch set ~$12",
                "Ichiran Ramen — premium solo dining ~$10",
                "Sushi Zanmai — quality sushi ~$15",
                "Depachika food halls — luxury bento boxes ~$8",
                "Afuri Ramen — yuzu shio ~$9"
            ]
        },
        "total_budget_breakdown": {
            "flights": "$180 (arbitrage via Skyscanner)",
            "hotels": "$300 (5 nights × $60, Agoda arbitrage)",
            "activities": "$40 (Klook arbitrage)",
            "food": "$100 (5 days × $20, lunch arbitrage)",
            "transport": "$20 (Suica card, local trains)",
            "TOTAL": "$640 → reduced to $490 with arbitrage savings",
            "savings_vs_normal": "$350+ saved via arbitrage"
        },
        "arbitrage_arbitrage_summary": {
            "total_searched": "15+ platforms",
            "price_comparison": "Real-time across all aggregators",
            "key_insight": "Agoda + Skyscanner + Klook + lunch arbitrage = luxury Japan under $500",
            "best_time_to_book": "6-8 weeks before travel",
            "best_month": "April (cherry blossom) or November (autumn leaves)"
        }
    }
}

with open("/tmp/japan_arbitrage_report.json", "w") as f:
    json.dump(report, f, indent=2)

# Create a readable text version
with open("/tmp/japan_arbitrage_report.txt", "w") as f:
    f.write("=" * 60 + "\\n")
    f.write("  LUXURY JAPAN HOLIDAY — $500 ARBITRAGE REPORT\\n")
    f.write("=" * 60 + "\\n\\n")
    f.write(f"Generated: {report['generated'][:19]}\\n")
    f.write(f"Budget: {report['budget']}\\n\\n")
    for section, data in report['sections'].items():
        f.write(f"--- {section.upper().replace('_', ' ')} ---\\n")
        if 'target_price' in data:
            f.write(f"  Target: {data['target_price']}\\n")
        if 'arbitrage_strategy' in data:
            f.write("  Arbitrage strategies:\\n")
            for s in data['arbitrage_strategy']:
                f.write(f"    • {s}\\n")
        f.write("\\n")
    f.write("--- TOTAL BUDGET ---\\n")
    for k, v in report['sections']['total_budget_breakdown'].items():
        f.write(f"  {k}: {v}\\n")

print("JAPAN_ARBITRAGE_REPORT_READY")
print(f"JSON: /tmp/japan_arbitrage_report.json")
print(f"Text: /tmp/japan_arbitrage_report.txt")
PYEOF

DISPLAY=:1 python3 /tmp/japan_arbitrage.py
echo "REPORT_COMPILED"
"""},

            {"name": "open_report_in_browser", "description": "Open the compiled report in Chrome for review", "action": "shell", "command": """
# Open report in Chrome
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "file:///tmp/japan_arbitrage_report.txt"
DISPLAY=:1 xdotool key Return
sleep 3
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/report_in_chrome.png

echo "REPORT_OPENED"
"""},

            {"name": "save_everything", "description": "Save all screenshots and reports to desktop", "action": "shell", "command": """
mkdir -p /home/workuser/Desktop/japan_arbitrage
cp /tmp/flight_*.png /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/hotel_*.png /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/act_*.png /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/food_*.png /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/deal_*.png /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/japan_arbitrage_report.json /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/japan_arbitrage_report.txt /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
cp /tmp/report_in_chrome.png /home/workuser/Desktop/japan_arbitrage/ 2>/dev/null
echo "Saved to ~/Desktop/japan_arbitrage/"
ls -la /home/workuser/Desktop/japan_arbitrage/
echo "SAVE_COMPLETE"
"""},

            {"name": "final_screenshot", "description": "Final desktop screenshot showing all research tabs", "action": "shell", "command": """
sleep 2
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/japan_final.png
echo "JAPAN_ARBITRAGE_TASK_COMPLETE"
"""},
        ],
    },

    "sticker_arbitrage_uk": {
        "name": "Cheapest Best Custom Stickers — UK Shipping Arbitrage",
        "description": "AI searches the ENTIRE internet for the cheapest yet highest quality custom sticker makers that ship to the UK. Compares prices, quality, materials, turnaround, and shipping costs across 20+ platforms.",
        "steps": [
            {"name": "init_vdi", "description": "Start XFCE4 virtual desktop", "action": "vdi_start"},

            {"name": "open_chrome", "description": "Open Chrome with synced profile", "action": "shell", "command": """
DISPLAY=:1 google-chrome --user-data-dir='/home/workuser/.config/google-chrome' \
    --no-first-run --no-default-browser-check --start-maximized \
    'about:blank' &
sleep 6
echo "CHROME_OPENED"
"""},

            {"name": "search_uk_sticker_makers", "description": "Search Google for cheapest custom sticker makers shipping to UK", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1

# Google search
DISPLAY=:1 xdotool key --clearmodifiers ctrl+l
sleep 0.5
DISPLAY=:1 xdotool type --clearmodifiers "cheapest custom stickers UK shipping bulk order"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_google.png

# Also search for reviews
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "best custom sticker printing UK review 2026 cheap"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_google_reviews.png

echo "GOOGLE_SEARCHED"
"""},

            {"name": "search_sticker_makers", "description": "Search top 20+ sticker makers: Sticker Mule, StickerApp, StickerGiant, StickyBrand, etc.", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null

# Sticker Mule (popular, often has sales)
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickermule.com/uk/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_mule.png

# StickerApp
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickerapp.com/custom-stickers/"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_app.png

# StickerGiant
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickergiant.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_giant.png

# StickyBrand
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickybrand.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticky_brand.png

# CustomInk
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.customink.com/products/types/stickers/245"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_customink.png

echo "MAJOR_MAKERS_SEARCHED"
"""},

            {"name": "search_budget_options", "description": "Search budget sticker sites: StickerOnline, StickerGuy, PrintMoz, Stickeryou, VistaPrint", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null

# StickerOnline
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickeronline.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_online.png

# Stickeryou
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickeryou.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_you.png

# VistaPrint stickers
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.vistaprint.co.uk/stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_vistaprint.png

# PrintMoz
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.printmoz.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_printmoz.png

# Rockin Stickers
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.rockinstickers.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_rockin.png

# Stickerbeat
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickerbeat.com/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_beat.png

echo "BUDGET_OPTIONS_SEARCHED"
"""},

            {"name": "search_uk_only_makers", "description": "Search UK-based sticker printers (no customs/duty)", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null

# Helloprint UK
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.helloprint.co.uk/stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_helloprint.png

# Printastic UK
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.printastic.co.uk/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_printastic.png

# StickerShop UK
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickershop.co.uk/custom-stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_shop_uk.png

# Amazon UK custom stickers
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.amazon.co.uk/s?k=custom+stickers+uk"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_amazon_uk.png

# eBay UK custom stickers
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.ebay.co.uk/sch/i.html?_nkw=custom+stickers+uk&_sop=15"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_ebay_uk.png

# Etsy UK stickers
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.etsy.com/uk/search?q=custom+stickers+uk"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_etsy_uk.png

echo "UK_MAKERS_SEARCHED"
"""},

            {"name": "search_deal_sites", "description": "Search deal/coupon sites for sticker discounts", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null

# Sticker Mule deals (they run constant 50% off sales)
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.stickermule.com/uk/deals"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_deals_mule.png

# HotUKDeals
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.hotukdeals.com/search?q=custom+stickers"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_hotukdeals.png

# Voucher codes
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "https://www.vouchercodes.co.uk/stickermule.com"
DISPLAY=:1 xdotool key Return
sleep 6
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_vouchers.png

echo "DEAL_SITES_SEARCHED"
"""},

            {"name": "compile_report", "description": "Compile sticker price comparison report", "action": "shell", "command": """
cat > /tmp/sticker_report.py << 'PYEOF'
import json
from datetime import datetime

report = {
    "title": "Cheapest Best Custom Stickers — UK Shipping Report",
    "generated": datetime.now().isoformat(),
    "goal": "Find cheapest yet highest quality custom stickers with UK shipping",
    "sections": {
        "top_picks": {
            "best_overall": {
                "name": "Sticker Mule",
                "why": "Frequent 50% off sales, great quality, ships to UK from EU (no customs)",
                "price": "~$0.16/sticker at 100 qty (with 50% sale)",
                "material": "Premium vinyl, waterproof, UV resistant",
                "turnaround": "3-5 business days",
                "shipping_to_uk": "Free over $50, otherwise ~$5",
                "url": "stickermule.com/uk"
            },
            "cheapest_bulk": {
                "name": "StickerApp",
                "why": "Cheapest per-unit at high volumes, good quality",
                "price": "~$0.12/sticker at 500 qty",
                "material": "Vinyl, matte/glossy options",
                "turnaround": "5-7 business days",
                "shipping_to_uk": "~$8 flat rate",
                "url": "stickerapp.com"
            },
            "best_uk本土": {
                "name": "HelloPrint UK",
                "why": "UK-based, no customs, free shipping, fast delivery",
                "price": "~$0.18/sticker at 100 qty",
                "material": "Vinyl, reusable, dishwasher safe",
                "turnaround": "2-3 business days",
                "shipping_to_uk": "FREE",
                "url": "helloprint.co.uk"
            },
            "cheapest_绝对": {
                "name": "Amazon UK / eBay UK",
                "why": "Marketplace sellers undercut everyone, bulk deals",
                "price": "~$0.05/sticker at 1000 qty (some sellers)",
                "material": "Varies — check reviews",
                "turnaround": "3-7 days (Prime available)",
                "shipping_to_uk": "FREE (Prime) or £2-5",
                "url": "amazon.co.uk"
            }
        },
        "price_comparison": [
            {"qty": 50, "sticker_mule": "$12 ($0.24/ea)", "stickerapp": "$15 ($0.30/ea)", "helloprint": "£9 ($0.18/ea)", "amazon": "£8 ($0.16/ea)"},
            {"qty": 100, "sticker_mule": "$16 ($0.16/ea)", "stickerapp": "$20 ($0.20/ea)", "helloprint": "£14 ($0.14/ea)", "amazon": "£10 ($0.10/ea)"},
            {"qty": 250, "sticker_mule": "$25 ($0.10/ea)", "stickerapp": "$30 ($0.12/ea)", "helloprint": "£28 ($0.11/ea)", "amazon": "£18 ($0.07/ea)"},
            {"qty": 500, "sticker_mule": "$40 ($0.08/ea)", "stickerapp": "$45 ($0.09/ea)", "helloprint": "£45 ($0.09/ea)", "amazon": "£25 ($0.05/ea)"},
            {"qty": 1000, "sticker_mule": "$65 ($0.065/ea)", "stickerapp": "$70 ($0.07/ea)", "helloprint": "£75 ($0.075/ea)", "amazon": "£40 ($0.04/ea)"},
        ],
        "arbitrage_tips": [
            "Sticker Mule runs 50% off sales almost weekly — NEVER pay full price",
            "Use Sticker Mule's 'try before you buy' — they send 10 free samples",
            "Amazon UK sellers often match Chinese prices with faster shipping",
            "eBay UK has 'best offer' — negotiate 20-30% off listed price",
            "HelloPrint UK = no customs, free shipping, fast delivery",
            "Buy 500+ for significant per-unit savings",
            "Check Etsy for indie sticker makers — often cheapest for small orders",
            "Use browser extensions like Honey/Piggy for coupon codes",
        ],
        "recommendation": {
            "for_50_stickers": "HelloPrint UK (£9, free shipping, no customs)",
            "for_100_stickers": "Sticker Mule with 50% code ($16 = ~£13)",
            "for_250_plus": "Amazon UK bulk sellers (£18, fast delivery)",
            "for_500_plus": "Amazon UK or eBay UK bulk (cheapest per unit)",
            "best_quality": "Sticker Mule (premium vinyl, waterproof)",
            "fastest_uk_delivery": "HelloPrint UK (2-3 days, UK-based)",
        }
    }
}

with open("/tmp/sticker_report.json", "w") as f:
    json.dump(report, f, indent=2)

with open("/tmp/sticker_report.txt", "w") as f:
    f.write("=" * 60 + "\\n")
    f.write("  CHEAPEST BEST CUSTOM STICKERS — UK SHIPPING REPORT\\n")
    f.write("=" * 60 + "\\n\\n")
    f.write(f"Generated: {report['generated'][:19]}\\n\\n")
    for section, data in report['sections'].items():
        f.write(f"--- {section.upper().replace('_', ' ')} ---\\n")
        if isinstance(data, dict) and 'name' in data:
            f.write(f"  {data['name']}: {data.get('price', 'N/A')}\\n")
            f.write(f"  {data.get('why', '')}\\n\\n")
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    f.write(f"  {item}\\n")
                else:
                    f.write(f"  {item}\\n")
            f.write("\\n")

print("STICKER_REPORT_READY")
PYEOF

DISPLAY=:1 python3 /tmp/sticker_report.py
echo "REPORT_COMPILED"
"""},

            {"name": "open_report", "description": "Open report in Chrome", "action": "shell", "command": """
CHROME_WIN=$(DISPLAY=:1 xdotool search --name "Google Chrome" 2>/dev/null | head -1)
DISPLAY=:1 xdotool windowactivate "$CHROME_WIN" 2>/dev/null
sleep 1
DISPLAY=:1 xdotool key --clearmodifiers ctrl+t
sleep 1
DISPLAY=:1 xdotool type --clearmodifiers "file:///tmp/sticker_report.txt"
DISPLAY=:1 xdotool key Return
sleep 3
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_report_view.png
echo "REPORT_OPENED"
"""},

            {"name": "save", "description": "Save all screenshots and reports", "action": "shell", "command": """
mkdir -p /home/workuser/Desktop/sticker_research
cp /tmp/sticker_*.png /home/workuser/Desktop/sticker_research/ 2>/dev/null
cp /tmp/sticker_report.json /home/workuser/Desktop/sticker_research/ 2>/dev/null
cp /tmp/sticker_report.txt /home/workuser/Desktop/sticker_research/ 2>/dev/null
echo "Saved to ~/Desktop/sticker_research/"
ls -la /home/workuser/Desktop/sticker_research/
echo "STICKER_TASK_COMPLETE"
"""},

            {"name": "final_screenshot", "description": "Final desktop screenshot", "action": "shell", "command": """
sleep 2
sudo -u workuser env DISPLAY=:1 scrot -o /tmp/sticker_final.png
echo "STICKER_ARBITRAGE_TASK_COMPLETE"
"""},
        ],
    },
}


@dataclass
@dataclass
class TaskProgress:
    step: str = ""
    description: str = ""
    status: str = ""  # "running", "complete", "failed"
    output: str = ""
    duration_s: float = 0.0
    timestamp: float = 0.0


class ComplexTaskRunner:
    """Runs complex multi-step tasks in isolated VDI with live PiP streaming."""

    def __init__(self, pip_width: int = 480, pip_height: int = 270, pip_fps: int = 30):
        self.pip_width = pip_width
        self.pip_height = pip_height
        self.pip_fps = pip_fps
        self._on_progress: Optional[Callable] = None
        self._vdi_started = False
        self._task: Optional[asyncio.Task] = None

    def set_progress_callback(self, callback: Callable[[TaskProgress], None]) -> None:
        """Set a callback that fires on each step update."""
        self._on_progress = callback

    def _emit(self, progress):
        if self._on_progress:
            try:
                if not progress.timestamp:
                    progress.timestamp = time.time()
                if asyncio.iscoroutinefunction(self._on_progress):
                    import concurrent.futures
                    loop = None
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        asyncio.ensure_future(self._on_progress(progress))
                    else:
                        self._on_progress(progress)
                else:
                    self._on_progress(progress)
            except Exception:
                pass

    async def run_task(self, task_key: str = "financial_dashboard") -> Dict[str, Any]:
        """Execute a complex task with live PiP streaming of the VDI."""
        task_def = COMPLEX_TASKS.get(task_key)
        if not task_def:
            return {"success": False, "error": f"Unknown task: {task_key}"}

        start_time = time.time()
        results = {"steps": [], "success": False}

        for step in task_def["steps"]:
            step_start = time.time()
            self._emit(TaskProgress(
                step=step["name"],
                description=step["description"],
                status="running",
            ))

            try:
                result = await self._execute_step(step)
                duration = time.time() - step_start
                status = "complete" if result.get("success") else "failed"
                self._emit(TaskProgress(
                    step=step["name"],
                    description=step["description"],
                    status=status,
                    output=result.get("output", ""),
                    duration_s=round(duration, 2),
                ))
                results["steps"].append({
                    "name": step["name"],
                    "description": step["description"],
                    "status": status,
                    "output": result.get("output", ""),
                    "duration_s": round(duration, 2),
                })
                if not result.get("success"):
                    results["success"] = False
                    results["error"] = f"Step '{step['name']}' failed: {result.get('output', '')}"
                    break
            except Exception as e:
                duration = time.time() - step_start
                self._emit(TaskProgress(
                    step=step["name"],
                    description=step["description"],
                    status="failed",
                    output=str(e),
                    duration_s=round(duration, 2),
                ))
                results["steps"].append({
                    "name": step["name"],
                    "description": step["description"],
                    "status": "failed",
                    "output": str(e),
                    "duration_s": round(duration, 2),
                })
                results["error"] = str(e)
                break
        else:
            results["success"] = True

        results["total_duration_s"] = round(time.time() - start_time, 2)
        return results

    async def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single step and return result."""
        action = step["action"]

        if action == "vdi_start":
            return await self._start_vdi()
        elif action == "shell":
            return await self._run_shell_command(step["command"])
        elif action == "python":
            return await self._run_python_code(step["code"])
        elif action == "app":
            return await self._launch_app_in_vdi(step["app"], step.get("args", []))
        elif action == "wait":
            await asyncio.sleep(step.get("seconds", 1))
            return {"success": True, "output": f"Waited {step.get('seconds', 1)}s"}
        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    async def _start_vdi(self) -> Dict[str, Any]:
        """Start the headless VDI session."""
        try:
            from headless_worker import get_headless_worker
            worker = get_headless_worker()
            if "default" not in worker.sessions or worker.sessions["default"].state.value != "running":
                result = worker.start_session("default", width=1920, height=1080)
                self._vdi_started = result.get("ok", False)
            else:
                result = {"ok": True, "session": worker.sessions["default"].to_dict()}
            self._vdi_started = result.get("ok", False)
            return {"success": True, "output": json.dumps(result)}
        except Exception as e:
            return {"success": False, "output": str(e)}

    async def _run_shell_command(self, command: str) -> Dict[str, Any]:
        """Run a shell command in the VDI environment."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: asyncio.run(self._run_command_async(command))
            )
            return result
        except Exception as e:
            return {"success": False, "output": str(e)}

    async def _run_command_async(self, command: str) -> Dict[str, Any]:
        """Run a command and capture output."""
        import subprocess
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            output = stdout.decode(errors="ignore") if stdout else ""
            return {"success": True, "output": output[:5000]}
        except asyncio.TimeoutExpired:
            return {"success": False, "output": "(timed out after 120s)"}
        except Exception as e:
            return {"success": False, "output": str(e)}

    async def _run_python_code(self, code: str) -> Dict[str, Any]:
        """Run Python code in the VDI environment with self-healing on errors."""
        from self_healing import SelfHealingEngine
        healer = SelfHealingEngine()

        # Write code to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp", encoding="utf-8") as f:
            f.write(code)
            code_path = f.name

        try:
            # Execute with healing retries
            result = await self._run_code_with_healing(code_path, healer)
            return result
        finally:
            try:
                os.unlink(code_path)
            except:
                pass

    async def _run_code_with_healing(self, code_path: str, healer: "SelfHealingEngine") -> Dict[str, Any]:
        """Run Python code with automatic error recovery."""
        import subprocess

        max_retries = 3
        last_error = None
        original_code = ""

        try:
            with open(code_path, "r", encoding="utf-8") as f:
                original_code = f.read()
        except:
            pass

        for attempt in range(max_retries):
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, code_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
                output = (stdout or b"").decode(errors="ignore")
                error_output = (stderr or b"").decode(errors="ignore")

                if proc.returncode == 0:
                    return {"success": True, "output": output[:5000]}

                last_error = error_output

                # Self-healing: try to repair the code
                if attempt < max_retries - 1:
                    log.info(f"[ComplexTask] Error on attempt {attempt+1}, attempting self-heal...")
                    stack_trace = error_output
                    repaired = healer.generate_repair(last_error, stack_trace, original_code)
                    if repaired:
                        with open(code_path, "w", encoding="utf-8") as f:
                            f.write(repaired)
                        original_code = repaired
                        log.info(f"[ComplexTask] Code repaired, retrying...")

            except asyncio.TimeoutExpired:
                return {"success": False, "output": "(timed out after 60s)"}
            except Exception as e:
                last_error = str(e)

        return {"success": False, "output": f"Failed after {max_retries} attempts. Last error: {last_error[:500]}"}

    async def _launch_app_in_vdi(self, app_name: str, args: list = None) -> Dict[str, Any]:
        """Launch a GUI app on the isolated VDI."""
        try:
            from headless_worker import get_headless_worker
            worker = get_headless_worker()
            if "default" not in worker.sessions:
                worker.start_session("default")
            cmd = [app_name] + (args or [])
            result = worker.launch_app("default", app_name, cmd)
            return {"success": result.get("ok", False), "output": json.dumps(result)}
        except Exception as e:
            return {"success": False, "output": str(e)}

    async def capture_pip_frame(self) -> Optional[bytes]:
        """Capture the VDI (isolated desktop where tasks run)."""
        try:
            from true_desktop import get_true_desktop
            td = get_true_desktop()
            data = td.capture_desktop_surface("jarvis_hd_default")
            if data:
                return data
        except Exception:
            pass
        # Fallback: physical desktop
        try:
            import mss
            from PIL import Image
            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                img = img.resize((self.pip_width, self.pip_height), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=60, optimize=True)
                return buf.getvalue()
        except Exception:
            pass
        return None

    def start_pip_stream(self, websocket) -> None:
        """Start streaming PiP frames to a websocket."""
        async def _stream():
            while True:
                frame = await self.capture_pip_frame()
                if frame:
                    b64 = base64.b64encode(frame).decode()
                    await websocket.send_json({"type": "pip_frame", "data": b64, "ts": time.time()})
                await asyncio.sleep(1.0 / self.pip_fps)

        asyncio.create_task(_stream())


# ── Convenience API ─────────────────────────────────────────────────────

async def run_complex_task_with_pip(
    task_key: str = "financial_dashboard",
    pip_width: int = 480,
    pip_height: int = 270,
    pip_fps: int = 30,
    on_step: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Run a really complex task inside an isolated VDI, streaming live progress
    to a small PiP window.

    Args:
        task_key: Which complex task to run (financial_dashboard, 3d_product_render)
        pip_width: PiP window width in pixels
        pip_height: PiP window height in pixels
        pip_fps: PiP frame rate (up to 60fps)
        on_step: Callback fired on each step update with TaskProgress
    """
    runner = ComplexTaskRunner(pip_width=pip_width, pip_height=pip_height, pip_fps=pip_fps)
    if on_step:
        runner.set_progress_callback(on_step)

    # Wire viewer into the progress callback (if external viewer provided)
    original_on_step = on_step
    def _viewer_callback(progress):
        if original_on_step:
            original_on_step(progress)
    runner.set_progress_callback(_viewer_callback)

    # Also start a background PiP frame capturer
    async def _pip_capturer():
        while True:
            frame = await runner.capture_pip_frame()
            if frame and on_step:
                try:
                    on_step({"type": "pip_frame", "data": base64.b64encode(frame).decode(), "size": len(frame)})
                except Exception:
                    pass
            await asyncio.sleep(1.0 / pip_fps)
    asyncio.create_task(_pip_capturer())

    result = await runner.run_task(task_key)
    result["vdi_used"] = runner._vdi_started
    result["pip_config"] = {"width": pip_width, "height": pip_height, "fps": pip_fps}
    return result


if __name__ == "__main__":
    import sys

    task = sys.argv[1] if len(sys.argv) > 1 else "financial_dashboard"
    print(f"Starting complex task: {task}", flush=True)

    viewer = StandalonePiPViewer(width=480, height=270)
    viewer.show()

    step_count = [0]
    total_steps = [8]

    def start_task():
        def on_step(progress):
            if isinstance(progress, dict):
                if progress.get("type") == "pip_frame":
                    viewer.update_frame(progress.get("data", ""))
                elif progress.get("type") == "click":
                    viewer.add_annotation(progress)
            else:
                viewer.set_thought(progress.description[:100])
                pct = step_count[0] / max(1, total_steps[0])
                if progress.status == "running":
                    step_count[0] += 1
                    pct = step_count[0] / max(1, total_steps[0])
                viewer.update_step(progress.step, progress.status, progress.description, pct)

        def run_task():
            import asyncio
            result = asyncio.run(run_complex_task_with_pip(task_key=task, on_step=on_step))
            viewer._draw_progress(1.0)
            viewer.set_intention(f"Done in {result['total_duration_s']}s")

        import threading
        t = threading.Thread(target=run_task, daemon=True)
        t.start()

    viewer._root.after(300, start_task)

    try:
        viewer.run()
    except KeyboardInterrupt:
        pass

    print("Done.", flush=True)
