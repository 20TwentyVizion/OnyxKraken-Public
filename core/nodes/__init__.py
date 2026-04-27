"""Onyx Node Engine — cross-app workflow orchestration.

Adapted from EVERA's node-based system (itself modeled after ComfyUI).
Each node: define_schema() → execute(**kwargs) → returns tuple of outputs.
Workflows are DAGs stored as JSON, executed via topological sort.
"""
