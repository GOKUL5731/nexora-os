"""JARVIS CORE OS package."""

__all__ = ["JarvisCoreOS"]


def __getattr__(name):
    if name == "JarvisCoreOS":
        from core.jarvis_core_os import JarvisCoreOS
        return JarvisCoreOS
    raise AttributeError(name)
