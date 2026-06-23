"""
Persistent notification window for macOS.
Shows a floating, always-on-top window that appears centre-screen,
stays visible until dismissed, and can be dragged or closed.

Usage:
  python notification_window.py "Your reminder message here"
  python notification_window.py "Title|Body text here"
"""

import sys
import tkinter as tk
from tkinter import font as tkfont

def show_notification(message: str):
    title = "J.A.R.V.I.S."
    body = message
    if "|" in message:
        parts = message.split("|", 1)
        title = parts[0].strip()
        body = parts[1].strip()

    root = tk.Tk()
    root.title(title)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.configure(bg="#1a1a2e")

    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w, win_h = 420, 200

    x = (screen_w - win_w) // 2
    y = (screen_h - win_h) // 2
    root.geometry(f"{win_w}x{win_h}+{x}+{y}")

    def start_move(event):
        root._drag_x = event.x
        root._drag_y = event.y

    def do_move(event):
        dx = event.x - root._drag_x
        dy = event.y - root._drag_y
        root.geometry(f"+{root.winfo_x()+dx}+{root.winfo_y()+dy}")

    def close_win(event=None):
        root.destroy()

    root.bind("<Button-1>", start_move)
    root.bind("<B1-Motion>", do_move)

    # Title bar
    title_bar = tk.Frame(root, bg="#16213e", height=32)
    title_bar.pack(fill="x")
    title_bar.pack_propagate(False)

    tk.Label(title_bar, text=f"  {title}", bg="#16213e", fg="#e94560",
             font=("Helvetica", 13, "bold"), anchor="w").pack(side="left", fill="x", expand=True)

    close_btn = tk.Label(title_bar, text=" ✕ ", bg="#16213e", fg="#aaa",
                         font=("Helvetica", 12), cursor="hand2")
    close_btn.pack(side="right", padx=4)
    close_btn.bind("<Button-1>", lambda e: close_win())
    close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#fff"))
    close_btn.bind("<Leave>", lambda e: close_btn.configure(fg="#aaa"))

    # Body
    body_frame = tk.Frame(root, bg="#1a1a2e")
    body_frame.pack(fill="both", expand=True, padx=16, pady=(10, 12))

    msg_label = tk.Label(body_frame, text=body, bg="#1a1a2e", fg="#e0e0e0",
                         font=("Helvetica", 12), wraplength=380, justify="left")
    msg_label.pack(anchor="w", fill="both", expand=True)

    # Dismiss button
    btn_frame = tk.Frame(root, bg="#1a1a2e")
    btn_frame.pack(fill="x", pady=(0, 10))

    dismiss_btn = tk.Button(btn_frame, text="  Dismiss  ", bg="#e94560", fg="#fff",
                            font=("Helvetica", 10, "bold"), relief="flat", cursor="hand2",
                            activebackground="#c7364f", activeforeground="#fff",
                            command=close_win)
    dismiss_btn.pack(side="right", padx=16)

    # Escape key to dismiss
    root.bind("<Escape>", close_win)

    root.mainloop()


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hello from J.A.R.V.I.S."
    show_notification(msg)
