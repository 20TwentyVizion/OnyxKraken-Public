"""Error Recovery — diagnose failures and suggest recovery strategies.

Uses the reasoning model (gpt-oss:120b-cloud) to analyze what went wrong
and produce an actionable recovery plan. Integrates with memory to avoid
repeating known-bad approaches.
"""

import json
from typing import Optional

from log import get_logger

_log = get_logger("error_recovery")
from agent.model_router import router
from agent.utils import summarize_history
from memory.store import MemoryStore


class ErrorDiagnoser:
    """Diagnoses action failures and suggests recovery strategies."""

    def __init__(self, memory: Optional[MemoryStore] = None, app_name: str = "unknown"):
        self.memory = memory
        self.app_name = app_name

    def diagnose(
        self,
        goal: str,
        current_step: str,
        failed_action: dict,
        error_message: str,
        recent_history: list[dict],
        observation: str = "",
    ) -> dict:
        """Analyze a failure and return a diagnosis + recovery suggestion.

        Returns:
            {
                "diagnosis": "What went wrong and why",
                "recovery": "What to try instead",
                "should_retry": True/False,
                "alternative_action": {...} or None,
                "skip_step": True/False,
            }
        """
        # Build context for the reasoning model
        history_summary = summarize_history(recent_history, max_entries=6)

        # Check memory for known failures
        memory_context = ""
        if self.memory:
            failures = self.memory.recall_failures(limit=5)
            if failures:
                memory_context = "KNOWN PAST FAILURES:\n"
                for f in failures:
                    memory_context += f"  - {f['action']} on {f['target']}: {f['error']}\n"

        prompt = (
            "You are an expert error diagnostician for a Windows desktop automation agent.\n"
            "An action just failed. Analyze the failure and suggest a recovery strategy.\n\n"
            f"GOAL: {goal}\n"
            f"CURRENT STEP: {current_step}\n"
            f"FAILED ACTION: {json.dumps(failed_action, default=str)}\n"
            f"ERROR: {error_message}\n\n"
            f"RECENT HISTORY:\n{history_summary}\n"
        )

        if observation:
            prompt += f"CURRENT SCREEN STATE:\n{observation[:500]}\n\n"

        if memory_context:
            prompt += f"{memory_context}\n"

        prompt += (
            "Respond with ONLY a JSON object:\n"
            '{"diagnosis": "what went wrong", "recovery": "what to try instead", '
            '"should_retry": true, "alternative_action": null, "skip_step": false}\n\n'
            "Rules:\n"
            "- If the element wasn't found, suggest using coordinates or a different target name\n"
            "- If the app isn't responding, suggest waiting or re-launching\n"
            "- If the action is fundamentally wrong, set skip_step=true\n"
            "- If you can suggest a specific alternative action, provide it as alternative_action\n"
            "  with the same schema: {action, target, target_type, params, fallback_coords}\n"
            "- Be concise. Output ONLY the JSON."
        )

        try:
            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])

            # Parse the diagnosis
            result = None
            try:
                # Try to find JSON in the response
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    result = json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass  # expected — LLM may return non-JSON; fallback below

            if result is None:
                result = {
                    "diagnosis": "Could not parse diagnosis",
                    "recovery": "Retry the action",
                    "should_retry": True,
                    "alternative_action": None,
                    "skip_step": False,
                }

            # Record failure to memory
            if self.memory:
                self.memory.remember_failure(
                    app_name=self.app_name,
                    action=failed_action.get("action", "unknown"),
                    target=failed_action.get("target", ""),
                    error=error_message[:200],
                )

            # Store recovery strategy in knowledge (closes error→learning loop)
            if result.get("recovery") and result.get("should_retry"):
                try:
                    from core.knowledge import get_knowledge_store
                    ks = get_knowledge_store()
                    strategy = (
                        f"Recovery for {failed_action.get('action', '?')} failure in "
                        f"{self.app_name}: {result['recovery'][:200]}"
                    )
                    ks.add(
                        content=strategy,
                        category="task_patterns",
                        tags=[self.app_name.lower(), "error_recovery"],
                        source=f"error_recovery:{goal[:40]}",
                    )
                except Exception as e:
                    _log.debug(f"Could not store recovery strategy in knowledge: {e}")

            return result

        except Exception as e:
            print(f"[ErrorDiag] Diagnosis failed: {e}")
            return {
                "diagnosis": f"Diagnosis unavailable: {e}",
                "recovery": "Retry with default approach",
                "should_retry": True,
                "alternative_action": None,
                "skip_step": False,
            }

    def diagnose_stuck(
        self,
        goal: str,
        current_step: str,
        repeated_action: dict,
        repeat_count: int,
        observation: str = "",
    ) -> dict:
        """Diagnose when the agent is stuck repeating the same action.

        Returns same schema as diagnose().
        """
        prompt = (
            "A Windows desktop automation agent is STUCK — it keeps repeating the same action.\n\n"
            f"GOAL: {goal}\n"
            f"CURRENT STEP: {current_step}\n"
            f"REPEATED ACTION (done {repeat_count}x): {json.dumps(repeated_action, default=str)}\n\n"
        )

        if observation:
            prompt += f"SCREEN STATE:\n{observation[:500]}\n\n"

        prompt += (
            "Why is it stuck? What should it do instead?\n"
            "Respond with ONLY a JSON object:\n"
            '{"diagnosis": "why its stuck", "recovery": "what to do instead", '
            '"should_retry": false, "alternative_action": null, "skip_step": true}\n'
            "Output ONLY the JSON."
        )

        try:
            raw = router.get_content("reasoning", [{"role": "user", "content": prompt}])
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception as e:
            print(f"[ErrorDiag] Stuck diagnosis failed: {e}")

        return {
            "diagnosis": "Agent is repeating the same action",
            "recovery": "Skip to next step",
            "should_retry": False,
            "alternative_action": None,
            "skip_step": True,
        }
