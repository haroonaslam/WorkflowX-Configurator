"""Private JsonX implementation used only by Unified Autoprompter's JsonX profile.

This package deliberately does not import the standalone JsonX node or the
standard Unified provider modules. It owns its catalog, providers and binary
cache so changes cannot cross those boundaries.
"""

from .routes import register_routes

__all__ = ["register_routes"]
