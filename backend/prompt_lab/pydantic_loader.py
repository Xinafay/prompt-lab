from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

from pydantic import BaseModel


def _load_module(path: Path) -> ModuleType:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    module_name = f"prompt_lab_dynamic_model_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("Cannot load model module.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _resolve_model_path(version_dir: Path, model_file: str) -> Path:
    model_path = Path(model_file)
    if model_path.is_absolute():
        raise ValueError("model_file must be a version-local relative path.")

    version_root = version_dir.resolve()
    candidate = (version_root / model_path).resolve()
    if not candidate.is_relative_to(version_root):
        raise ValueError("model_file must be a version-local relative path.")
    return candidate


def load_model_entrypoint(version_dir: Path, model_file: str, model_entrypoint: str) -> type[BaseModel]:
    """Load a Pydantic model class from a version-local Python file."""
    parts = model_entrypoint.split(".")
    if len(parts) != 2:
        raise ValueError("model_entrypoint must look like '<model_file_stem>.<ClassName>'.")
    module_name, class_name = parts
    if module_name != Path(model_file).stem or not class_name:
        raise ValueError("model_entrypoint must look like '<model_file_stem>.<ClassName>'.")
    module = _load_module(_resolve_model_path(version_dir, model_file))
    try:
        value = getattr(module, class_name)
    except AttributeError as error:
        raise AttributeError(f"Model entrypoint not found: {model_entrypoint}") from error
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        raise TypeError(f"Entrypoint is not a Pydantic BaseModel subclass: {model_entrypoint}")
    return cast(type[BaseModel], value)
