"""WidgetPlugin abstract base + registry."""
from __future__ import annotations

import abc
import importlib
import logging
import pkgutil
from typing import ClassVar, Type

logger = logging.getLogger(__name__)

REGISTRY: dict[str, Type["WidgetPlugin"]] = {}


def register(cls: Type["WidgetPlugin"]) -> Type["WidgetPlugin"]:
    """Class decorator: add plugin class to global registry."""
    if not getattr(cls, "id", None):
        raise ValueError(f"Plugin {cls.__name__} missing required `id`")
    if cls.id in REGISTRY:
        raise ValueError(f"Duplicate plugin id: {cls.id}")
    REGISTRY[cls.id] = cls
    logger.info("Registered widget plugin: %s", cls.id)
    return cls


class WidgetPlugin(abc.ABC):
    """Base class every widget plugin must subclass.

    Subclasses must:
      - define class-level ``id``, ``category``, ``template``
      - implement ``async def fetch(self) -> dict`` returning JSON-serialisable data
    """

    # ── Required class attributes ─────────────────────────────────────────
    id: ClassVar[str] = ""
    category: ClassVar[str] = "misc"
    template: ClassVar[str] = ""

    # ── Optional class attributes ─────────────────────────────────────────
    title_en: ClassVar[str] = ""
    title_or: ClassVar[str] = ""
    schedule: ClassVar[str] = "30 0 * * *"  # cron, 00:30 IST default
    enabled: ClassVar[bool] = True
    timeout_seconds: ClassVar[int] = 30
    dedup_strategy: ClassVar[str] = "none"          # see widgets_core.dedup
    dedup_window_days: ClassVar[int] = 0            # used if strategy=unique_within_days
    translate_fields: ClassVar[list[str]] = []      # field paths to translate to Odia
    max_retries: ClassVar[int] = 1
    # Attribution shown at the bottom of the rendered card
    source_name: ClassVar[str] = ""
    source_url: ClassVar[str] = ""

    @abc.abstractmethod
    async def fetch(self) -> dict:
        """Fetch fresh data. Returns dict serialisable to JSON.

        Should raise on hard failure; the framework handles retries/timeouts.
        """
        raise NotImplementedError

    # ── Helpers subclasses may override ───────────────────────────────────
    def dedup_key(self, payload: dict) -> str | None:
        """Return a content key used for dedup. Override for custom logic.

        Default: hash of full payload (good for `unique_*` strategies).
        Return None to skip dedup for this fetch.
        """
        from .dedup import content_hash
        return content_hash(payload)


def discover_plugins(package: str = "plugins") -> dict[str, Type[WidgetPlugin]]:
    """Import every module in `plugins/` so their `@register` decorators run."""
    pkg = importlib.import_module(package)
    for _, modname, _ in pkgutil.iter_modules(pkg.__path__):
        importlib.import_module(f"{package}.{modname}")
    return dict(REGISTRY)
