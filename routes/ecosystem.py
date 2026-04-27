"""Ecosystem routes — health dashboard, service dispatch, and workflow execution."""

import threading
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class DispatchRequest(BaseModel):
    service: str = Field(..., description="Target service name (e.g. 'blakvision', 'evera')")
    action: str = Field(..., description="Full action name (e.g. 'blakvision_generate')")
    params: dict = Field(default_factory=dict, description="Action parameters")


class WorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow template ID")
    params: dict = Field(default_factory=dict, description="Workflow parameters")
    context: dict = Field(default_factory=dict, description="Initial context variables")


class WorkflowStep(BaseModel):
    service: str
    action: str
    params: dict = Field(default_factory=dict)
    description: str = ""
    optional: bool = False


class CustomWorkflowRequest(BaseModel):
    steps: list[WorkflowStep]
    context: dict = Field(default_factory=dict)


class ScheduleRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow template to schedule")
    params: dict = Field(default_factory=dict, description="Workflow parameters")
    context: dict = Field(default_factory=dict, description="Context variables")
    cron: str = Field(default="", description="Cron expression (minute hour * * *)")
    interval_seconds: int = Field(default=0, description="Run every N seconds (alternative to cron)")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def ecosystem_health(force: bool = False):
    """Full ecosystem health dashboard — all services status at a glance."""
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    return eco.dashboard(force=force)


@router.get("/services")
async def list_services():
    """List all registered ecosystem services and their capabilities."""
    from apps.onyx_ecosystem import SERVICES
    return {
        name: {
            "name": svc.name,
            "description": svc.description,
            "category": svc.category,
            "port": svc.port,
            "capabilities": svc.capabilities,
            "depends_on": svc.depends_on,
        }
        for name, svc in SERVICES.items()
    }


@router.get("/services/{service_name}/health")
async def service_health(service_name: str, force: bool = False):
    """Check health of a specific service."""
    from apps.onyx_ecosystem import get_ecosystem, SERVICES
    if service_name not in SERVICES:
        raise HTTPException(404, f"Unknown service: {service_name}")
    eco = get_ecosystem()
    return eco.check_health(service_name, force=force)


@router.post("/dispatch")
async def dispatch_action(req: DispatchRequest):
    """Execute a single action on an ecosystem service.

    Standard envelope:
        {"service": "blakvision", "action": "blakvision_generate", "params": {"prompt": "..."}}
    """
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    result = eco.dispatch(req.service, req.action, req.params)
    return result


@router.get("/workflows")
async def list_workflows_endpoint():
    """List all available workflow templates with their parameters."""
    from apps.workflows import list_workflows
    return {"workflows": list_workflows()}


@router.post("/workflows/{workflow_id}")
async def run_workflow(workflow_id: str, req: WorkflowRequest):
    """Execute a pre-built workflow template.

    Builds the workflow steps from the template and runs them sequentially.
    Each step's output is available to subsequent steps via ${step_N.key} refs.
    """
    from apps.workflows import build_workflow, WORKFLOWS
    from apps.onyx_ecosystem import get_ecosystem

    if workflow_id not in WORKFLOWS:
        raise HTTPException(404, f"Unknown workflow: {workflow_id}. Available: {list(WORKFLOWS.keys())}")

    steps = build_workflow(workflow_id, req.params)
    if steps is None:
        raise HTTPException(500, f"Failed to build workflow: {workflow_id}")

    eco = get_ecosystem()
    result = eco.run_workflow(steps, req.context)
    return result


@router.post("/workflows/custom")
async def run_custom_workflow(req: CustomWorkflowRequest):
    """Execute a custom workflow with user-defined steps.

    Each step: {"service": "...", "action": "...", "params": {...}, "optional": false}
    """
    from apps.onyx_ecosystem import get_ecosystem

    steps = [s.model_dump() for s in req.steps]
    eco = get_ecosystem()
    result = eco.run_workflow(steps, req.context)
    return result


@router.get("/capabilities")
async def list_capabilities():
    """List all ecosystem capabilities grouped by category."""
    from apps.onyx_ecosystem import get_ecosystem
    eco = get_ecosystem()
    return eco.list_capabilities()


# ---------------------------------------------------------------------------
# Workflow scheduling
# ---------------------------------------------------------------------------

@router.get("/schedules")
async def list_schedules():
    """List all workflow schedules and their status."""
    from apps.workflow_scheduler import get_scheduler
    sched = get_scheduler()
    return {"schedules": sched.list_schedules(), "stats": sched.get_stats()}


@router.post("/schedules/{schedule_id}")
async def add_schedule(schedule_id: str, req: ScheduleRequest):
    """Add or update a workflow schedule.

    Use cron for time-of-day scheduling: "0 9 * * *" = 9:00 AM daily.
    Use interval_seconds for periodic: 3600 = every hour.
    """
    from apps.workflow_scheduler import get_scheduler
    from apps.workflows import WORKFLOWS

    if req.workflow_id not in WORKFLOWS:
        raise HTTPException(404, f"Unknown workflow: {req.workflow_id}")
    if not req.cron and req.interval_seconds <= 0:
        raise HTTPException(400, "Must specify either 'cron' or 'interval_seconds'")

    sched = get_scheduler()
    entry = sched.add(
        schedule_id, req.workflow_id,
        params=req.params, context=req.context,
        cron=req.cron, interval_seconds=req.interval_seconds,
    )
    return {"created": True, "schedule": entry.to_dict()}


@router.delete("/schedules/{schedule_id}")
async def remove_schedule(schedule_id: str):
    """Remove a workflow schedule."""
    from apps.workflow_scheduler import get_scheduler
    sched = get_scheduler()
    if sched.remove(schedule_id):
        return {"removed": True, "id": schedule_id}
    raise HTTPException(404, f"Schedule not found: {schedule_id}")


@router.post("/schedules/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: str, enabled: bool = True):
    """Enable or disable a workflow schedule."""
    from apps.workflow_scheduler import get_scheduler
    sched = get_scheduler()
    if sched.enable(schedule_id, enabled):
        return {"id": schedule_id, "enabled": enabled}
    raise HTTPException(404, f"Schedule not found: {schedule_id}")
