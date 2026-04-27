"""Onyx Notepad — a self-built tool by OnyxKraken.

A fully functional text editor with file operations, search, and keyboard shortcuts.
Built by Onyx as part of its self-sustaining tool ecosystem.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox


class OnyxNotepad:
    """Dark-themed text editor with file I/O and search."""

    BG = "#0a0e18"
    TEXT_BG = "#0c1220"
    TEXT_FG = "#c0d0e0"
    MENU_BG = "#0a1525"
    MENU_FG = "#8899aa"
    STATUS_BG = "#060a12"
    STATUS_FG = "#445566"
    ACCENT = "#00d4ff"
    SELECTION_BG = "#0a3050"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Onyx Notepad — Untitled")
        self.root.configure(bg=self.BG)
        self.root.geometry("700x500")

        self._file_path = None
        self._modified = False

        self._build_menu()
        self._build_editor()
        self._build_status_bar()
        self._bind_keys()

    def _build_menu(self):
        menubar = tk.Menu(self.root, bg=self.MENU_BG, fg=self.MENU_FG,
                          activebackground="#1a2a3a", activeforeground=self.ACCENT,
                          borderwidth=0, relief="flat")

        file_menu = tk.Menu(menubar, tearoff=0, bg=self.MENU_BG, fg=self.MENU_FG,
                            activebackground="#1a2a3a", activeforeground=self.ACCENT)
        file_menu.add_command(label="New         Ctrl+N", command=self._new_file)
        file_menu.add_command(label="Open        Ctrl+O", command=self._open_file)
        file_menu.add_command(label="Save        Ctrl+S", command=self._save_file)
        file_menu.add_command(label="Save As     Ctrl+Shift+S", command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0, bg=self.MENU_BG, fg=self.MENU_FG,
                            activebackground="#1a2a3a", activeforeground=self.ACCENT)
        edit_menu.add_command(label="Find        Ctrl+F", command=self._show_find)
        edit_menu.add_command(label="Select All  Ctrl+A",
                              command=lambda: self._text.tag_add("sel", "1.0", "end"))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        self.root.config(menu=menubar)

    def _build_editor(self):
        frame = tk.Frame(self.root, bg=self.BG)
        frame.pack(fill="both", expand=True, padx=4, pady=(4, 0))

        scrollbar = tk.Scrollbar(frame, orient="vertical",
                                 bg=self.BG, troughcolor=self.BG)
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            frame, bg=self.TEXT_BG, fg=self.TEXT_FG,
            font=("Consolas", 11), wrap="word",
            insertbackground=self.ACCENT, selectbackground=self.SELECTION_BG,
            relief="flat", borderwidth=0, padx=12, pady=8,
            undo=True, maxundo=-1,
            yscrollcommand=scrollbar.set,
        )
        self._text.pack(fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        self._text.bind("<<Modified>>", self._on_modified)

    def _build_status_bar(self):
        self._status = tk.Label(
            self.root, text="Ready", bg=self.STATUS_BG, fg=self.STATUS_FG,
            font=("Consolas", 9), anchor="w", padx=8,
        )
        self._status.pack(fill="x", side="bottom")

    def _bind_keys(self):
        self.root.bind("<Control-n>", lambda e: self._new_file())
        self.root.bind("<Control-o>", lambda e: self._open_file())
        self.root.bind("<Control-s>", lambda e: self._save_file())
        self.root.bind("<Control-Shift-S>", lambda e: self._save_as())
        self.root.bind("<Control-f>", lambda e: self._show_find())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_modified(self, event=None):
        if self._text.edit_modified():
            self._modified = True
            title = self._file_path or "Untitled"
            self.root.title(f"Onyx Notepad — *{os.path.basename(title)}")
            self._text.edit_modified(False)

    def _update_status(self, msg: str):
        self._status.configure(text=msg)

    def _new_file(self):
        if self._modified and not self._confirm_discard():
            return
        self._text.delete("1.0", "end")
        self._file_path = None
        self._modified = False
        self.root.title("Onyx Notepad — Untitled")
        self._update_status("New file")

    def _open_file(self):
        if self._modified and not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._text.delete("1.0", "end")
            self._text.insert("1.0", content)
            self._file_path = path
            self._modified = False
            self._text.edit_modified(False)
            self.root.title(f"Onyx Notepad — {os.path.basename(path)}")
            self._update_status(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def _save_file(self):
        if self._file_path:
            self._write_file(self._file_path)
        else:
            self._save_as()

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._write_file(path)

    def _write_file(self, path: str):
        try:
            content = self._text.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._file_path = path
            self._modified = False
            self._text.edit_modified(False)
            self.root.title(f"Onyx Notepad — {os.path.basename(path)}")
            self._update_status(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _show_find(self):
        find_win = tk.Toplevel(self.root)
        find_win.title("Find")
        find_win.configure(bg=self.BG)
        find_win.geometry("300x60")
        find_win.transient(self.root)

        tk.Label(find_win, text="Find:", bg=self.BG, fg=self.TEXT_FG,
                 font=("Consolas", 10)).pack(side="left", padx=(8, 4), pady=8)
        entry = tk.Entry(find_win, bg=self.TEXT_BG, fg=self.TEXT_FG,
                         font=("Consolas", 10), insertbackground=self.ACCENT,
                         relief="flat")
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=8)
        entry.focus_set()

        def _find():
            query = entry.get()
            self._text.tag_remove("found", "1.0", "end")
            if not query:
                return
            idx = "1.0"
            while True:
                idx = self._text.search(query, idx, nocase=True, stopindex="end")
                if not idx:
                    break
                end = f"{idx}+{len(query)}c"
                self._text.tag_add("found", idx, end)
                idx = end
            self._text.tag_configure("found", background="#0a4060", foreground=self.ACCENT)

        entry.bind("<Return>", lambda e: _find())
        tk.Button(find_win, text="Find", command=_find,
                  bg=self.MENU_BG, fg=self.ACCENT, relief="flat",
                  font=("Consolas", 9)).pack(side="right", padx=8, pady=8)

    def _confirm_discard(self) -> bool:
        return messagebox.askyesno(
            "Unsaved Changes",
            "You have unsaved changes. Discard them?")

    def _on_close(self):
        if self._modified:
            if not self._confirm_discard():
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    OnyxNotepad().run()
