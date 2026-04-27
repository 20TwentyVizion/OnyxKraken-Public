"""Pluggable intent / emotion classifier."""
from core.intent.classifier import (
    IntentResult,
    IntentClassifier,
    RegexClassifier,
    OllamaClassifier,
    get_classifier,
    set_classifier,
    classify,
)

__all__ = [
    "IntentResult",
    "IntentClassifier",
    "RegexClassifier",
    "OllamaClassifier",
    "get_classifier",
    "set_classifier",
    "classify",
]
