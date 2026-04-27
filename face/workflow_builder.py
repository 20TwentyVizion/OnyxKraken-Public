"""List-based workflow builder — simple UI for creating and running workflows.

A Toplevel window with:
  - Left panel: node palette (grouped by extension)
  - Center: workflow step list (ordered nodes with input config)
  - Right: execution log / progress
  - Bottom: preset browser, save/load, run/stop

This is the "simple" workflow editor. The visual node canvas is separate.
"""

from __future__ import annotations

import json
import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme constants (match face/app.py dark theme)
# ---------------------------------------------------------------------------
BG = "#0e1117"
PANEL_BG = "#161b22"
CARD_BG = "#1c2333"
ACCENT = "#7c3aed"
TEXT = "#c9d1d9"
TEXT_DIM = "#6a7a8a"
BORDER = "#30363d"
BTN_BG = "#21262d"
BTN_FG = "#c9d1d9"
SUCCESS = "#2ea043"
ERROR = "#f85149"
EVERA_CLR = "#e67e22"
SE_CLR = "#9b59b6"
JE_CLR = "#3498db"
ONYX_CLR = "#7c3aed"

EXT_COLORS = {
    "onyx": ONYX_CLR,
    "evera": EVERA_CLR,
    "smartengine": SE_CLR,
    "justedit": JE_CLR,
}


class WorkflowBuilderWindow(tk.Toplevel):
    """List-based workflow builder window."""

    def __init__(self, master, on_close: Optional[Callable] = None):
        super().__init__(master)
        self.title("Onyx \u2014 Workflow Builder")
        self.configure(bg=BG)
        self.geometry("1100x700")
        self.minsize(900, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_close_cb = on_close

        self._manager = None
        self._workflow_steps: List[Dict] = []  # ordered list of node configs
        self._step_widgets: List[tk.Frame] = []
        self._running = False
        self._run_thread: Optional[threading.Thread] = None
        self._log_lines: List[str] = []

        self._build_ui()
        self._load_palette()

    # ------------------------------------------------------------------
    # Lazy manager access
    # ------------------------------------------------------------------

    def _get_manager(self):
        if self._manager is None:
            from core.nodes.workflow_manager import get_workflow_manager
            self._manager = get_workflow_manager(
                progress_callback=self._on_progress,
            )
            self._manager.initialize()
        return self._manager

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self, bg=PANEL_BG, height=40)
        top.pack(fill="x", padx=0, pady=0)
        top.pack_propagate(False)

        tk.Label(
            top, text="\u26a1 Workflow Builder", bg=PANEL_BG, fg=ACCENT,
            font=("Consolas", 12, "bold"),
        ).pack(side="left", padx=12, pady=8)

        # Right-side buttons in top bar
        btn_frame = tk.Frame(top, bg=PANEL_BG)
        btn_frame.pack(side="right", padx=8)

        for text, cmd in [
            ("\u25b6 Run", self._run_workflow),
            ("\u23f9 Stop", self._stop_workflow),
            ("\U0001f4be Save", self._save_workflow),
            ("\U0001f4c2 Load", self._load_workflow),
            ("\U0001f5d1 Clear", self._clear_workflow),
            ("\U0001f3a8 Canvas", self._open_canvas),
        ]:
            b = tk.Button(
                btn_frame, text=text, bg=BTN_BG, fg=BTN_FG,
                font=("Consolas", 8), relief="flat", bd=0,
                activebackground=ACCENT, activeforeground="#fff",
                cursor="hand2", command=cmd,
            )
            b.pack(side="left", padx=2, pady=4)

        # Main body: 3 columns
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Left: node palette
        self._build_palette(body)

        # Center: step list
        self._build_step_list(body)

        # Right: execution log
        self._build_log(body)

        # Bottom: preset bar
        self._build_preset_bar()

    def _build_palette(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG, width=220)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 2))
        frame.grid_propagate(False)

        tk.Label(
            frame, text="Node Palette", bg=PANEL_BG, fg=TEXT,
            font=("Consolas", 9, "bold"),
        ).pack(fill="x", padx=8, pady=(8, 4))

        # Search
        self._palette_search_var = tk.StringVar()
        self._palette_search_var.trace_add("write", lambda *_: self._filter_palette())
        search = tk.Entry(
            frame, textvariable=self._palette_search_var,
            bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
            font=("Consolas", 8), relief="flat", bd=0,
        )
        search.pack(fill="x", padx=8, pady=(0, 4))

        # Scrollable palette
        canvas = tk.Canvas(frame, bg=PANEL_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self._palette_inner = tk.Frame(canvas, bg=PANEL_BG)

        self._palette_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._palette_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=4)
        self._palette_canvas = canvas

    def _build_step_list(self, parent):
        frame = tk.Frame(parent, bg=BG)
        frame.grid(row=0, column=1, sticky="nsew", padx=2)

        tk.Label(
            frame, text="Workflow Steps", bg=BG, fg=TEXT,
            font=("Consolas", 9, "bold"),
        ).pack(fill="x", padx=8, pady=(8, 4))

        # Scrollable step list
        canvas = tk.Canvas(frame, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self._steps_inner = tk.Frame(canvas, bg=BG)

        self._steps_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._steps_inner, anchor="nw",
                             tags="inner")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>",
                     lambda e: canvas.itemconfig("inner", width=e.width))

        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True, padx=4)
        self._steps_canvas = canvas

        # Empty state
        self._empty_label = tk.Label(
            self._steps_inner,
            text="No steps yet.\nClick a node in the palette to add it,\nor load a preset below.",
            bg=BG, fg=TEXT_DIM, font=("Consolas", 9), justify="center",
        )
        self._empty_label.pack(pady=40)

    def _build_log(self, parent):
        frame = tk.Frame(parent, bg=PANEL_BG, width=260)
        frame.grid(row=0, column=2, sticky="nsew", padx=(2, 0))
        frame.grid_propagate(False)

        tk.Label(
            frame, text="Execution Log", bg=PANEL_BG, fg=TEXT,
            font=("Consolas", 9, "bold"),
        ).pack(fill="x", padx=8, pady=(8, 4))

        self._log_text = tk.Text(
            frame, bg=CARD_BG, fg=TEXT_DIM, font=("Consolas", 7),
            relief="flat", bd=0, wrap="word", state="disabled",
            highlightthickness=0,
        )
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            frame, textvariable=self._status_var, bg=PANEL_BG, fg=TEXT_DIM,
            font=("Consolas", 7), anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 4))

    def _build_preset_bar(self):
        bar = tk.Frame(self, bg=PANEL_BG, height=50)
        bar.pack(fill="x", padx=0, pady=0)
        bar.pack_propagate(False)

        tk.Label(
            bar, text="Presets:", bg=PANEL_BG, fg=TEXT_DIM,
            font=("Consolas", 8),
        ).pack(side="left", padx=(12, 4), pady=8)

        self._preset_frame = tk.Frame(bar, bg=PANEL_BG)
        self._preset_frame.pack(side="left", fill="x", expand=True, padx=4)

    # ------------------------------------------------------------------
    # Palette population
    # ------------------------------------------------------------------

    def _load_palette(self):
        """Populate the node palette from the registry."""
        try:
            mgr = self._get_manager()
            self._all_nodes = mgr.list_by_extension()
            self._render_palette(self._all_nodes)
            self._load_presets()
        except Exception as e:
            logger.error("Failed to load palette: %s", e)
            self._log(f"Error loading palette: {e}")

    def _render_palette(self, grouped: Dict[str, List[Dict]]):
        """Render node palette grouped by extension."""
        for w in self._palette_inner.winfo_children():
            w.destroy()

        for ext_name, nodes in grouped.items():
            color = EXT_COLORS.get(ext_name, TEXT_DIM)

            # Extension header
            hdr = tk.Frame(self._palette_inner, bg=PANEL_BG)
            hdr.pack(fill="x", padx=4, pady=(8, 2))
            tk.Label(
                hdr, text=f"\u25cf {ext_name.upper()}", bg=PANEL_BG, fg=color,
                font=("Consolas", 8, "bold"),
            ).pack(side="left")
            tk.Label(
                hdr, text=f"({len(nodes)})", bg=PANEL_BG, fg=TEXT_DIM,
                font=("Consolas", 7),
            ).pack(side="left", padx=4)

            # Node buttons
            for node in sorted(nodes, key=lambda n: n.get("display_name", "")):
                icon = node.get("icon", "")
                name = node.get("display_name", node.get("node_id", "?"))
                node_id = node.get("node_id", "")

                btn = tk.Button(
                    self._palette_inner,
                    text=f"  {icon} {name}",
                    bg=CARD_BG, fg=TEXT, font=("Consolas", 7),
                    relief="flat", bd=0, anchor="w",
                    activebackground=color, activeforeground="#fff",
                    cursor="hand2",
                    command=lambda nid=node_id: self._add_step(nid),
                )
                btn.pack(fill="x", padx=8, pady=1)

    def _filter_palette(self):
        """Filter palette by search text."""
        query = self._palette_search_var.get().lower().strip()
        if not query:
            self._render_palette(self._all_nodes)
            return

        filtered = {}
        for ext, nodes in self._all_nodes.items():
            matches = [
                n for n in nodes
                if query in n.get("display_name", "").lower()
                or query in n.get("node_id", "").lower()
                or query in n.get("description", "").lower()
                or query in ext.lower()
            ]
            if matches:
                filtered[ext] = matches
        self._render_palette(filtered)

    def _load_presets(self):
        """Populate preset buttons."""
        for w in self._preset_frame.winfo_children():
            w.destroy()

        try:
            mgr = self._get_manager()
            presets = mgr.list_presets()
            for p in presets:
                pid = p.get("id", "")
                icon = p.get("icon", "\u26a1")
                name = p.get("name", pid)
                btn = tk.Button(
                    self._preset_frame,
                    text=f" {icon} {name} ",
                    bg=CARD_BG, fg=TEXT, font=("Consolas", 7),
                    relief="flat", bd=0,
                    activebackground=ACCENT, activeforeground="#fff",
                    cursor="hand2",
                    command=lambda p_id=pid: self._load_preset(p_id),
                )
                btn.pack(side="left", padx=2, pady=4)
        except Exception as e:
            logger.warning("Failed to load presets: %s", e)

    # ------------------------------------------------------------------
    # Step management
    # ------------------------------------------------------------------

    def _add_step(self, node_id: str):
        """Add a node as a step to the workflow."""
        mgr = self._get_manager()
        schema = mgr.get_node_schema(node_id)
        if not schema:
            self._log(f"Unknown node: {node_id}")
            return

        step_num = len(self._workflow_steps) + 1
        step = {
            "id": str(step_num),
            "class_type": node_id,
            "inputs": {},
            "schema": schema,
        }

        # Pre-fill defaults
        for inp in schema.get("inputs", []):
            if inp.get("default") is not None:
                step["inputs"][inp["name"]] = inp["default"]

        self._workflow_steps.append(step)
        self._render_steps()
        self._log(f"Added step {step_num}: {schema.get('display_name', node_id)}")

    def _remove_step(self, index: int):
        """Remove a step by index."""
        if 0 <= index < len(self._workflow_steps):
            removed = self._workflow_steps.pop(index)
            # Re-number
            for i, s in enumerate(self._workflow_steps):
                s["id"] = str(i + 1)
            self._render_steps()
            self._log(f"Removed step: {removed['class_type']}")

    def _move_step(self, index: int, direction: int):
        """Move a step up (-1) or down (+1)."""
        new_idx = index + direction
        if 0 <= new_idx < len(self._workflow_steps):
            steps = self._workflow_steps
            steps[index], steps[new_idx] = steps[new_idx], steps[index]
            for i, s in enumerate(steps):
                s["id"] = str(i + 1)
            self._render_steps()

    def _render_steps(self):
        """Render all workflow steps."""
        for w in self._steps_inner.winfo_children():
            w.destroy()

        if not self._workflow_steps:
            self._empty_label = tk.Label(
                self._steps_inner,
                text="No steps yet.\nClick a node in the palette to add it,\nor load a preset below.",
                bg=BG, fg=TEXT_DIM, font=("Consolas", 9), justify="center",
            )
            self._empty_label.pack(pady=40)
            return

        for idx, step in enumerate(self._workflow_steps):
            self._render_step_card(idx, step)

    def _render_step_card(self, idx: int, step: Dict):
        """Render a single step card with input fields."""
        schema = step.get("schema", {})
        node_id = step.get("class_type", "")
        ext = schema.get("extension", "onyx")
        color = EXT_COLORS.get(ext, TEXT_DIM)
        icon = schema.get("icon", "")
        name = schema.get("display_name", node_id)

        card = tk.Frame(self._steps_inner, bg=CARD_BG, bd=1, relief="flat",
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", padx=4, pady=2)

        # Header row
        hdr = tk.Frame(card, bg=CARD_BG)
        hdr.pack(fill="x", padx=8, pady=(6, 2))

        tk.Label(
            hdr, text=f"{idx + 1}.", bg=CARD_BG, fg=TEXT_DIM,
            font=("Consolas", 9, "bold"),
        ).pack(side="left")
        tk.Label(
            hdr, text=f" {icon} {name}", bg=CARD_BG, fg=color,
            font=("Consolas", 9, "bold"),
        ).pack(side="left", padx=(2, 8))
        tk.Label(
            hdr, text=ext, bg=CARD_BG, fg=TEXT_DIM,
            font=("Consolas", 7),
        ).pack(side="left")

        # Action buttons
        btn_row = tk.Frame(hdr, bg=CARD_BG)
        btn_row.pack(side="right")
        for text, cmd in [
            ("\u25b2", lambda i=idx: self._move_step(i, -1)),
            ("\u25bc", lambda i=idx: self._move_step(i, 1)),
            ("\u2715", lambda i=idx: self._remove_step(i)),
        ]:
            tk.Button(
                btn_row, text=text, bg=CARD_BG, fg=TEXT_DIM,
                font=("Consolas", 7), relief="flat", bd=0,
                activebackground=ERROR, activeforeground="#fff",
                cursor="hand2", width=2, command=cmd,
            ).pack(side="left", padx=1)

        # Input fields
        inputs = schema.get("inputs", [])
        if inputs:
            inp_frame = tk.Frame(card, bg=CARD_BG)
            inp_frame.pack(fill="x", padx=12, pady=(0, 6))

            for inp in inputs:
                iname = inp["name"]
                itype = inp.get("type", "STRING")
                default = step["inputs"].get(iname, inp.get("default", ""))
                options = inp.get("options")

                row = tk.Frame(inp_frame, bg=CARD_BG)
                row.pack(fill="x", pady=1)

                tk.Label(
                    row, text=f"{iname}:", bg=CARD_BG, fg=TEXT_DIM,
                    font=("Consolas", 7), width=14, anchor="e",
                ).pack(side="left")

                if options:
                    var = tk.StringVar(value=str(default or options[0]))
                    combo = ttk.Combobox(
                        row, textvariable=var, values=options,
                        font=("Consolas", 7), width=20, state="readonly",
                    )
                    combo.pack(side="left", padx=4)
                    var.trace_add("write", lambda *_, s=step, n=iname, v=var:
                                  s["inputs"].__setitem__(n, v.get()))
                elif itype == "BOOL":
                    var = tk.BooleanVar(value=bool(default))
                    cb = tk.Checkbutton(
                        row, variable=var, bg=CARD_BG, fg=TEXT,
                        selectcolor=CARD_BG, activebackground=CARD_BG,
                        font=("Consolas", 7),
                    )
                    cb.pack(side="left", padx=4)
                    var.trace_add("write", lambda *_, s=step, n=iname, v=var:
                                  s["inputs"].__setitem__(n, v.get()))
                elif itype in ("INT", "FLOAT"):
                    var = tk.StringVar(value=str(default or ""))
                    ent = tk.Entry(
                        row, textvariable=var, bg=BG, fg=TEXT,
                        insertbackground=TEXT, font=("Consolas", 7),
                        relief="flat", bd=0, width=12,
                    )
                    ent.pack(side="left", padx=4)
                    var.trace_add("write", lambda *_, s=step, n=iname, v=var, t=itype:
                                  self._update_num_input(s, n, v, t))
                else:
                    # String / file path / connection ref
                    var = tk.StringVar(value=str(default or ""))
                    ent = tk.Entry(
                        row, textvariable=var, bg=BG, fg=TEXT,
                        insertbackground=TEXT, font=("Consolas", 7),
                        relief="flat", bd=0, width=24,
                    )
                    ent.pack(side="left", padx=4, fill="x", expand=True)
                    var.trace_add("write", lambda *_, s=step, n=iname, v=var:
                                  s["inputs"].__setitem__(n, v.get()))

                # Connection hint
                if inp.get("required") and itype not in ("STRING", "INT", "FLOAT", "BOOL"):
                    tk.Label(
                        row, text="(wire)", bg=CARD_BG, fg=TEXT_DIM,
                        font=("Consolas", 6),
                    ).pack(side="left", padx=2)

    def _update_num_input(self, step, name, var, typ):
        """Update a numeric input, coercing to int/float."""
        val = var.get()
        try:
            step["inputs"][name] = int(val) if typ == "INT" else float(val)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Workflow build / execute
    # ------------------------------------------------------------------

    def _build_workflow_json(self) -> Dict:
        """Convert step list to workflow JSON format."""
        nodes = {}
        for step in self._workflow_steps:
            sid = step["id"]
            nodes[sid] = {
                "class_type": step["class_type"],
                "inputs": dict(step["inputs"]),
            }

        # Auto-wire: if an input value is "[N, idx]" string, parse as connection
        for sid, node_def in nodes.items():
            for iname, ival in list(node_def["inputs"].items()):
                if isinstance(ival, str) and ival.startswith("[") and ival.endswith("]"):
                    try:
                        parsed = json.loads(ival)
                        if isinstance(parsed, list) and len(parsed) == 2:
                            node_def["inputs"][iname] = parsed
                    except (json.JSONDecodeError, ValueError):
                        pass

        return {
            "meta": {
                "name": "Custom Workflow",
                "description": f"Built in Workflow Builder ({len(nodes)} steps)",
            },
            "nodes": nodes,
        }

    def _run_workflow(self):
        """Execute the current workflow."""
        if self._running:
            self._log("Workflow already running")
            return
        if not self._workflow_steps:
            self._log("No steps to run")
            return

        workflow = self._build_workflow_json()

        # Validate first
        mgr = self._get_manager()
        validation = mgr.validate(workflow)
        if not validation.get("valid"):
            for err in validation.get("errors", []):
                self._log(f"Validation error: {err}")
            return

        self._running = True
        self._status_var.set("Running...")
        self._log("--- Workflow started ---")

        def on_complete(wf_id, results, error):
            self._running = False
            if error:
                self._log(f"Workflow FAILED: {error}")
                self.after(0, lambda: self._status_var.set(f"Error: {error}"))
            else:
                self._log(f"--- Workflow completed ({len(results or {})} nodes) ---")
                self.after(0, lambda: self._status_var.set("Completed"))

        mgr.execute_async(workflow, on_complete=on_complete)

    def _stop_workflow(self):
        """Stop the running workflow (best-effort)."""
        self._running = False
        self._status_var.set("Stopped")
        self._log("Workflow stopped by user")

    def _on_progress(self, message: Dict):
        """Progress callback from executor (called from worker thread)."""
        msg_type = message.get("type", "")
        node_id = message.get("node_id", "")

        if msg_type == "node_running":
            ct = message.get("class_type", "")
            self.after(0, lambda: self._log(f"  [{node_id}] Running: {ct}"))
        elif msg_type == "node_done":
            elapsed = message.get("elapsed", 0)
            self.after(0, lambda: self._log(f"  [{node_id}] Done ({elapsed}s)"))
        elif msg_type == "node_error":
            err = message.get("error", "")
            self.after(0, lambda: self._log(f"  [{node_id}] ERROR: {err}"))
        elif msg_type == "node_cached":
            self.after(0, lambda: self._log(f"  [{node_id}] Cached"))
        elif msg_type.startswith("workflow_"):
            self.after(0, lambda: self._log(f"  Workflow: {msg_type}"))

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def _save_workflow(self):
        if not self._workflow_steps:
            return
        workflow = self._build_workflow_json()
        mgr = self._get_manager()
        path = mgr.save_workflow(workflow)
        self._log(f"Saved: {path}")

    def _load_workflow(self):
        path = filedialog.askopenfilename(
            title="Load Workflow",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialdir=str(self._get_manager()._cache.__class__.__module__),
        )
        if not path:
            return
        self._load_workflow_file(path)

    def _load_workflow_file(self, path: str):
        mgr = self._get_manager()
        workflow = mgr.load_workflow(path)
        if not workflow:
            self._log(f"Failed to load: {path}")
            return
        self._import_workflow(workflow)

    def _load_preset(self, preset_id: str):
        mgr = self._get_manager()
        workflow = mgr.load_preset(preset_id)
        if not workflow:
            self._log(f"Failed to load preset: {preset_id}")
            return
        self._import_workflow(workflow)
        self._log(f"Loaded preset: {workflow.get('meta', {}).get('name', preset_id)}")

    def _import_workflow(self, workflow: Dict):
        """Import a workflow JSON into the step list."""
        mgr = self._get_manager()
        self._workflow_steps.clear()

        nodes = workflow.get("nodes", {})
        for node_id in sorted(nodes.keys(), key=lambda k: int(k) if k.isdigit() else k):
            node_def = nodes[node_id]
            class_type = node_def.get("class_type", "")
            schema = mgr.get_node_schema(class_type) or {}

            step = {
                "id": node_id,
                "class_type": class_type,
                "inputs": dict(node_def.get("inputs", {})),
                "schema": schema,
            }
            # Convert connection lists to "[N, idx]" display strings
            for iname, ival in list(step["inputs"].items()):
                if isinstance(ival, list) and len(ival) == 2:
                    step["inputs"][iname] = json.dumps(ival)

            self._workflow_steps.append(step)

        self._render_steps()

    def _clear_workflow(self):
        self._workflow_steps.clear()
        self._render_steps()
        self._log("Workflow cleared")

    # ------------------------------------------------------------------
    # Visual canvas launcher
    # ------------------------------------------------------------------

    def _open_canvas(self):
        """Open the visual node canvas for the current workflow."""
        try:
            from face.node_canvas import NodeCanvasWindow
            workflow = self._build_workflow_json() if self._workflow_steps else None
            NodeCanvasWindow(self, workflow=workflow)
        except ImportError as e:
            self._log(f"Node canvas not available: {e}")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, text: str):
        """Append a line to the execution log."""
        self._log_lines.append(text)
        self._log_text.configure(state="normal")
        self._log_text.insert("end", text + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _on_close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.destroy()
