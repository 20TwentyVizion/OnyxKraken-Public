"""Onyx Timer — Countdown timer with lap tracking and alarm."""
import tkinter as tk
import winsound
import time

BG = "#0a0e16"
FG = "#c8d8e0"
ACCENT = "#00e5ff"
DIM = "#1a2a3a"
ENTRY_BG = "#0c1525"

class TimerApp:
    def __init__(self, root):
        self.root = root
        root.title("Onyx Timer")
        root.configure(bg=BG)
        root.geometry("400x520")
        root.resizable(False, False)

        self.running = False
        self.remaining = 0
        self.laps = []

        # Title
        tk.Label(root, text="ONYX TIMER", font=("Consolas", 14, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(18, 6))

        # Time display
        self.display = tk.Label(root, text="00:00.0", font=("Consolas", 48, "bold"),
                                bg=BG, fg=ACCENT)
        self.display.pack(pady=10)

        # Input frame
        inp = tk.Frame(root, bg=BG)
        inp.pack(pady=6)
        tk.Label(inp, text="Min:", bg=BG, fg=FG, font=("Consolas", 11)).pack(side="left", padx=4)
        self.min_var = tk.StringVar(value="5")
        tk.Entry(inp, textvariable=self.min_var, width=4, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, font=("Consolas", 14), justify="center",
                 relief="flat").pack(side="left", padx=2)
        tk.Label(inp, text="Sec:", bg=BG, fg=FG, font=("Consolas", 11)).pack(side="left", padx=4)
        self.sec_var = tk.StringVar(value="0")
        tk.Entry(inp, textvariable=self.sec_var, width=4, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, font=("Consolas", 14), justify="center",
                 relief="flat").pack(side="left", padx=2)

        # Buttons
        btn_frame = tk.Frame(root, bg=BG)
        btn_frame.pack(pady=10)
        self.start_btn = self._btn(btn_frame, "▶ Start", self.toggle_start)
        self.start_btn.pack(side="left", padx=6)
        self._btn(btn_frame, "⟳ Reset", self.reset).pack(side="left", padx=6)
        self._btn(btn_frame, "Lap", self.lap).pack(side="left", padx=6)

        # Lap list
        tk.Label(root, text="Laps", bg=BG, fg=DIM, font=("Consolas", 10)).pack(anchor="w", padx=20)
        self.lap_list = tk.Listbox(root, bg=ENTRY_BG, fg=FG, font=("Consolas", 10),
                                   selectbackground=ACCENT, relief="flat", height=8)
        self.lap_list.pack(fill="x", padx=20, pady=4)

        root.bind("<space>", lambda e: self.toggle_start())
        root.bind("r", lambda e: self.reset())

    def _btn(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=DIM, fg=FG, font=("Consolas", 11, "bold"),
                     padx=14, pady=6, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg="#1a3a4a"))
        b.bind("<Leave>", lambda e: b.configure(bg=DIM))
        return b

    def toggle_start(self):
        if self.running:
            self.running = False
            self.start_btn.configure(text="▶ Start")
        else:
            if self.remaining <= 0:
                try:
                    m = int(self.min_var.get() or 0)
                    s = int(self.sec_var.get() or 0)
                except ValueError:
                    m, s = 5, 0
                self.remaining = m * 60 + s
            if self.remaining > 0:
                self.running = True
                self.start_btn.configure(text="⏸ Pause")
                self._tick()

    def reset(self):
        self.running = False
        self.remaining = 0
        self.start_btn.configure(text="▶ Start")
        self.display.configure(text="00:00.0")

    def lap(self):
        if self.remaining > 0:
            self.laps.append(self.remaining)
            m, s = divmod(self.remaining, 60)
            self.lap_list.insert(0, f"  Lap {len(self.laps):>2}:  {m:02d}:{s:04.1f}")

    def _tick(self):
        if not self.running:
            return
        self.remaining -= 0.1
        if self.remaining <= 0:
            self.remaining = 0
            self.running = False
            self.start_btn.configure(text="▶ Start")
            self.display.configure(text="00:00.0", fg="#ff4466")
            try:
                winsound.Beep(1000, 500)
                winsound.Beep(1200, 500)
            except Exception:
                pass
            self.root.after(2000, lambda: self.display.configure(fg=ACCENT))
            return
        m, s = divmod(self.remaining, 60)
        self.display.configure(text=f"{int(m):02d}:{s:04.1f}")
        self.root.after(100, self._tick)

if __name__ == "__main__":
    root = tk.Tk()
    TimerApp(root)
    root.mainloop()
