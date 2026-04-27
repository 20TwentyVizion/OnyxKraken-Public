"""Hands — autonomous capability packages that run on schedules.

Inspired by OpenFang's Hands concept, adapted for Onyx's local desktop focus.
Each Hand is a named, scheduled autonomous agent with:
  - A manifest (config, schedule, tools, metrics)
  - An execute() method that does the actual work
  - Status reporting for the dashboard
  - Integration with telemetry for tracking

Unlike regular commands that wait for user input, Hands run 24/7
on their own schedules, building knowledge, creating content,
and maintaining the system.
"""

from core.hands.base import Hand, HandManifest, HandResult, HandStatus
from core.hands.scheduler import HandScheduler

__all__ = ["Hand", "HandManifest", "HandResult", "HandStatus", "HandScheduler"]
