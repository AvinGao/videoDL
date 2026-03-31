"""HTTP headers management module."""

from .manager import HeaderManager
from .presets import UserAgentPresets
from .cookie_import import CookieImporter

__all__ = ["HeaderManager", "UserAgentPresets", "CookieImporter"]