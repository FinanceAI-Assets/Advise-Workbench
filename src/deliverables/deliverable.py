from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class DeliverableMetadata:
    output_type: str
    file_extension: str
    mime_type: str
    supports_branding: bool = True
    supports_quality_rubric: bool = True
    requires_rendering: bool = True
    intermediate_format: str = "text"
    skill_output_key: str = ""


class IDeliverable(ABC):
    @abstractmethod
    def get_metadata(self) -> DeliverableMetadata:
        raise NotImplementedError

    @abstractmethod
    def render(self, payload: dict[str, Any], run_dir: Path, branding: Any | None = None) -> Path | None:
        raise NotImplementedError

    def extract_quality_signals(self, artifact_path: Path) -> dict[str, Any]:
        return {"artifact_path": str(artifact_path)}

    def apply_branding(self, payload: dict[str, Any], branding: Any | None = None) -> dict[str, Any]:
        return payload


class DeliverableRegistry:
    _lock = RLock()
    _deliverables: dict[str, IDeliverable] = {}

    @classmethod
    def register(cls, output_type: str, deliverable: IDeliverable) -> None:
        key = str(output_type or "").strip().lower()
        if not key:
            raise ValueError("output_type must be non-empty")
        with cls._lock:
            cls._deliverables[key] = deliverable

    @classmethod
    def get(cls, output_type: str) -> IDeliverable:
        key = str(output_type or "").strip().lower()
        with cls._lock:
            d = cls._deliverables.get(key)
        if d is None:
            _init_default_deliverables()
            with cls._lock:
                d = cls._deliverables.get(key)
        if d is None:
            raise ValueError(f"Unknown output type: {output_type}")
        return d

    @classmethod
    def all(cls) -> dict[str, IDeliverable]:
        with cls._lock:
            return dict(cls._deliverables)


# ── Auto-register implementations ─────────────────────────────────────────

_DEFAULT_DELIVERABLES: tuple[tuple[str, str, str], ...] = (
    ("pptx", "src.deliverables.pptx.deliverable_pptx", "PPTXDeliverable"),
    ("docx", "src.deliverables.docx.deliverable_docx", "DOCXDeliverable"),
    ("pdf", "src.deliverables.pdf.deliverable_pdf", "PDFDeliverable"),
    ("xlsx", "src.deliverables.xlsx.deliverable_xlsx", "XLSXDeliverable"),
)


def _init_default_deliverables() -> None:
    """Register every default deliverable that is not registered yet.

    Implementations are imported lazily to avoid circular imports. A type whose
    import fails now (for example because ``src.core.storage`` is still being
    imported) is retried on the next call, and ``DeliverableRegistry.get`` calls
    this when a type is missing, so one partial import cannot leave a type
    permanently unregistered.
    """
    import importlib

    for key, module_name, class_name in _DEFAULT_DELIVERABLES:
        if key in DeliverableRegistry._deliverables:
            continue
        try:
            module = importlib.import_module(module_name)
            DeliverableRegistry.register(key, getattr(module, class_name)())
        except ImportError:
            continue


# Initialize on module load; anything that could not load yet is retried by get().
_init_default_deliverables()
