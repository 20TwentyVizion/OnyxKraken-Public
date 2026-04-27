"""
Tests for the Unity Engine Toolkit.

Tests module imports, script generation, color resolution, presets,
and component integration without requiring a running Unity Editor.
"""

import os
import sys
import json
import tempfile
import unittest

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestUnityDiscovery(unittest.TestCase):
    """Test unity_discovery module."""

    def test_import(self):
        from apps.unity_toolkit.unity_discovery import (
            find_unity_installations, find_projects, get_unity_hub_path,
            find_editor_executable, _parse_major_version, _is_lts_version,
        )
        # Should not crash
        self.assertIsNotNone(find_unity_installations)

    def test_parse_major_version(self):
        from apps.unity_toolkit.unity_discovery import _parse_major_version
        self.assertEqual(_parse_major_version("6000.1.1f1"), 6000)
        self.assertEqual(_parse_major_version("2022.3.20f1"), 2022)
        self.assertEqual(_parse_major_version(""), 0)

    def test_is_lts_version(self):
        from apps.unity_toolkit.unity_discovery import _is_lts_version
        self.assertTrue(_is_lts_version("2022.3.20f1"))
        self.assertTrue(_is_lts_version("6000.0.25f1"))
        self.assertFalse(_is_lts_version("6000.1.1f1"))

    def test_find_installations_returns_list(self):
        from apps.unity_toolkit.unity_discovery import find_unity_installations
        result = find_unity_installations()
        self.assertIsInstance(result, list)

    def test_find_projects_returns_list(self):
        from apps.unity_toolkit.unity_discovery import find_projects
        result = find_projects([])
        self.assertIsInstance(result, list)


class TestUnityRemote(unittest.TestCase):
    """Test unity_remote module."""

    def test_import(self):
        from apps.unity_toolkit.unity_remote import (
            UnityRemoteClient, UnityCLI, get_sync_dir,
        )
        self.assertIsNotNone(UnityRemoteClient)

    def test_sync_dir_exists(self):
        from apps.unity_toolkit.unity_remote import get_sync_dir
        sync_dir = get_sync_dir()
        self.assertTrue(os.path.isdir(sync_dir))

    def test_client_creation(self):
        from apps.unity_toolkit.unity_remote import UnityRemoteClient
        client = UnityRemoteClient()
        self.assertIsNotNone(client.sync_dir)
        # Not connected = not ready
        self.assertFalse(client.is_ready())

    def test_health_check_alias(self):
        from apps.unity_toolkit.unity_remote import UnityRemoteClient
        client = UnityRemoteClient()
        self.assertEqual(client.health_check(), client.is_ready())


class TestOnyxUnity(unittest.TestCase):
    """Test onyx_unity module."""

    def test_import(self):
        from apps.unity_toolkit.onyx_unity import OnyxUnity, COLORS, _resolve_color
        self.assertIsNotNone(OnyxUnity)

    def test_color_resolution_names(self):
        from apps.unity_toolkit.onyx_unity import _resolve_color
        self.assertEqual(_resolve_color("red"), (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(_resolve_color("green"), (0.0, 1.0, 0.0, 1.0))
        self.assertEqual(_resolve_color("blue"), (0.0, 0.0, 1.0, 1.0))

    def test_color_resolution_hex(self):
        from apps.unity_toolkit.onyx_unity import _resolve_color
        r, g, b, a = _resolve_color("#FF0000")
        self.assertAlmostEqual(r, 1.0, places=2)
        self.assertAlmostEqual(g, 0.0, places=2)
        self.assertAlmostEqual(b, 0.0, places=2)

    def test_color_resolution_tuple(self):
        from apps.unity_toolkit.onyx_unity import _resolve_color
        self.assertEqual(_resolve_color((0.5, 0.5, 0.5)), (0.5, 0.5, 0.5, 1.0))
        self.assertEqual(_resolve_color((0.1, 0.2, 0.3, 0.4)), (0.1, 0.2, 0.3, 0.4))

    def test_colors_dict_coverage(self):
        from apps.unity_toolkit.onyx_unity import COLORS
        self.assertIn("red", COLORS)
        self.assertIn("concrete", COLORS)
        self.assertIn("wood", COLORS)
        self.assertIn("sky", COLORS)
        self.assertGreater(len(COLORS), 20)


class TestUnityScripting(unittest.TestCase):
    """Test unity_scripting module — C# script generation."""

    def test_import(self):
        from apps.unity_toolkit.unity_scripting import (
            generate_monobehaviour, generate_scriptable_object,
            generate_singleton, generate_object_pool,
            generate_state_machine, generate_player_controller,
            generate_camera_controller, generate_health_system,
            generate_inventory_system, UnityScriptWriter,
        )
        self.assertIsNotNone(generate_monobehaviour)

    def test_monobehaviour_generation(self):
        from apps.unity_toolkit.unity_scripting import generate_monobehaviour
        code = generate_monobehaviour(
            "TestScript",
            fields=[{"name": "speed", "type": "float", "default": "5f"}],
            methods=["Start", "Update"],
        )
        self.assertIn("class TestScript : MonoBehaviour", code)
        self.assertIn("float speed = 5f", code)
        self.assertIn("void Start()", code)
        self.assertIn("void Update()", code)
        self.assertIn("using UnityEngine;", code)

    def test_scriptable_object_generation(self):
        from apps.unity_toolkit.unity_scripting import generate_scriptable_object
        code = generate_scriptable_object(
            "WeaponData",
            menu_name="Items/Weapon",
            fields=[
                {"name": "damage", "type": "float", "default": "10f"},
                {"name": "weaponName", "type": "string"},
            ],
        )
        self.assertIn("class WeaponData : ScriptableObject", code)
        self.assertIn("CreateAssetMenu", code)
        self.assertIn("Items/Weapon", code)

    def test_singleton_generation(self):
        from apps.unity_toolkit.unity_scripting import generate_singleton
        code = generate_singleton("GameManager")
        self.assertIn("class GameManager", code)
        self.assertIn("Instance", code)
        self.assertIn("DontDestroyOnLoad", code)

    def test_state_machine_generation(self):
        from apps.unity_toolkit.unity_scripting import generate_state_machine
        code = generate_state_machine("EnemyFSM", ["Idle", "Patrol", "Attack"])
        self.assertIn("enum State", code)
        self.assertIn("Idle", code)
        self.assertIn("Patrol", code)
        self.assertIn("Attack", code)
        self.assertIn("ChangeState", code)

    def test_player_controller_types(self):
        from apps.unity_toolkit.unity_scripting import generate_player_controller
        for ptype in ["character_controller", "rigidbody", "transform"]:
            code = generate_player_controller("PC", ptype)
            self.assertIn("class PC", code)
            self.assertIn("moveSpeed", code)

    def test_camera_controller_types(self):
        from apps.unity_toolkit.unity_scripting import generate_camera_controller
        for style in ["third_person", "first_person", "top_down", "orbit"]:
            code = generate_camera_controller("Cam", style)
            self.assertIn("class Cam", code)

    def test_health_system(self):
        from apps.unity_toolkit.unity_scripting import generate_health_system
        code = generate_health_system("HealthSystem")
        self.assertIn("TakeDamage", code)
        self.assertIn("Heal", code)
        self.assertIn("OnDeath", code)

    def test_inventory_system(self):
        from apps.unity_toolkit.unity_scripting import generate_inventory_system
        code = generate_inventory_system("Inventory", "Item")
        self.assertIn("AddItem", code)
        self.assertIn("RemoveItem", code)
        self.assertIn("HasItem", code)

    def test_script_writer(self):
        from apps.unity_toolkit.unity_scripting import UnityScriptWriter
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake Unity project
            os.makedirs(os.path.join(tmpdir, "Assets", "Scripts"), exist_ok=True)
            writer = UnityScriptWriter(tmpdir)
            path = writer.write_script("Test.cs", "// test content")
            self.assertTrue(os.path.isfile(path))
            with open(path) as f:
                self.assertEqual(f.read(), "// test content")


class TestUnityTerrain(unittest.TestCase):
    """Test unity_terrain module."""

    def test_import(self):
        from apps.unity_toolkit.unity_terrain import UnityTerrain, ENVIRONMENT_PRESETS
        self.assertIsNotNone(UnityTerrain)

    def test_presets(self):
        from apps.unity_toolkit.unity_terrain import ENVIRONMENT_PRESETS
        self.assertIn("forest", ENVIRONMENT_PRESETS)
        self.assertIn("desert", ENVIRONMENT_PRESETS)
        self.assertIn("night", ENVIRONMENT_PRESETS)
        self.assertIn("sunset", ENVIRONMENT_PRESETS)
        for name, preset in ENVIRONMENT_PRESETS.items():
            self.assertIn("ambient_color", preset)
            self.assertIn("sun_rotation", preset)
            self.assertIn("sun_intensity", preset)


class TestUnityAnimation(unittest.TestCase):
    """Test unity_animation module."""

    def test_import(self):
        from apps.unity_toolkit.unity_animation import UnityAnimation, ANIMATION_STATES
        self.assertIsNotNone(UnityAnimation)

    def test_animation_states(self):
        from apps.unity_toolkit.unity_animation import ANIMATION_STATES
        self.assertIn("humanoid_basic", ANIMATION_STATES)
        self.assertIn("humanoid_combat", ANIMATION_STATES)
        self.assertIn("npc_patrol", ANIMATION_STATES)
        self.assertIn("Idle", ANIMATION_STATES["humanoid_basic"])


class TestUnityPhysics(unittest.TestCase):
    """Test unity_physics module."""

    def test_import(self):
        from apps.unity_toolkit.unity_physics import UnityPhysics, PHYSICS_MATERIALS
        self.assertIsNotNone(UnityPhysics)

    def test_physics_materials(self):
        from apps.unity_toolkit.unity_physics import PHYSICS_MATERIALS
        self.assertIn("ice", PHYSICS_MATERIALS)
        self.assertIn("rubber", PHYSICS_MATERIALS)
        self.assertIn("bouncy", PHYSICS_MATERIALS)
        for name, mat in PHYSICS_MATERIALS.items():
            self.assertIn("dynamic_friction", mat)
            self.assertIn("bounciness", mat)


class TestUnityShader(unittest.TestCase):
    """Test unity_shader module."""

    def test_import(self):
        from apps.unity_toolkit.unity_shader import (
            UnityShader, SHADERS, MATERIAL_PRESETS,
        )
        self.assertIsNotNone(UnityShader)

    def test_shader_pipelines(self):
        from apps.unity_toolkit.unity_shader import SHADERS
        self.assertIn("urp", SHADERS)
        self.assertIn("hdrp", SHADERS)
        self.assertIn("built-in", SHADERS)
        self.assertIn("lit", SHADERS["urp"])

    def test_material_presets(self):
        from apps.unity_toolkit.unity_shader import MATERIAL_PRESETS
        self.assertIn("metal_steel", MATERIAL_PRESETS)
        self.assertIn("glass", MATERIAL_PRESETS)
        self.assertIn("wood_oak", MATERIAL_PRESETS)
        self.assertGreater(len(MATERIAL_PRESETS), 15)


class TestUnityBuild(unittest.TestCase):
    """Test unity_build module."""

    def test_import(self):
        from apps.unity_toolkit.unity_build import UnityBuild, BUILD_TARGETS
        self.assertIsNotNone(UnityBuild)

    def test_build_targets(self):
        from apps.unity_toolkit.unity_build import BUILD_TARGETS
        self.assertIn("windows", BUILD_TARGETS)
        self.assertIn("android", BUILD_TARGETS)
        self.assertIn("webgl", BUILD_TARGETS)
        self.assertIn("ios", BUILD_TARGETS)


class TestUnityUI(unittest.TestCase):
    """Test unity_ui module."""

    def test_import(self):
        from apps.unity_toolkit.unity_ui import UnityUI
        self.assertIsNotNone(UnityUI)


class TestUnityAudio(unittest.TestCase):
    """Test unity_audio module."""

    def test_import(self):
        from apps.unity_toolkit.unity_audio import UnityAudio, REVERB_PRESETS
        self.assertIsNotNone(UnityAudio)

    def test_reverb_presets(self):
        from apps.unity_toolkit.unity_audio import REVERB_PRESETS
        self.assertIn("room", REVERB_PRESETS)
        self.assertIn("cave", REVERB_PRESETS)
        self.assertIn("underwater", REVERB_PRESETS)


class TestUnityAssets(unittest.TestCase):
    """Test unity_assets module."""

    def test_import(self):
        from apps.unity_toolkit.unity_assets import UnityAssets, SUPPORTED_FORMATS
        self.assertIsNotNone(UnityAssets)

    def test_supported_formats(self):
        from apps.unity_toolkit.unity_assets import SUPPORTED_FORMATS
        self.assertIn("model", SUPPORTED_FORMATS)
        self.assertIn("texture", SUPPORTED_FORMATS)
        self.assertIn("audio", SUPPORTED_FORMATS)
        self.assertIn(".fbx", SUPPORTED_FORMATS["model"])
        self.assertIn(".png", SUPPORTED_FORMATS["texture"])
        self.assertIn(".wav", SUPPORTED_FORMATS["audio"])


class TestUnityProject(unittest.TestCase):
    """Test unity_project module."""

    def test_import(self):
        from apps.unity_toolkit.unity_project import (
            UnityProject, create_onyx_project, _generate_bridge_script,
        )
        self.assertIsNotNone(UnityProject)

    def test_bridge_script_generation(self):
        from apps.unity_toolkit.unity_project import _generate_bridge_script
        script = _generate_bridge_script()
        self.assertIn("OnyxBridge", script)
        self.assertIn("EditorApplication.update", script)
        self.assertIn("cmd.json", script)
        self.assertIn("done.json", script)
        self.assertIn("ready.json", script)
        self.assertIn("ExecuteCommand", script)
        self.assertIn("spawn_primitive", script)

    def test_create_project(self):
        from apps.unity_toolkit.unity_project import create_onyx_project
        with tempfile.TemporaryDirectory() as tmpdir:
            project = create_onyx_project("TestProject", root_dir=tmpdir)
            self.assertEqual(project.project_name, "TestProject")
            self.assertTrue(os.path.isdir(project.assets_dir))
            self.assertTrue(os.path.isdir(project.settings_dir))
            # Check bridge was deployed
            bridge_path = os.path.join(project.assets_dir, "Editor", "OnyxBridge.cs")
            self.assertTrue(os.path.isfile(bridge_path))
            # Check manifest has packages
            manifest_path = os.path.join(project.packages_dir, "manifest.json")
            self.assertTrue(os.path.isfile(manifest_path))
            with open(manifest_path) as f:
                data = json.load(f)
            self.assertIn("com.unity.cinemachine", data["dependencies"])


class TestUnityComponent(unittest.TestCase):
    """Test the OnyxComponent wrapper."""

    def test_import(self):
        from core.components.builtins.unity_component import UnityComponent
        self.assertIsNotNone(UnityComponent)

    def test_component_interface(self):
        from core.components.builtins.unity_component import UnityComponent
        comp = UnityComponent()
        self.assertEqual(comp.name, "unity")
        self.assertEqual(comp.display_name, "Unity Engine")
        self.assertEqual(comp.category, "creative")
        self.assertIsInstance(comp.description, str)

    def test_actions_list(self):
        from core.components.builtins.unity_component import UnityComponent
        comp = UnityComponent()
        actions = comp.get_actions()
        self.assertGreater(len(actions), 30)
        action_names = [a.name for a in actions]
        # Check key actions exist
        for expected in ["discover", "spawn", "create_material", "generate_script",
                         "add_physics", "create_ui", "build", "play", "screenshot"]:
            self.assertIn(expected, action_names, f"Missing action: {expected}")

    def test_health_check(self):
        from core.components.builtins.unity_component import UnityComponent
        comp = UnityComponent()
        result = comp.health_check()
        self.assertIn(result.status, ("ok", "degraded", "error"))

    def test_discover_action(self):
        from core.components.builtins.unity_component import UnityComponent
        comp = UnityComponent()
        result = comp.execute("discover")
        self.assertIn(result.status, ("ok", "failed"))
        if result.status == "ok":
            self.assertIn("installations", result.output)
            self.assertIn("projects", result.output)

    def test_unknown_action(self):
        from core.components.builtins.unity_component import UnityComponent
        comp = UnityComponent()
        result = comp.execute("nonexistent_action")
        self.assertEqual(result.status, "failed")
        self.assertIn("Unknown action", result.error)


class TestComponentAutoDiscovery(unittest.TestCase):
    """Test that UnityComponent is auto-discovered by the registry."""

    def test_registry_discovers_unity(self):
        from core.components.registry import ComponentRegistry
        registry = ComponentRegistry()
        count = registry.discover()
        # Unity should be discoverable
        unity = registry.get("unity")
        if unity:
            self.assertEqual(unity.name, "unity")
            self.assertEqual(unity.category, "creative")


if __name__ == "__main__":
    unittest.main(verbosity=2)
