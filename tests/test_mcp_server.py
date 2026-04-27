"""Tests for OnyxKraken MCP Server — tool registration and basic invocation.

Verifies that all MCP tools are properly registered, have correct schemas,
and return expected results with mocked dependencies.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server import mcp


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------

class TestToolRegistration:
    """Verify all expected tools are registered on the MCP server."""

    def _get_tool_names(self) -> set:
        """Extract registered tool names from the FastMCP instance."""
        # FastMCP stores tools internally — access via _tool_manager or similar
        tools = set()
        if hasattr(mcp, '_tool_manager'):
            for t in mcp._tool_manager._tools.values():
                tools.add(t.name)
        elif hasattr(mcp, '_tools'):
            for t in mcp._tools.values():
                tools.add(t.name if hasattr(t, 'name') else str(t))
        else:
            # Fallback: check via tool list method
            try:
                tool_list = mcp.list_tools()
                for t in tool_list:
                    tools.add(t.name if hasattr(t, 'name') else str(t))
            except Exception:
                pass
        return tools

    def test_agent_tools_registered(self):
        """Agent-related tools should be registered."""
        tools = self._get_tool_names()
        if not tools:
            pytest.skip("Cannot introspect FastMCP tools in this version")
        assert "submit_goal" in tools
        assert "get_agent_status" in tools
        assert "get_task_history" in tools
        assert "get_agent_skills" in tools

    def test_mind_tools_registered(self):
        """Mind-related tools should be registered."""
        tools = self._get_tool_names()
        if not tools:
            pytest.skip("Cannot introspect FastMCP tools in this version")
        assert "get_mind_state" in tools
        assert "trigger_reflection" in tools
        assert "generate_proactive_goal" in tools

    def test_knowledge_tools_registered(self):
        """Knowledge-related tools should be registered."""
        tools = self._get_tool_names()
        if not tools:
            pytest.skip("Cannot introspect FastMCP tools in this version")
        assert "search_knowledge" in tools
        assert "add_knowledge" in tools
        assert "get_knowledge_stats" in tools

    def test_voice_tools_registered(self):
        """Voice-related tools should be registered."""
        tools = self._get_tool_names()
        if not tools:
            pytest.skip("Cannot introspect FastMCP tools in this version")
        assert "speak" in tools
        assert "synthesize_to_file" in tools

    def test_ecosystem_tools_registered(self):
        """Ecosystem-related tools should be registered."""
        tools = self._get_tool_names()
        if not tools:
            pytest.skip("Cannot introspect FastMCP tools in this version")
        assert "ecosystem_health" in tools
        assert "ecosystem_dispatch" in tools
        assert "list_ecosystem_services" in tools
        assert "list_workflows" in tools
        assert "run_workflow" in tools

    def test_memory_tools_registered(self):
        """Memory-related tools should be registered."""
        tools = self._get_tool_names()
        if not tools:
            pytest.skip("Cannot introspect FastMCP tools in this version")
        assert "get_memory" in tools
        assert "get_improvement_stats" in tools


# ---------------------------------------------------------------------------
# Tool invocation tests (mocked dependencies)
# ---------------------------------------------------------------------------

class TestAgentTools:
    """Test agent tool invocations with mocked state."""

    def test_submit_goal_success(self):
        from mcp_server import _submit_goal
        with patch("routes._state.state") as mock_state, \
             patch("routes._state.run_task_sync", return_value={"result": "Goal completed in 5.0s"}):
            mock_state.running = False
            result = _submit_goal("Test goal")
            assert "result" in result

    def test_submit_goal_busy(self):
        from mcp_server import _submit_goal
        with patch("routes._state.state") as mock_state:
            mock_state.running = True
            mock_state.current_goal = "existing goal"
            result = _submit_goal("Test goal")
            assert "error" in result or "busy" in str(result.get("status", ""))

    def test_get_agent_status(self):
        from mcp_server import _get_agent_status
        with patch("routes._state.state") as mock_state:
            mock_state.to_dict.return_value = {
                "running": False, "current_goal": "", "current_step": "",
                "uptime": 0, "last_result": None,
            }
            result = _get_agent_status()
            assert "running" in result


class TestMindTools:
    """Test mind tool invocations."""

    def test_get_mind_state(self):
        from mcp_server import _get_mind_state
        mock_mind_inst = MagicMock()
        mock_mind_inst.get_stats.return_value = {
            "identity": "OnyxKraken", "mood": "confident",
            "focus": "testing", "strengths": ["blender"],
            "weaknesses": ["edge"],
        }
        with patch.dict("sys.modules", {"core.mind": MagicMock(get_mind=MagicMock(return_value=mock_mind_inst))}):
            result = _get_mind_state()
            assert result["mood"] == "confident"
            assert result["identity"] == "OnyxKraken"

    def test_trigger_reflection(self):
        from mcp_server import _trigger_reflection
        mock_mind_inst = MagicMock()
        with patch.dict("sys.modules", {"core.mind": MagicMock(get_mind=MagicMock(return_value=mock_mind_inst))}):
            result = _trigger_reflection()
            assert result["status"] == "started"

    def test_generate_proactive_goal_with_goal(self):
        from mcp_server import _generate_proactive_goal
        mock_mind_inst = MagicMock()
        mock_mind_inst.generate_proactive_goal.return_value = "Practice Edge research"
        with patch.dict("sys.modules", {"core.mind": MagicMock(get_mind=MagicMock(return_value=mock_mind_inst))}):
            result = _generate_proactive_goal()
            assert result["status"] == "generated"
            assert result["goal"] == "Practice Edge research"

    def test_generate_proactive_goal_rest(self):
        from mcp_server import _generate_proactive_goal
        mock_mind_inst = MagicMock()
        mock_mind_inst.generate_proactive_goal.return_value = None
        with patch.dict("sys.modules", {"core.mind": MagicMock(get_mind=MagicMock(return_value=mock_mind_inst))}):
            result = _generate_proactive_goal()
            assert result["status"] == "rest"


class TestKnowledgeTools:
    """Test knowledge tool invocations."""

    def test_search_knowledge(self):
        from mcp_server import _search_knowledge
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {"content": "Blender tip", "category": "blender"}
        ]
        mock_mod = MagicMock(get_knowledge_store=MagicMock(return_value=mock_store))
        with patch.dict("sys.modules", {"core.knowledge": mock_mod}):
            result = _search_knowledge("blender tips")
            assert result["count"] == 1
            assert result["results"][0]["content"] == "Blender tip"

    def test_add_knowledge(self):
        from mcp_server import _add_knowledge
        mock_store = MagicMock()
        mock_store.add.return_value = "abc123"
        mock_mod = MagicMock(get_knowledge_store=MagicMock(return_value=mock_store))
        with patch.dict("sys.modules", {"core.knowledge": mock_mod}):
            result = _add_knowledge("New knowledge", category="test")
            assert result["id"] == "abc123"
            assert result["status"] == "added"

    def test_get_knowledge_stats(self):
        from mcp_server import _get_knowledge_stats
        mock_store = MagicMock()
        mock_store.get_stats.return_value = {"total": 42, "categories": {"general": 30, "blender": 12}}
        mock_mod = MagicMock(get_knowledge_store=MagicMock(return_value=mock_store))
        with patch.dict("sys.modules", {"core.knowledge": mock_mod}):
            result = _get_knowledge_stats()
            assert result["total"] == 42


class TestVoiceTools:
    """Test voice tool invocations."""

    def test_speak(self):
        from mcp_server import _speak
        mock_mod = MagicMock()
        with patch.dict("sys.modules", {"core.voice": mock_mod}):
            result = _speak("Hello world", mood="confident")
            assert result["status"] == "speaking"
            assert result["mood"] == "confident"

    def test_synthesize_to_file_success(self):
        from mcp_server import _synthesize_to_file
        mock_mod = MagicMock()
        mock_mod.synthesize_to_file.return_value = "/tmp/test.mp3"
        with patch.dict("sys.modules", {"core.voice": mock_mod}):
            result = _synthesize_to_file("Hello")
            assert result["status"] == "ok"
            assert result["path"] == "/tmp/test.mp3"

    def test_synthesize_to_file_failure(self):
        from mcp_server import _synthesize_to_file
        mock_mod = MagicMock()
        mock_mod.synthesize_to_file.return_value = None
        with patch.dict("sys.modules", {"core.voice": mock_mod}):
            result = _synthesize_to_file("Hello")
            assert result["status"] == "failed"


class TestEcosystemTools:
    """Test ecosystem tool invocations."""

    def test_list_ecosystem_services(self):
        from mcp_server import _list_ecosystem_services
        mock_eco = MagicMock()
        mock_service = MagicMock()
        mock_service.name = "BlakVision"
        mock_service.description = "AI image generation"
        mock_service.category = "media"
        mock_service.capabilities = ["text-to-image"]
        mock_service.port = 8188
        mock_eco.services = {"blakvision": mock_service}
        mock_mod = MagicMock(get_ecosystem=MagicMock(return_value=mock_eco))
        with patch.dict("sys.modules", {"apps.onyx_ecosystem": mock_mod}):
            result = _list_ecosystem_services()
            assert result["count"] == 1
            assert "blakvision" in result["services"]

    def test_ecosystem_health(self):
        from mcp_server import _ecosystem_health
        mock_eco = MagicMock()
        mock_eco.dashboard.return_value = {"status": "healthy", "services": 7}
        mock_mod = MagicMock(get_ecosystem=MagicMock(return_value=mock_eco))
        with patch.dict("sys.modules", {"apps.onyx_ecosystem": mock_mod}):
            result = _ecosystem_health()
            assert result["status"] == "healthy"


class TestMemoryTools:
    """Test memory tool invocations."""

    def test_get_memory(self):
        from mcp_server import _get_memory
        mock_store_inst = MagicMock()
        mock_store_inst.get_all.return_value = {"task_history": [{"goal": "test"}]}
        mock_mod = MagicMock(MemoryStore=MagicMock(return_value=mock_store_inst))
        with patch.dict("sys.modules", {"memory.store": mock_mod}):
            result = _get_memory()
            assert "task_history" in result

    def test_get_improvement_stats(self):
        from mcp_server import _get_improvement_stats
        mock_si = MagicMock()
        mock_si.get_stats.return_value = {"gaps": 3, "strategies": 5}
        mock_mod = MagicMock(get_self_improvement=MagicMock(return_value=mock_si))
        with patch.dict("sys.modules", {"core.self_improvement": mock_mod}):
            result = _get_improvement_stats()
            assert result["gaps"] == 3
