"""Onyx To-Do List — Task manager with priorities and JSON persistence."""
import tkinter as tk
from tkinter import messagebox
import json
import os

BG = "#0a0e16"
FG = "#c8d8e0"
ACCENT = "#00e5ff"
DIM = "#1a2a3a"
ENTRY_BG = "#0c1525"
PRIORITY_COLORS = {"high": "#ff4466", "medium": "#ffaa00", "low": "#44ff88"}
DATA_FILE = os.path.join(os.path.dirname(__file__), "todo_data.json")

class TodoApp:
    def __init__(self, root):
        self.root = root
        root.title("Onyx To-Do List")
        root.configure(bg=BG)
        root.geometry("420x560")
        self.tasks = []

        tk.Label(root, text="ONYX TO-DO", font=("Consolas", 14, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(14, 6))

        # Add task
        add_f = tk.Frame(root, bg=BG)
        add_f.pack(fill="x", padx=16, pady=6)
        self.entry = tk.Entry(add_f, bg=ENTRY_BG, fg=FG, insertbackground=FG,
                              font=("Consolas", 11), relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.entry.bind("<Return>", lambda e: self.add_task())

        self.pri_var = tk.StringVar(value="medium")
        for p in ("high", "medium", "low"):
            tk.Radiobutton(add_f, text=p[0].upper(), variable=self.pri_var, value=p,
                           bg=BG, fg=PRIORITY_COLORS[p], selectcolor=BG,
                           activebackground=BG, activeforeground=PRIORITY_COLORS[p],
                           font=("Consolas", 9, "bold")).pack(side="left", padx=2)

        self._btn(add_f, "+", self.add_task).pack(side="left", padx=(6, 0))

        # Task list
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.task_frame = tk.Frame(self.canvas, bg=BG)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True, padx=16, pady=6)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.task_frame, anchor="nw")
        self.task_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        # Status
        self.status = tk.Label(root, text="", bg=BG, fg=DIM, font=("Consolas", 9))
        self.status.pack(pady=4)

        self.load_tasks()
        root.bind("<Delete>", lambda e: self.delete_checked())

    def _btn(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=DIM, fg=FG, font=("Consolas", 11, "bold"),
                     padx=10, pady=3, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg="#1a3a4a"))
        b.bind("<Leave>", lambda e: b.configure(bg=DIM))
        return b

    def add_task(self):
        text = self.entry.get().strip()
        if not text:
            return
        task = {"text": text, "priority": self.pri_var.get(), "done": False}
        self.tasks.append(task)
        self.entry.delete(0, "end")
        self.refresh()
        self.save_tasks()

    def toggle_task(self, idx):
        if 0 <= idx < len(self.tasks):
            self.tasks[idx]["done"] = not self.tasks[idx]["done"]
            self.refresh()
            self.save_tasks()

    def delete_task(self, idx):
        if 0 <= idx < len(self.tasks):
            self.tasks.pop(idx)
            self.refresh()
            self.save_tasks()

    def delete_checked(self):
        self.tasks = [t for t in self.tasks if not t["done"]]
        self.refresh()
        self.save_tasks()

    def refresh(self):
        for w in self.task_frame.winfo_children():
            w.destroy()
        order = {"high": 0, "medium": 1, "low": 2}
        sorted_tasks = sorted(enumerate(self.tasks), key=lambda x: (x[1]["done"], order.get(x[1]["priority"], 1)))
        for orig_idx, task in sorted_tasks:
            f = tk.Frame(self.task_frame, bg=ENTRY_BG, pady=4, padx=8)
            f.pack(fill="x", pady=2)
            pc = PRIORITY_COLORS.get(task["priority"], FG)
            tk.Label(f, text="●", bg=ENTRY_BG, fg=pc, font=("Consolas", 10)).pack(side="left")
            txt = task["text"]
            fg_c = DIM if task["done"] else FG
            deco = "overstrike" if task["done"] else ""
            lbl = tk.Label(f, text=txt, bg=ENTRY_BG, fg=fg_c,
                           font=("Consolas", 10, deco), anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=6)
            check_txt = "✓" if task["done"] else "○"
            cb = tk.Label(f, text=check_txt, bg=ENTRY_BG, fg=ACCENT,
                          font=("Consolas", 12), cursor="hand2")
            cb.pack(side="right", padx=4)
            idx = orig_idx
            cb.bind("<Button-1>", lambda e, i=idx: self.toggle_task(i))
            db = tk.Label(f, text="✕", bg=ENTRY_BG, fg="#ff4466",
                          font=("Consolas", 10), cursor="hand2")
            db.pack(side="right")
            db.bind("<Button-1>", lambda e, i=idx: self.delete_task(i))

        done = sum(1 for t in self.tasks if t["done"])
        self.status.configure(text=f"{done}/{len(self.tasks)} completed")

    def save_tasks(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self.tasks, f, indent=2)
        except Exception:
            pass

    def load_tasks(self):
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    self.tasks = json.load(f)
        except Exception:
            self.tasks = []
        self.refresh()

if __name__ == "__main__":
    root = tk.Tk()
    TodoApp(root)
    root.mainloop()
