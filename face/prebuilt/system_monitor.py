"""Onyx System Monitor — Live CPU, RAM, and disk usage with graphs."""
import tkinter as tk
import subprocess
import re

BG = "#0a0e16"
FG = "#c8d8e0"
ACCENT = "#00e5ff"
DIM = "#1a2a3a"

class SystemMonitorApp:
    def __init__(self, root):
        self.root = root
        root.title("Onyx System Monitor")
        root.configure(bg=BG)
        root.geometry("400x440")
        root.resizable(False, False)

        self.cpu_history = [0] * 60
        self.ram_history = [0] * 60

        tk.Label(root, text="ONYX SYSTEM MONITOR", font=("Consolas", 14, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(12, 6))

        # CPU
        self.cpu_lbl = tk.Label(root, text="CPU: —%", font=("Consolas", 12, "bold"),
                                bg=BG, fg=ACCENT)
        self.cpu_lbl.pack()
        self.cpu_canvas = tk.Canvas(root, width=360, height=80, bg="#0c1220",
                                    highlightthickness=1, highlightbackground=DIM)
        self.cpu_canvas.pack(pady=4)

        # RAM
        self.ram_lbl = tk.Label(root, text="RAM: —%", font=("Consolas", 12, "bold"),
                                bg=BG, fg="#44ff88")
        self.ram_lbl.pack(pady=(8, 0))
        self.ram_canvas = tk.Canvas(root, width=360, height=80, bg="#0c1220",
                                    highlightthickness=1, highlightbackground=DIM)
        self.ram_canvas.pack(pady=4)

        # Disk bar
        self.disk_lbl = tk.Label(root, text="Disk: —%", font=("Consolas", 12, "bold"),
                                 bg=BG, fg="#ffaa00")
        self.disk_lbl.pack(pady=(8, 0))
        self.disk_canvas = tk.Canvas(root, width=360, height=24, bg=DIM,
                                     highlightthickness=0)
        self.disk_canvas.pack(pady=4)
        self.disk_bar = self.disk_canvas.create_rectangle(0, 0, 0, 24, fill="#ffaa00")

        # Info
        self.info_lbl = tk.Label(root, text="", font=("Consolas", 9), bg=BG, fg=DIM)
        self.info_lbl.pack(pady=8)

        self._update()

    def _get_stats(self):
        cpu = ram = disk = 0
        try:
            # Use wmic for CPU
            out = subprocess.check_output(
                "wmic cpu get loadpercentage /value", shell=True,
                timeout=5, stderr=subprocess.DEVNULL).decode()
            m = re.search(r'LoadPercentage=(\d+)', out)
            if m:
                cpu = int(m.group(1))
        except Exception:
            pass
        try:
            # Use wmic for RAM
            out = subprocess.check_output(
                "wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /value",
                shell=True, timeout=5, stderr=subprocess.DEVNULL).decode()
            free = total = 0
            m1 = re.search(r'FreePhysicalMemory=(\d+)', out)
            m2 = re.search(r'TotalVisibleMemorySize=(\d+)', out)
            if m1 and m2:
                free = int(m1.group(1))
                total = int(m2.group(1))
                ram = int((1 - free / total) * 100) if total else 0
        except Exception:
            pass
        try:
            import shutil
            usage = shutil.disk_usage("C:\\")
            disk = int(usage.used / usage.total * 100)
        except Exception:
            pass
        return cpu, ram, disk

    def _draw_graph(self, canvas, history, color):
        canvas.delete("graph")
        w, h = 360, 80
        if not history:
            return
        n = len(history)
        for i in range(1, n):
            x1 = (i - 1) * w / (n - 1)
            x2 = i * w / (n - 1)
            y1 = h - (history[i - 1] / 100) * h
            y2 = h - (history[i] / 100) * h
            canvas.create_line(x1, y1, x2, y2, fill=color, width=2, tags="graph")

    def _update(self):
        cpu, ram, disk = self._get_stats()

        self.cpu_history.append(cpu)
        self.cpu_history = self.cpu_history[-60:]
        self.ram_history.append(ram)
        self.ram_history = self.ram_history[-60:]

        self.cpu_lbl.configure(text=f"CPU: {cpu}%")
        self.ram_lbl.configure(text=f"RAM: {ram}%")
        self.disk_lbl.configure(text=f"Disk: {disk}%")

        self._draw_graph(self.cpu_canvas, self.cpu_history, ACCENT)
        self._draw_graph(self.ram_canvas, self.ram_history, "#44ff88")
        self.disk_canvas.coords(self.disk_bar, 0, 0, 360 * disk / 100, 24)

        self.root.after(2000, self._update)

if __name__ == "__main__":
    root = tk.Tk()
    SystemMonitorApp(root)
    root.mainloop()
