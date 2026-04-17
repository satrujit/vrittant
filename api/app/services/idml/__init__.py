"""IDML generator package — produces InDesign-compatible IDML packages.

Public entry point: ``generate_idml(story)``.
"""

from .package import generate_idml

__all__ = ["generate_idml"]
