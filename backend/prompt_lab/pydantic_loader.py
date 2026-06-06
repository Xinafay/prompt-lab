from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

from pydantic import BaseModel


def _load_module(path: Path) -> ModuleType:
    module_name = f"prompt_lab_dynamic_model_{abs(hash(path))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load model module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_model_entrypoint(version_dir: Path, model_file: str, model_entrypoint: str) -> type[BaseModel]:
    """Load a Pydantic model class from a version-local Python file."""
    module_name, _, class_name = model_entrypoint.partition(".")
    if module_name != Path(model_file).stem or not class_name:
        raise ValueError("model_entrypoint must look like '<model_file_stem>.<ClassName>'.")
    module = _load_module(version_dir / model_file)
    value = getattr(module, class_name)
    if not isinstance(value, type) or not issubclass(value, BaseModel):
        raise TypeError(f"Entrypoint is not a Pydantic BaseModel subclass: {model_entrypoint}")
    return cast(type[BaseModel], value)
