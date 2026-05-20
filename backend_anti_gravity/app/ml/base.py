"""
ml/base.py — Abstract base class for all ML model wrappers.
All concrete ML modules must implement the predict() interface.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseMLModel(ABC):
    """
    Standard interface for every ML inference wrapper in the platform.
    Concrete implementations must override predict() and optionally train().
    All models must handle graceful fallback when training data is insufficient.
    """

    model_name: str = "BaseModel"
    model_version: str = "1.0.0"
    is_trained: bool = False

    @abstractmethod
    def predict(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Run inference and return a structured result dictionary.
        Must never raise on insufficient data — return a fallback/rule-based result instead.
        """
        ...

    def train(self, data: Any) -> None:
        """
        Optional training entry point.
        Default no-op — override in models that support in-process training.
        """
        pass

    def _fallback_response(self, reason: str = "Insufficient data") -> Dict[str, Any]:
        """Standard fallback payload returned when model cannot execute."""
        return {
            "fallback": True,
            "reason": reason,
            "model": self.model_name,
            "version": self.model_version,
        }
