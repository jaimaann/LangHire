"""Plugin-based job source system for LangHire."""
from .registry import PluginRegistry, PluginConfig

__all__ = ["PluginRegistry", "PluginConfig"]
