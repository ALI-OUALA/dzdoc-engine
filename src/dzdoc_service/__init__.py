"""Provider-neutral DzDoc service layer."""

from .api import create_app
from .config import ServiceSettings

__all__ = ["ServiceSettings", "create_app"]
