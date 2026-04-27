"""Onyx Sticky Notes — Floating note windows with color coding and auto-save."""
import tkinter as tk
import json
import os

BG = "#0a0e16"
FG = "#c8d8e0"
ACCENT = "#00e5ff"
DIM = "#1a2a3a"
ENTRY_BG = "#0c1525"
NOTE_COLORS = ["#1a2a3a", "#2a1a1a", "#1a2a1a", "#1a1a2a", "#2a2a1a", "#1a2a2a"]
DATA_FILE = os.path.join(os.path.dirname(__file__), "sticky_data.json")

class StickyApp:
    def __init__(self, root):
        self.root = root
        root.title("Onyx Sticky Notes")
        root.configure(bg=BG)
        root.geometry("340x480")
        self.notes = []
        self.windows = {}

        tk.Label(root, text="ONYX NOTES", font=("Consolas", 14, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(14, 6))

        btn_f = tk.Frame(root, bg=BG)
        btn_f.pack(fill="x", padx=16, pady=6)
        self._btn(btn_f, "+ New Note", self.new_note).pack(side="left")
        self._btn(btn_f, "Save All", self.save_notes).pack(side="right")

        self.list_frame = tk.Frame(root, bg=BG)
        self.list_frame.pack(fill="both", expand=True, padx=16, pady=6)

        self.load_notes()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _btn(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=DIM, fg=FG, font=("Consolas", 10, "bold"),
                     padx=10, pady=4, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg="#1a3a4a"))
        b.bind("<Leave>", lambda e: b.configure(bg=DIM))
        return b

    def new_note(self, title="New Note", body="", color=0):
        note = {"title": title, "body": body, "color": color}
        self.notes.append(note)
        self.refresh_list()
        self.open_note(len(self.notes) - 1)
        self.save_notes()

    def open_note(self, idx):
        if idx in self.windows:
            self.windows[idx].lift()
            return
        note = self.notes[idx]
        win = tk.Toplevel(self.root)
        win.title(note["title"])
        win.geometry("280x320")
        bg_c = NOTE_COLORS[note["color"] % len(NOTE_COLORS)]
        win.configure(bg=bg_c)
        win.attributes("-topmost", True)

        title_e = tk.Entry(win, bg=bg_c, fg=ACCENT, font=("Consolas", 12, "bold"),
                           insertbackground=ACCENT, relief="flat")
        title_e.insert(0, note["title"])
        title_e.pack(fill="x", padx=8, pady=(8, 4))

        body_t = tk.Text(win, bg=bg_c, fg=FG, font=("Consolas", 10),
                         insertbackground=FG, relief="flat", wrap="word")
        body_t.insert("1.0", note["body"])
        body_t.pack(fill="both", expand=True, padx=8, pady=4)

        color_f = tk.Frame(win, bg=bg_c)
        color_f.pack(fill="x", padx=8, pady=4)
        for ci, c in enumerate(NOTE_COLORS):
            cb = tk.Label(color_f, text="●", bg=bg_c, fg=c, font=("Consolas", 14), cursor="hand2")
            cb.pack(side="left", padx=2)
            cb.bind("<Button-1>", lambda e, i=idx, cc=ci: self._change_color(i, cc))

        def on_close_note():
            note["title"] = title_e.get()
            note["body"] = body_t.get("1.0", "end-1c")
            self.save_notes()
            self.refresh_list()
            del self.windows[idx]
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close_note)
        self.windows[idx] = win

    def _change_color(self, idx, color):
        self.notes[idx]["color"] = color
        if idx in self.windows:
            self.windows[idx].destroy()
            del self.windows[idx]
            self.open_note(idx)
        self.save_notes()

    def delete_note(self, idx):
        if idx in self.windows:
            self.windows[idx].destroy()
            del self.windows[idx]
        self.notes.pop(idx)
        self.refresh_list()
        self.save_notes()

    def refresh_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        for i, note in enumerate(self.notes):
            f = tk.Frame(self.list_frame, bg=ENTRY_BG, pady=4, padx=8)
            f.pack(fill="x", pady=2)
            c = NOTE_COLORS[note["color"] % len(NOTE_COLORS)]
            tk.Label(f, text="■", bg=ENTRY_BG, fg=c, font=("Consolas", 10)).pack(side="left")
            lbl = tk.Label(f, text=note["title"][:30], bg=ENTRY_BG, fg=FG,
                           font=("Consolas", 10), cursor="hand2", anchor="w")
            lbl.pack(side="left", fill="x", expand=True, padx=6)
            lbl.bind("<Button-1>", lambda e, idx=i: self.open_note(idx))
            db = tk.Label(f, text="✕", bg=ENTRY_BG, fg="#ff4466",
                          font=("Consolas", 10), cursor="hand2")
            db.pack(side="right")
            db.bind("<Button-1>", lambda e, idx=i: self.delete_note(idx))

    def save_notes(self):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self.notes, f, indent=2)
        except Exception:
            pass

    def load_notes(self):
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE) as f:
                    self.notes = json.load(f)
        except Exception:
            self.notes = []
        self.refresh_list()

    def on_close(self):
        for idx in list(self.windows):
            self.windows[idx].destroy()
        self.save_notes()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    StickyApp(root)
    root.mainloop()
