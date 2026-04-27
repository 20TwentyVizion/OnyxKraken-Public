"""Onyx JSON Viewer — Tree view of JSON files with expand/collapse."""
import tkinter as tk
from tkinter import ttk, filedialog
import json

BG = "#0a0e16"
FG = "#c8d8e0"
ACCENT = "#00e5ff"
DIM = "#1a2a3a"
ENTRY_BG = "#0c1525"

class JsonViewerApp:
    def __init__(self, root):
        self.root = root
        root.title("Onyx JSON Viewer")
        root.configure(bg=BG)
        root.geometry("560x520")

        tk.Label(root, text="ONYX JSON VIEWER", font=("Consolas", 14, "bold"),
                 bg=BG, fg=ACCENT).pack(pady=(12, 4))

        btn_f = tk.Frame(root, bg=BG)
        btn_f.pack(fill="x", padx=12, pady=4)
        self._btn(btn_f, "Open JSON", self.open_file).pack(side="left", padx=4)
        self._btn(btn_f, "Paste JSON", self.paste_json).pack(side="left", padx=4)
        self._btn(btn_f, "Collapse All", self.collapse_all).pack(side="right", padx=4)
        self._btn(btn_f, "Expand All", self.expand_all).pack(side="right", padx=4)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=ENTRY_BG, foreground=FG,
                         fieldbackground=ENTRY_BG, font=("Consolas", 10))
        style.configure("Treeview.Heading", background=DIM, foreground=ACCENT,
                         font=("Consolas", 10, "bold"))
        style.map("Treeview", background=[("selected", DIM)])

        tree_f = tk.Frame(root, bg=BG)
        tree_f.pack(fill="both", expand=True, padx=12, pady=6)
        self.tree = ttk.Treeview(tree_f, columns=("value", "type"), show="tree headings")
        self.tree.heading("#0", text="Key")
        self.tree.heading("value", text="Value")
        self.tree.heading("type", text="Type")
        self.tree.column("#0", width=200)
        self.tree.column("value", width=250)
        self.tree.column("type", width=60)
        sb = ttk.Scrollbar(tree_f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        self.status = tk.Label(root, text="Open a JSON file or paste JSON", bg=BG, fg=DIM,
                               font=("Consolas", 9))
        self.status.pack(pady=4)

    def _btn(self, parent, text, cmd):
        b = tk.Label(parent, text=text, bg=DIM, fg=FG, font=("Consolas", 9, "bold"),
                     padx=8, pady=3, cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg="#1a3a4a"))
        b.bind("<Leave>", lambda e: b.configure(bg=DIM))
        return b

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._populate(data)
                self.status.configure(text=f"Loaded: {path.split('/')[-1].split(chr(92))[-1]}")
            except Exception as e:
                self.status.configure(text=f"Error: {e}")

    def paste_json(self):
        try:
            text = self.root.clipboard_get()
            data = json.loads(text)
            self._populate(data)
            self.status.configure(text="Loaded from clipboard")
        except Exception as e:
            self.status.configure(text=f"Invalid JSON: {e}")

    def _populate(self, data):
        self.tree.delete(*self.tree.get_children())
        self._add_node("", "root", data)

    def _add_node(self, parent, key, value):
        if isinstance(value, dict):
            node = self.tree.insert(parent, "end", text=str(key),
                                     values=(f"{{{len(value)} keys}}", "object"))
            for k, v in value.items():
                self._add_node(node, k, v)
        elif isinstance(value, list):
            node = self.tree.insert(parent, "end", text=str(key),
                                     values=(f"[{len(value)} items]", "array"))
            for i, v in enumerate(value):
                self._add_node(node, f"[{i}]", v)
        elif isinstance(value, str):
            self.tree.insert(parent, "end", text=str(key),
                              values=(value[:80], "string"))
        elif isinstance(value, bool):
            self.tree.insert(parent, "end", text=str(key),
                              values=(str(value).lower(), "bool"))
        elif isinstance(value, (int, float)):
            self.tree.insert(parent, "end", text=str(key),
                              values=(str(value), "number"))
        elif value is None:
            self.tree.insert(parent, "end", text=str(key),
                              values=("null", "null"))

    def expand_all(self):
        for item in self._all_items():
            self.tree.item(item, open=True)

    def collapse_all(self):
        for item in self._all_items():
            self.tree.item(item, open=False)

    def _all_items(self):
        items = []
        stack = list(self.tree.get_children())
        while stack:
            item = stack.pop()
            items.append(item)
            stack.extend(self.tree.get_children(item))
        return items

if __name__ == "__main__":
    root = tk.Tk()
    JsonViewerApp(root)
    root.mainloop()
