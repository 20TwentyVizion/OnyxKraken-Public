"""Visual node canvas — drag-and-drop workflow editor.

A Toplevel window with a pannable/zoomable canvas where nodes are
rendered as colored rectangles with input/output ports. Connections
are drawn as curved lines between ports.

This is the "advanced" visual editor. The list-based builder is separate.
"""

from __future__ import annotations

import json
import logging
import math
import tkinter as tk
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
BG = "#0a0e14"
GRID_COLOR = "#141a24"
NODE_BG = "#1c2333"
NODE_HEADER = "#252d3a"
NODE_BORDER = "#30363d"
NODE_SELECTED = "#7c3aed"
NODE_RUNNING = "#00e5ff"
NODE_DONE = "#00e676"
NODE_FAIL = "#ff5252"
TEXT = "#c9d1d9"
TEXT_DIM = "#6a7a8a"
WIRE_COLOR = "#4a5568"
WIRE_ACTIVE = "#7c3aed"
WIRE_FLOWING = "#00e5ff"
PORT_RADIUS = 5
NODE_WIDTH = 180
NODE_HEADER_H = 28
PORT_H = 20
BTN_BG = "#21262d"
BTN_FG = "#c9d1d9"
ACCENT = "#7c3aed"

EXT_COLORS = {
    "onyx": "#7c3aed",
    "evera": "#e67e22",
    "smartengine": "#9b59b6",
    "justedit": "#3498db",
}

# Type colors for port dots
TYPE_PORT_COLORS = {
    "STRING": "#bdc3c7", "INT": "#bdc3c7", "FLOAT": "#bdc3c7",
    "BOOL": "#bdc3c7", "FILE_PATH": "#95a5a6",
    "AUDIO_FILE": "#e74c3c", "VIDEO_FILE": "#e67e22",
    "TEXT_DOCUMENT": "#2ecc71", "ARTIST": "#9b59b6",
    "CONCEPT": "#3498db", "LYRICS": "#2ecc71",
    "TRACK_INFO": "#e74c3c", "ANY": "#7f8c8d",
    "SE_PROJECT": "#f39c12", "JE_PROJECT": "#2980b9",
    "MANUSCRIPT": "#8e44ad", "SCENE_TEXT": "#27ae60",
    "AGENT_RESULT": "#1abc9c", "PROJECT_REF": "#9b59b6",
}


class CanvasNode:
    """Visual representation of a node on the canvas."""

    def __init__(self, node_id: str, class_type: str, schema: Dict,
                 x: float = 0, y: float = 0, inputs: Optional[Dict] = None):
        self.node_id = node_id
        self.class_type = class_type
        self.schema = schema
        self.x = x
        self.y = y
        self.inputs = inputs or {}
        self.canvas_ids: List[int] = []  # tk canvas item IDs
        self.input_ports: Dict[str, Tuple[float, float]] = {}
        self.output_ports: Dict[str, Tuple[float, float]] = {}
        self.selected = False

    @property
    def ext(self) -> str:
        return self.schema.get("extension", "onyx")

    @property
    def color(self) -> str:
        return EXT_COLORS.get(self.ext, TEXT_DIM)

    @property
    def display_name(self) -> str:
        return self.schema.get("display_name", self.class_type)

    @property
    def icon(self) -> str:
        return self.schema.get("icon", "")

    @property
    def height(self) -> float:
        n_inputs = len(self.schema.get("inputs", []))
        n_outputs = len(self.schema.get("outputs", []))
        ports = max(n_inputs, n_outputs)
        return NODE_HEADER_H + max(ports, 1) * PORT_H + 8


class CanvasWire:
    """Visual connection between two ports."""

    def __init__(self, src_node: str, src_output: int,
                 dst_node: str, dst_input: str):
        self.src_node = src_node
        self.src_output = src_output
        self.dst_node = dst_node
        self.dst_input = dst_input
        self.canvas_id: Optional[int] = None


class NodeCanvasWindow(tk.Toplevel):
    """Visual node canvas editor window."""

    def __init__(self, master, workflow: Optional[Dict] = None,
                 on_close: Optional[Callable] = None):
        super().__init__(master)
        self.title("Onyx \u2014 Node Canvas")
        self.configure(bg=BG)
        self.geometry("1200x800")
        self.minsize(800, 500)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._on_close_cb = on_close

        self._manager = None
        self._nodes: Dict[str, CanvasNode] = {}
        self._wires: List[CanvasWire] = []
        self._next_id = 1
        self._selected_node: Optional[str] = None
        self._drag_offset = (0, 0)
        self._pan_offset = (0.0, 0.0)
        self._zoom = 1.0
        self._dragging_wire = False
        self._wire_src: Optional[Tuple[str, int]] = None
        self._temp_wire_id: Optional[int] = None
        self._exec_states: Dict[str, str] = {}  # node_id -> "running"|"done"|"fail"
        self._exec_pulse_id = None
        self._exec_pulse_phase = 0

        self._build_ui()

        if workflow:
            self.after(100, lambda: self._import_workflow(workflow))

    def _get_manager(self):
        if self._manager is None:
            from core.nodes.workflow_manager import get_workflow_manager
            self._manager = get_workflow_manager()
            self._manager.initialize()
        return self._manager

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Toolbar
        toolbar = tk.Frame(self, bg="#161b22", height=36)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        tk.Label(
            toolbar, text="\U0001f578\ufe0f Node Canvas", bg="#161b22", fg=ACCENT,
            font=("Consolas", 11, "bold"),
        ).pack(side="left", padx=12)

        for text, cmd in [
            ("\u25b6 Run", self._run_workflow),
            ("\U0001f4be Save", self._save_workflow),
            ("\U0001f4c2 Load", self._load_workflow),
            ("\U0001f5d1 Clear", self._clear_canvas),
            ("Fit", self._fit_view),
        ]:
            tk.Button(
                toolbar, text=text, bg=BTN_BG, fg=BTN_FG,
                font=("Consolas", 8), relief="flat", bd=0,
                activebackground=ACCENT, activeforeground="#fff",
                cursor="hand2", command=cmd,
            ).pack(side="left", padx=2, pady=4)

        # Presets dropdown
        tk.Label(toolbar, text="  Presets:", bg="#161b22", fg=TEXT_DIM,
                 font=("Consolas", 8)).pack(side="left", padx=(12, 2))
        self._preset_menu_btn = tk.Menubutton(
            toolbar, text="\U0001f4cb Workflows", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 8), relief="flat", bd=0,
            activebackground=ACCENT, activeforeground="#fff",
            cursor="hand2",
        )
        self._preset_menu_btn.pack(side="left", padx=2, pady=4)
        self._build_preset_menu()

        # Extension add-node buttons
        tk.Label(toolbar, text="  Add:", bg="#161b22", fg=TEXT_DIM,
                 font=("Consolas", 8)).pack(side="left", padx=(16, 4))

        self._node_menu_btn = tk.Menubutton(
            toolbar, text="\u2795 Node", bg=BTN_BG, fg=BTN_FG,
            font=("Consolas", 8), relief="flat", bd=0,
            activebackground=ACCENT, activeforeground="#fff",
            cursor="hand2",
        )
        self._node_menu_btn.pack(side="left", padx=2, pady=4)
        self._build_node_menu()

        # Status
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            toolbar, textvariable=self._status_var, bg="#161b22", fg=TEXT_DIM,
            font=("Consolas", 7),
        ).pack(side="right", padx=12)

        # Canvas
        self._canvas = tk.Canvas(
            self, bg=BG, highlightthickness=0, cursor="crosshair",
        )
        self._canvas.pack(fill="both", expand=True)

        # Bindings
        self._canvas.bind("<ButtonPress-1>", self._on_click)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self._canvas.bind("<B2-Motion>", self._on_pan_move)
        self._canvas.bind("<ButtonPress-3>", self._on_pan_start)
        self._canvas.bind("<B3-Motion>", self._on_pan_move)
        self._canvas.bind("<MouseWheel>", self._on_zoom)
        self.bind("<Delete>", self._on_delete)
        self.bind("<BackSpace>", self._on_delete)

        self._draw_grid()

    def _build_node_menu(self):
        """Build the add-node dropdown menu."""
        menu = tk.Menu(self._node_menu_btn, tearoff=0, bg=NODE_BG, fg=TEXT,
                       font=("Consolas", 8), activebackground=ACCENT)
        self._node_menu_btn["menu"] = menu

        try:
            mgr = self._get_manager()
            by_ext = mgr.list_by_extension()
            for ext_name, nodes in sorted(by_ext.items()):
                sub = tk.Menu(menu, tearoff=0, bg=NODE_BG, fg=TEXT,
                              font=("Consolas", 8), activebackground=ACCENT)
                color = EXT_COLORS.get(ext_name, TEXT_DIM)
                menu.add_cascade(label=f"\u25cf {ext_name.upper()}", menu=sub)
                for node in sorted(nodes, key=lambda n: n.get("display_name", "")):
                    nid = node.get("node_id", "")
                    icon = node.get("icon", "")
                    name = node.get("display_name", nid)
                    sub.add_command(
                        label=f"  {icon} {name}",
                        command=lambda n=nid: self._add_node_at_center(n),
                    )
        except Exception as e:
            menu.add_command(label=f"Error: {e}", state="disabled")

    def _build_preset_menu(self):
        """Build the chain workflow presets dropdown menu."""
        menu = tk.Menu(self._preset_menu_btn, tearoff=0, bg=NODE_BG, fg=TEXT,
                       font=("Consolas", 8), activebackground=ACCENT)
        self._preset_menu_btn["menu"] = menu

        try:
            import pathlib
            presets_dir = pathlib.Path(__file__).resolve().parent.parent / "core" / "nodes" / "presets"
            if presets_dir.is_dir():
                for p in sorted(presets_dir.glob("*.json")):
                    try:
                        with open(p, "r") as f:
                            data = json.load(f)
                        meta = data.get("meta", {})
                        name = meta.get("name", p.stem)
                        desc = meta.get("description", "")[:50]
                        menu.add_command(
                            label=f"  {name}",
                            command=lambda path=str(p): self._load_preset(path),
                        )
                    except Exception:
                        pass
            if not menu.index("end") and menu.index("end") is None:
                menu.add_command(label="  No presets found", state="disabled")
        except Exception as e:
            menu.add_command(label=f"Error: {e}", state="disabled")

    def _load_preset(self, path: str):
        """Load a preset workflow JSON onto the canvas."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self._import_workflow(data)
            meta = data.get("meta", {})
            name = meta.get("name", "Preset")
            self._status_var.set(f"Loaded: {name}")
            self.after(200, self._fit_view)
        except Exception as e:
            self._status_var.set(f"Load error: {e}")

    # ------------------------------------------------------------------
    # Execution state highlighting
    # ------------------------------------------------------------------

    def set_node_exec_state(self, node_id: str, state: str):
        """Set a node's execution state for visual feedback.

        state: 'running', 'done', 'fail', or '' to clear.
        """
        if state:
            self._exec_states[node_id] = state
        else:
            self._exec_states.pop(node_id, None)

        node = self._nodes.get(node_id)
        if node:
            self._render_node(node)
            # Re-render connected wires with flow color
            for wire in self._wires:
                if wire.src_node == node_id or wire.dst_node == node_id:
                    self._render_wire(wire)

        # Start pulse animation if any node is running
        if any(s == "running" for s in self._exec_states.values()):
            if not self._exec_pulse_id:
                self._exec_pulse()
        else:
            if self._exec_pulse_id:
                self.after_cancel(self._exec_pulse_id)
                self._exec_pulse_id = None

    def clear_exec_states(self):
        """Clear all execution states."""
        self._exec_states.clear()
        if self._exec_pulse_id:
            self.after_cancel(self._exec_pulse_id)
            self._exec_pulse_id = None
        self._render_all()

    def _exec_pulse(self):
        """Animate running nodes with a glow pulse."""
        self._exec_pulse_phase = (self._exec_pulse_phase + 1) % 30
        for nid, state in self._exec_states.items():
            if state == "running":
                node = self._nodes.get(nid)
                if node:
                    self._render_node(node)
        self._exec_pulse_id = self.after(60, self._exec_pulse)

    # ------------------------------------------------------------------
    # Grid drawing
    # ------------------------------------------------------------------

    def _draw_grid(self):
        """Draw background grid."""
        self._canvas.delete("grid")
        w = self.winfo_width() or 1200
        h = self.winfo_height() or 800
        step = max(int(40 * self._zoom), 10)
        ox, oy = self._pan_offset

        for x in range(int(-ox % step), w, step):
            self._canvas.create_line(x, 0, x, h, fill=GRID_COLOR, tags="grid")
        for y in range(int(-oy % step), h, step):
            self._canvas.create_line(0, y, w, y, fill=GRID_COLOR, tags="grid")
        self._canvas.tag_lower("grid")

    # ------------------------------------------------------------------
    # Node rendering
    # ------------------------------------------------------------------

    def _render_node(self, node: CanvasNode):
        """Draw a node on the canvas."""
        # Remove old items
        for cid in node.canvas_ids:
            self._canvas.delete(cid)
        node.canvas_ids.clear()
        node.input_ports.clear()
        node.output_ports.clear()

        ox, oy = self._pan_offset
        z = self._zoom
        x = node.x * z + ox
        y = node.y * z + oy
        w = NODE_WIDTH * z
        h = node.height * z
        hdr_h = NODE_HEADER_H * z
        port_h = PORT_H * z
        pr = PORT_RADIUS * z

        # Determine border color based on execution state
        exec_state = self._exec_states.get(node.node_id, "")
        if exec_state == "running":
            import math as _m
            t = self._exec_pulse_phase / 30.0
            bright = 0.5 + 0.5 * _m.sin(t * 2 * _m.pi)
            r = int(0x00 + 0x00 * bright)
            g = int(0x88 + (0xe5 - 0x88) * bright)
            b = int(0xaa + (0xff - 0xaa) * bright)
            border_color = f"#{r:02x}{g:02x}{b:02x}"
            border_w = 3
        elif exec_state == "done":
            border_color = NODE_DONE
            border_w = 2
        elif exec_state == "fail":
            border_color = NODE_FAIL
            border_w = 2
        elif node.selected:
            border_color = NODE_SELECTED
            border_w = 2
        else:
            border_color = NODE_BORDER
            border_w = 1

        # Body
        body = self._canvas.create_rectangle(
            x, y, x + w, y + h,
            fill=NODE_BG, outline=border_color, width=border_w,
            tags=("node", node.node_id),
        )
        node.canvas_ids.append(body)

        # Header — tint based on execution state
        header_color = node.color
        if exec_state == "running":
            header_color = "#0a3040"
        elif exec_state == "done":
            header_color = "#0a3020"
        elif exec_state == "fail":
            header_color = "#3a1010"

        hdr = self._canvas.create_rectangle(
            x, y, x + w, y + hdr_h,
            fill=header_color, outline="", tags=("node", node.node_id),
        )
        node.canvas_ids.append(hdr)

        # Title
        title = self._canvas.create_text(
            x + 8 * z, y + hdr_h / 2,
            text=f"{node.icon} {node.display_name}",
            fill="#fff", font=("Consolas", max(int(8 * z), 6), "bold"),
            anchor="w", tags=("node", node.node_id),
        )
        node.canvas_ids.append(title)

        # Input ports
        inputs = node.schema.get("inputs", [])
        for i, inp in enumerate(inputs):
            py = y + hdr_h + (i + 0.5) * port_h
            port_color = TYPE_PORT_COLORS.get(inp.get("type", "ANY"), "#7f8c8d")

            dot = self._canvas.create_oval(
                x - pr, py - pr, x + pr, py + pr,
                fill=port_color, outline="#000", width=1,
                tags=("port", "input_port", node.node_id, inp["name"]),
            )
            node.canvas_ids.append(dot)
            node.input_ports[inp["name"]] = (x, py)

            lbl = self._canvas.create_text(
                x + 10 * z, py,
                text=inp["name"], fill=TEXT_DIM,
                font=("Consolas", max(int(6 * z), 5)),
                anchor="w", tags=("node", node.node_id),
            )
            node.canvas_ids.append(lbl)

        # Output ports
        outputs = node.schema.get("outputs", [])
        for i, out in enumerate(outputs):
            py = y + hdr_h + (i + 0.5) * port_h
            port_color = TYPE_PORT_COLORS.get(out.get("type", "ANY"), "#7f8c8d")

            dot = self._canvas.create_oval(
                x + w - pr, py - pr, x + w + pr, py + pr,
                fill=port_color, outline="#000", width=1,
                tags=("port", "output_port", node.node_id, str(i)),
            )
            node.canvas_ids.append(dot)
            node.output_ports[out["name"]] = (x + w, py)

            lbl = self._canvas.create_text(
                x + w - 10 * z, py,
                text=out["name"], fill=TEXT_DIM,
                font=("Consolas", max(int(6 * z), 5)),
                anchor="e", tags=("node", node.node_id),
            )
            node.canvas_ids.append(lbl)

    def _render_wire(self, wire: CanvasWire):
        """Draw a connection wire as a bezier curve."""
        if wire.canvas_id:
            self._canvas.delete(wire.canvas_id)

        src_node = self._nodes.get(wire.src_node)
        dst_node = self._nodes.get(wire.dst_node)
        if not src_node or not dst_node:
            return

        outputs = src_node.schema.get("outputs", [])
        if wire.src_output < len(outputs):
            out_name = outputs[wire.src_output]["name"]
        else:
            return

        src_pos = src_node.output_ports.get(out_name)
        dst_pos = dst_node.input_ports.get(wire.dst_input)
        if not src_pos or not dst_pos:
            return

        x1, y1 = src_pos
        x2, y2 = dst_pos

        # Wire color based on source node execution state
        src_state = self._exec_states.get(wire.src_node, "")
        if src_state == "done":
            wire_color = WIRE_FLOWING
            wire_w = 2.5
        elif src_state == "running":
            wire_color = NODE_RUNNING
            wire_w = 2
        elif src_state == "fail":
            wire_color = NODE_FAIL
            wire_w = 2
        else:
            wire_color = WIRE_COLOR
            wire_w = 2

        # Bezier control points
        dx = abs(x2 - x1) * 0.5
        wire.canvas_id = self._canvas.create_line(
            x1, y1,
            x1 + dx, y1,
            x2 - dx, y2,
            x2, y2,
            fill=wire_color, width=wire_w, smooth=True,
            tags="wire",
        )
        self._canvas.tag_lower("wire", "node")

    def _render_all(self):
        """Redraw everything."""
        self._draw_grid()
        for node in self._nodes.values():
            self._render_node(node)
        for wire in self._wires:
            self._render_wire(wire)

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def _add_node_at_center(self, class_type: str):
        """Add a node at the center of the visible canvas."""
        mgr = self._get_manager()
        schema = mgr.get_node_schema(class_type)
        if not schema:
            return

        cw = self.winfo_width() or 1200
        ch = self.winfo_height() or 800
        ox, oy = self._pan_offset
        z = self._zoom

        cx = (cw / 2 - ox) / z
        cy = (ch / 2 - oy) / z

        nid = str(self._next_id)
        self._next_id += 1

        node = CanvasNode(nid, class_type, schema, x=cx - NODE_WIDTH / 2, y=cy - 40)
        self._nodes[nid] = node
        self._render_node(node)
        self._status_var.set(f"Added: {schema.get('display_name', class_type)}")

    def _delete_selected(self):
        """Delete the selected node and its wires."""
        if not self._selected_node:
            return
        nid = self._selected_node
        node = self._nodes.pop(nid, None)
        if node:
            for cid in node.canvas_ids:
                self._canvas.delete(cid)

        # Remove connected wires
        self._wires = [
            w for w in self._wires
            if w.src_node != nid and w.dst_node != nid
        ]
        self._selected_node = None
        self._render_all()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_click(self, event):
        """Handle canvas click — select node or start wire drag."""
        items = self._canvas.find_closest(event.x, event.y)
        if not items:
            self._deselect_all()
            return

        tags = self._canvas.gettags(items[0])

        # Clicked on output port — start wire
        if "output_port" in tags:
            node_id = tags[2] if len(tags) > 2 else None
            output_idx = int(tags[3]) if len(tags) > 3 else 0
            if node_id:
                self._dragging_wire = True
                self._wire_src = (node_id, output_idx)
                return

        # Clicked on node — select and prepare for drag
        if "node" in tags:
            node_id = tags[1] if len(tags) > 1 else None
            if node_id and node_id in self._nodes:
                self._select_node(node_id)
                node = self._nodes[node_id]
                ox, oy = self._pan_offset
                z = self._zoom
                self._drag_offset = (
                    event.x - (node.x * z + ox),
                    event.y - (node.y * z + oy),
                )
                return

        self._deselect_all()

    def _on_drag(self, event):
        """Handle mouse drag — move node or draw wire."""
        if self._dragging_wire and self._wire_src:
            # Draw temp wire from source to cursor
            if self._temp_wire_id:
                self._canvas.delete(self._temp_wire_id)
            src_node = self._nodes.get(self._wire_src[0])
            if src_node:
                outputs = src_node.schema.get("outputs", [])
                if self._wire_src[1] < len(outputs):
                    out_name = outputs[self._wire_src[1]]["name"]
                    pos = src_node.output_ports.get(out_name)
                    if pos:
                        x1, y1 = pos
                        dx = abs(event.x - x1) * 0.5
                        self._temp_wire_id = self._canvas.create_line(
                            x1, y1, x1 + dx, y1,
                            event.x - dx, event.y, event.x, event.y,
                            fill=WIRE_ACTIVE, width=2, smooth=True, dash=(4, 2),
                        )
            return

        if self._selected_node:
            node = self._nodes.get(self._selected_node)
            if node:
                ox, oy = self._pan_offset
                z = self._zoom
                dx, dy = self._drag_offset
                node.x = (event.x - dx - ox) / z
                node.y = (event.y - dy - oy) / z
                self._render_node(node)
                # Re-render connected wires
                for wire in self._wires:
                    if wire.src_node == node.node_id or wire.dst_node == node.node_id:
                        self._render_wire(wire)

    def _on_release(self, event):
        """Handle mouse release — complete wire connection."""
        if self._dragging_wire and self._wire_src:
            if self._temp_wire_id:
                self._canvas.delete(self._temp_wire_id)
                self._temp_wire_id = None

            # Find target input port
            items = self._canvas.find_closest(event.x, event.y)
            if items:
                tags = self._canvas.gettags(items[0])
                if "input_port" in tags and len(tags) > 3:
                    dst_node_id = tags[2]
                    dst_input = tags[3]
                    src_node_id, src_output = self._wire_src

                    if dst_node_id != src_node_id:
                        wire = CanvasWire(src_node_id, src_output,
                                          dst_node_id, dst_input)
                        self._wires.append(wire)
                        self._render_wire(wire)

                        # Update node inputs
                        dst_node = self._nodes.get(dst_node_id)
                        if dst_node:
                            dst_node.inputs[dst_input] = [src_node_id, src_output]

            self._dragging_wire = False
            self._wire_src = None

    def _on_pan_start(self, event):
        self._pan_start = (event.x, event.y)
        self._pan_start_offset = self._pan_offset

    def _on_pan_move(self, event):
        if hasattr(self, "_pan_start"):
            dx = event.x - self._pan_start[0]
            dy = event.y - self._pan_start[1]
            self._pan_offset = (
                self._pan_start_offset[0] + dx,
                self._pan_start_offset[1] + dy,
            )
            self._render_all()

    def _on_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9
        self._zoom = max(0.3, min(3.0, self._zoom * factor))
        self._render_all()

    def _on_delete(self, event):
        self._delete_selected()

    def _select_node(self, node_id: str):
        self._deselect_all()
        self._selected_node = node_id
        node = self._nodes.get(node_id)
        if node:
            node.selected = True
            self._render_node(node)

    def _deselect_all(self):
        if self._selected_node:
            node = self._nodes.get(self._selected_node)
            if node:
                node.selected = False
                self._render_node(node)
        self._selected_node = None

    # ------------------------------------------------------------------
    # Workflow operations
    # ------------------------------------------------------------------

    def _build_workflow_json(self) -> Dict:
        """Convert canvas state to workflow JSON."""
        nodes = {}
        for nid, node in self._nodes.items():
            inputs = {}
            for iname, ival in node.inputs.items():
                inputs[iname] = ival
            # Also add direct values from schema defaults
            for inp in node.schema.get("inputs", []):
                if inp["name"] not in inputs and inp.get("default") is not None:
                    inputs[inp["name"]] = inp["default"]

            nodes[nid] = {
                "class_type": node.class_type,
                "inputs": inputs,
                "position": [round(node.x), round(node.y)],
            }
        return {
            "meta": {"name": "Canvas Workflow", "category": "custom"},
            "nodes": nodes,
        }

    def _import_workflow(self, workflow: Dict):
        """Import a workflow JSON onto the canvas."""
        self._nodes.clear()
        self._wires.clear()
        self._canvas.delete("all")

        mgr = self._get_manager()
        graph = workflow.get("nodes", {})

        max_id = 0
        for nid, node_def in graph.items():
            class_type = node_def.get("class_type", "")
            schema = mgr.get_node_schema(class_type) or {
                "node_id": class_type, "display_name": class_type,
                "extension": "onyx", "inputs": [], "outputs": [],
            }
            pos = node_def.get("position", [100, 100])
            inputs = {}
            for iname, ival in node_def.get("inputs", {}).items():
                if isinstance(ival, list) and len(ival) == 2:
                    # Connection — store and create wire
                    inputs[iname] = ival
                else:
                    inputs[iname] = ival

            node = CanvasNode(nid, class_type, schema,
                              x=pos[0], y=pos[1], inputs=inputs)
            self._nodes[nid] = node
            try:
                max_id = max(max_id, int(nid))
            except ValueError:
                pass

        self._next_id = max_id + 1

        # Build wires from connection inputs
        for nid, node in self._nodes.items():
            for iname, ival in node.inputs.items():
                if isinstance(ival, list) and len(ival) == 2:
                    src_id = str(ival[0])
                    src_idx = int(ival[1])
                    wire = CanvasWire(src_id, src_idx, nid, iname)
                    self._wires.append(wire)

        self._render_all()
        self._status_var.set(f"Loaded {len(self._nodes)} nodes")

    def _run_workflow(self):
        workflow = self._build_workflow_json()
        mgr = self._get_manager()

        validation = mgr.validate(workflow)
        if not validation.get("valid"):
            errors = validation.get("errors", [])
            self._status_var.set(f"Invalid: {errors[0] if errors else 'unknown'}")
            return

        self._status_var.set("Running...")

        def on_complete(wf_id, results, error):
            if error:
                self.after(0, lambda: self._status_var.set(f"Error: {error}"))
            else:
                count = len(results or {})
                self.after(0, lambda: self._status_var.set(f"Done ({count} nodes)"))

        mgr.execute_async(workflow, on_complete=on_complete)

    def _save_workflow(self):
        workflow = self._build_workflow_json()
        mgr = self._get_manager()
        path = mgr.save_workflow(workflow)
        self._status_var.set(f"Saved: {path}")

    def _load_workflow(self):
        from core.nodes.workflow_manager import USER_WORKFLOWS_DIR, PRESETS_DIR
        path = filedialog.askopenfilename(
            title="Load Workflow",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialdir=str(USER_WORKFLOWS_DIR),
        )
        if path:
            mgr = self._get_manager()
            wf = mgr.load_workflow(path)
            if wf:
                self._import_workflow(wf)

    def _clear_canvas(self):
        self._nodes.clear()
        self._wires.clear()
        self._canvas.delete("all")
        self._draw_grid()
        self._status_var.set("Cleared")

    def _fit_view(self):
        """Fit all nodes in view."""
        if not self._nodes:
            return
        min_x = min(n.x for n in self._nodes.values())
        min_y = min(n.y for n in self._nodes.values())
        max_x = max(n.x + NODE_WIDTH for n in self._nodes.values())
        max_y = max(n.y + n.height for n in self._nodes.values())

        cw = self.winfo_width() or 1200
        ch = self.winfo_height() or 800
        margin = 60

        range_x = max_x - min_x + margin * 2
        range_y = max_y - min_y + margin * 2

        self._zoom = min(cw / max(range_x, 1), ch / max(range_y, 1))
        self._zoom = max(0.3, min(2.0, self._zoom))

        self._pan_offset = (
            margin - min_x * self._zoom,
            margin - min_y * self._zoom,
        )
        self._render_all()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _on_close(self):
        if self._on_close_cb:
            self._on_close_cb()
        self.destroy()
