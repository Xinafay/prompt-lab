from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from prompt_lab.pydantic_loader import load_model_entrypoint


def test_load_model_entrypoint_loads_class() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text(
            "from pydantic import BaseModel\n\nclass Demo(BaseModel):\n    name: str\n",
            encoding="utf-8",
        )

        model = load_model_entrypoint(root, "model.py", "model.Demo")

        assert issubclass(model, BaseModel)
        assert getattr(model.model_validate({"name": "Ada"}), "name") == "Ada"


def test_load_model_entrypoint_rejects_invalid_entrypoint_shapes() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text(
            "raise RuntimeError('module should not load for invalid entrypoints')\n",
            encoding="utf-8",
        )

        for entrypoint in ["model.Demo.Extra", "model", ".Demo", "model."]:
            try:
                load_model_entrypoint(root, "model.py", entrypoint)
            except ValueError as error:
                assert str(error) == "model_entrypoint must look like '<model_file_stem>.<ClassName>'."
            else:
                raise AssertionError(f"Expected ValueError for {entrypoint}")


def test_load_model_entrypoint_rejects_absolute_model_file_before_import() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text(
            "raise RuntimeError('module should not load for absolute model_file')\n",
            encoding="utf-8",
        )

        try:
            load_model_entrypoint(root, str(model_path), "model.Demo")
        except ValueError as error:
            assert str(error) == "model_file must be a version-local relative path."
        else:
            raise AssertionError("Expected ValueError for absolute model_file")


def test_load_model_entrypoint_rejects_model_file_path_escape_before_import() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        version_dir = root / "version"
        version_dir.mkdir()
        outside_path = root / "outside.py"
        outside_path.write_text(
            "raise RuntimeError('module should not load for escaped model_file')\n",
            encoding="utf-8",
        )

        try:
            load_model_entrypoint(version_dir, "../outside.py", "outside.Demo")
        except ValueError as error:
            assert str(error) == "model_file must be a version-local relative path."
        else:
            raise AssertionError("Expected ValueError for escaped model_file")


def test_load_model_entrypoint_missing_class_names_requested_entrypoint() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text(
            "from pydantic import BaseModel\n\nclass Demo(BaseModel):\n    name: str\n",
            encoding="utf-8",
        )

        try:
            load_model_entrypoint(root, "model.py", "model.Missing")
        except AttributeError as error:
            assert str(error) == "Model entrypoint not found: model.Missing"
        else:
            raise AssertionError("Expected AttributeError for missing class")


def test_load_model_entrypoint_rejects_non_base_model_entrypoint() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text("class Demo:\n    pass\n", encoding="utf-8")

        try:
            load_model_entrypoint(root, "model.py", "model.Demo")
        except TypeError as error:
            assert str(error) == "Entrypoint is not a Pydantic BaseModel subclass: model.Demo"
        else:
            raise AssertionError("Expected TypeError for non-BaseModel entrypoint")


def test_load_model_entrypoint_failed_import_removes_dynamic_module() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        model_path = root / "model.py"
        model_path.write_text("raise RuntimeError('import failed')\n", encoding="utf-8")
        before = {key for key in sys.modules if key.startswith("prompt_lab_dynamic_model_")}

        try:
            load_model_entrypoint(root, "model.py", "model.Demo")
        except RuntimeError as error:
            assert str(error) == "import failed"
        else:
            raise AssertionError("Expected RuntimeError for failed import")

        after = {key for key in sys.modules if key.startswith("prompt_lab_dynamic_model_")}
        assert after == before


def main() -> int:
    tests = [
        test_load_model_entrypoint_loads_class,
        test_load_model_entrypoint_rejects_invalid_entrypoint_shapes,
        test_load_model_entrypoint_rejects_absolute_model_file_before_import,
        test_load_model_entrypoint_rejects_model_file_path_escape_before_import,
        test_load_model_entrypoint_missing_class_names_requested_entrypoint,
        test_load_model_entrypoint_rejects_non_base_model_entrypoint,
        test_load_model_entrypoint_failed_import_removes_dynamic_module,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
