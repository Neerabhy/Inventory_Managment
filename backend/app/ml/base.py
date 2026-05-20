from abc import ABC, abstractmethod
from typing import Any

class BaseMLModel(ABC):
    """Abstract interface defining standard methods for all analytical engine pipelines."""
    
    @abstractmethod
    def load_model(self) -> None:
        """Loads serialized model files or initializes fallback states on startup."""
        pass

    @abstractmethod
    def predict(self, data: Any) -> Any:
        """Executes model inference on incoming feature inputs."""
        pass