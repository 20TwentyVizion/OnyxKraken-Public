"""
Unity Component — OnyxComponent wrapper for the Unity Engine Toolkit.

Exposes all Unity capabilities through the standardized component interface:
- Scene management (new, open, save, hierarchy)
- GameObject CRUD (spawn, transform, destroy, query)
- C# script generation and deployment
- Materials and shaders (PBR, presets, emission, transparency)
- Lighting and environment (presets, fog, ambient, post-processing)
- Animation (Animator, clips, Timeline, Cinemachine)
- Physics (Rigidbody, colliders, joints, physics materials)
- Audio (AudioSource, reverb zones, spatial audio)
- UI generation (Canvas, panels, buttons, menus, HUD)
- Terrain creation and sculpting
- Asset management (import, search, prefabs, AssetBundles)
- Build pipeline (multi-platform, player settings, CLI builds)
- Project management (create, open, packages, bridge deployment)
- Editor control (play, stop, pause, undo, redo, screenshot)
"""

import logging
import time
from typing import Dict, List, Optional

from core.components.base import OnyxComponent, ComponentResult, ActionDescriptor

_log = logging.getLogger(__name__)


class UnityComponent(OnyxComponent):
    """Unity Engine component — builds games, scenes, and interactive experiences in Unity."""

    # Lazy-loaded toolkit modules
    _unity = None
    _project = None
    _scripting = None
    _terrain = None
    _animation = None
    _physics = None
    _audio = None
    _shader = None
    _ui = None
    _assets = None
    _build = None

    @property
    def name(self) -> str:
        return "unity"

    @property
    def display_name(self) -> str:
        return "Unity Engine"

    @property
    def description(self) -> str:
        return "Build games, interactive 3D scenes, and applications in Unity Engine"

    @property
    def category(self) -> str:
        return "creative"

    # ------------------------------------------------------------------
    # Lazy module loading
    # ------------------------------------------------------------------

    def _get_unity(self):
        if self._unity is None:
            from apps.unity_toolkit.onyx_unity import OnyxUnity
            self._unity = OnyxUnity()
        return self._unity

    def _get_scripting(self):
        if self._scripting is None:
            from apps.unity_toolkit.unity_scripting import UnityScriptWriter
            # Requires active project path
            project_path = self._get_project_path()
            if project_path:
                self._scripting = UnityScriptWriter(project_path)
        return self._scripting

    def _get_terrain(self):
        if self._terrain is None:
            from apps.unity_toolkit.unity_terrain import UnityTerrain
            self._terrain = UnityTerrain(self._get_unity())
        return self._terrain

    def _get_animation(self):
        if self._animation is None:
            from apps.unity_toolkit.unity_animation import UnityAnimation
            self._animation = UnityAnimation(self._get_unity())
        return self._animation

    def _get_physics(self):
        if self._physics is None:
            from apps.unity_toolkit.unity_physics import UnityPhysics
            self._physics = UnityPhysics(self._get_unity())
        return self._physics

    def _get_audio(self):
        if self._audio is None:
            from apps.unity_toolkit.unity_audio import UnityAudio
            self._audio = UnityAudio(self._get_unity())
        return self._audio

    def _get_shader(self):
        if self._shader is None:
            from apps.unity_toolkit.unity_shader import UnityShader
            self._shader = UnityShader(self._get_unity())
        return self._shader

    def _get_ui(self):
        if self._ui is None:
            from apps.unity_toolkit.unity_ui import UnityUI
            self._ui = UnityUI(self._get_unity())
        return self._ui

    def _get_assets(self):
        if self._assets is None:
            project_path = self._get_project_path()
            if project_path:
                from apps.unity_toolkit.unity_assets import UnityAssets
                self._assets = UnityAssets(project_path, self._get_unity())
        return self._assets

    def _get_build(self):
        if self._build is None:
            project_path = self._get_project_path()
            if project_path:
                from apps.unity_toolkit.unity_build import UnityBuild
                self._build = UnityBuild(project_path, self._get_unity().client)
        return self._build

    def _get_project_path(self) -> Optional[str]:
        """Get the current project path from the bridge ready signal."""
        unity = self._get_unity()
        info = unity.client.get_editor_info()
        if info and "project_path" in info:
            import os
            # project_path from Unity is Application.dataPath (Assets dir)
            return os.path.dirname(info["project_path"])
        return None

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def get_actions(self) -> List[ActionDescriptor]:
        return [
            # --- Discovery & Project ---
            ActionDescriptor(
                name="discover",
                description="Find Unity installations and projects on this system",
                params=["search_dirs"],
            ),
            ActionDescriptor(
                name="create_project",
                description="Create a new Unity project pre-configured for Onyx",
                params=["name", "render_pipeline", "root_dir"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="open_project",
                description="Open a Unity project in the editor and deploy the bridge",
                params=["path", "version"],
                required_params=["path"],
            ),
            ActionDescriptor(
                name="project_info",
                description="Get information about the current Unity project",
            ),

            # --- Scene ---
            ActionDescriptor(name="new_scene", description="Create a new empty Unity scene"),
            ActionDescriptor(name="save_scene", description="Save the current scene"),
            ActionDescriptor(name="scene_info", description="Get current scene information and hierarchy"),

            # --- GameObjects ---
            ActionDescriptor(
                name="spawn",
                description="Spawn a GameObject (Cube/Sphere/Cylinder/Capsule/Plane/Quad/Empty)",
                params=["name", "type", "position", "rotation", "scale", "color"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="transform",
                description="Set position, rotation, and/or scale of a GameObject",
                params=["name", "position", "rotation", "scale"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="destroy",
                description="Delete a GameObject from the scene",
                params=["name"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="find",
                description="Find GameObjects by name, tag, or component type",
                params=["query", "tag", "type"],
            ),
            ActionDescriptor(
                name="build_room",
                description="Build a room with 4 walls and floor",
                params=["name", "width", "height", "depth", "color"],
            ),

            # --- Materials ---
            ActionDescriptor(
                name="create_material",
                description="Create a PBR material (preset or custom)",
                params=["name", "preset", "color", "metallic", "smoothness"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="set_color",
                description="Set an object's color",
                params=["name", "color"],
                required_params=["name", "color"],
            ),

            # --- Lighting & Environment ---
            ActionDescriptor(
                name="setup_environment",
                description="Apply an environment preset (forest, desert, snow, night, sunset, etc.)",
                params=["preset"],
                required_params=["preset"],
            ),
            ActionDescriptor(
                name="create_light",
                description="Create a light source (Directional/Point/Spot/Area)",
                params=["name", "type", "position", "rotation", "intensity", "color"],
            ),
            ActionDescriptor(name="setup_lighting", description="Set up standard 3-point lighting"),

            # --- C# Scripting ---
            ActionDescriptor(
                name="generate_script",
                description="Generate a C# script and deploy it to the project",
                params=["class_name", "script_type", "fields", "methods", "subfolder"],
                required_params=["class_name", "script_type"],
            ),

            # --- Animation ---
            ActionDescriptor(
                name="create_animator",
                description="Create an Animator Controller with states",
                params=["name", "states", "preset"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="create_animation",
                description="Create an animation clip (bob, spin, pulse, custom)",
                params=["name", "type"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="create_virtual_camera",
                description="Create a Cinemachine virtual camera",
                params=["name", "follow", "look_at"],
            ),

            # --- Physics ---
            ActionDescriptor(
                name="add_physics",
                description="Add physics components (Rigidbody, Collider) to an object",
                params=["name", "mass", "gravity", "collider"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="add_joint",
                description="Add a joint between objects (fixed, hinge, spring)",
                params=["name", "type", "connected_to"],
                required_params=["name", "type"],
            ),

            # --- Audio ---
            ActionDescriptor(
                name="add_audio",
                description="Add an AudioSource to an object",
                params=["name", "type", "volume", "spatial", "loop"],
                required_params=["name"],
            ),
            ActionDescriptor(
                name="create_reverb_zone",
                description="Create an audio reverb zone",
                params=["name", "preset", "position"],
            ),

            # --- UI ---
            ActionDescriptor(
                name="create_ui",
                description="Create UI elements or complete menus (canvas/panel/text/button/image/slider/input/health_bar/main_menu/pause_menu/dialog)",
                params=["type", "name", "text", "parent"],
                required_params=["type"],
            ),

            # --- Terrain ---
            ActionDescriptor(
                name="create_terrain",
                description="Create a Unity terrain",
                params=["name", "width", "height", "length"],
            ),
            ActionDescriptor(
                name="setup_outdoor",
                description="Set up a complete outdoor scene with terrain and environment",
                params=["preset", "size"],
            ),
            ActionDescriptor(
                name="setup_indoor",
                description="Set up an indoor scene with room and lighting",
                params=["width", "height", "depth"],
            ),

            # --- Assets ---
            ActionDescriptor(
                name="import_asset",
                description="Import an external file into the Unity project",
                params=["source", "dest", "type"],
                required_params=["source"],
            ),
            ActionDescriptor(
                name="search_assets",
                description="Search project assets",
                params=["query", "type"],
            ),
            ActionDescriptor(
                name="create_prefab",
                description="Save a scene object as a prefab",
                params=["name", "save_path"],
                required_params=["name"],
            ),

            # --- Build ---
            ActionDescriptor(
                name="build",
                description="Build the Unity project for a target platform",
                params=["platform", "development"],
            ),
            ActionDescriptor(
                name="player_settings",
                description="Configure player settings (resolution, company, version)",
                params=["company_name", "product_name", "version"],
            ),

            # --- Editor Control ---
            ActionDescriptor(name="play", description="Enter Play mode"),
            ActionDescriptor(name="stop", description="Exit Play mode"),
            ActionDescriptor(name="pause", description="Toggle pause in Play mode"),
            ActionDescriptor(name="undo", description="Undo last operation"),
            ActionDescriptor(name="redo", description="Redo last operation"),
            ActionDescriptor(
                name="screenshot",
                description="Capture a screenshot from the game camera",
                params=["output_path", "width", "height"],
            ),
            ActionDescriptor(name="launch", description="Launch Unity Editor with the current project"),
            ActionDescriptor(name="shutdown", description="Close the Unity Editor"),
        ]

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def health_check(self) -> ComponentResult:
        start = time.time()
        try:
            from apps.unity_toolkit.unity_discovery import find_unity_installations
            installations = find_unity_installations()

            unity = self._get_unity()
            bridge_ready = unity.is_ready()

            return ComponentResult(
                status="ok" if installations else "degraded",
                output={
                    "installations": len(installations),
                    "versions": [i["version"] for i in installations[:5]],
                    "bridge_connected": bridge_ready,
                },
                duration=time.time() - start,
                summary=f"Unity: {len(installations)} install(s), bridge={'connected' if bridge_ready else 'disconnected'}",
            )
        except Exception as e:
            return ComponentResult(
                status="error",
                error=str(e),
                duration=time.time() - start,
            )

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, action: str, params: Optional[Dict] = None) -> ComponentResult:
        params = params or {}
        start = time.time()

        try:
            if action == "discover":
                return self._discover(params)
            elif action == "create_project":
                return self._create_project(params)
            elif action == "open_project":
                return self._open_project(params)
            elif action == "project_info":
                return self._project_info(params)
            elif action == "new_scene":
                return self._new_scene(params)
            elif action == "save_scene":
                return self._save_scene(params)
            elif action == "scene_info":
                return self._scene_info(params)
            elif action == "spawn":
                return self._spawn(params)
            elif action == "transform":
                return self._transform(params)
            elif action == "destroy":
                return self._destroy(params)
            elif action == "find":
                return self._find(params)
            elif action == "build_room":
                return self._build_room(params)
            elif action == "create_material":
                return self._create_material(params)
            elif action == "set_color":
                return self._set_color(params)
            elif action == "setup_environment":
                return self._setup_environment(params)
            elif action == "create_light":
                return self._create_light(params)
            elif action == "setup_lighting":
                return self._setup_lighting(params)
            elif action == "generate_script":
                return self._generate_script(params)
            elif action == "create_animator":
                return self._create_animator(params)
            elif action == "create_animation":
                return self._create_animation(params)
            elif action == "create_virtual_camera":
                return self._create_virtual_camera(params)
            elif action == "add_physics":
                return self._add_physics(params)
            elif action == "add_joint":
                return self._add_joint(params)
            elif action == "add_audio":
                return self._add_audio(params)
            elif action == "create_reverb_zone":
                return self._create_reverb_zone(params)
            elif action == "create_ui":
                return self._create_ui(params)
            elif action == "create_terrain":
                return self._create_terrain(params)
            elif action == "setup_outdoor":
                return self._setup_outdoor(params)
            elif action == "setup_indoor":
                return self._setup_indoor(params)
            elif action == "import_asset":
                return self._import_asset(params)
            elif action == "search_assets":
                return self._search_assets(params)
            elif action == "create_prefab":
                return self._create_prefab(params)
            elif action == "build":
                return self._build(params)
            elif action == "player_settings":
                return self._player_settings(params)
            elif action == "play":
                return self._wrap(self._get_unity().play())
            elif action == "stop":
                return self._wrap(self._get_unity().stop())
            elif action == "pause":
                return self._wrap(self._get_unity().pause())
            elif action == "undo":
                return self._wrap(self._get_unity().undo())
            elif action == "redo":
                return self._wrap(self._get_unity().redo())
            elif action == "screenshot":
                return self._screenshot(params)
            elif action == "launch":
                return self._launch(params)
            elif action == "shutdown":
                return self._shutdown()
            else:
                return ComponentResult(status="failed", error=f"Unknown action: {action}")
        except Exception as e:
            _log.error("Unity action '%s' failed: %s", action, e, exc_info=True)
            return ComponentResult(
                status="failed",
                error=str(e),
                duration=time.time() - start,
            )

    # ------------------------------------------------------------------
    # Action Implementations
    # ------------------------------------------------------------------

    def _wrap(self, result: Dict) -> ComponentResult:
        """Wrap a raw IPC result dict into a ComponentResult."""
        return ComponentResult(
            status="ok" if result.get("success") else "failed",
            output=result.get("data", {}),
            error=result.get("error", ""),
            duration=result.get("duration", 0),
        )

    def _discover(self, params: Dict) -> ComponentResult:
        from apps.unity_toolkit.unity_discovery import find_unity_installations, find_projects
        installations = find_unity_installations()
        projects = find_projects(params.get("search_dirs"))
        return ComponentResult(
            status="ok",
            output={
                "installations": [{"version": i["version"], "path": i["path"]} for i in installations],
                "projects": [{"name": p["name"], "path": p["path"], "version": p.get("version", "")} for p in projects],
            },
            summary=f"Found {len(installations)} Unity install(s) and {len(projects)} project(s)",
        )

    def _create_project(self, params: Dict) -> ComponentResult:
        from apps.unity_toolkit.unity_project import create_onyx_project
        name = params.get("name", "OnyxWorkspace")
        pipeline = params.get("render_pipeline", "urp")
        root = params.get("root_dir")
        project = create_onyx_project(name, root, pipeline)
        self._project = project
        return ComponentResult(
            status="ok",
            output=project.get_info(),
            summary=f"Created Unity project '{name}' with {pipeline.upper()} pipeline",
        )

    def _open_project(self, params: Dict) -> ComponentResult:
        from apps.unity_toolkit.unity_project import UnityProject
        path = params["path"]
        project = UnityProject(path)
        version = params.get("version")
        success = project.open_in_editor(version=version)
        self._project = project
        return ComponentResult(
            status="ok" if success else "failed",
            output=project.get_info(),
            error="" if success else "Failed to open or connect to Unity Editor",
            summary=f"{'Opened' if success else 'Failed to open'} Unity project: {project.project_name}",
        )

    def _project_info(self, params: Dict) -> ComponentResult:
        if self._project:
            return ComponentResult(status="ok", output=self._project.get_info())
        # Try to get info from bridge
        info = self._get_unity().client.get_editor_info()
        return ComponentResult(
            status="ok" if info else "failed",
            output=info or {},
            error="" if info else "No project connected",
        )

    def _new_scene(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().new_scene())

    def _save_scene(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().save_scene())

    def _scene_info(self, params: Dict) -> ComponentResult:
        unity = self._get_unity()
        info = unity.get_scene_info()
        hierarchy = unity.get_hierarchy()
        return ComponentResult(
            status="ok" if info.get("success") else "failed",
            output={
                "scene": info.get("data", {}),
                "hierarchy": hierarchy.get("data", {}),
            },
        )

    def _spawn(self, params: Dict) -> ComponentResult:
        unity = self._get_unity()
        name = params.get("name", "Object")
        obj_type = params.get("type", "Cube")
        pos = tuple(params["position"]) if "position" in params else None
        rot = tuple(params["rotation"]) if "rotation" in params else None
        scale = tuple(params["scale"]) if "scale" in params else None
        color = params.get("color")

        if obj_type.lower() == "empty":
            result = unity.spawn_empty(name, position=pos, rotation=rot)
        else:
            result = unity.spawn_primitive(name, obj_type,
                                           position=pos, rotation=rot,
                                           scale=scale, color=color)
        return self._wrap(result)

    def _transform(self, params: Dict) -> ComponentResult:
        name = params["name"]
        pos = tuple(params["position"]) if "position" in params else None
        rot = tuple(params["rotation"]) if "rotation" in params else None
        scale = tuple(params["scale"]) if "scale" in params else None
        return self._wrap(self._get_unity().set_transform(name, pos, rot, scale))

    def _destroy(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().destroy(params["name"]))

    def _find(self, params: Dict) -> ComponentResult:
        unity = self._get_unity()
        if "tag" in params:
            return self._wrap(unity.find_by_tag(params["tag"]))
        elif "type" in params:
            return self._wrap(unity.find_by_type(params["type"]))
        else:
            return self._wrap(unity.find(params.get("query", "")))

    def _build_room(self, params: Dict) -> ComponentResult:
        unity = self._get_unity()
        result = unity.build_room(
            params.get("name", "Room"),
            width=float(params.get("width", 10)),
            height=float(params.get("height", 3)),
            depth=float(params.get("depth", 10)),
            color=params.get("color", "white"),
        )
        return self._wrap(result)

    def _create_material(self, params: Dict) -> ComponentResult:
        shader = self._get_shader()
        preset = params.get("preset")
        name = params.get("name", "NewMaterial")
        if preset:
            result = shader.create_material_from_preset(name, preset)
        else:
            result = shader.create_material(
                name,
                color=params.get("color", "white"),
                metallic=float(params.get("metallic", 0)),
                smoothness=float(params.get("smoothness", 0.5)),
            )
        return self._wrap(result)

    def _set_color(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().set_color(params["name"], params["color"]))

    def _setup_environment(self, params: Dict) -> ComponentResult:
        terrain = self._get_terrain()
        preset = params.get("preset", "default")
        success = terrain.apply_environment(preset)
        return ComponentResult(
            status="ok" if success else "failed",
            output={"preset": preset},
            error="" if success else f"Unknown preset: {preset}",
            summary=f"Applied {preset} environment",
        )

    def _create_light(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().create_light(
            name=params.get("name", "Light"),
            light_type=params.get("type", "Point"),
            position=tuple(params["position"]) if "position" in params else None,
            rotation=tuple(params["rotation"]) if "rotation" in params else None,
            intensity=float(params.get("intensity", 1.0)),
            color=params.get("color", "white"),
        ))

    def _setup_lighting(self, params: Dict) -> ComponentResult:
        self._get_unity().setup_basic_lighting()
        return ComponentResult(status="ok", summary="Set up 3-point lighting")

    def _generate_script(self, params: Dict) -> ComponentResult:
        writer = self._get_scripting()
        if not writer:
            return ComponentResult(status="failed", error="No active Unity project")

        class_name = params["class_name"]
        script_type = params["script_type"]
        subfolder = params.get("subfolder", "")

        kwargs = {}
        if "fields" in params:
            kwargs["fields"] = params["fields"]
        if "methods" in params:
            kwargs["methods"] = params["methods"]
        if "states" in params:
            kwargs["states"] = params["states"]

        filepath = writer.generate_and_write(script_type, class_name, subfolder, **kwargs)
        return ComponentResult(
            status="ok",
            output={"path": filepath, "class": class_name, "type": script_type},
            artifact_paths=[filepath],
            artifact_type="csharp",
            summary=f"Generated {script_type} script: {class_name}.cs",
        )

    def _create_animator(self, params: Dict) -> ComponentResult:
        anim = self._get_animation()
        name = params["name"]
        preset = params.get("preset")
        states = params.get("states")

        if preset and not states:
            from apps.unity_toolkit.unity_animation import ANIMATION_STATES
            states = ANIMATION_STATES.get(preset)

        result = anim.create_animator_controller(name, states=states)
        return self._wrap(result)

    def _create_animation(self, params: Dict) -> ComponentResult:
        anim = self._get_animation()
        name = params["name"]
        anim_type = params.get("type", "bob")

        if anim_type == "bob":
            result = anim.create_bob_animation(name)
        elif anim_type == "spin":
            result = anim.create_spin_animation(name)
        elif anim_type == "pulse":
            result = anim.create_pulse_animation(name)
        else:
            result = anim.create_animation_clip(name)
        return self._wrap(result)

    def _create_virtual_camera(self, params: Dict) -> ComponentResult:
        anim = self._get_animation()
        return self._wrap(anim.create_virtual_camera(
            name=params.get("name", "VirtualCamera"),
            follow_target=params.get("follow", ""),
            look_at_target=params.get("look_at", ""),
        ))

    def _add_physics(self, params: Dict) -> ComponentResult:
        physics = self._get_physics()
        name = params["name"]
        # Add Rigidbody
        physics.add_rigidbody(
            name,
            mass=float(params.get("mass", 1)),
            gravity=params.get("gravity", True),
        )
        # Add Collider if specified
        collider_type = params.get("collider")
        if collider_type:
            self._get_unity().add_collider(name, collider_type)

        return ComponentResult(
            status="ok",
            output={"name": name},
            summary=f"Added physics to {name}",
        )

    def _add_joint(self, params: Dict) -> ComponentResult:
        physics = self._get_physics()
        name = params["name"]
        joint_type = params.get("type", "fixed")
        connected = params.get("connected_to", "")

        if joint_type == "fixed":
            result = physics.add_fixed_joint(name, connected)
        elif joint_type == "hinge":
            result = physics.add_hinge_joint(name, connected)
        elif joint_type == "spring":
            result = physics.add_spring_joint(name, connected)
        else:
            return ComponentResult(status="failed", error=f"Unknown joint type: {joint_type}")
        return self._wrap(result)

    def _add_audio(self, params: Dict) -> ComponentResult:
        audio = self._get_audio()
        name = params["name"]
        audio_type = params.get("type", "source")

        if audio_type == "ambient":
            result = audio.create_ambient_source(
                name, volume=float(params.get("volume", 0.5)))
        elif audio_type == "music":
            result = audio.create_music_source(
                name, volume=float(params.get("volume", 0.7)))
        else:
            result = audio.add_audio_source(
                name,
                volume=float(params.get("volume", 1.0)),
                spatial_blend=float(params.get("spatial", 0.0)),
                loop=params.get("loop", False),
            )
        return self._wrap(result)

    def _create_reverb_zone(self, params: Dict) -> ComponentResult:
        audio = self._get_audio()
        pos = tuple(params.get("position", [0, 0, 0]))
        return self._wrap(audio.create_reverb_zone(
            params.get("name", "ReverbZone"),
            position=pos,
            preset=params.get("preset", "room"),
        ))

    def _create_ui(self, params: Dict) -> ComponentResult:
        ui = self._get_ui()
        ui_type = params.get("type", "text")
        name = params.get("name", "UIElement")
        parent = params.get("parent", "Canvas")
        text = params.get("text", "")

        if ui_type == "canvas":
            return self._wrap(ui.create_canvas(name))
        elif ui_type == "panel":
            return self._wrap(ui.create_panel(name, parent))
        elif ui_type == "text":
            return self._wrap(ui.create_text(name, parent, text=text or "Hello World"))
        elif ui_type == "button":
            return self._wrap(ui.create_button(name, parent, text=text or "Click"))
        elif ui_type == "image":
            return self._wrap(ui.create_image(name, parent))
        elif ui_type == "slider":
            return self._wrap(ui.create_slider(name, parent))
        elif ui_type == "input":
            return self._wrap(ui.create_input_field(name, parent))
        elif ui_type == "health_bar":
            return self._wrap(ui.create_health_bar(name, parent))
        elif ui_type == "main_menu":
            ui.create_main_menu(
                title=params.get("title", "My Game"),
                buttons=params.get("buttons"))
            return ComponentResult(status="ok", summary="Created main menu")
        elif ui_type == "pause_menu":
            ui.create_pause_menu()
            return ComponentResult(status="ok", summary="Created pause menu")
        elif ui_type == "dialog":
            ui.create_dialog_box(
                title=params.get("title", "Dialog"),
                message=text or "Are you sure?")
            return ComponentResult(status="ok", summary="Created dialog box")
        else:
            return ComponentResult(status="failed", error=f"Unknown UI type: {ui_type}")

    def _create_terrain(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().create_terrain(
            name=params.get("name", "Terrain"),
            width=float(params.get("width", 500)),
            height=float(params.get("height", 100)),
            length=float(params.get("length", 500)),
        ))

    def _setup_outdoor(self, params: Dict) -> ComponentResult:
        terrain = self._get_terrain()
        terrain.setup_outdoor_scene(
            preset=params.get("preset", "forest"),
            terrain_size=float(params.get("size", 200)),
        )
        return ComponentResult(status="ok", summary="Set up outdoor scene")

    def _setup_indoor(self, params: Dict) -> ComponentResult:
        terrain = self._get_terrain()
        terrain.setup_indoor_scene(
            room_size=(
                float(params.get("width", 10)),
                float(params.get("height", 3)),
                float(params.get("depth", 10)),
            ),
        )
        return ComponentResult(status="ok", summary="Set up indoor scene")

    def _import_asset(self, params: Dict) -> ComponentResult:
        assets = self._get_assets()
        if not assets:
            return ComponentResult(status="failed", error="No active Unity project")

        source = params["source"]
        dest = params.get("dest", "Assets/Imported")
        result = assets.import_file(source, dest)
        return self._wrap(result)

    def _search_assets(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().search_assets(
            params.get("query", ""),
            params.get("type", ""),
        ))

    def _create_prefab(self, params: Dict) -> ComponentResult:
        return self._wrap(self._get_unity().create_prefab(
            params["name"],
            params.get("save_path", ""),
        ))

    def _build(self, params: Dict) -> ComponentResult:
        build = self._get_build()
        if not build:
            return ComponentResult(status="failed", error="No active Unity project")

        result = build.build(
            platform=params.get("platform", "windows"),
            development=params.get("development", False),
        )
        return self._wrap(result)

    def _player_settings(self, params: Dict) -> ComponentResult:
        build = self._get_build()
        if not build:
            return ComponentResult(status="failed", error="No active Unity project")

        result = build.set_player_settings(
            company_name=params.get("company_name", ""),
            product_name=params.get("product_name", ""),
            version=params.get("version", ""),
        )
        return self._wrap(result)

    def _screenshot(self, params: Dict) -> ComponentResult:
        result = self._get_unity().screenshot(
            output_path=params.get("output_path", ""),
            width=int(params.get("width", 1920)),
            height=int(params.get("height", 1080)),
        )
        return ComponentResult(
            status="ok" if result.get("success") else "failed",
            output=result.get("data", {}),
            artifact_paths=[result.get("data", {}).get("path", "")],
            artifact_type="image",
        )

    def _launch(self, params: Dict) -> ComponentResult:
        if self._project:
            success = self._project.open_in_editor()
            return ComponentResult(
                status="ok" if success else "failed",
                summary="Launched Unity Editor" if success else "Failed to launch",
            )
        return ComponentResult(status="failed", error="No project configured. Use open_project first.")

    def _shutdown(self) -> ComponentResult:
        if self._project:
            self._project.quit_editor()
            return ComponentResult(status="ok", summary="Unity Editor shutdown requested")
        unity = self._get_unity()
        unity.client.quit_editor()
        return ComponentResult(status="ok", summary="Sent quit to Unity bridge")
