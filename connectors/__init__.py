"""Day 0 synthetic and explicitly disabled provider connector adapters."""

from .synthetic import SyntheticCompustatLikeConnector, SyntheticCrspLikeConnector
from .wrds import WrdsCompustatConnector, WrdsCrspConnector

__all__ = ["SyntheticCompustatLikeConnector", "SyntheticCrspLikeConnector", "WrdsCompustatConnector", "WrdsCrspConnector"]
