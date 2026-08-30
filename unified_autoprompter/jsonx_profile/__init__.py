"""Private JsonX implementation used only by Unified Autoprompter's JsonX profile.

This package deliberately does not import the standalone JsonX node or the
standard Unified provider modules. It owns its catalog, providers and binary
cache so changes cannot cross those boundaries.
"""

def register_routes(*args, **kwargs):
    from .routes import register_routes as _register_routes

    return _register_routes(*args, **kwargs)

__all__ = ["register_routes"]
