"""Onyx Calculator — a self-built tool by OnyxKraken.

A fully functional calculator with arithmetic, history, and keyboard support.
Built by Onyx as part of its self-sustaining tool ecosystem.
"""

import tkinter as tk
from tkinter import font as tkfont


class OnyxCalculator:
    """Compact, dark-themed calculator with full keyboard support."""

    BG = "#0a0e18"
    DISPLAY_BG = "#0c1220"
    DISPLAY_FG = "#00d4ff"
    BTN_BG = "#121a2a"
    BTN_FG = "#c0d0e0"
    BTN_OP_BG = "#0a2838"
    BTN_OP_FG = "#00d4ff"
    BTN_EQ_BG = "#00557a"
    BTN_EQ_FG = "#ffffff"
    BTN_HOVER = "#1a2a3a"
    HISTORY_FG = "#445566"

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Onyx Calculator")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)
        self.root.geometry("320x480")

        self._expression = ""
        self._history = []

        self._build_ui()
        self._bind_keys()

    def _build_ui(self):
        # History label
        self._history_label = tk.Label(
            self.root, text="", bg=self.BG, fg=self.HISTORY_FG,
            font=("Consolas", 9), anchor="e",
        )
        self._history_label.pack(fill="x", padx=12, pady=(10, 0))

        # Display
        self._display_var = tk.StringVar(value="0")
        display = tk.Label(
            self.root, textvariable=self._display_var,
            bg=self.DISPLAY_BG, fg=self.DISPLAY_FG,
            font=("Consolas", 28, "bold"), anchor="e",
            padx=16, pady=12, relief="flat",
        )
        display.pack(fill="x", padx=8, pady=(4, 8))

        # Button grid
        buttons = [
            ["C", "⌫", "%", "÷"],
            ["7", "8", "9", "×"],
            ["4", "5", "6", "−"],
            ["1", "2", "3", "+"],
            ["±", "0", ".", "="],
        ]

        btn_frame = tk.Frame(self.root, bg=self.BG)
        btn_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        for row_idx, row in enumerate(buttons):
            btn_frame.rowconfigure(row_idx, weight=1)
            for col_idx, label in enumerate(row):
                btn_frame.columnconfigure(col_idx, weight=1)

                if label == "=":
                    bg, fg = self.BTN_EQ_BG, self.BTN_EQ_FG
                elif label in ("÷", "×", "−", "+", "%"):
                    bg, fg = self.BTN_OP_BG, self.BTN_OP_FG
                elif label in ("C", "⌫"):
                    bg, fg = self.BTN_OP_BG, "#ff6666"
                else:
                    bg, fg = self.BTN_BG, self.BTN_FG

                btn = tk.Label(
                    btn_frame, text=label, bg=bg, fg=fg,
                    font=("Consolas", 16, "bold"), cursor="hand2",
                    relief="flat", borderwidth=0,
                )
                btn.grid(row=row_idx, column=col_idx, sticky="nsew", padx=2, pady=2)
                btn.bind("<Button-1>", lambda e, l=label: self._on_button(l))
                btn.bind("<Enter>", lambda e, b=btn: b.configure(bg=self.BTN_HOVER))
                btn.bind("<Leave>", lambda e, b=btn, orig=bg: b.configure(bg=orig))

    def _bind_keys(self):
        self.root.bind("<Key>", self._on_key)
        self.root.bind("<Return>", lambda e: self._on_button("="))
        self.root.bind("<BackSpace>", lambda e: self._on_button("⌫"))
        self.root.bind("<Escape>", lambda e: self._on_button("C"))

    def _on_key(self, event):
        ch = event.char
        if ch in "0123456789.":
            self._on_button(ch)
        elif ch in ("+",):
            self._on_button("+")
        elif ch in ("-",):
            self._on_button("−")
        elif ch in ("*",):
            self._on_button("×")
        elif ch in ("/",):
            self._on_button("÷")
        elif ch in ("%",):
            self._on_button("%")

    def _on_button(self, label: str):
        if label == "C":
            self._expression = ""
            self._display_var.set("0")
        elif label == "⌫":
            self._expression = self._expression[:-1]
            self._display_var.set(self._expression or "0")
        elif label == "±":
            if self._expression and self._expression[0] == "-":
                self._expression = self._expression[1:]
            elif self._expression:
                self._expression = "-" + self._expression
            self._display_var.set(self._expression or "0")
        elif label == "=":
            self._evaluate()
        else:
            # Map display symbols to Python operators
            char_map = {"÷": "/", "×": "*", "−": "-", "+": "+", "%": "%"}
            ch = char_map.get(label, label)
            self._expression += ch
            self._display_var.set(self._expression)

    def _evaluate(self):
        if not self._expression:
            return
        expr_display = self._expression
        try:
            # Safe eval: only allow numbers and basic operators
            allowed = set("0123456789.+-*/%()")
            sanitized = self._expression.replace(" ", "")
            if not all(c in allowed for c in sanitized):
                self._display_var.set("Error")
                return
            result = eval(sanitized)
            # Format: remove trailing .0 for integers
            if isinstance(result, float) and result == int(result):
                result = int(result)
            result_str = str(result)
            self._history.append(f"{expr_display} = {result_str}")
            self._history_label.configure(text=f"{expr_display} =")
            self._expression = result_str
            self._display_var.set(result_str)
        except ZeroDivisionError:
            self._display_var.set("÷ by 0")
            self._expression = ""
        except Exception:
            self._display_var.set("Error")
            self._expression = ""

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    OnyxCalculator().run()
